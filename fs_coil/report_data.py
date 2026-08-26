"""_report_data — one-pass data collection for every dashboard section.

Parses today's log dir, runs the launchctl probe, compiles the deny list,
aggregates counters and returns a big dict. Callers then pass it to
_render_* functions which do their own presentation."""

import os
import pwd
from collections import Counter
from datetime import datetime
from pathlib import Path

from fs_coil.classify import _short_sign
from fs_coil.constants import ESLOGGER
from fs_coil.denylist import compile_deny
from fs_coil.icons import _find_notifier
from fs_coil.parser import (
    _hits_per_day, _hits_per_hour, _log_volume, _parse_execs, _parse_matches,
)
from fs_coil.runtime import _daemon_runtime, console_user, user_home


def _report_data():
    """Collect everything the dashboard sections need in one pass."""
    user = console_user() or pwd.getpwuid(os.getuid()).pw_name
    home = user_home(user)
    log_dir  = Path(home) / "Library" / "Logs"   / "llmsnitch" / "fs-coil"
    icon_dir = Path(home) / "Library" / "Caches" / "llmsnitch" / "fs-coil" / "icons"

    all_matches = _parse_matches(log_dir, days=7)
    # --- Reporting rule for severity --------------------------------------
    # Keep ALL matches in `all_matches` (for audit / raw access). The
    # "alerts" counts + breakdowns use only severity=high so Claude's
    # legitimate self-keychain reads don't inflate the numbers. Low events
    # are surfaced separately as `audit_*` counters.
    def _is_low(m): return m.get("severity") == "low"
    matches     = [m for m in all_matches if not _is_low(m)]
    audit_match = [m for m in all_matches if     _is_low(m)]
    rt = _daemon_runtime()
    deny = compile_deny(home)

    r_cnt  = sum(1 for (m, *_) in deny if m == "R")
    w_cnt  = sum(1 for (m, *_) in deny if m == "W")
    rw_cnt = sum(1 for (m, *_) in deny if m == "RW")
    total  = r_cnt + w_cnt + rw_cnt

    now = datetime.now()
    def _within(src, sec):
        return sum(1 for x in src if (now - x["dt"]).total_seconds() <= sec)
    h1, d1, d7 = _within(matches, 3600), _within(matches, 86400), len(matches)
    # Separate audit (severity=low) windowed counters.
    audit_h1, audit_d1, audit_d7 = (
        _within(audit_match, 3600),
        _within(audit_match, 86400),
        len(audit_match),
    )

    actors   = Counter((m.get("via") or m["proc"]) for m in matches)
    patterns = Counter(m["pattern"] for m in matches)
    paths    = Counter(m["path"] for m in matches)
    parents  = Counter((m.get("parent") or "?") for m in matches)
    sources  = Counter((m.get("src")  or "?") for m in matches)
    signs    = Counter(_short_sign(m.get("sign") or "") for m in matches
                       if m.get("sign") and m.get("sign") != "-")
    # Who/what/where: unique (name, source, short-sign) combo + count
    actor_identity = Counter(
        ((m.get("via") or m["proc"]), m.get("src") or "?",
         _short_sign(m.get("sign") or ""))
        for m in matches
    )
    daemon_n      = sum(1 for m in matches if m.get("daemon") == "yes")
    interactive_n = d7 - daemon_n

    log_files = sorted(log_dir.glob("fs-coil-*.log")) if log_dir.is_dir() else []
    log_span = (f"{len(log_files)} day(s) since {log_files[0].stem[-10:]}"
                if log_files else "(no logs yet)")
    log_bytes, log_lines, match_lines = _log_volume(log_files)

    icon_count = 0
    if icon_dir.is_dir():
        icon_count = sum(1 for _ in icon_dir.glob("*.png"))

    notifier = _find_notifier()
    eslogger_ok = os.access(ESLOGGER, os.X_OK)
    fda_inferred = rt["state"] == "running" and rt.get("pid") is not None
    log_writable = log_dir.is_dir() and os.access(log_dir, os.W_OK)

    # EXEC aggregation — per-AI command counters across 1h/24h/7d.
    execs = _parse_execs(log_dir, days=7)
    def _execs_within(sec):
        bucket = {"vscode_claude": Counter(),
                  "claude_app":    Counter(),
                  "opencode":      Counter()}
        for e in execs:
            if (now - e["dt"]).total_seconds() > sec:
                continue
            bucket.setdefault(e["ai"], Counter())[e["cmd"]] += 1
        return bucket
    execs_1h  = _execs_within(3600)
    execs_24h = _execs_within(86400)
    execs_7d  = _execs_within(7 * 86400)
    execs_total_1h = sum(sum(c.values()) for c in execs_1h.values())

    return {
        "user": user, "home": home, "log_dir": log_dir, "icon_dir": icon_dir,
        "matches":     matches,      # high-severity only (alerts)
        "audit":       audit_match,  # low-severity (Claude self-keychain etc.)
        "rt": rt,
        "r_cnt": r_cnt, "w_cnt": w_cnt, "rw_cnt": rw_cnt, "total": total,
        "h1": h1, "d1": d1, "d7": d7,
        "audit_h1": audit_h1, "audit_d1": audit_d1, "audit_d7": audit_d7,
        "actors": actors, "patterns": patterns, "paths": paths, "parents": parents,
        "sources": sources, "signs": signs, "actor_identity": actor_identity,
        "daemon_n": daemon_n, "interactive_n": interactive_n,
        "log_files": log_files, "log_span": log_span,
        "log_bytes": log_bytes, "log_lines": log_lines, "match_lines": match_lines,
        "icon_count": icon_count,
        "notifier": notifier, "eslogger_ok": eslogger_ok,
        "fda_inferred": fda_inferred, "log_writable": log_writable,
        "hits_per_day":  _hits_per_day(matches, 7),
        "hits_per_hour": _hits_per_hour(matches, 24),
        "execs": execs, "execs_1h": execs_1h, "execs_24h": execs_24h,
        "execs_7d": execs_7d, "execs_total_1h": execs_total_1h,
    }
