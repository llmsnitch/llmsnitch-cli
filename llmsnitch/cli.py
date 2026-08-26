"""llmsnitch CLI.

  llmsnitch setup [--write]   print/install Claude Code hook config
  llmsnitch list              recorded sessions, newest first
  llmsnitch show <id>         one session: aggregates + recent events
  llmsnitch check             cost/fail-rate/health gate (exit 0/1/2)
  llmsnitch scan [ROOT ...]   config audit over agent artifacts (exit 0/1/2)
  llmsnitch patrol [--write]  print/install the daily scan LaunchAgent
  llmsnitch ingest            sweep harness ledgers (also runs lazily
                              before list/show/check)
  llmsnitch migrate-paths     move legacy ~/.config/llm-snitch, ~/Library/
                              Logs|Caches/llm-snitch to the dashless paths
                              (idempotent; leaves compat symlinks)
  llmsnitch hook <event>      internal — invoked by Claude Code hooks
"""

import sys
from datetime import datetime

from . import __version__, gate, hook, scan, setup_cmd, store


def _cost_label(cost, subscription):
    """Label a cost figure honestly. Subscription mode: bracket it as an
    estimate the user isn't actually billed for."""
    if cost is None:
        return "-"
    return f"~${cost:.2f}" if subscription else f"${cost:.2f}"


def _fmt_ts(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "-"


def cmd_list(out):
    rows = store.list_sessions()
    if not rows:
        out.write("no sessions recorded yet — run `llmsnitch setup`\n")
        return 0
    cfg = gate.load_cfg()
    subscription = cfg["billing_mode"] == "subscription"
    header_cost = "EST.COST" if subscription else "COST"
    out.write(f"{'ID':<14} {'HARNESS':<12} {'STARTED':<17} {'TOOLS':>5} {'ERR':>4} "
              f"{'HEALTH':>6} {header_cost:>9}  ENDED\n")
    for sid, _ in rows:
        s = store.summarize(sid)
        h = gate.health(s["tool_calls"], s["errors"])
        cost = _cost_label(s.get("cost_usd"), subscription)
        out.write(f"{sid[:14]:<14} {s['harness'][:12]:<12} {_fmt_ts(s['started_at']):<17} "
                  f"{s['tool_calls']:>5} {s['errors']:>4} {h:>6} {cost:>9}  "
                  f"{'yes' if s['ended'] else 'live'}\n")
    if subscription:
        out.write("note: est.cost = per-token equivalent; "
                  "subscription plans are not billed this. "
                  "Set [gate] billing_mode = per_token to enforce.\n")
    return 0


def cmd_show(sid, out):
    s = store.summarize(sid)
    if not s["tool_calls"] and not s["started_at"]:
        out.write(f"[ERROR] no such session: {sid}\n")
        return 2
    out.write(f"session   {s['session_id']}\n"
              f"harness   {s['harness']}\n"
              f"started   {_fmt_ts(s['started_at'])}   "
              f"duration {s['duration_s']}s   ended: {s['ended']}\n"
              f"tools     {s['tool_calls']} calls, {s['errors']} errors, "
              f"health {gate.health(s['tool_calls'], s['errors'])}\n")
    if s.get("signals_partial"):   # honest degradation (contract C4)
        out.write(f"health    partial — {s['signals_partial']}\n")
    if s.get("cost_usd") is not None:
        cfg = gate.load_cfg()
        subscription = cfg["billing_mode"] == "subscription"
        prefix = "est.cost" if subscription else "cost    "
        tilde = "~" if subscription else ""
        out.write(f"{prefix}  {tilde}${s['cost_usd']:.4f} "
                  f"({s.get('total_tokens', 0)} tokens)"
                  + (" — subscription plans not billed this\n"
                     if subscription else "\n"))
        if s.get("cost_note"):
            out.write(f"          {s['cost_note']}\n")
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
    if cmd == "ingest":
        from . import ingest
        out.write(f"ingested/updated {ingest.sweep()} session(s)\n")
        return 0
    if cmd == "migrate-paths":
        from . import migrate_paths
        return migrate_paths.run(out)
    if cmd in ("list", "show", "check"):
        try:                       # lazy sweep (contract C8) — never blocks reads
            from . import ingest
            ingest.sweep()
        except Exception:  # noqa: BLE001
            pass
    if cmd == "list":
        return cmd_list(out)
    if cmd == "show" and len(argv) >= 2:
        return cmd_show(argv[1], out)
    if cmd == "check":
        return gate.cmd_check(gate.load_cfg(), out)
    if cmd == "scan":
        return scan.cmd_scan(argv[1:], out)
    if cmd == "patrol":
        from . import patrol
        return patrol.run("--write" in argv, out)
    if cmd in ("--version", "version"):
        out.write(f"llmsnitch {__version__}\n")
        return 0
    out.write(__doc__)
    return 0 if cmd in ("help", "-h", "--help") else 2


if __name__ == "__main__":
    sys.exit(main())
