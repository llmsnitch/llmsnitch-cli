"""Log-file parsers + small aggregators used by report_data.

Regex definitions for DENY-MATCH and EXEC log lines, plus _hits_per_day,
_hits_per_hour, _log_volume, _daemon_loaded, _fmt_size."""

import os
import re
import subprocess
from datetime import datetime, timedelta

from fs_coil.constants import PLIST_LABEL

_REPORT_LOG_RE = re.compile(
    # src= and sign= were added later; make them optional so lines written
    # by older daemon builds still parse (otherwise the report shows empty
    # matches even when the log file has hits).
    r"^\[(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] DENY-MATCH "
    r"proc=(?P<proc>\S+?)\[(?P<pid>\d+)\](?: via (?P<via>\S+))? "
    r"(?:src=(?P<src>\S+) sign=(?P<sign>\S+) )?"
    r"(?:severity=(?P<severity>low|high) )?"
    r"parent=(?P<parent>\S*?)\[(?P<ppid>\d+)\] "
    r"daemon=(?P<daemon>yes|no) "
    r"event=(?P<event>\S+) "
    r"mode=(?P<mode>RW|R|W) "
    r"path=(?P<path>.+?) "
    r"pattern=(?P<pattern>.+?)\s*$"
)


_EXEC_LOG_RE = re.compile(
    r"^\[(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] EXEC "
    r"ai=(?P<ai>\S+) "
    r"by=(?P<by>\S+?)\[(?P<bypid>\d+)\] "
    r"cmd=(?P<cmd>\S+)"
    r"(?: args=(?P<args>.*))?\s*$"
)


def _parse_matches(log_dir, days=7):
    if not log_dir.is_dir():
        return []
    files = sorted(log_dir.glob("fs-coil-*.log"))[-days:]
    out = []
    for f in files:
        try:
            with open(f, "r", errors="replace") as fp:
                for ln in fp:
                    m = _REPORT_LOG_RE.match(ln.rstrip("\r\n"))
                    if not m:
                        continue
                    d = m.groupdict()
                    try:
                        d["dt"] = datetime.strptime(d["ts"], "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        continue
                    out.append(d)
        except OSError:
            continue
    return out


def _parse_execs(log_dir, days=7):
    """Parse EXEC log lines. Same file as DENY-MATCH — we just use a
    different regex."""
    if not log_dir.is_dir():
        return []
    files = sorted(log_dir.glob("fs-coil-*.log"))[-days:]
    out = []
    for f in files:
        try:
            with open(f, "r", errors="replace") as fp:
                for ln in fp:
                    m = _EXEC_LOG_RE.match(ln.rstrip("\r\n"))
                    if not m:
                        continue
                    d = m.groupdict()
                    try:
                        d["dt"] = datetime.strptime(d["ts"], "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        continue
                    out.append(d)
        except OSError:
            continue
    return out


def _daemon_loaded():
    try:
        r = subprocess.run(
            ["/bin/launchctl", "print", f"system/{PLIST_LABEL}"],
            capture_output=True, text=True,
        )
        return r.returncode == 0
    except Exception:
        return False


def _fmt_size(n):
    n = float(n)
    for u in ("B", "K", "M", "G"):
        if n < 1024:
            return f"{n:.0f}{u}" if n >= 10 else f"{n:.1f}{u}"
        n /= 1024
    return f"{n:.1f}T"


def _log_volume(log_files):
    """Scan all fs-coil log files; return (bytes, lines, match_lines)."""
    total_b = total_l = match_l = 0
    for f in log_files:
        try:
            total_b += f.stat().st_size
        except OSError:
            continue
        try:
            with open(f, "r", errors="replace") as fp:
                for ln in fp:
                    total_l += 1
                    if "DENY-MATCH" in ln:
                        match_l += 1
        except OSError:
            continue
    return total_b, total_l, match_l


def _hits_per_day(matches, days=7):
    """Return [(date, count), …] for the last `days` (oldest → newest)."""
    today = datetime.now().date()
    buckets = {today - timedelta(days=i): 0 for i in range(days)}
    for m in matches:
        d = m["dt"].date()
        if d in buckets:
            buckets[d] += 1
    return sorted(buckets.items())


def _hits_per_hour(matches, hours=24):
    """Return [(datetime, count), …] for the last `hours` hours (oldest → newest)."""
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    buckets = {now - timedelta(hours=hours - 1 - i): 0 for i in range(hours)}
    for m in matches:
        h = m["dt"].replace(minute=0, second=0, microsecond=0)
        if h in buckets:
            buckets[h] += 1
    return sorted(buckets.items())
