"""Concrete CLI subcommand implementations except `report`/`dashboard` (which
have their own modules) and the `daemon` runtime entry (which goes straight to
fs_coil.monitor.run_monitor)."""

import os
import pwd
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from fs_coil.constants import BIN_PATH, PLIST_LABEL, PLIST_PATH
from fs_coil.logger import _colorize_log_line
from fs_coil.monitor import run_monitor
from fs_coil.runtime import console_user, user_home
from fs_coil.theme import (
    _C7, _DIM, _GREEN, _R, _TREE_MID, _YELLOW, _tty,
    err, head, item, ok, print_banner, warn,
)


def require_sudo():
    if os.geteuid() != 0:
        err("this command needs sudo")
        sys.exit(1)


def cmd_status():
    loaded = False
    try:
        out = subprocess.run(
            ["/bin/launchctl", "print", f"system/{PLIST_LABEL}"],
            capture_output=True, text=True,
        )
        loaded = out.returncode == 0
    except Exception:
        pass

    user = console_user() or "(none)"
    home = user_home(user) if user != "(none)" else "~"

    from fs_coil import notify as _notify
    reason = _notify.get_degraded()

    head("fs-coil status")
    def _kv(k, v, good=True):
        c = _GREEN if good else _YELLOW
        if _tty():
            print(f"{_C7}{_TREE_MID}{_R} {_DIM}{k:<9}{_R} {c}{v}{_R}")
        else:
            print(f"  {k:<9} {v}")
    _kv("plist",    str(PLIST_PATH),  PLIST_PATH.exists())
    _kv("binary",   str(BIN_PATH),    BIN_PATH.exists())
    _kv("daemon",   "loaded" if loaded else "not loaded", loaded)
    _kv("user",     user, user != "(none)")
    _kv("log dir",  f"{home}/Library/Logs/llmsnitch/fs-coil")
    _kv("degraded", reason or "none", good=reason is None)


def cmd_start():
    require_sudo()
    if not PLIST_PATH.exists():
        err(f"{PLIST_PATH} not found — run ./install.sh first")
        sys.exit(1)
    # Enable first (in case it was previously disabled), then bootstrap.
    # Check bootstrap's return code — EIO (error 5) means the service is still
    # registered from a prior load; fall through to a kickstart-k which does
    # an in-place replace without needing bootout/bootstrap.
    subprocess.run(["/bin/launchctl", "enable", f"system/{PLIST_LABEL}"],
                   capture_output=True)
    r = subprocess.run(
        ["/bin/launchctl", "bootstrap", "system", str(PLIST_PATH)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        # Common cause: stale registration. kickstart -k asks launchd to kill
        # and relaunch the service using the currently-loaded plist.
        subprocess.run(
            ["/bin/launchctl", "kickstart", "-k", f"system/{PLIST_LABEL}"],
            capture_output=True,
        )
    ok(f"{PLIST_LABEL} loaded")


def cmd_stop():
    require_sudo()
    # Bootout by label AND by plist path — the path form clears launchd's
    # inode-level cache so a subsequent bootstrap doesn't EIO.
    # Both can legitimately fail with "error 3: No such process" when the
    # service wasn't loaded — that's not an error condition, swallow it.
    subprocess.run(
        ["/bin/launchctl", "bootout", f"system/{PLIST_LABEL}"],
        capture_output=True,
    )
    subprocess.run(
        ["/bin/launchctl", "bootout", "system", str(PLIST_PATH)],
        capture_output=True,
    )
    ok(f"{PLIST_LABEL} unloaded")


def cmd_restart():
    cmd_stop()
    time.sleep(1)  # let launchd finish evicting before re-registering
    cmd_start()


def cmd_logs(follow=False):
    user = console_user() or pwd.getpwuid(os.getuid()).pw_name
    home = user_home(user)
    log_dir = Path(home) / "Library" / "Logs" / "llmsnitch" / "fs-coil"
    today = log_dir / f"fs-coil-{datetime.now():%Y-%m-%d}.log"
    if not today.exists():
        warn(f"no log yet at {today}")
        return
    args = ["tail", "-n", "200"]
    if follow:
        args += ["-F"]
    args += [str(today)]
    # Python-side piping so we can colorize each line on TTY.
    try:
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, text=True, bufsize=1)
        assert proc.stdout is not None
        for raw in iter(proc.stdout.readline, ""):
            sys.stdout.write(_colorize_log_line(raw))
            sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            proc.terminate()
        except Exception:
            pass


def _prune_dated(dir_path, name_re, days, label):
    """Delete regular non-symlink files in dir_path whose name matches name_re
    (group 1 = YYYY-MM-DD) and whose stamp is older than `days` days. No
    recursion, no symlink following. Returns the count removed."""
    import re as _re
    dir_p = Path(dir_path)
    if not dir_p.is_dir():
        warn(f"no {label} dir at {dir_p}")
        return 0
    cutoff = datetime.now().date() - timedelta(days=days)
    removed = 0
    for f in sorted(dir_p.iterdir()):
        m = _re.match(name_re, f.name)
        if not m or os.path.islink(str(f)) or not f.is_file():
            continue
        try:
            fdate = datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            continue
        if fdate < cutoff:
            try:
                f.unlink()
                removed += 1
            except OSError as e:
                warn(f"could not remove {f.name}: {e}")
    return removed


def cmd_prune(days=None, target=None):
    """Delete dated files older than `days`. target None|'logs' → fs-coil
    log dir (default 30 days); 'notify' → ledger + digests (default 45)."""
    if target in (None, "logs"):
        user = console_user() or pwd.getpwuid(os.getuid()).pw_name
        d = Path(user_home(user)) / "Library" / "Logs" / "llmsnitch" / "fs-coil"
        spec = (str(d), r"^fs-coil-(\d{4}-\d{2}-\d{2})\.log$", 30, "logs")
    elif target == "notify":
        from fs_coil import ledger
        spec = (ledger.ledger_dir(),
                r"^(?:events|digest)-(\d{4}-\d{2}-\d{2})\.(?:ndjson|txt|html)$", 45, "notify")
    else:
        err(f"unknown prune target: {target!r} (use 'logs' or 'notify')")
        sys.exit(1)
    days = spec[2] if days is None else days
    if days < 1:
        err("prune: --days must be >= 1")
        sys.exit(1)
    n = _prune_dated(spec[0], spec[1], days, spec[3])
    ok(f"pruned {n} {spec[3]} file(s) older than {days} day(s)")


def cmd_test():
    if os.geteuid() != 0:
        warn("test mode needs sudo — eslogger requires root")
        sys.exit(1)
    print_banner()
    head("test mode")
    item("matches print to stdout, no notifications")
    item(f"{_DIM}Ctrl-C to stop{_R}" if _tty() else "Ctrl-C to stop")
    print()
    run_monitor(stdout_only=True)
