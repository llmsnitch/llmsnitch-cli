"""llmsnitch CLI.

  llmsnitch setup [--write]   print/install Claude Code hook config
  llmsnitch list              recorded sessions, newest first
  llmsnitch show <id>         one session: aggregates + recent events
  llmsnitch check             cost/fail-rate/health gate (exit 0/1/2)
  llmsnitch hook <event>      internal — invoked by Claude Code hooks
"""

import sys
from datetime import datetime

from . import __version__, gate, hook, setup_cmd, store


def _fmt_ts(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "-"


def cmd_list(out):
    rows = store.list_sessions()
    if not rows:
        out.write("no sessions recorded yet — run `llmsnitch setup`\n")
        return 0
    out.write(f"{'ID':<14} {'STARTED':<17} {'TOOLS':>5} {'ERR':>4} "
              f"{'HEALTH':>6} {'COST':>8}  ENDED\n")
    for sid, _ in rows:
        s = store.summarize(sid)
        h = gate.health(s["tool_calls"], s["errors"])
        cost = f"${s['cost_usd']:.2f}" if s.get("cost_usd") is not None else "-"
        out.write(f"{sid[:14]:<14} {_fmt_ts(s['started_at']):<17} "
                  f"{s['tool_calls']:>5} {s['errors']:>4} {h:>6} {cost:>8}  "
                  f"{'yes' if s['ended'] else 'live'}\n")
    return 0


def cmd_show(sid, out):
    s = store.summarize(sid)
    if not s["tool_calls"] and not s["started_at"]:
        out.write(f"[ERROR] no such session: {sid}\n")
        return 2
    out.write(f"session   {s['session_id']}\n"
              f"started   {_fmt_ts(s['started_at'])}   "
              f"duration {s['duration_s']}s   ended: {s['ended']}\n"
              f"tools     {s['tool_calls']} calls, {s['errors']} errors, "
              f"health {gate.health(s['tool_calls'], s['errors'])}\n")
    if s.get("cost_usd") is not None:
        out.write(f"cost      ${s['cost_usd']:.4f} "
                  f"({s.get('total_tokens', 0)} tokens)\n")
    if s["tools"]:
        top = sorted(s["tools"].items(), key=lambda kv: -kv[1])
        out.write("by tool   " + ", ".join(f"{k}={v}" for k, v in top[:8]) + "\n")
    events = list(store.iter_events(sid))
    out.write(f"events    {len(events)} recorded; last 5:\n")
    for ev in events[-5:]:
        line = f"  {_fmt_ts(ev.get('ts'))} {ev.get('event', '?'):<12} {ev.get('tool', '')}"
        if ev.get("error"):
            line += "  [ERROR]"
        out.write(line + "\n")
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    cmd = argv[0] if argv else "help"
    out = sys.stdout

    if cmd == "hook" and len(argv) >= 2:
        return hook.handle(argv[1])
    if cmd == "setup":
        return setup_cmd.run("--write" in argv, out)
    if cmd == "list":
        return cmd_list(out)
    if cmd == "show" and len(argv) >= 2:
        return cmd_show(argv[1], out)
    if cmd == "check":
        return gate.cmd_check(gate.load_cfg(), out)
    if cmd in ("--version", "version"):
        out.write(f"llmsnitch {__version__}\n")
        return 0
    out.write(__doc__)
    return 0 if cmd in ("help", "-h", "--help") else 2


if __name__ == "__main__":
    sys.exit(main())
