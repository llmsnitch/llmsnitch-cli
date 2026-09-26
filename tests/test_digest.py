#!/usr/bin/env python3
"""T601 guards for the digest outlet: health, render, banner, window, plist,
dep-audit stamp. Stdlib only, no root, no banners (delivery stubbed).

Run: python3 tests/test_digest.py
"""

import io
import json
import os
import sys
from html import unescape as html_unescape
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from fs_coil import digest, digest_agent, notify as nf  # noqa: E402
from tests._seams import row, rows as _rows, run, seed_ledger, with_tmp  # noqa: E402

T0 = 1_755_600_000.0
H = 3600.0
D = 86400.0


def _tmp(fn):
    with_tmp(fn, store=True)


def _healthy(t, now=T0, patrol_age=H, dep_age=H, bulletin_age=2.0):
    scan = t / "store" / "scans" / "scan-x"
    scan.mkdir(parents=True, exist_ok=True)
    (scan / "meta.json").write_text(json.dumps(
        {"trigger": "patrol", "ended_at": now - patrol_age}))
    (t / "store" / "depaudit-state.json").write_text(json.dumps(
        {"ts": now - dep_age, "bulletin_age_days": bulletin_age}))


def _run(**kw):
    out = io.StringIO()
    code = digest.cmd_digest(now=T0, out=out, **kw)
    return code, out.getvalue()


# ---------------------------------------------------------------- health

def test_health_all_good_has_no_problems():
    def body(t, d, e):
        _healthy(t)
        h = digest.health_report(T0)
        assert h["problems"] == [], h
        assert h["patrol_ts"] == T0 - H and h["bulletin_age_days"] == 2.0
    _tmp(body)


def test_health_each_condition_alone():
    def body(t, d, e):
        _healthy(t, patrol_age=27 * H)
        assert [p[:13] for p in digest.health_report(T0)["problems"]] == ["patrol missed"]
        _healthy(t)
        (t / "store" / "depaudit-state.json").unlink()
        assert digest.health_report(T0)["problems"] == [
            "dep-audit missed (never)", "bulletin stale (unknown)"]
        _healthy(t, bulletin_age=15)
        assert digest.health_report(T0)["problems"] == ["bulletin stale (15d)"]
        _healthy(t)
        nf.set_degraded("state_reset", now=T0)
        assert digest.health_report(T0)["problems"] == ["notifier degraded: state_reset"]
    _tmp(body)


def test_health_missing_or_corrupt_files_never_raise():
    def body(t, d, e):
        h = digest.health_report(T0)               # no store at all
        assert h["problems"][0] == "patrol missed (never)"
        scan = t / "store" / "scans" / "scan-bad"
        scan.mkdir(parents=True)
        (scan / "meta.json").write_text("{not json")
        (t / "store" / "depaudit-state.json").write_text('{"ts": "yesterday"}')
        h = digest.health_report(T0)
        assert h["patrol_ts"] is None and h["depaudit_ts"] is None
        # a manual scan does not count as the patrol
        (scan / "meta.json").write_text(json.dumps({"trigger": "manual", "ended_at": T0}))
        assert digest.health_report(T0)["patrol_ts"] is None
    _tmp(body)


# ---------------------------------------------------------------- render

def _render(window, lookback=(), prior=(), full=False, **hkw):
    h = {"now": T0, "patrol_ts": T0 - H, "depaudit_ts": T0 - H,
         "bulletin_age_days": 1.0, "degraded": None, "problems": []}
    h.update(hkw)
    return digest.render(list(window), list(lookback), list(prior), h,
                         start_ts=T0 - D, end_ts=T0, full=full)


