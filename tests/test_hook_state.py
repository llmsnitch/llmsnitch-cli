#!/usr/bin/env python3
"""Quiet-patrol T702: Hook state class (D08) and semantic drift on
~/.claude.json (D09). Stdlib only.

Run: python3 tests/test_hook_state.py
"""

import hashlib
import io
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from llmsnitch import scan, scanrules  # noqa: E402
from tests._seams import with_tmp  # noqa: E402

SECRET = "sk-abcdefghijklmnop1234"


def _with_tmp_store(fn):
    def body(t, _delivered, _errors):
        (t / "store").mkdir()
        fn(t / "store")
    with_tmp(body, store=True)


def _rows(t):
    scans = sorted((t / "scans").iterdir())
    return [json.loads(x) for x in
            (scans[-1] / "findings.ndjson").read_text().splitlines()]


def _drift_rows(t):
    return [r for r in _rows(t) if r.get("rule_id", "").startswith("drift_")]


def _baseline(t):
    return json.loads((t / "baseline.json").read_text())


def _hooks_tree(t):
    """The live ~/.claude/hooks shape (2026-09-18) as a fixture."""
    h = t / "home" / ".claude" / "hooks"
    (h / "_lib").mkdir(parents=True)
    (h / "claude-notifier-active.d").mkdir()
    (h / "claude-notifier-task-start").mkdir()
    state = [h / "claude-signal", h / "claude-notifier-focus",
             h / "claude-notifier-config.json",
             h / "claude-notifier-active.d" / "20375",
             h / "claude-notifier-task-start" / "1d445c5f.json"]
    script = [h / "claude-notifier-on-stop.js", h / "enforce-pr-evidence.sh",
              h / "pre-commit", h / "_lib" / "notify.js"]
    for p in state + script:
        p.write_text("x\n")
    for p in (h / "claude-notifier-on-stop.js", h / "enforce-pr-evidence.sh",
              h / "pre-commit"):
        p.chmod(0o755)          # _lib/*.js stay 0644 like the live tree
    return h, state, script


def test_classify_hook_state_table():
    def body(t):
        _, state, script = _hooks_tree(t)
        for p in state:
            assert scan.classify(p) == "hook_state", p
        for p in script:
            assert scan.classify(p) == "hook_script", p
    _with_tmp_store(body)


def test_hook_state_outside_control_and_rules():
    assert "hook_state" not in scanrules.CONTROL_CLASSES
    for rid, _, _, classes, _ in scanrules.RULES:
        assert "hook_state" not in classes, rid


def test_hook_state_still_gets_secret_pass():
    def body(t):
        h, _, _ = _hooks_tree(t)
        (h / "claude-signal").write_text(f"token={SECRET}\n")
        assert scan.cmd_scan([str(h)], io.StringIO()) == 1
        hits = [r for r in _rows(t) if r.get("rule_id") == "secret_shape"]
        assert hits and hits[0]["artifact_class"] == "hook_state", hits
    _with_tmp_store(body)


def test_hook_state_rewrite_is_not_drift():
    def body(t):
        h, _, _ = _hooks_tree(t)
        assert scan.cmd_scan([str(h)], io.StringIO()) == 0
        (h / "claude-signal").write_text("rewritten\n")
        (h / "claude-notifier-active.d" / "99999").write_text("new\n")
        (h / "claude-notifier-task-start" / "1d445c5f.json").unlink()
        assert scan.cmd_scan([str(h)], io.StringIO()) == 0
        assert _drift_rows(t) == [], _drift_rows(t)
        keys = list(_baseline(t))
        assert keys and all(k.startswith("hook_script\x1f") for k in keys), keys
    _with_tmp_store(body)


def test_stale_hook_script_baseline_entry_is_dropped():
    def body(t):
        h, _, _ = _hooks_tree(t)
        assert scan.cmd_scan([str(h)], io.StringIO()) == 0   # seed
        # a pre-D08 baseline tracked the signal file as a hook_script
        key = "hook_script\x1f" + scan._display(h / "claude-signal")
        b = _baseline(t)
        b[key] = {"sha256": "0" * 64, "first_seen_ts": 1.0}
        (t / "baseline.json").write_text(json.dumps(b))
        assert scan.cmd_scan([str(h)], io.StringIO()) == 0
        assert _drift_rows(t) == [], _drift_rows(t)
        assert key not in _baseline(t)
    _with_tmp_store(body)


_DOC = {"numStartups": 1, "tipsHistory": {"a": 1},
        "mcpServers": {"fs": {"command": "npx", "args": ["fs-server"]}},
        "projects": {"/p/one": {"allowedTools": [], "mcpServers": {"x": {}}},
                     "/p/two": {"allowedTools": []}}}


def _cj(t):
    root = t / "root"
    root.mkdir(exist_ok=True)
    return root, root / ".claude.json"


def test_claude_json_churn_is_not_drift():
    def body(t):
        root, cj = _cj(t)
        cj.write_text(json.dumps(_DOC))
        assert scan.cmd_scan([str(root)], io.StringIO()) == 0
        doc = dict(_DOC, numStartups=2, tipsHistory={"b": 3})
        doc["projects"] = dict(doc["projects"], **{"/p/three": {"z": 1}})
        cj.write_text(json.dumps(doc, indent=2))
        assert scan.cmd_scan([str(root)], io.StringIO()) == 0
        assert _drift_rows(t) == [], _drift_rows(t)
    _with_tmp_store(body)


def test_claude_json_mcp_add_is_drift():
    def body(t):
        root, cj = _cj(t)
        cj.write_text(json.dumps(_DOC))
        assert scan.cmd_scan([str(root)], io.StringIO()) == 0
        doc = json.loads(json.dumps(_DOC))
        doc["mcpServers"]["evil"] = {"command": "curl"}
        cj.write_text(json.dumps(doc))
        assert scan.cmd_scan([str(root)], io.StringIO()) == 1
        d = _drift_rows(t)
        assert len(d) == 1 and d[0]["rule_id"] == "drift_changed", d
        assert d[0]["evidence"] == "mcpServers changed", d
        assert d[0]["category"] == "config_drift", d
        # a project-level MCP change drifts too
        doc["projects"]["/p/two"]["mcpServers"] = {"y": {}}
        cj.write_text(json.dumps(doc))
        assert scan.cmd_scan([str(root)], io.StringIO()) == 1
        assert [r["evidence"] for r in _drift_rows(t)] == ["mcpServers changed"]
    _with_tmp_store(body)


def test_claude_json_malformed_falls_back_to_file_sha():
    def body(t):
        root, cj = _cj(t)
        cj.write_text('{"mcpServers": {')
        assert scan.cmd_scan([str(root)], io.StringIO()) == 0
        key, entry = next(iter(_baseline(t).items()))
        assert key.startswith("mcp_config\x1f")
        assert entry["sha256"] == hashlib.sha256(cj.read_bytes()).hexdigest()
        cj.write_text('{"mcpServers": {{')
        assert scan.cmd_scan([str(root)], io.StringIO()) == 1
        d = _drift_rows(t)
        assert len(d) == 1 and d[0]["evidence"] == "changed", d
    _with_tmp_store(body)


if __name__ == "__main__":
    from tests._seams import run
    sys.exit(run(globals()))
