#!/usr/bin/env python3
"""T004 guards for the notify layer. Stdlib only, no root, no banners.

Run: python3 tests/test_notify.py
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from fs_coil import agent_registry, notify as nf  # noqa: E402

T0 = 1_755_600_000.0   # fixed epoch base for the injectable clock


def _env(t):
    return {"LLMSNITCH_NOTIFY_DIR": str(t / "notify"),
            "LLMSNITCH_HOT_STATE": str(t / "cache" / "notify-state.json"),
            "LLMSNITCH_CONFIG": str(t / "config.ini")}


def _with_tmp(fn, config=""):
    """Tmp dirs + env seams + no-banner _deliver stub + captured NOTIFIER-ERROR."""
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        (t / "cache").mkdir()
        (t / "config.ini").write_text(config or "[notify]\ncold_start = 0\n")
        old_env = {k: os.environ.get(k) for k in _env(t)}
        os.environ.update(_env(t))
        delivered, errors = [], []
        old_deliver, old_log = nf._deliver, nf._log_error
        nf._deliver = lambda *a, **k: delivered.append(a)
        nf._log_error = errors.append
        try:
            fn(t, delivered, errors)
        finally:
            nf._deliver, nf._log_error = old_deliver, old_log
            for k, v in old_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


def _rows(t):
    out = []
    for f in sorted((t / "notify").glob("events-*.ndjson")):
        out += [json.loads(l) for l in f.read_text().splitlines()]
    return out


def _state(t):
    return json.loads((t / "cache" / "notify-state.json").read_text())


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
            assert nf.notify("session-shed", "threshold_breach",
                             "cost 6.10 > ceiling 5.00", _now=T0 + i) is True
        assert [r["novelty_reason"] for r in _rows(t)][1:] == ["edge", "edge"]
        assert len(delivered) == 3
    _with_tmp(body)


def test_cold_start_suppresses_high_even_edge_but_not_critical():
    cfg = "[notify]\ncold_start = 24h\n"
    def body(t, delivered, errors):
        r1 = nf.notify("fs-coil-light", "deny_write", "~/.ssh/a",
                       deny_pattern="~/.ssh/**", _now=T0)          # high
        r2 = nf.notify("session-shed", "threshold_breach", "b", _now=T0)  # edge
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
        r = nf.notify("session-shed", "threshold_breach", "recovered",
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
for k in {list(_env(t).items())!r}:
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


def test_registry_invalid_agent_name_rejected():
    cfg = "[agent.bad@name]\npaths = ~/.bad\n[agent.goodname]\npaths = ~/.good\n"
    def body(t, delivered, errors):
        logged = []
        reg = agent_registry.load_registry(log=logged.append)
        assert "bad@name" not in reg
        assert "goodname" in reg
        assert logged and "invalid agent name" in logged[0]
    _with_tmp(body, config=cfg)


def test_registry_merge_replaces_listed_keeps_unlisted():
    cfg = "[agent.claude-code]\nexes = claude-custom\n"
    def body(t, delivered, errors):
        reg = agent_registry.load_registry()
        assert reg["claude-code"]["exes"] == ["claude-custom"]        # replaced
        assert reg["claude-code"]["paths"] == ["~/.claude", "~/.claude.json"]  # kept
    _with_tmp(body, config=cfg)


def test_attribute_actor_branches():
    def body(t, delivered, errors):
        reg = agent_registry.load_registry()
        # signing id wins over exe, path never consulted with pinfo present
        b, raw = agent_registry.attribute_actor(
            path=os.path.expanduser("~/.codex/x"),
            pinfo={"exe": "/usr/bin/mystery", "sign": "com.anthropic.claude"},
            registry=reg)
        assert b == "claude-code" and raw == "/usr/bin/mystery"
        # exe basename
        b, _ = agent_registry.attribute_actor(
            pinfo={"exe": "/opt/x/codex"}, registry=reg)
        assert b == "codex"
        # known tool normalization
        b, _ = agent_registry.attribute_actor(
            pinfo={"exe": "/opt/homebrew/bin/python3.14"}, registry=reg)
        assert b == "python"
        b, _ = agent_registry.attribute_actor(
            pinfo={"exe": "/usr/local/bin/mystery"}, registry=reg)
        assert b == "unknown"
        # light mode: territory only
        b, raw = agent_registry.attribute_actor(
            path=os.path.expanduser("~/.claude/settings.json"), registry=reg)
        assert b == "claude-code" and raw is None
        b, _ = agent_registry.attribute_actor(
            path=os.path.expanduser("~/.ssh/config"), registry=reg)
        assert b == "unknown"
    _with_tmp(body)


def test_classify_event_table():
    def body(t, delivered, errors):
        reg = agent_registry.load_registry()
        home = os.path.expanduser("~")
        # row 1: outside any territory
        assert agent_registry.classify_event(
            home + "/.ssh/config", "W", "unknown", reg) == ("deny_write", None)
        assert agent_registry.classify_event(
            home + "/.ssh/config", "R", "unknown", reg) == ("deny_read", None)
        # row 2: own territory — self vs cache
        assert agent_registry.classify_event(
            home + "/.claude/settings.json", "W", "claude-code", reg) == ("agent_self", None)
        assert agent_registry.classify_event(
            home + "/.claude/plugins/cache/x/y", "W", "claude-code", reg) == ("agent_plugin_cache", None)
        # row 3: registered agent in ANOTHER agent's territory → mismatch
        assert agent_registry.classify_event(
            home + "/.claude/settings.json", "W", "codex", reg) == ("deny_write", "claude-code")
        # row 4: non-agent bucket inside territory
        assert agent_registry.classify_event(
            home + "/.claude/settings.json", "W", "bash", reg) == ("deny_write", None)
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


def main():
    tests = sorted((v for k, v in globals().items()
                    if k.startswith("test_") and callable(v)),
                   key=lambda f: f.__name__)
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