def test_render_sections_tiers_and_classification():
    window = [row(T0 - H, "scan_finding", "critical hook_curl: ~/x", "unknown"),
              row(T0 - H, "scan_finding", "hook_unquoted: ~/y", "claude-code"),
              row(T0 - H, "depaudit_finding", "vuln: pkg 1.0 (GHSA-1)", "codex",
                  record_only=True),
              row(T0 - H, "scan_finding", "known_thing: ~/k", "claude-code"),
              row(T0 - 2 * H, "scan_finding", "known_thing: ~/k", "claude-code")]
    before = [row(T0 - 2 * D, "scan_finding", "known_thing: ~/k", "claude-code"),
              row(T0 - 2 * D, "scan_finding", "gone_thing: ~/g", "claude-code")]
    text = _render(window, before, prior=before)
    for h in ("① health", "② new since last digest (3)",
              "③ counts (category · actor: rows  new/known/resolved)",
              "④ noisiest subjects", "  → all watchers healthy"):
        assert h in text, text
    sec2 = text.split("② new")[1].split("③ counts")[0]
    assert sec2.index("[CRITICAL]") < sec2.index("[HIGH]") < sec2.index("[LESSER]"), sec2
    assert "known_thing" not in sec2, sec2                     # known never listed
    assert sec2.count("→ action: review the findings: llmsnitch scan --report") == 2
    assert "    unknown · critical hook_curl: ~/x" in sec2, sec2   # actor on the line
    assert "[HIGH] scan_finding\n" in sec2                        # not in the header
    assert "→ action: uninstall if unexpected; detail: llmsnitch depaudit" in sec2
    sec3 = text.split("③ counts")[1].split("④")[0]
    assert "  scan_finding · claude-code  3  1/1/1" in sec3, sec3   # new/known/resolved
    assert "  scan_finding · unknown  1  1/0/0" in sec3, sec3
    sec4 = text.split("④ noisiest subjects")[1]
    assert sec4.strip().startswith("2  known_thing: ~/k"), sec4


def test_render_cap_and_full():
    window = [row(T0 - H, "scan_finding", f"rule_{i:02d}: ~/f{i}") for i in range(25)]
    text = _render(window)
    assert "  … 5 more (fs-coil digest --full)" in text, text
    assert "rule_24" not in text
    full = _render(window, full=True)
    assert "more (fs-coil" not in full and "rule_24" in full


def test_render_empty_and_unhealthy():
    text = _render([], problems=["patrol missed (never)"], patrol_ts=None)
    assert "  nothing new" in text and "  (no rows)" in text
    assert "  patrol      MISSED — last never" in text, text
    assert "  → action: patrol missed (never) — launchctl kickstart" in text


def test_render_strips_control_chars_from_subjects():
    text = _render([row(T0 - H, "scan_finding", "evil\x1b[2Jrule: ~/z")])
    assert "\x1b" not in text and "evil [2Jrule" in text


# ---------------------------------------------------------------- cmd_digest

def test_cmd_digest_healthy_writes_0600_file_no_banner():
    def body(t, delivered, errors):
        _healthy(t)
        seed_ledger(t, [row(T0 - H, "scan_finding", "hook_a: ~/a")])
        code, out = _run()
        assert code == 0 and "digest written:" in out and "banner" not in out, out
        f = t / "notify" / f"digest-{digest.datetime.fromtimestamp(T0):%Y-%m-%d}.txt"
        assert f.exists() and oct(f.stat().st_mode)[-3:] == "600"
        text = f.read_text()
        assert "① health" in text and "hook_a: ~/a" in text
        assert not [r for r in _rows(t) if r["category"] == "watcher_health"]
        assert delivered == [] and not errors
        code, shown = _run(show=True)
        assert shown == text
    _tmp(body)


def test_cmd_digest_writes_escaped_browser_twin():
    def body(t, delivered, errors):
        _healthy(t)
        seed_ledger(t, [row(T0 - H, "scan_finding", "<script>alert(1)</script> ~/a & b")])
        _run()
        stamp = f"{digest.datetime.fromtimestamp(T0):%Y-%m-%d}"
        twin = t / "notify" / f"digest-{stamp}.html"
        assert twin.exists() and oct(twin.stat().st_mode)[-3:] == "600"
        page = twin.read_text()
        assert page.startswith("<!doctype html>") and "<pre>" in page
        assert "<script>" not in page and "&lt;script&gt;alert(1)&lt;/script&gt; ~/a &amp; b" in page
        assert html_unescape(page.split("<pre>", 1)[1].rsplit("</pre>", 1)[0]) == \
            (t / "notify" / f"digest-{stamp}.txt").read_text()
        code, shown = _run(show=True)                      # --show stays the text digest
        assert "<pre>" not in shown
    _tmp(body)


