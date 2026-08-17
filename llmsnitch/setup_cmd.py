"""Install (or print) the Claude Code hook configuration.

Default is PRINT-ONLY. `--write` merges into ~/.claude/settings.json after
snapshotting it — and refuses to run from inside a Claude Code session
(CLAUDECODE env set): the settings file that wires the hooks is exactly the
file a monitored agent must never modify about itself.
"""

import json
import os
import time
from pathlib import Path

_EVENTS = ("PreToolUse", "PostToolUse", "Stop")


def hooks_block(bin_path="llmsnitch"):
    return {
        ev: [{"matcher": "*",
              "hooks": [{"type": "command", "command": f"{bin_path} hook {ev}"}]}]
        if ev != "Stop" else
        [{"hooks": [{"type": "command", "command": f"{bin_path} hook {ev}"}]}]
        for ev in _EVENTS
    }


def run(write, out, settings_path=None, env=None):
    env = env if env is not None else os.environ
    block = hooks_block()

    if not write:
        out.write("Add to ~/.claude/settings.json under \"hooks\" "
                  "(or re-run with --write):\n")
        out.write(json.dumps({"hooks": block}, indent=2) + "\n")
        return 0

    if env.get("CLAUDECODE"):
        out.write("[ERROR] refusing --write from inside a Claude Code session — "
                  "run from a plain terminal (the monitored agent must not "
                  "edit its own hook wiring)\n")
        return 2

    sp = Path(settings_path or "~/.claude/settings.json").expanduser()
    settings = {}
    if sp.exists():
        snap_dir = Path("~/.config/llmsnitch").expanduser()
        snap_dir.mkdir(parents=True, exist_ok=True)
        snap = snap_dir / f"settings-snapshot-{time.strftime('%Y%m%d%H%M%S')}.json"
        snap.write_text(sp.read_text())
        out.write(f"[OK] snapshot: {snap}\n")
        try:
            settings = json.loads(sp.read_text())
        except json.JSONDecodeError:
            out.write("[ERROR] settings.json is not valid JSON — fix it first, "
                      "not overwriting\n")
            return 2

    hooks = settings.setdefault("hooks", {})
    for ev, entries in block.items():
        existing = hooks.setdefault(ev, [])
        already = any("llmsnitch hook" in h.get("command", "")
                      for e in existing for h in e.get("hooks", []))
        if not already:
            existing.extend(entries)
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(settings, indent=2) + "\n")
    out.write(f"[OK] hooks written to {sp} — diff the snapshot to audit\n")
    return 0
