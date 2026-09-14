"""Unified notify layer — the doctrine gate (docs/notifier-spec.md, T004).

One entry point, `notify()`, for every alert surface. Category enum,
duration parser, NDJSON ledger (cold trail), flock'd hot state (novelty
index), cold-start learning window, degraded flag, fail-closed.

Library only — no callers are wired until T005/T006. Stdlib only.

Test seams (production never sets them):
  LLMSNITCH_NOTIFY_DIR — ledger/digest directory
  LLMSNITCH_HOT_STATE  — hot-state JSON path
  LLMSNITCH_CONFIG     — INI path
"""

import configparser
import fcntl
import json
import os
import pwd
import re
import time
from datetime import datetime

from fs_coil.deny_rules import CRITICAL_DENY_PATTERNS
from fs_coil.runtime import console_user, user_home

_now = time.time   # module-level for test monkeypatching

STATE_VERSION = 1
ROW_VERSION = 1
_TEXT_CAP = 500        # actor_raw / subject truncation
_ROW_CAP = 3500        # drop pinfo beyond this encoded size
_LOCK_TRIES = 5        # bounded lock acquisition: 5 × 20 ms then fail-closed
_LOCK_WAIT = 0.02

# Category enum (D05, D06): name -> (default window, default severity,
# action line the page names). Categories are code, not config.
CATEGORIES = {
    "agent_self":             ("24h", "low",  "none — digest only; recall via fs-coil noise"),
    "agent_plugin_cache":     ("24h", "low",  "none — digest only"),
    "agent_signed_self_read": ("24h", "low",  "none — digest only; audit trail intact"),
    "deny_write":             ("1h",  "high", "investigate the writing process; revoke/kill if unexpected"),
    "deny_read":              ("5m",  "high", "investigate; rotate the credential if unexpected"),
    "keychain_access":        ("5m",  "high", "check which item was read; rotate if unexpected"),
    "threshold_breach":       ("0",   "high", "review the session; kill the runaway session"),
    "scan_finding":           ("24h", "high", "review the findings: llmsnitch scan --report"),
    "depaudit_finding":       ("24h", "critical", "uninstall if unexpected; detail: llmsnitch depaudit"),
    "watcher_health":         ("24h", "high", "check the watchers: fs-coil digest --show"),
}

_SURFACE_SECTION = {          # fixed surface -> config-section map
    "fs-coil-light": "notify.fs-coil",
    "fs-coil-deep":  "notify.fs-coil",
    "config-audit":  "notify.config-audit",
    "dep-audit":     "notify.dep-audit",
}
_GLYPH = {"fs-coil-deep": "🦍"}   # default 🐍

