#!/usr/bin/env python3
"""T004 guards for the notify layer. Stdlib only, no root, no banners.

Run: python3 tests/test_notify.py
"""

import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from fs_coil import notify as nf  # noqa: E402
from tests._seams import with_tmp as _with_tmp, rows as _rows, state as _state, run  # noqa: E402

T0 = 1_755_600_000.0   # fixed epoch base for the injectable clock


def test_parse_window():
    assert nf.parse_window("24h") == 86400
    assert nf.parse_window("5m") == 300
    assert nf.parse_window("0") == 0
    assert nf.parse_window("7d") == 604800
    try:
        nf.parse_window("soon")
        raise AssertionError("bad duration accepted")
    except ValueError:
        pass


def test_first_seen_pages_then_window_repeat_suppresses():
    def body(t, delivered, errors):
        r1 = nf.notify("fs-coil-light", "deny_write", "~/.ssh/config",
                       deny_pattern="~/.ssh/**", _now=T0)
        r2 = nf.notify("fs-coil-light", "deny_write", "~/.ssh/config",
                       deny_pattern="~/.ssh/**", _now=T0 + 10)
        assert r1 is True and r2 is False, (r1, r2)
        rows = _rows(t)
        assert [r["novelty_reason"] for r in rows] == ["first_seen", "window_repeat"]
        assert [r["notified"] for r in rows] == [True, False]
        assert rows[1]["count_in_window"] == 2
        assert len(delivered) == 1 and not errors
    _with_tmp(body)


def test_window_expired_repages_and_resets_window_fields():
    def body(t, delivered, errors):
        nf.notify("fs-coil-light", "deny_write", "~/.ssh/x",
                  deny_pattern="~/.ssh/**", _now=T0)
        r = nf.notify("fs-coil-light", "deny_write", "~/.ssh/x",
                      deny_pattern="~/.ssh/**", _now=T0 + 3601)
        assert r is True
        last = _rows(t)[-1]
        assert last["novelty_reason"] == "window_expired"
        assert last["count_in_window"] == 1
        assert last["first_seen_ts"] == T0 + 3601   # current window, not all time
    _with_tmp(body)


def test_edge_pages_every_call():
    def body(t, delivered, errors):
        for i in range(3):
            assert nf.notify("gate", "threshold_breach",
                             "cost 6.10 > ceiling 5.00", _now=T0 + i) is True
        assert [r["novelty_reason"] for r in _rows(t)][1:] == ["edge", "edge"]
        assert len(delivered) == 3
    _with_tmp(body)


def test_cold_start_suppresses_high_even_edge_but_not_critical():
    cfg = "[notify]\ncold_start = 24h\n"
    def body(t, delivered, errors):
        r1 = nf.notify("fs-coil-light", "deny_write", "~/.ssh/a",
                       deny_pattern="~/.ssh/**", _now=T0)          # high
        r2 = nf.notify("gate", "threshold_breach", "b", _now=T0)  # edge
        r3 = nf.notify("fs-coil-deep", "deny_write", "~/.codex/c",
                       actor_bucket="aider", deny_pattern="~/.codex/**",
                       actor_mismatch="codex", _now=T0)            # critical
        assert (r1, r2, r3) == (False, False, True), (r1, r2, r3)
        reasons = [r["novelty_reason"] for r in _rows(t)]
        assert reasons[0] == "cold_start_suppressed"
        assert reasons[1] == "cold_start_suppressed"   # cold start beats edge
        assert reasons[2] == "first_seen"
        # A cold-start-suppressed event must not burn the page slot.
        assert _state(t)["tuples"]["deny_write|unknown"]["last_notified_ts"] is None
    _with_tmp(body, config=cfg)


def test_critical_patterns_pierce_cold_start():
    cfg = "[notify]\ncold_start = 24h\ncritical_patterns = ~/.ssh/**\n"
    def body(t, delivered, errors):
        r = nf.notify("fs-coil-light", "deny_write", "~/.ssh/id_rsa",
                      deny_pattern="~/.ssh/**", _now=T0)
        assert r is True
        row = _rows(t)[0]
        assert row["severity"] == "critical" and row["notified"] is True
    _with_tmp(body, config=cfg)


