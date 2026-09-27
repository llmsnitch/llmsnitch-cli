"""Install (or print) the patrol LaunchAgent — an unattended daily run of
the config-audit surface (CONTEXT.md: Patrol).

Default is PRINT-ONLY. `--write` writes the plist to ~/Library/LaunchAgents
and bootstraps it. No refuse-inside-Claude-Code guard: the plist does not
wire the monitored agent's own hook config (scan-rollout map, grilling Q7).
`launchctl` runs via subprocess only under `--write` — cold path, never the
hook hot path, and never the network.
"""

import os
import subprocess
import sys
from pathlib import Path

LABEL = "com.slav-it.llmsnitch-patrol"

# Logs live under the canonical llmsnitch namespace, beside the notify ledger.
_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{bin}</string>
    <string>scan</string>
    <string>--patrol</string>
  </array>
  <key>WorkingDirectory</key><string>{home}</string>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>30</integer></dict>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>{home}/Library/Logs/llmsnitch/patrol.out</string>
  <key>StandardErrorPath</key><string>{home}/Library/Logs/llmsnitch/patrol.err</string>
</dict>
</plist>
"""


def plist():
    home = os.path.expanduser("~")
    # ponytail: pipx shim path hardcoded (T201 resolution: stable across
    # reinstalls); use shutil.which if a second install layout ever appears.
    return _PLIST.format(label=LABEL, home=home,
                         bin=os.path.join(home, ".local", "bin", "llmsnitch"))


def run(write, out, plist_path=None, err=None):
    text = plist()
    if not write:
        (err or sys.stderr).write(f"Save as ~/Library/LaunchAgents/{LABEL}.plist "
                                  "(or re-run with --write):\n")
        out.write(text)
        return 0
    default = plist_path is None   # overriding the path is the test seam:
    p = Path(plist_path or         # custom target skips launchctl + log dir
             f"~/Library/LaunchAgents/{LABEL}.plist").expanduser()
    try:
        if default:
            p.parent.mkdir(parents=True, exist_ok=True)
            (Path(os.path.expanduser("~")) / "Library" / "Logs"
             / "llmsnitch").mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    except OSError as e:
        out.write(f"[ERROR] cannot write {p}: {e}\n")
        return 2
    out.write(f"[OK] wrote {p}\n")
    if default:
        uid = os.getuid()
        subprocess.run(["launchctl", "bootout", f"gui/{uid}/{LABEL}"],
                       capture_output=True)   # fine if it wasn't loaded
        r = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(p)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            out.write("[ERROR] launchctl bootstrap failed: "
                      f"{(r.stderr or r.stdout).strip()}\n")
            return 2
        out.write(f"[OK] bootstrapped {LABEL} — daily 09:30. Run now with:\n"
                  f"  launchctl kickstart gui/{uid}/{LABEL}\n")
    return 0
