"""Recover Claude.app ancestry for processes spawned via `disclaimer`.

Claude.app ships `Contents/Helpers/disclaimer` — a 100-line wrapper that
spawns its argv child with `responsibility_spawnattrs_setdisclaim(..., 1)`.
Apple's Endpoint Security then reports the CHILD as its own responsible
process, hiding Claude.app as the real origin. That defeats the
`is_watched` blob check in events.py, and reads like `sqlite3` against
another app's state DB fly under the tripwire.

We recover the real ancestry by walking the ppid chain via /bin/ps. One
snapshot of all processes is taken per SNAPSHOT_TTL_SECS (subprocess cost
amortized across all events in that window) and consulted in-memory.
Per-pid verdict is cached for CACHE_TTL_SECS to keep the steady-state hot
path at dict-lookup speed.
"""

import os
import subprocess
import time

SNAPSHOT_TTL_SECS = 5    # re-enumerate /bin/ps at most this often
CACHE_TTL_SECS    = 60   # per-pid verdict retention
MAX_DEPTH         = 12   # defensive ancestor-walk bound

_CACHE = {}              # pid -> (is_descendant: bool, ts: float)
_SNAPSHOT = {}           # pid -> (ppid: int, exe: str)
_SNAPSHOT_TS = 0.0


def _snapshot():
    """{pid: (ppid, exe_path)} for all live processes. Single ps call.

    `comm` can contain spaces (e.g. `Claude Helper (Renderer)`), so we
    split only on the first two whitespaces — pid + ppid are numeric,
    the rest is the executable path.
    """
    try:
        r = subprocess.run(
            ["/bin/ps", "-axo", "pid=,ppid=,comm="],
            capture_output=True, text=True, timeout=1,
        )
    except Exception:
        return {}
    out = {}
    for line in r.stdout.splitlines():
        s = line.lstrip()
        parts = s.split(None, 2)
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue
        out[pid] = (ppid, parts[2].rstrip())
    return out


def _refresh_if_stale(now):
    global _SNAPSHOT, _SNAPSHOT_TS
    if now - _SNAPSHOT_TS > SNAPSHOT_TTL_SECS:
        _SNAPSHOT = _snapshot()
        _SNAPSHOT_TS = now


def _ancestor_is_claude(pid):
    """Walk ppid chain; True if any ancestor exe path points into a
    Claude.app bundle or into the disclaimer helper itself."""
    cur = pid
    for _ in range(MAX_DEPTH):
        entry = _SNAPSHOT.get(cur)
        if not entry:
            return False
        ppid, exe = entry
        exe_l = exe.lower()
        # `/claude.app/` anywhere catches both the main bundle and any
        # nested helper.app under Contents/Frameworks. Disclaimer lives
        # under Contents/Helpers/disclaimer — belt-and-braces.
        if "/claude.app/" in exe_l or "/helpers/disclaimer" in exe_l:
            return True
        if ppid <= 1:
            return False
        cur = ppid
    return False


def is_claude_descendant(pid):
    """True if pid's ancestor chain leads to Claude.app (possibly via
    disclaimer). Short-circuits on cached verdicts."""
    if not pid or pid <= 1:
        return False
    now = time.time()
    cached = _CACHE.get(pid)
    if cached and now - cached[1] < CACHE_TTL_SECS:
        return cached[0]
    _refresh_if_stale(now)
    verdict = _ancestor_is_claude(pid)
    _CACHE[pid] = (verdict, now)
    return verdict


def cleanup_cache():
    """Drop stale cache entries. Optional periodic call to keep memory
    bounded when the daemon is long-running."""
    now = time.time()
    stale = [p for p, (_, ts) in _CACHE.items() if now - ts > CACHE_TTL_SECS]
    for p in stale:
        _CACHE.pop(p, None)
