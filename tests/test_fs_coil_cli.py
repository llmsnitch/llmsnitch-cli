#!/usr/bin/env python3
"""T601 integration guards: the fs-coil CLI dispatch for digest / noise /
prune --target, run as a subprocess under the notify + store seams.

Run: python3 tests/test_fs_coil_cli.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from tests._seams import row, rows as _rows, run, seed_ledger, with_tmp  # noqa: E402

T0 = 1_755_600_000.0


def _cli(*args):
    """Run `python3 -m fs_coil.cli ...` with the seam env already exported
    by with_tmp; a non-TTY so theme helpers print plain text."""
    return subprocess.run([sys.executable, "-m", "fs_coil.cli", *args],
                          cwd=_ROOT, capture_output=True, text=True,
                          env=dict(os.environ, PYTHONPATH=str(_ROOT)))


def _healthy(t, now):
    scan = t / "store" / "scans" / "scan-x"
    scan.mkdir(parents=True)
    (scan / "meta.json").write_text(json.dumps(
        {"trigger": "patrol", "ended_at": now - 1800}))
    (t / "store" / "depaudit-state.json").write_text(json.dumps(
        {"ts": now - 1800, "bulletin_age_days": 1.0}))


def test_digest_cli_writes_file_and_exits_0():
    def body(t, delivered, errors):
        # No --now flag on the CLI: the subprocess uses wall time, so health
        # files and rows are seeded relative to it. Health MUST be seeded
        # healthy — an unhealthy run in a subprocess would post a real banner.
        import time
        now = time.time()
        _healthy(t, now)
        seed_ledger(t, [row(now - 60, "scan_finding", "hook_y: ~/b")])
        r = _cli("digest")
        assert r.returncode == 0, r.stderr
        assert not [x for x in _rows(t) if x["category"] == "watcher_health"]
        assert "digest written:" in r.stdout, r.stdout
        files = sorted((t / "notify").glob("digest-*.txt"))
        assert len(files) == 1, files
        assert oct(files[0].stat().st_mode)[-3:] == "600"
        text = files[0].read_text()
        for h in ("① health", "② new since last digest", "③ counts",
                  "④ noisiest subjects"):
            assert h in text, text
        assert "hook_y: ~/b" in text, text
        show = _cli("digest", "--show")
        assert show.returncode == 0 and "① health" in show.stdout
    with_tmp(body, store=True)


def test_noise_cli_groups_rows():
    def body(t, delivered, errors):
        import time
        now = time.time()
        seed_ledger(t, [row(now - 10, "scan_finding", "hook_a: ~/x"),
                        row(now - 20, "scan_finding", "hook_b: ~/y",
                            actor_bucket="codex", notified=True)])
        r = _cli("noise")
        assert r.returncode == 0, r.stderr
        assert "hook_a: ~/x" in r.stdout and "hook_b: ~/y" not in r.stdout, r.stdout
        r = _cli("noise", "--all", "--actor", "codex")
        assert "hook_b: ~/y" in r.stdout and "hook_a: ~/x" not in r.stdout, r.stdout
    with_tmp(body, store=True)


def test_prune_cli_target_notify_and_bad_target():
    def body(t, delivered, errors):
        d = t / "notify"
        d.mkdir(exist_ok=True)
        (d / "events-2020-01-01.ndjson").write_text("{}\n")
        (d / "digest-2020-01-01.txt").write_text("old\n")
        (d / "keep-me.txt").write_text("x\n")
        r = _cli("prune", "--target", "notify", "--days", "3650")
        assert r.returncode == 0, r.stderr
        assert (d / "events-2020-01-01.ndjson").exists()   # 3650d guard: nothing older
        r = _cli("prune", "--target", "notify")             # default 45 days
        assert r.returncode == 0, r.stderr
        assert not (d / "events-2020-01-01.ndjson").exists()
        assert not (d / "digest-2020-01-01.txt").exists()
        assert (d / "keep-me.txt").exists()
        r = _cli("prune", "--target", "bogus")
        assert r.returncode == 1, (r.returncode, r.stderr)
    with_tmp(body, store=True)


def test_digest_install_agent_prints_plist():
    plist = Path("~/Library/LaunchAgents/com.slav-it.llmsnitch-digest.plist").expanduser()
    before = plist.stat().st_mtime if plist.exists() else None
    r = _cli("digest", "--install-agent")
    assert r.returncode == 0, r.stderr
    assert "com.slav-it.llmsnitch-digest" in r.stdout
    assert "<integer>10</integer>" in r.stdout and "--prune" in r.stdout
    after = plist.stat().st_mtime if plist.exists() else None
    assert before == after   # print-only never writes or rewrites the plist


def test_usage_lists_new_commands():
    r = _cli("--help")
    for s in ("fs-coil digest", "--install-agent", "--actor", "--target"):
        assert s in r.stdout, s


def test_status_fresh_machine_collapses_deep():
    import contextlib, io
    from pathlib import Path
    from fs_coil import commands
    old = commands.PLIST_PATH, commands.BIN_PATH
    try:
        commands.PLIST_PATH = Path("/nonexistent/llmsnitch-test.plist")
        commands.BIN_PATH = Path("/nonexistent/fs-coil-test")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            commands.cmd_status()
        out = buf.getvalue()
        assert "deep mode not installed" in out, out
        assert "/Library/LaunchDaemons" not in out, out
        assert "light" in out, out          # row KEY only — never assert the
                                            # light VALUE: the gui-domain
                                            # launchctl probe is real and
                                            # machine-dependent
    finally:
        commands.PLIST_PATH, commands.BIN_PATH = old


if __name__ == "__main__":
    sys.exit(run(globals()))
