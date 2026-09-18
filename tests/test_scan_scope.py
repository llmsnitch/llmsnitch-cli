#!/usr/bin/env python3
"""T703 guards: plugin roots are walked subs (D10) and novelty resolution
is scope-aware (D11).

Run: python3 tests/test_scan_scope.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from llmsnitch import scan, scanrules   # noqa: E402
from tests._seams import run, with_tmp  # noqa: E402


def _as_home(t, body):
    """t is $HOME: the only territory is t/.claude, tilde display and the
    unattested sweep anchor on t. cwd is restored afterwards."""
    old = (scanrules.TERRITORIES, scan._HOME, os.environ.get("HOME"),
           os.getcwd())
    scanrules.TERRITORIES = {"claude-code": [str(t / ".claude")]}
    scan._HOME = str(t)
    os.environ["HOME"] = str(t)
    try:
        body()
    finally:
        scanrules.TERRITORIES, scan._HOME = old[0], old[1]
        if old[2] is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old[2]
        os.chdir(old[3])


def test_plugin_skill_at_depth_8_is_discovered():
    """A skill eight levels below ~/.claude (plugins/cache/<mkt>/<plug>/
    <ver>/skills/<name>/SKILL.md) is reached because depth is measured
    from the plugin root; a marketplace clone likewise; a symlinked root
    and a root nested in a junk dir (.git) are skipped; budget untouched."""
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        (t / "empty").mkdir()
        c = t / ".claude"
        ver = c / "plugins" / "cache" / "mkt" / "plug" / "1.0.0"
        deep = ver / "skills" / "deep"
        deep.mkdir(parents=True)
        (deep / "SKILL.md").write_text("---\nname: deep\n---\nhi\n")
        assert len((deep / "SKILL.md").relative_to(c).parts) == 8
        mk = c / "plugins" / "marketplaces" / "mkt" / "plugins" / "x" / "skills" / "y"
        mk.mkdir(parents=True)
        (mk / "SKILL.md").write_text("---\nname: y\n---\nhi\n")
        (ver.parent / "link").symlink_to(ver, target_is_directory=True)
        junk = c / "plugins" / "cache" / "temp_git_1" / ".git" / "hooks"
        junk.mkdir(parents=True)
        (junk / "pre-commit").write_text("#!/bin/sh\necho x\n")

        def body():
            os.chdir(t / "empty")
            targets, skipped = scan.discover()
            paths = sorted(str(p) for p, _, _ in targets)
            assert paths == sorted([str(deep / "SKILL.md"),
                                    str(mk / "SKILL.md")]), paths
            assert skipped == 0, skipped
        _as_home(t, body)


def _two_cwds(t):
    """A/.claude/settings.json breaches (wildcard grant); B/.claude is
    clean; t/.claude is an empty territory. Returns (A, B, run)."""
    a, b = t / "A", t / "B"
    for d in (a, b, t):
        (d / ".claude").mkdir(parents=True, exist_ok=True)
    (a / ".claude" / "settings.json").write_text(json.dumps({
        "permissions": {"allow": ["Bash(*)"],
                        "defaultMode": "bypassPermissions"}}))
    (b / ".claude" / "settings.json").write_text("{}")

    def run_from(cwd):
        os.chdir(cwd)
        return scan.run_scan(None, False, "manual")[1]
    return a, b, run_from


def _fp(findings, rule_id):
    return next(f["fingerprint"] for f in findings
                if f.get("rule_id") == rule_id)


def test_out_of_scope_finding_carries_forward():
    """Scan from A, then from B: A's finding is neither re-emitted nor
    tombstoned in B's scan; scanning from A again sees it as known."""
    def body(t, delivered, errors):
        a, b, run_from = _two_cwds(t)

        def inner():
            fp = _fp(run_from(a), "wildcard_bash_grant")
            assert not any(f.get("fingerprint") == fp for f in run_from(b))
            again = [f for f in run_from(a) if f.get("fingerprint") == fp]
            assert len(again) == 1 and again[0]["new"] is False, again
            assert not again[0].get("resolved")
        _as_home(t, inner)
    with_tmp(body, store=True)


def test_deleted_artifact_resolves_from_any_cwd():
    """A genuinely deleted artifact tombstones even when the scan runs
    from a cwd that would not have discovered it; the tombstone closes
    the fingerprint for later scans."""
    def body(t, delivered, errors):
        a, b, run_from = _two_cwds(t)

        def inner():
            fp = _fp(run_from(a), "wildcard_bash_grant")
            (a / ".claude" / "settings.json").unlink()
            tomb = [f for f in run_from(b) if f.get("fingerprint") == fp]
            assert tomb and tomb[0].get("resolved") is True, tomb
            assert not any(f.get("fingerprint") == fp for f in run_from(a))
        _as_home(t, inner)
    with_tmp(body, store=True)


def test_size_skipped_artifact_still_in_scope():
    """Scope is the discovered set (targets), not the scanned set: a file
    inventoried but skipped for size still resolves its stale finding."""
    def body(t, delivered, errors):
        a, b, run_from = _two_cwds(t)

        def inner():
            fp = _fp(run_from(a), "wildcard_bash_grant")
            old = scan._MAX_FILE
            scan._MAX_FILE = 1
            try:
                second = run_from(a)
            finally:
                scan._MAX_FILE = old
            tomb = [f for f in second if f.get("fingerprint") == fp]
            assert tomb and tomb[0].get("resolved") is True, tomb
        _as_home(t, inner)
    with_tmp(body, store=True)




def test_unattested_finding_resolves_when_signal_gone():
    """Spec review 2026-09-18: an unattested_agent_* artifact is a directory
    the sweep probed, never a target — it must still tombstone once its
    agent-home signal disappears while the directory stays."""
    def body(t, delivered, errors):
        def inner():
            os.chdir(t / "empty")
            sig = t / ".faketool" / "sessions" / "s.jsonl"
            sig.parent.mkdir(parents=True)
            sig.write_text('{"x": 1}\n')
            first = scan.run_scan(None, False, "patrol")[1]
            fp = _fp(first, "unattested_agent_home")
            sig.unlink()
            second = scan.run_scan(None, False, "patrol")[1]
            assert any(f.get("fingerprint") == fp and f.get("resolved")
                       for f in second), second
        (t / "empty").mkdir()
        _as_home(t, inner)
    with_tmp(body, store=True)


def test_cwd_control_files_outrank_plugin_cache():
    """Spec review 2026-09-18: under budget pressure the project's own
    .claude/settings.json is discovered before any plugin cache file."""
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        proj = t / "proj" / ".claude"
        proj.mkdir(parents=True)
        (proj / "settings.json").write_text('{"permissions": {"allow": ["Bash(*)"]}}')
        ver = t / ".claude" / "plugins" / "cache" / "mkt" / "plug" / "1.0.0" / "skills"
        for i in range(12):
            d = ver / f"s{i}"
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text("---\nname: s\n---\nhi\n")
        old = scan._MAX_FILES
        scan._MAX_FILES = 6
        try:
            def inner():
                os.chdir(t / "proj")
                targets, overflow = scan.discover()
                found = {os.path.realpath(p) for p, _, _ in targets}
                assert os.path.realpath(proj / "settings.json") in found, found
                assert overflow > 0
            _as_home(t, inner)
        finally:
            scan._MAX_FILES = old

if __name__ == "__main__":
    sys.exit(run(globals()))