def test_record_only_ledgers_never_banners_never_burns_slot():
    def body(t, delivered, errors):
        r = nf.notify("gate", "threshold_breach", "recovered",
                      record_only=True, _now=T0)
        assert r is False and not delivered
        row = _rows(t)[0]
        assert row["notified"] is False and row["record_only"] is True
        assert row["novelty_reason"] == "first_seen"   # gate outcome preserved
        assert _state(t)["tuples"]["threshold_breach|unknown"]["last_notified_ts"] is None
    _with_tmp(body)


def test_forced_ledger_ioerror_sets_degraded_returns_false():
    def body(t, delivered, errors):
        old = nf._append_ledger
        nf._append_ledger = lambda row, now: (_ for _ in ()).throw(IOError("disk"))
        try:
            r = nf.notify("fs-coil-light", "deny_write", "~/.ssh/z",
                          deny_pattern="~/.ssh/**", _now=T0)
        finally:
            nf._append_ledger = old
        assert r is False
        assert "OSError" in _state(t)["degraded"] or "disk" in _state(t)["degraded"]
        assert errors and "NOTIFIER-ERROR" not in errors[0]  # reason text only
        assert not delivered
        # Next fully-successful call clears an error-reason flag.
        # (Fresh tuple — deny_write|git — so the gate itself also pages.)
        assert nf.notify("fs-coil-light", "deny_write", "~/.aws/ok",
                         actor_bucket="git",
                         deny_pattern="~/.aws/**", _now=T0 + 1) is True
        assert _state(t)["degraded"] is None
    _with_tmp(body)


def test_corrupt_hot_state_recovers_install_ts_and_flags_state_reset():
    def body(t, delivered, errors):
        (t / "notify").mkdir()
        (t / "notify" / "events-2026-08-01.ndjson").write_text("")
        sp = t / "cache" / "notify-state.json"
        sp.write_text("{not json")
        r = nf.notify("fs-coil-light", "deny_write", "~/.ssh/q",
                      deny_pattern="~/.ssh/**", _now=T0)
        assert r is True
        st = _state(t)
        from datetime import datetime
        assert st["install_ts"] == datetime.strptime("2026-08-01", "%Y-%m-%d").timestamp()
        assert st["degraded"] == "state_reset"        # success does NOT clear it
        assert (t / "cache" / "notify-state.json.bak").exists()
    _with_tmp(body)


def test_state_reset_cleared_only_by_ttl():
    cfg = "[notify]\ncold_start = 0\ndegraded_flag_ttl = 1h\n"
    def body(t, delivered, errors):
        nf.set_degraded("state_reset", now=T0)
        nf.notify("fs-coil-light", "deny_write", "~/.ssh/r",
                  deny_pattern="~/.ssh/**", _now=T0 + 10)
        assert _state(t)["degraded"] == "state_reset"
        nf.notify("fs-coil-light", "deny_write", "~/.aws/r2",
                  deny_pattern="~/.aws/**", _now=T0 + 3601)
        assert _state(t)["degraded"] is None
    _with_tmp(body, config=cfg)


def test_window_resolution_order():
    cfg = ("[notify]\ncold_start = 0\nwindow_deny_write = 2h\n"
           "window_deny_write@git = 4h\n"
           "[notify.fs-coil]\nwindow_deny_write = 3h\n")
    def body(t, delivered, errors):
        # per-tuple beats surface beats global: git tuple gets 4h
        nf.notify("fs-coil-light", "deny_write", "~/.ssh/w",
                  actor_bucket="git", deny_pattern="~/.ssh/**", _now=T0)
        r = nf.notify("fs-coil-light", "deny_write", "~/.ssh/w",
                      actor_bucket="git", deny_pattern="~/.ssh/**",
                      _now=T0 + 3.5 * 3600)   # inside 4h tuple window
        assert r is False
        # unknown bucket resolves surface override (3h): expired at 3.5h
        nf.notify("fs-coil-light", "deny_write", "~/.aws/w2",
                  deny_pattern="~/.aws/**", _now=T0)
        r2 = nf.notify("fs-coil-light", "deny_write", "~/.aws/w2",
                       deny_pattern="~/.aws/**", _now=T0 + 3.5 * 3600)
        assert r2 is True
    _with_tmp(body, config=cfg)