def test_cmd_digest_unhealthy_banners_once_per_window():
    def body(t, delivered, errors):
        _healthy(t, bulletin_age=20)
        code, out = _run()
        assert "banner: bulletin stale (20d)" in out, out
        wh = [r for r in _rows(t) if r["category"] == "watcher_health"]
        assert len(wh) == 1 and wh[0]["notified"] is True
        assert wh[0]["subject"] == "bulletin stale (20d)" and wh[0]["actor_bucket"] == "llmsnitch"
        assert len(delivered) == 1
        out2 = io.StringIO()
        digest.cmd_digest(now=T0 + H, out=out2)          # still unhealthy, 1h later
        wh = [r for r in _rows(t) if r["category"] == "watcher_health"]
        assert [r["notified"] for r in wh] == [True, False], wh
        assert wh[1]["novelty_reason"] == "window_repeat" and len(delivered) == 1
        assert "banner" not in out2.getvalue()
    _tmp(body)


def test_cmd_digest_outlet_digest_false_never_ledgers_health():
    def body(t, delivered, errors):
        _healthy(t, bulletin_age=20)
        code, out = _run()
        assert code == 0 and "banner" not in out
        assert not [r for r in _rows(t) if r["category"] == "watcher_health"]
        assert delivered == []
    with_tmp(body, config="[notify]\ncold_start = 0\noutlet_digest = false\n",
             store=True)


def test_cmd_digest_window_starts_at_previous_digest():
    def body(t, delivered, errors):
        _healthy(t)
        prev = t / "notify"
        prev.mkdir(exist_ok=True)
        old = prev / "digest-2000-01-01.txt"
        old.write_text("old\n")
        os.utime(old, (T0 - 40000, T0 - 40000))
        seed_ledger(t, [row(T0 - 50000, "scan_finding", "before_prev: ~/b"),
                        row(T0 - 30000, "scan_finding", "after_prev: ~/a")])
        _run()
        text = sorted(prev.glob("digest-*.txt"))[-1].read_text()
        assert "after_prev" in text and "before_prev" not in text, text
        assert f"window {digest._fmt(T0 - 40000)}" in text
        # previous digest far in the past → capped at LOOKBACK
        os.utime(old, (T0 - 30 * D, T0 - 30 * D))
        _run()
        text = sorted(prev.glob("digest-*.txt"))[-1].read_text()
        assert f"window {digest._fmt(T0 - digest.LOOKBACK)}" in text, text
        # future mtime (clock skew) → plain 24h
        os.utime(old, (T0 + D, T0 + D))
        _run()
        text = sorted(prev.glob("digest-*.txt"))[-1].read_text()
        assert f"window {digest._fmt(T0 - D)}" in text, text
    _tmp(body)


def test_cmd_digest_show_before_any_digest():
    def body(t, delivered, errors):
        code, out = _run(show=True)
        assert code == 0 and out == "no digest yet\n"
    _tmp(body)


def test_cmd_digest_prune_runs_notify_prune():
    def body(t, delivered, errors):
        _healthy(t)
        d = t / "notify"
        d.mkdir(exist_ok=True)
        (d / "events-2000-01-01.ndjson").write_text("{}\n")
        (d / "unrelated.txt").write_text("x\n")
        code, out = _run(prune=True)
        assert code == 0
        assert not (d / "events-2000-01-01.ndjson").exists()
        assert (d / "unrelated.txt").exists()
    _tmp(body)


# ---------------------------------------------------------------- LaunchAgent

def test_plist_and_install_agent_seam():
    text = digest_agent.plist()
    home = os.path.expanduser("~")
    assert digest_agent.LABEL in text and f"{home}/.local/bin/fs-coil" in text
    assert "<string>digest</string>" in text and "<string>--prune</string>" in text
    assert "<key>Hour</key><integer>10</integer><key>Minute</key><integer>0</integer>" in text
    out = io.StringIO()
    assert digest.cmd_digest(install_agent=True, out=out) == 0 and out.getvalue() == text
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "x.plist"
        out = io.StringIO()
        assert digest_agent.install_agent_run(True, out, plist_path=str(p)) == 0
        assert p.read_text() == text and "[OK] wrote" in out.getvalue()
        assert "bootstrapped" not in out.getvalue()      # seam skips launchctl


# ---------------------------------------------------------------- producer stamp

