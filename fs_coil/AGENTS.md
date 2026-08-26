# src/fs_coil/

Python daemon package. Runs **as root** via LaunchDaemon. Files ≤250 lines (project rule) — `render_*.py` are split for this reason.

Hard constraints (from the security audit — do not regress):
- `monitor.py` is the eslogger read loop. Never add latency or an uncaught exception path — one bad event crashes it → 10s launchd-respawn evasion window. Per-event body is wrapped in try/except; keep it.
- Logs: 0600 files / 0700 dirs; `os.chown(..., follow_symlinks=False)` (TOCTOU).
- `keychain.py` redacts `account=`/`service=`/key-paths (SHA-256) — never log raw.
- Notifier dedupe key must NOT contain a timestamp (breaks the 60s cooldown).
- Subprocess: list-form argv only, never `shell=True`.
- `_low_noise` trusts the OS signing-id prefix, not a `/claude.app/` path substring (spoofable).