_WINDOW_RE = re.compile(r"^(\d+)([smhd]?)$")
_MULT = {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_window(s):
    """'24h' → 86400. Integer + s/m/h/d; bare integer = seconds."""
    m = _WINDOW_RE.match(str(s).strip())
    if not m:
        raise ValueError(f"bad duration: {s!r}")
    return int(m.group(1)) * _MULT[m.group(2)]


def _bool(raw, default):
    if raw is None:
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _home():
    user = console_user()
    home = user_home(user) if user else None
    return home or os.path.expanduser("~")


def _notify_dir():
    return os.environ.get(
        "LLMSNITCH_NOTIFY_DIR",
        os.path.join(_home(), "Library", "Logs", "llmsnitch", "notify"))


def _hot_state_path():
    return os.environ.get(
        "LLMSNITCH_HOT_STATE",
        os.path.join(_home(), "Library", "Caches", "llmsnitch",
                     "notify-state.json"))


def _read_ini():
    """{section: {key: raw}} — whole-file read, per-key fallback at use."""
    path = os.environ.get("LLMSNITCH_CONFIG",
                          os.path.expanduser("~/.config/llmsnitch/config"))
    cp = configparser.ConfigParser(inline_comment_prefixes=("#",))
    try:
        if os.path.exists(path):
            cp.read(path)
    except configparser.Error:
        return {}
    return {s: dict(cp[s]) for s in cp.sections()}


def _chown_user(path):
    """Root must never leave root-owned notify files under the user's home."""
    if os.geteuid() != 0:
        return
    user = console_user()
    if not user:
        return
    pw = pwd.getpwnam(user)
    os.chown(path, pw.pw_uid, pw.pw_gid, follow_symlinks=False)


def _mkdir_owned(path, mode):
    if not os.path.isdir(path):
        os.makedirs(path, mode=mode, exist_ok=True)
        _chown_user(path)
    os.chmod(path, mode)


def _log_error(reason):
    """Best-effort NOTIFIER-ERROR line to the daily fs-coil log."""
    try:
        from fs_coil.logger import Logger
        Logger(console_user() or "").write(
            f"[{datetime.now():%Y-%m-%d %H:%M:%S}] NOTIFIER-ERROR: {reason}")
    except Exception:  # noqa: BLE001 — the trace itself is best-effort
        pass


# ---------------------------------------------------------------- ledger

def _ledger_path(now):
    d = _notify_dir()
    _mkdir_owned(d, 0o700)
    return os.path.join(
        d, f"events-{datetime.fromtimestamp(now):%Y-%m-%d}.ndjson")


def _append_ledger(row, now):
    """One O_APPEND write per row — kernel-serialized, never interleaves."""
    path = _ledger_path(now)
    data = (json.dumps(row) + "\n").encode()
    if len(data) > _ROW_CAP and "pinfo" in row:
        row = dict(row)
        del row["pinfo"]
        data = (json.dumps(row) + "\n").encode()
    created = not os.path.exists(path)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    if created:
        _chown_user(path)


# ------------------------------------------------------------- hot state

def _install_ts_from_ledger(now):
    """Recover install_ts from the earliest daily ledger filename (D23 —
    a hot-state reset must never silently re-arm cold-start suppression)."""
    try:
        names = sorted(f for f in os.listdir(_notify_dir())
                       if re.match(r"^events-\d{4}-\d{2}-\d{2}\.ndjson$", f))
    except OSError:
        names = []
    if not names:
        return now
    stamp = names[0][len("events-"):-len(".ndjson")]
    return datetime.strptime(stamp, "%Y-%m-%d").timestamp()


class _HotState:
    """flock'd read-modify-write on notify-state.json (D12)."""

    def __init__(self, now):
        self.path = _hot_state_path()
        _mkdir_owned(os.path.dirname(self.path), 0o700)
        self._lock_fd = None
        self.now = now
        self.state = None

    def __enter__(self):
        lock = self.path + ".lock" if not self.path.endswith(".json") else \
            self.path[:-len(".json")] + ".lock"
        self._lock_fd = os.open(lock, os.O_WRONLY | os.O_CREAT, 0o600)
        for i in range(_LOCK_TRIES):
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if i == _LOCK_TRIES - 1:
                    os.close(self._lock_fd)
                    self._lock_fd = None
                    raise RuntimeError("hot-state lock contended")
                time.sleep(_LOCK_WAIT)
        self.state = self._load()
        return self

    def __exit__(self, *exc):
        if self._lock_fd is not None:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(self._lock_fd)
                self._lock_fd = None
        return False

    def _fresh(self, install_ts, degraded=None):
        return {"version": STATE_VERSION, "install_ts": install_ts,
                "degraded": degraded,
                "degraded_ts": self.now if degraded else None,
                "tuples": {}}

    def _load(self):
        if not os.path.exists(self.path):
            return self._fresh(self.now)
        try:
            with open(self.path) as f:
                state = json.load(f)
            if state.get("version") != STATE_VERSION:
                raise ValueError("unknown hot-state version")
            return state
        except (OSError, ValueError):
            # Corrupt/foreign: move aside, rebuild, recover install_ts from
            # the cold trail, flag state_reset (cleared only by TTL).
            try:
                os.replace(self.path, self.path + ".bak")
            except OSError:
                pass
            return self._fresh(_install_ts_from_ledger(self.now),
                               degraded="state_reset")

    def write(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.state, f)
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)
        _chown_user(self.path)


def set_degraded(reason, now=None):
    """Set the degraded flag (D22). Never raises."""
    try:
        with _HotState(now if now is not None else _now()) as hs:
            hs.state["degraded"] = reason
            hs.state["degraded_ts"] = hs.now
            hs.write()
    except Exception:  # noqa: BLE001
        pass


def get_degraded():
    """Current degraded reason or None (for status/dashboard)."""
    try:
        with open(_hot_state_path()) as f:
            return json.load(f).get("degraded")
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------ the gate

def _resolve_window(cfg, surface, category, actor_bucket):
    """First defined of: per-tuple, per-surface, global, code default (D13/D20)."""
    notify_g = cfg.get("notify", {})
    surf = cfg.get(_SURFACE_SECTION.get(surface, ""), {})
    for raw in (notify_g.get(f"window_{category}@{actor_bucket}"),
                surf.get(f"window_{category}"),
                notify_g.get(f"window_{category}")):
        if raw is not None:
            try:
                return parse_window(raw)
            except ValueError:
                pass   # malformed key never resets its siblings
    return parse_window(CATEGORIES[category][0])


def _critical_patterns(cfg):
    raw = cfg.get("notify", {}).get("critical_patterns", "")
    return CRITICAL_DENY_PATTERNS | {p.strip() for p in raw.split(",") if p.strip()}


def _deliver(surface, category, subject, actor_bucket, deny_pattern,
             title, message, icon_actor, exe_path, rexe_path):
    """Step 7: post via the existing Notifier NC mechanics. Fresh instance
    per call — its legacy cooldown is per-instance and empty (D24)."""
    from fs_coil.notifier import Notifier
    glyph = _GLYPH.get(surface, "🐍")
    action = CATEGORIES[category][2]
    Notifier().notify(
        title or f"{glyph} {actor_bucket} · {category}",
        message or f"{subject}\nrule: {deny_pattern or '-'}\naction: {action}",
        key=(surface, category, subject),
        icon_actor=icon_actor, exe_path=exe_path, rexe_path=rexe_path)