def test_depaudit_stamps_state_even_when_bulletin_missing():
    def body(t, delivered, errors):
        from llmsnitch import depaudit
        out = io.StringIO()
        code = depaudit.cmd_depaudit([], out)
        assert code == 2, out.getvalue()                 # no bulletin → operational
        p = t / "store" / "depaudit-state.json"
        assert p.exists() and oct(p.stat().st_mode)[-3:] == "600"
        st = json.loads(p.read_text())
        assert isinstance(st["ts"], float) and st["note"] and st["bulletin_age_days"] is None
        h = digest.health_report(st["ts"])
        assert "dep-audit missed" not in " ".join(h["problems"])
        assert "bulletin stale (unknown)" in h["problems"]
    _tmp(body)


# ---------------------------------------------------------------- open findings (plan 012)

def test_open_findings_readout_from_scan_meta():
    def body(t, d, e):
        _healthy(t)
        scan = t / "store" / "scans" / "scan-x"
        (scan / "meta.json").write_text(json.dumps(
            {"trigger": "patrol", "ended_at": T0 - H,
             "findings_by_severity": {"critical": 1, "high": 2, "low": 3}}))
        text = _render([], **{k: v for k, v in digest.health_report(T0).items()
                              if k != "now"})
        assert "open findings (last patrol): scan 1c/2h/3l (llmsnitch scan --report)" in text, text
    _tmp(body)


def test_open_findings_readout_dep_audit():
    def body(t, d, e):
        _healthy(t)
        (t / "store" / "depaudit-state.json").write_text(json.dumps(
            {"ts": T0 - H, "bulletin_age_days": 2.0,
             "findings": 4, "findings_critical": 1}))
        text = _render([], **{k: v for k, v in digest.health_report(T0).items()
                              if k != "now"})
        assert "open findings (last patrol): dep-audit 1c/4 (llmsnitch depaudit)" in text, text
    _tmp(body)


def test_open_findings_none_when_clean():
    def body(t, d, e):
        _healthy(t)
        # patrol meta with empty findings_by_severity (default), dep findings:0
        (t / "store" / "depaudit-state.json").write_text(json.dumps(
            {"ts": T0 - H, "bulletin_age_days": 2.0,
             "findings": 0, "findings_critical": 0}))
        text = _render([], **{k: v for k, v in digest.health_report(T0).items()
                              if k != "now"})
        assert "\nopen findings: none\n" in text, text
    _tmp(body)


def test_open_findings_survives_novelty_window():
    """Core regression: a persistent scan finding aged out of ② still shows
    in the standing readout, because the readout reads producer state, not
    the 7-day novelty window."""
    def body(t, d, e):
        _healthy(t)
        scan = t / "store" / "scans" / "scan-x"
        (scan / "meta.json").write_text(json.dumps(
            {"trigger": "patrol", "ended_at": T0 - H,
             "findings_by_severity": {"critical": 1}}))
        # same row in window and lookback → "known", never listed in ②
        known = row(T0 - H, "scan_finding", "critical wildcard: ~/x")
        text = _render([known], lookback=[known], prior=[],
                       **{k: v for k, v in digest.health_report(T0).items()
                          if k != "now"})
        sec2 = text.split("② new")[1].split("③ counts")[0]
        assert "nothing new" in sec2, sec2
        assert "open findings (last patrol): scan 1c/0h/0l" in text, text
    _tmp(body)


def test_depaudit_finding_renders_in_section_two():
    """New unwaived critical depaudit_finding renders under ② with the
    right decision line and tier — the never-run render path."""
    def body(t, d, e):
        r = row(T0 - H, "depaudit_finding", "critical malicious: evilpkg 1.0", "codex")
        text = _render([r], lookback=[], prior=[])
        sec2 = text.split("② new")[1].split("③ counts")[0]
        assert "[CRITICAL] depaudit_finding" in sec2, sec2
        assert "→ action: uninstall if unexpected; detail: llmsnitch depaudit" in sec2, sec2
        assert "codex · critical malicious: evilpkg 1.0" in sec2, sec2
    _tmp(body)


def test_health_report_missing_meta_is_zero():
    def body(t, d, e):
        h = digest.health_report(T0)         # no store at all
        assert h["scan_findings"] == {} and h["dep_findings"] == 0
        assert h["dep_critical"] == 0
    _tmp(body)


if __name__ == "__main__":
    sys.exit(run(globals()))