def test_outlets_off_still_ledgers_gate_outcome():
    cfg = "[notify]\ncold_start = 0\noutlet_nc = false\n"
    def body(t, delivered, errors):
        r = nf.notify("fs-coil-light", "deny_write", "~/.ssh/o",
                      deny_pattern="~/.ssh/**", _now=T0)
        assert r is False and not delivered
        row = _rows(t)[0]
        assert row["novelty_reason"] == "first_seen" and row["notified"] is False
    _with_tmp(body, config=cfg)


def test_concurrent_append_rows_stay_intact():
    def body(t, delivered, errors):
        script = (t / "writer.py")
        script.write_text(f"""
import json, os, sys
sys.path.insert(0, {str(_ROOT)!r})
for k in {[(k, os.environ[k]) for k in ("LLMSNITCH_NOTIFY_DIR", "LLMSNITCH_HOT_STATE", "LLMSNITCH_CONFIG")]!r}:
    os.environ[k[0]] = k[1]
from fs_coil import notify as nf
tag = sys.argv[1]
for i in range(500):
    nf._append_ledger({{"v": 1, "tag": tag, "i": i, "pad": "x" * 200}}, {T0})
""")
        procs = [subprocess.Popen([sys.executable, str(script), tag])
                 for tag in ("a", "b")]
        for p in procs:
            assert p.wait() == 0
        rows = _rows(t)
        assert len(rows) == 1000, len(rows)          # every row parsed intact
        assert sum(1 for r in rows if r["tag"] == "a") == 500
    _with_tmp(body)


def test_actor_mismatch_is_critical_and_respects_window():
    def body(t, delivered, errors):
        r1 = nf.notify("fs-coil-deep", "deny_write", "~/.claude/settings.json",
                       actor_bucket="codex", actor_mismatch="claude-code",
                       deny_pattern="/**/.claude/settings.json", _now=T0)
        r2 = nf.notify("fs-coil-deep", "deny_write", "~/.claude/settings.json",
                       actor_bucket="codex", actor_mismatch="claude-code",
                       deny_pattern="/**/.claude/settings.json", _now=T0 + 60)
        assert r1 is True and r2 is False   # one page per tuple per hour, not per write
        rows = _rows(t)
        assert rows[0]["severity"] == "critical"
        assert rows[0]["actor_mismatch"] == "claude-code"
    _with_tmp(body)


def test_icon_key_is_filename_safe():
    from fs_coil.notifier import _icon_key
    assert _icon_key("../../Evil Actor") == ".._.._evil_actor"
    assert "/" not in _icon_key("a/b\\c")
    assert _icon_key("") == ""
    assert _icon_key("claude-code") == "claude-code"


def test_icon_dir_created_0700():
    """Notifier's constructor is the one call that creates the llmsnitch-owned
    icon cache tree — dirs 0700 (CLAUDE.md constraint 5), not the umask default."""
    import tempfile
    from fs_coil import notifier as nt
    with tempfile.TemporaryDirectory() as t:
        home = Path(t) / "home"
        home.mkdir()
        old_u, old_h = nt.console_user, nt.user_home
        nt.console_user, nt.user_home = (lambda: "tester"), (lambda u: str(home))
        try:
            n = nt.Notifier()
        finally:
            nt.console_user, nt.user_home = old_u, old_h
        icons = home / "Library" / "Caches" / "llmsnitch" / "fs-coil" / "icons"
        assert n._icon_dir == icons, n._icon_dir
        for p in (icons, icons.parent):
            assert oct(p.stat().st_mode & 0o777) == "0o700", (str(p), oct(p.stat().st_mode))


if __name__ == "__main__":
    sys.exit(run(globals()))