def notify(surface, category, subject, *,
           actor_bucket=None, actor_raw=None, pinfo=None,
           deny_pattern=None, actor_mismatch=None, record_only=False,
           title=None, message=None,
           icon_actor=None, exe_path=None, rexe_path=None,
           _now=None):
    """Single entry point for every alert surface. Returns True iff an NC
    banner was posted. NEVER raises (D21 fail-closed)."""
    try:
        return _notify_inner(
            surface, category, subject, actor_bucket, actor_raw, pinfo,
            deny_pattern, actor_mismatch, record_only, title, message,
            icon_actor, exe_path, rexe_path, _now)
    except Exception as e:  # noqa: BLE001 — the whole chain fails closed
        reason = f"{type(e).__name__}: {e}"[:200]
        _log_error(reason)
        set_degraded(reason, now=_now)
        return False


def _notify_inner(surface, category, subject, actor_bucket, actor_raw,
                  pinfo, deny_pattern, actor_mismatch, record_only,
                  title, message, icon_actor, exe_path, rexe_path, now):
    now = now if now is not None else _now()
    if category not in CATEGORIES:
        raise ValueError(f"unknown category: {category!r}")
    bucket = actor_bucket or "unknown"
    cfg = _read_ini()
    notify_g = cfg.get("notify", {})

    # Step 3 — severity is derived, never passed.
    severity = "critical" if (
        actor_mismatch or (deny_pattern and deny_pattern in _critical_patterns(cfg))
    ) else CATEGORIES[category][1]

    window = _resolve_window(cfg, surface, category, bucket)
    cold_start = parse_window(notify_g.get("cold_start", "24h"))
    ttl = parse_window(notify_g.get("degraded_flag_ttl", "24h"))

    # Steps 4–6 under one lock acquisition (degraded writes included).
    with _HotState(now) as hs:
        st = hs.state
        key = f"{category}|{bucket}"
        t = st["tuples"].get(key)
        if t is None:
            t = {"first_seen_ts": now, "count_in_window": 1,
                 "last_notified_ts": None}
            st["tuples"][key] = t
            reason, page = "first_seen", True
        elif window == 0:
            t["count_in_window"] += 1
            reason, page = "edge", True
        elif t["last_notified_ts"] is None:
            t["count_in_window"] += 1
            reason, page = "first_seen", True
        elif now - t["last_notified_ts"] >= window:
            t["first_seen_ts"] = now      # both fields describe the CURRENT window
            t["count_in_window"] = 1
            reason, page = "window_expired", True
        else:
            t["count_in_window"] += 1
            reason, page = "window_repeat", False

        # Step 5 — cold start beats edge; only critical pierces (D23).
        if (cold_start > 0 and now < st["install_ts"] + cold_start
                and severity != "critical" and page):
            reason, page = "cold_start_suppressed", False

        # Step 6 — notified means "a banner was posted", nothing else.
        surf_cfg = cfg.get(_SURFACE_SECTION.get(surface, ""), {})
        notified = (page and not record_only
                    and _bool(notify_g.get("enabled"), True)
                    and _bool(notify_g.get("outlet_nc"), True)
                    and _bool(surf_cfg.get("enabled"), True))
        if notified:
            t["last_notified_ts"] = now   # only a real page burns the slot

        # Degraded flag lifecycle: TTL expiry (any reason), else a fully-
        # successful call clears error reasons — never state_reset.
        if st.get("degraded"):
            dts = st.get("degraded_ts") or 0
            if ttl > 0 and now - dts >= ttl:
                st["degraded"] = None
                st["degraded_ts"] = None
            elif st["degraded"] != "state_reset":
                st["degraded"] = None
                st["degraded_ts"] = None

        first_seen_ts = t["first_seen_ts"]
        count = t["count_in_window"]
        hs.write()

    row = {"v": ROW_VERSION, "ts": now, "surface": surface,
           "category": category, "actor_bucket": bucket}
    if actor_raw:
        row["actor_raw"] = str(actor_raw)[:_TEXT_CAP]
    row.update({"subject": str(subject)[:_TEXT_CAP], "severity": severity,
                "first_seen_ts": first_seen_ts, "count_in_window": count,
                "novelty_reason": reason, "notified": notified})
    if deny_pattern:
        row["deny_pattern"] = deny_pattern
    if pinfo:
        row["pinfo"] = pinfo
    if actor_mismatch:
        row["actor_mismatch"] = actor_mismatch
    if record_only:
        row["record_only"] = True
    _append_ledger(row, now)

    if notified:
        _deliver(surface, category, row["subject"], bucket, deny_pattern,
                 title, message, icon_actor, exe_path, rexe_path)
    return notified
