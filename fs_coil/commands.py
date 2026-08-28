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

    head("fs-coil status")
    def _kv(k, v, good=True):
        c = _GREEN if good else _YELLOW
        if _tty():
            print(f"{_C7}{_TREE_MID}{_R} {_DIM}{k:<9}{_R} {c}{v}{_R}")
        else:
            print(f"  {k:<9} {v}")
    _kv("plist",   str(PLIST_PATH),  PLIST_PATH.exists())
    _kv("binary",  str(BIN_PATH),    BIN_PATH.exists())
    _kv("daemon",  "loaded" if loaded else "not loaded", loaded)
    _kv("user",    user, user != "(none)")
    _kv("log dir", f"{home}/Library/Logs/llmsnitch/fs-coil")


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


def cmd_prune(days=30):
    """Delete daily log files older than `days`. The audit log accumulates
    forever otherwise — it's the full list of every secret path touched, so
    unbounded retention is a standing liability (GDPR storage-limitation +
    breach blast-radius). Parses the YYYY-MM-DD stamp in each filename."""
    if days < 1:
        err("prune: --days must be >= 1")
        sys.exit(1)
    user = console_user() or pwd.getpwuid(os.getuid()).pw_name
    home = user_home(user)
    log_dir = Path(home) / "Library" / "Logs" / "llmsnitch" / "fs-coil"
    if not log_dir.is_dir():
        warn(f"no log dir at {log_dir}")
        return
    cutoff = datetime.now().date() - timedelta(days=days)
    removed = 0
    for f in sorted(log_dir.glob("fs-coil-*.log")):
        stamp = f.stem[len("fs-coil-"):]
        try:
            fdate = datetime.strptime(stamp, "%Y-%m-%d").date()
        except ValueError:
            continue  # unrecognized name — leave it alone
        if fdate < cutoff:
            try:
                f.unlink()
                removed += 1
            except OSError as e:
                warn(f"could not remove {f.name}: {e}")
    ok(f"pruned {removed} log file(s) older than {days} day(s)")


def cmd_noise(category=None, days=1):
    """Display suppressed-but-logged deny matches (things we chose NOT to
    page you about). Groups by category and shows counts + recent paths.

    --category=NAME     show only that category (default: all)
    --days=N            look back N days of logs (default 1 = today only)
    """
    import re as _re
    from collections import defaultdict
    user = console_user() or pwd.getpwuid(os.getuid()).pw_name
    home = user_home(user)
    log_dir = Path(home) / "Library" / "Logs" / "llmsnitch" / "fs-coil"
    if not log_dir.is_dir():
        warn(f"no log dir at {log_dir}")
        return
    cutoff = datetime.now().date() - timedelta(days=max(0, days - 1))
    logs = []
    for f in sorted(log_dir.glob("fs-coil-*.log")):
        stamp = f.stem[len("fs-coil-"):]
        try:
            fdate = datetime.strptime(stamp, "%Y-%m-%d").date()
        except ValueError:
            continue
        if fdate >= cutoff:
            logs.append(f)
    if not logs:
        warn(f"no logs in the last {days} day(s)")
        return

    line_re = _re.compile(
        r"^\[(?P<ts>[^\]]+)\] DENY-MATCH .* path=(?P<path>.+?) "
        r"pattern=(?P<pattern>\S+) suppressed=(?P<cat>\S+)$"
    )
    by_cat = defaultdict(list)
    for f in logs:
        try:
            for raw in f.read_text().splitlines():
                m = line_re.match(raw)
                if not m:
                    continue
                if category and m.group("cat") != category:
                    continue
                by_cat[m.group("cat")].append(
                    (m.group("ts"), m.group("path"), m.group("pattern")))
        except OSError:
            continue

    print_banner()
    head(f"suppressed events (last {days} day{'s' if days != 1 else ''})")
    if not by_cat:
        item("nothing suppressed in this window — "
             "add [notify] suppress_<name> = <glob> to ~/.config/llmsnitch/config")
        return
    for cat in sorted(by_cat):
        entries = by_cat[cat]
        item(f"{cat}: {len(entries)} event(s)")
        for ts, path, pattern in entries[-10:]:
            if _tty():
                print(f"    {_DIM}{ts}{_R}  {path}  {_DIM}rule={pattern}{_R}")
            else:
                print(f"    {ts}  {path}  rule={pattern}")
        if len(entries) > 10:
            more = len(entries) - 10
            if _tty():
                print(f"    {_DIM}… {more} older event(s) not shown{_R}")
            else:
                print(f"    ... {more} older event(s) not shown")


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
