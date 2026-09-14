"""The digest LaunchAgent — print (default) or --write + bootstrap
`com.slav-it.llmsnitch-digest`, daily 10:00, `fs-coil digest --prune`.
Mirror of llmsnitch/patrol.py; split out of digest.py for the 250-line cap.
"""

import os
import subprocess
from pathlib import Path

LABEL = "com.slav-it.llmsnitch-digest"

_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{bin}</string>
    <string>digest</string>
    <string>--prune</string>
  </array>
  <key>WorkingDirectory</key><string>{home}</string>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>10</integer><key>Minute</key><integer>0</integer></dict>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>{home}/Library/Logs/llmsnitch/digest.out</string>
  <key>StandardErrorPath</key><string>{home}/Library/Logs/llmsnitch/digest.err</string>
</dict>
</plist>
"""



def plist():
    home = os.path.expanduser("~")
    return _PLIST.format(label=LABEL, home=home,
                         bin=os.path.join(home, ".local", "bin", "fs-coil"))


def install_agent_run(write, out, plist_path=None):
    """Mirror of llmsnitch/patrol.run: print by default; --write writes the
    plist and bootstraps it. plist_path is the test seam (skips launchctl)."""
    text = plist()
    if not write:
        out.write(text)
        return 0
    default = plist_path is None
    p = Path(plist_path or f"~/Library/LaunchAgents/{LABEL}.plist").expanduser()
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
                       capture_output=True)
        r = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(p)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            out.write("[ERROR] launchctl bootstrap failed: "
                      f"{(r.stderr or r.stdout).strip()}\n")
            return 2
        out.write(f"[OK] bootstrapped {LABEL} — daily 10:00. Run now with:\n"
                  f"  launchctl kickstart gui/{uid}/{LABEL}\n")
    return 0
