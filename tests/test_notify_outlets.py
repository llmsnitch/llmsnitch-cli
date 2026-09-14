#!/usr/bin/env python3
"""T601 tests: ledger.py (iter_rows, cmd_noise) and commands.py (cmd_prune, cmd_status).

Run: python3 tests/test_notify_outlets.py
"""

import contextlib
import io
import json
import os
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from fs_coil import notify as nf                            # noqa: E402
from tests._seams import with_tmp, row, seed_ledger, run   # noqa: E402

T0 = 1_755_600_000.0   # fixed epoch — 2025-08-19 (local); use now= everywhere


# ---------------------------------------------------------------- helpers

def _capture(fn, *a, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(*a, **kw)
    return buf.getvalue()


def _date_of(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


# ================================================================ iter_rows

def test_iter_rows_two_files_ascending():
    """iter_rows reads across two daily files and returns rows in ts order."""
    from fs_coil import ledger

    def body(t, delivered, errors):
        day1 = T0
        day2 = T0 + 86400          # next calendar day

        r1 = row(day1, "deny_write", "~/.ssh/config")
        r2 = row(day1 + 3600, "deny_write", "~/.aws/credentials")
        r3 = row(day2, "scan_finding", "critical rule: /tmp/foo")

        seed_ledger(t, [r1, r2, r3])

        result, skipped = ledger.iter_rows(day1 - 1, day2 + 1)
        assert skipped == 0, skipped
        assert len(result) == 3, len(result)
        tss = [r["ts"] for r in result]
        assert tss == sorted(tss), "not ascending"
        assert result[0]["subject"] == "~/.ssh/config"
        assert result[2]["subject"] == "critical rule: /tmp/foo"

    with_tmp(body)


def test_iter_rows_date_span_filter():
    """iter_rows reads only files within [date(start)-1d, date(end)+1d]."""
    from fs_coil import ledger

    def body(t, delivered, errors):
        old_ts = T0 - 4 * 86400   # 4 days before T0
        r_old = row(old_ts, "deny_write", "old_subject")
        r_new = row(T0, "deny_write", "new_subject")
        seed_ledger(t, [r_old, r_new])

        # query only T0 window — old file is outside [date(T0)-1d, date(T0)+1d]
        result, _ = ledger.iter_rows(T0 - 3600, T0 + 3600)
        subjects = [r["subject"] for r in result]
        assert "new_subject" in subjects
        assert "old_subject" not in subjects, subjects

    with_tmp(body)


def test_iter_rows_start_end_exclusive():
    """start_ts is inclusive, end_ts is exclusive."""
    from fs_coil import ledger

    def body(t, delivered, errors):
        seed_ledger(t, [
            row(T0,       "deny_write", "at_start"),
            row(T0 + 10,  "deny_write", "inside"),
            row(T0 + 100, "deny_write", "at_end"),
        ])
        result, _ = ledger.iter_rows(T0, T0 + 100)
        subjects = [r["subject"] for r in result]
        assert "at_start" in subjects
        assert "inside" in subjects
        assert "at_end" not in subjects, subjects

    with_tmp(body)


def test_iter_rows_missing_dir():
    """Missing notify dir returns ([], 0) without raising."""
    from fs_coil import ledger

    result, skipped = ledger.iter_rows(T0, T0 + 1,
                                        dir="/nonexistent/path/that/cannot/exist")
    assert result == []
    assert skipped == 0


def test_iter_rows_hostile_invalid_json():
    """Invalid JSON lines are skipped and counted."""
    from fs_coil import ledger

    def body(t, delivered, errors):
        stamp = _date_of(T0)
        seed_ledger(t, [
            f"{stamp}|not valid json {{{{",
            row(T0, "deny_write", "good_row"),
        ])
        result, skipped = ledger.iter_rows(T0 - 1, T0 + 1)
        assert skipped == 1, skipped
        assert len(result) == 1
        assert result[0]["subject"] == "good_row"

    with_tmp(body)


def test_iter_rows_hostile_non_dict_json():
    """Non-dict JSON (list, string) is skipped."""
    from fs_coil import ledger

    def body(t, delivered, errors):
        stamp = _date_of(T0)
        seed_ledger(t, [
            f"{stamp}|[1, 2]",
            f'{stamp}|"just a string"',
            row(T0, "deny_write", "good"),
        ])
        result, skipped = ledger.iter_rows(T0 - 1, T0 + 1)
        assert skipped == 2, skipped
        assert len(result) == 1

    with_tmp(body)


def test_iter_rows_hostile_missing_ts():
    """Dict with missing or non-numeric ts is skipped."""
    from fs_coil import ledger

    def body(t, delivered, errors):
        stamp = _date_of(T0)
        no_ts = {"v": 1, "category": "deny_write", "subject": "x",
                 "actor_bucket": "unknown"}
        str_ts = dict(no_ts, ts="not-a-number")
        seed_ledger(t, [
            f"{stamp}|" + json.dumps(no_ts),
            f"{stamp}|" + json.dumps(str_ts),
            row(T0, "deny_write", "valid"),
        ])
        result, skipped = ledger.iter_rows(T0 - 1, T0 + 1)
        assert skipped == 2, skipped
        assert len(result) == 1

    with_tmp(body)


def test_iter_rows_hostile_missing_subject_or_category():
    """Dict missing subject or category (non-str) is skipped."""
    from fs_coil import ledger

    def body(t, delivered, errors):
        stamp = _date_of(T0)
        no_subj = {"v": 1, "ts": T0, "category": "deny_write",
                   "actor_bucket": "unknown"}
        no_cat = {"v": 1, "ts": T0, "subject": "x", "actor_bucket": "unknown"}
        int_cat = {"v": 1, "ts": T0, "category": 42, "subject": "x",
                   "actor_bucket": "unknown"}
        seed_ledger(t, [
            f"{stamp}|" + json.dumps(no_subj),
            f"{stamp}|" + json.dumps(no_cat),
            f"{stamp}|" + json.dumps(int_cat),
            row(T0, "deny_write", "valid"),
        ])
        result, skipped = ledger.iter_rows(T0 - 1, T0 + 1)
        assert skipped == 3, skipped
        assert len(result) == 1

    with_tmp(body)


def test_iter_rows_hostile_undecodable_bytes():
    """Undecodable bytes in a line are skipped and counted."""
    from fs_coil import ledger

    def body(t, delivered, errors):
        d = t / "notify"
        d.mkdir(mode=0o700, exist_ok=True)
        stamp = _date_of(T0)
        f = d / f"events-{stamp}.ndjson"
        # write a good row + a non-UTF8 line + another good row
        good_line = json.dumps(row(T0, "deny_write", "good")).encode() + b"\n"
        bad_line = b"\xff\xfe" + b"\n"
        good_line2 = json.dumps(row(T0 + 1, "deny_write", "good2")).encode() + b"\n"
        with open(os.open(str(f), os.O_WRONLY | os.O_CREAT, 0o600), "wb") as fh:
            fh.write(good_line + bad_line + good_line2)

        result, skipped = ledger.iter_rows(T0 - 1, T0 + 2)
        assert skipped == 1, skipped
        assert len(result) == 2

    with_tmp(body)


# ================================================================ cmd_noise

def test_cmd_noise_default_hides_notified():
    """cmd_noise default hides notified==True rows."""
    from fs_coil.ledger import cmd_noise

    def body(t, delivered, errors):
        notified_row = row(T0, "deny_write", "notified_subj", notified=True)
        suppressed_row = row(T0 + 1, "deny_write", "suppressed_subj",
                             notified=False)
        seed_ledger(t, [notified_row, suppressed_row])

        out = _capture(cmd_noise, now=T0 + 3600)
        assert "suppressed_subj" in out
        assert "notified_subj" not in out

    with_tmp(body)


def test_cmd_noise_all_includes_notified():
    """cmd_noise --all includes notified rows."""
    from fs_coil.ledger import cmd_noise

    def body(t, delivered, errors):
        seed_ledger(t, [
            row(T0, "deny_write", "notified_subj", notified=True),
            row(T0 + 1, "deny_write", "suppressed_subj", notified=False),
        ])

        out = _capture(cmd_noise, all_rows=True, now=T0 + 3600)
        assert "notified_subj" in out
        assert "suppressed_subj" in out

    with_tmp(body)


def test_cmd_noise_category_filter():
    """--category filters by category (AND logic)."""
    from fs_coil.ledger import cmd_noise

    def body(t, delivered, errors):
        seed_ledger(t, [
            row(T0, "deny_write", "write_subj"),
            row(T0 + 1, "scan_finding", "scan_subj"),
        ])

        out = _capture(cmd_noise, category="deny_write", now=T0 + 3600)
        assert "write_subj" in out
        assert "scan_subj" not in out

    with_tmp(body)


def test_cmd_noise_actor_filter():
    """--actor filters by actor_bucket (AND logic)."""
    from fs_coil.ledger import cmd_noise

    def body(t, delivered, errors):
        seed_ledger(t, [
            row(T0, "deny_write", "unknown_subj", actor_bucket="unknown"),
            row(T0 + 1, "deny_write", "codex_subj", actor_bucket="codex"),
        ])

        out = _capture(cmd_noise, actor="codex", now=T0 + 3600)
        assert "codex_subj" in out
        assert "unknown_subj" not in out

    with_tmp(body)


def test_cmd_noise_days_selects_files():
    """--days selects the right calendar files."""
    from fs_coil.ledger import cmd_noise

    def body(t, delivered, errors):
        old_ts = T0 - 3 * 86400   # 3 days ago
        seed_ledger(t, [
            row(old_ts, "deny_write", "old_subj"),
            row(T0, "deny_write", "today_subj"),
        ])

        # days=1 → today only
        out = _capture(cmd_noise, days=1, now=T0 + 3600)
        assert "today_subj" in out
        assert "old_subj" not in out

        # days=4 → covers 3-days-ago file
        out4 = _capture(cmd_noise, days=4, now=T0 + 3600)
        assert "old_subj" in out4
        assert "today_subj" in out4

    with_tmp(body)


def test_cmd_noise_empty_prints_hint():
    """Empty result prints the config hint."""
    from fs_coil.ledger import cmd_noise

    def body(t, delivered, errors):
        # No ledger rows at all
        out = _capture(cmd_noise, now=T0 + 3600)
        assert "window" in out.lower() or "nothing" in out.lower()

    with_tmp(body)


def test_cmd_noise_groups_by_category_and_actor():
    """Rows are grouped by category then actor_bucket."""
    from fs_coil.ledger import cmd_noise

    def body(t, delivered, errors):
        seed_ledger(t, [
            row(T0, "deny_write", "s1", actor_bucket="unknown"),
            row(T0 + 1, "deny_write", "s2", actor_bucket="unknown"),
            row(T0 + 2, "deny_write", "s3", actor_bucket="codex"),
            row(T0 + 3, "scan_finding", "s4", actor_bucket="unknown"),
        ])
        out = _capture(cmd_noise, all_rows=True, now=T0 + 3600)
        # Each group header must appear
        assert "deny_write · unknown" in out
        assert "deny_write · codex" in out
        assert "scan_finding · unknown" in out

    with_tmp(body)


# ================================================================ cmd_prune

def _prune_helper():
    """Return the _prune_dated helper from commands."""
    import fs_coil.commands as cmd_mod
    return cmd_mod._prune_dated


def test_prune_dated_notify_deletes_old_leaves_young():
    """_prune_dated removes only old matching files, leaves young, non-matching,
    subdirectories, and symlinks to outside targets intact."""
    import fs_coil.commands as cmd_mod
    from fs_coil import ledger

    def body(t, delivered, errors):
        notify_dir = t / "notify"
        notify_dir.mkdir(mode=0o700, exist_ok=True)

        # old event file — should be pruned
        old_date = (date.today() - timedelta(days=50)).strftime("%Y-%m-%d")
        old_file = notify_dir / f"events-{old_date}.ndjson"
        old_file.write_text('{"v":1}\n')

        # young event file — should survive
        young_date = (date.today() - timedelta(days=2)).strftime("%Y-%m-%d")
        young_file = notify_dir / f"events-{young_date}.ndjson"
        young_file.write_text('{"v":1}\n')

        # non-matching file — should survive
        notes = notify_dir / "notes.txt"
        notes.write_text("keep me")

        # non-matching name pattern — should survive
        latest = notify_dir / "events-latest.ndjson"
        latest.write_text('{"v":1}\n')

        # subdirectory — should survive
        subdir = notify_dir / "subdir"
        subdir.mkdir()

        # symlink named like a dated file but pointing outside the dir
        outside = t / "outside.txt"
        outside.write_text("target")
        sym_date = old_date
        sym = notify_dir / f"digest-{sym_date}.txt"
        sym.symlink_to(outside)

        name_re = r"^(events|digest)-\d{4}-\d{2}-\d{2}\.(ndjson|txt)$"
        n = cmd_mod._prune_dated(str(notify_dir), name_re, 45, "notify")

        assert n == 1, f"expected 1 pruned, got {n}"
        assert not old_file.exists(), "old file should be removed"
        assert young_file.exists(), "young file must survive"
        assert notes.exists(), "notes.txt must survive"
        assert latest.exists(), "events-latest.ndjson must survive"
        assert subdir.exists(), "subdirectory must survive"
        assert sym.exists() or sym.is_symlink(), "symlink must survive"
        assert outside.exists(), "symlink target must survive"

    with_tmp(body)


def test_cmd_prune_target_notify():
    """cmd_prune(target='notify') uses ledger_dir and correct defaults."""
    import fs_coil.commands as cmd_mod

    def body(t, delivered, errors):
        notify_dir = t / "notify"
        notify_dir.mkdir(mode=0o700, exist_ok=True)

        old_date = (date.today() - timedelta(days=50)).strftime("%Y-%m-%d")
        old_file = notify_dir / f"events-{old_date}.ndjson"
        old_file.write_text('{"v":1}\n')

        young_date = (date.today() - timedelta(days=2)).strftime("%Y-%m-%d")
        young_file = notify_dir / f"events-{young_date}.ndjson"
        young_file.write_text('{"v":1}\n')

        cmd_mod.cmd_prune(target="notify")
        assert not old_file.exists(), "old file should be pruned"
        assert young_file.exists(), "young file must survive"

    with_tmp(body)


def test_cmd_prune_unknown_target_exits_1():
    """Unknown target exits with code 1."""
    import fs_coil.commands as cmd_mod

    def body(t, delivered, errors):
        try:
            _capture(cmd_mod.cmd_prune, target="bogus")
            raise AssertionError("should have raised SystemExit")
        except SystemExit as e:
            assert e.code == 1, e.code

    with_tmp(body)


def test_cmd_prune_logs_target():
    """cmd_prune(target='logs') deletes old log files via _prune_dated."""
    import tempfile
    import fs_coil.commands as cmd_mod

    with tempfile.TemporaryDirectory() as td:
        tmp_path = Path(td)
        log_dir = tmp_path / "Library" / "Logs" / "llmsnitch" / "fs-coil"
        log_dir.mkdir(parents=True)

        old_date = (date.today() - timedelta(days=35)).strftime("%Y-%m-%d")
        old_log = log_dir / f"fs-coil-{old_date}.log"
        old_log.write_text("old")

        young_date = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
        young_log = log_dir / f"fs-coil-{young_date}.log"
        young_log.write_text("young")

        orig_user_home = cmd_mod.user_home
        orig_console_user = cmd_mod.console_user
        cmd_mod.user_home = lambda u: str(tmp_path)
        cmd_mod.console_user = lambda: "testuser"
        try:
            cmd_mod.cmd_prune(target="logs")
        finally:
            cmd_mod.user_home = orig_user_home
            cmd_mod.console_user = orig_console_user

        assert not old_log.exists(), "old log should be pruned"
        assert young_log.exists(), "young log must survive"


# ================================================================ cmd_status

def test_cmd_status_degraded_reason():
    """cmd_status shows degraded reason when notify.set_degraded has been called."""
    import fs_coil.commands as cmd_mod

    def body(t, delivered, errors):
        nf.set_degraded("test-reason")

        # Monkeypatch subprocess.run to avoid launchctl call
        orig_run = cmd_mod.subprocess.run
        cmd_mod.subprocess.run = lambda *a, **kw: type(
            "R", (), {"returncode": 1, "stdout": "", "stderr": ""})()
        try:
            out = _capture(cmd_mod.cmd_status)
        finally:
            cmd_mod.subprocess.run = orig_run

        assert "degraded" in out
        assert "test-reason" in out

    with_tmp(body)


def test_cmd_status_no_degraded_shows_none():
    """cmd_status shows 'none' when not degraded."""
    import fs_coil.commands as cmd_mod

    def body(t, delivered, errors):
        # No set_degraded call — fresh state file won't exist
        orig_run = cmd_mod.subprocess.run
        cmd_mod.subprocess.run = lambda *a, **kw: type(
            "R", (), {"returncode": 1, "stdout": "", "stderr": ""})()
        try:
            out = _capture(cmd_mod.cmd_status)
        finally:
            cmd_mod.subprocess.run = orig_run

        assert "degraded" in out
        assert "none" in out

    with_tmp(body)


if __name__ == "__main__":
    sys.exit(run(globals()))
