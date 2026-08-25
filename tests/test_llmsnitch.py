#!/usr/bin/env python3
"""Tier-1 guards for llmsnitch. Stdlib only, no network, no Claude Code.

Run: python3 tests/test_llmsnitch.py
"""

import io
import json
import os
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from llmsnitch import gate, hook, setup_cmd, store, transcript  # noqa: E402

SECRET = "sk-abcdefghijklmnop1234"


def _payload(event, sid="s1", **kw):
    return io.StringIO(json.dumps(dict({"session_id": sid,
                                        "hook_event_name": event}, **kw)))


def _with_tmp_store(fn):
    with tempfile.TemporaryDirectory() as t:
        old = os.environ.get("LLMSNITCH_DIR")
        os.environ["LLMSNITCH_DIR"] = t
        try:
            fn(Path(t))
        finally:
            if old is None:
                os.environ.pop("LLMSNITCH_DIR", None)
            else:
                os.environ["LLMSNITCH_DIR"] = old


def test_hook_records_and_redacts():
    def body(t):
        rc = hook.handle("PreToolUse", _payload(
            "PreToolUse", tool_name="Bash",
            tool_input={"command": f"curl -H 'Authorization: {SECRET}'"}))
        assert rc == 0
        raw = (t / "sessions" / "s1" / "events.ndjson").read_text()
        assert SECRET not in raw, "secret reached disk"
        assert "<redacted>" in raw
    _with_tmp_store(body)


def test_redactor_covers_bearer_and_pem():
    """Extended credential shapes seen in real agent traffic —
    Authorization: Bearer headers and inline PEM private keys."""
    bearer = "Bearer abcdef.1234567890_ghijklmnop-qrstuv"
    pem = "-----BEGIN OPENSSH PRIVATE KEY-----"
    ant = "sk-ant-api03-" + "x" * 40
    def body(t):
        hook.handle("PreToolUse", _payload(
            "PreToolUse", tool_name="Bash",
            tool_input={"command": f"curl -H 'Authorization: {bearer}'"}))
        hook.handle("PreToolUse", _payload(
            "PreToolUse", tool_name="Write",
            tool_input={"content": f"key.txt\n{pem}\nAAAA..."}))
        hook.handle("PreToolUse", _payload(
            "PreToolUse", tool_name="Bash",
            tool_input={"command": f"export ANTHROPIC_API_KEY={ant}"}))
        raw = (t / "sessions" / "s1" / "events.ndjson").read_text()
        assert bearer not in raw, "Bearer token reached disk"
        assert pem not in raw, "PEM header reached disk"
        assert ant not in raw, "Anthropic key reached disk"
        assert raw.count("<redacted>") >= 3
    _with_tmp_store(body)


def test_hook_never_fails_on_garbage():
    def body(t):
        assert hook.handle("PreToolUse", io.StringIO("not json {{{")) == 0
        assert hook.handle("PostToolUse", io.StringIO("")) == 0
        assert hook.handle("PostToolUse", io.StringIO('"just a string"')) == 0
    _with_tmp_store(body)


def test_error_heuristic_and_summary():
    def body(t):
        hook.handle("PostToolUse", _payload("PostToolUse", tool_name="Bash",
                                            tool_response={"ok": True}))
        hook.handle("PostToolUse", _payload("PostToolUse", tool_name="Bash",
                                            tool_response={"is_error": True,
                                                           "message": SECRET}))
        s = store.summarize("s1")
        assert s["tool_calls"] == 2 and s["errors"] == 1, s
        raw = (t / "sessions" / "s1" / "events.ndjson").read_text()
        assert SECRET not in raw, "secret in error excerpt"
    _with_tmp_store(body)


def test_truncated_tail_tolerated():
    def body(t):
        store.append_event("s2", {"ts": 1.0, "event": "PostToolUse", "tool": "Read"})
        p = t / "sessions" / "s2" / "events.ndjson"
        with open(p, "a") as f:
            f.write('{"ts": 2.0, "event": "PostTo')   # truncated tail
        assert len(list(store.iter_events("s2"))) == 1
    _with_tmp_store(body)


def test_files_are_0600():
    def body(t):
        store.append_event("s3", {"ts": 1.0, "event": "PostToolUse"})
        store.write_meta("s3", {"session_id": "s3"})
        for name in ("events.ndjson", "meta.json"):
            mode = oct((t / "sessions" / "s3" / name).stat().st_mode & 0o777)
            assert mode == "0o600", (name, mode)
        assert oct((t / "sessions").stat().st_mode & 0o777) == "0o700"
    _with_tmp_store(body)


def test_stop_folds_transcript_cost():
    def body(t):
        tr = t / "transcript.jsonl"
        tr.write_text(
            json.dumps({"type": "assistant", "message": {
                "model": "claude-sonnet-5", "usage": {
                    "input_tokens": 1_000_000, "output_tokens": 1_000_000}}}) + "\n"
            + "garbage line\n")
        hook.handle("Stop", _payload("Stop", transcript_path=str(tr), cwd="/x"))
        meta = store.read_meta("s1")
        assert meta["cost_usd"] == 18.0, meta   # 1M*3$ + 1M*15$ per MTok
        assert meta["total_tokens"] == 2_000_000
        assert meta["ended_at"] > 0
    _with_tmp_store(body)


def test_cost_math_cache_and_unknown_model():
    totals = {"weird-model-x": {"input": 1_000_000, "output": 0,
                                "cache_read": 1_000_000, "cache_create": 1_000_000}}
    cost, tokens, unknown = transcript.estimate_cost(totals)
    # sonnet default: 3 + 0.3 (10% read) + 3.75 (125% create) = 7.05
    assert cost == 7.05, cost
    assert tokens == 3_000_000 and unknown


def test_gate_verdicts_and_exit_codes():
    cfg = dict(gate.DEFAULTS, billing_mode="per_token")
    healthy = {"session_id": "a", "started_at": 1, "tool_calls": 10,
               "errors": 0, "cost_usd": 0.5}
    costly = dict(healthy, session_id="b", cost_usd=9.9)
    flaky = dict(healthy, session_id="c", errors=5)
    assert gate.evaluate(cfg, [healthy]) == ("pass", [])
    v, f = gate.evaluate(cfg, [costly, flaky])
    assert v == "breach" and len(f) == 2
    assert "cost $9.90" in f[0]["reasons"][0]
    assert gate.EXIT_PASS == 0 and gate.EXIT_BREACH == 1 and gate.EXIT_OPERATIONAL == 2


def test_subscription_mode_skips_cost_breach():
    """Cost gate is per-token only — subscription plans aren't billed the
    theoretical per-token equivalent, so a $916 session shouldn't page you."""
    cfg = dict(gate.DEFAULTS, billing_mode="subscription")
    assert cfg["billing_mode"] == "subscription"   # default is subscription
    costly = {"session_id": "b", "started_at": 1, "tool_calls": 10,
              "errors": 0, "cost_usd": 916.41}
    assert gate.evaluate(cfg, [costly]) == ("pass", [])
    # Error-rate and health gates still fire regardless of billing mode.
    flaky = dict(costly, errors=5)
    v, f = gate.evaluate(cfg, [flaky])
    assert v == "breach"
    assert not any("cost" in r for r in f[0]["reasons"])


def test_fable_falls_to_unknown_default():
    """Fable pricing is unpublished — the table must not invent a rate."""
    totals = {"claude-fable-5": {"input": 1_000_000, "output": 1_000_000,
                                 "cache_read": 0, "cache_create": 0}}
    cost, tokens, unknown = transcript.estimate_cost(totals)
    assert unknown, "fable must trigger unknown-model note, not an invented price"
    # Sonnet-tier fallback: 3 + 15 = 18 per MTok
    assert cost == 18.0, cost


def test_gate_operational_when_empty():
    def body(t):
        out = io.StringIO()
        assert gate.cmd_check(dict(gate.DEFAULTS), out) == 2
    _with_tmp_store(body)


def test_health_formula():
    assert gate.health(0, 0) == 100          # no calls -> nothing failed
    assert gate.health(10, 0) == 100
    assert gate.health(10, 5) == 35           # 100 - 15 - 50
    assert gate.health(2, 2) == 0             # floored at 0


def test_config_per_key_fallback(tmp=None):
    with tempfile.TemporaryDirectory() as t:
        cfgfile = Path(t) / "config"
        cfgfile.write_text("[gate]\ncost_ceiling = junk\n"
                           "max_tool_fail_rate = 25  # comment\n")
        orig = gate.os.path.expanduser
        gate.os.path.expanduser = \
            lambda p: str(cfgfile) if p.endswith("llmsnitch/config") else orig(p)
        try:
            cfg = gate.load_cfg()
        finally:
            gate.os.path.expanduser = orig
        assert cfg["cost_ceiling"] == 5.0
        assert cfg["max_tool_fail_rate"] == 25.0


def test_setup_refuses_inside_claude_and_snapshots():
    with tempfile.TemporaryDirectory() as t:
        out = io.StringIO()
        rc = setup_cmd.run(True, out, settings_path=str(Path(t) / "s.json"),
                           env={"CLAUDECODE": "1"})
        assert rc == 2 and "refusing" in out.getvalue()
        # plain env: writes, idempotent, valid JSON
        sp = Path(t) / "s.json"
        sp.write_text('{"model": "opus"}')
        out = io.StringIO()
        assert setup_cmd.run(True, out, settings_path=str(sp), env={}) == 0
        cfg1 = json.loads(sp.read_text())
        assert "PreToolUse" in cfg1["hooks"] and cfg1["model"] == "opus"
        assert setup_cmd.run(True, io.StringIO(), settings_path=str(sp), env={}) == 0
        assert json.loads(sp.read_text()) == cfg1, "second run must be a no-op"


_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "codex-rollout.jsonl"
_CODEX_SID = "codex-0199aaaa-bbbb-7ccc-8ddd-eeeeffff0001"


def _with_codex_fixture(fn):
    """Temp store + codex entry pointed at a temp copy of the fixture."""
    from llmsnitch import harness

    def body(t):
        led = Path(t) / "ledger"
        led.mkdir()
        fx = led / "rollout-fixture.jsonl"
        fx.write_text(_FIXTURE.read_text())
        old = harness.HARNESSES["codex"]["session_paths"]
        harness.HARNESSES["codex"]["session_paths"] = [str(led / "rollout-*.jsonl")]
        try:
            fn(Path(t), fx)
        finally:
            harness.HARNESSES["codex"]["session_paths"] = old
    _with_tmp_store(body)


def test_codex_ledger_signal_set():
    from llmsnitch import ingest
    def body(t, fx):
        assert ingest.sweep() == 1
        meta = json.loads((t / "sessions" / _CODEX_SID / "meta.json").read_text())
        assert meta["harness"] == "codex" and meta["native_id"].endswith("0001")
        assert meta["cwd"] == "/tmp/proj", "cwd must come from FIRST session_meta"
        tok = meta["tokens_by_model"]["gpt-5.5"]
        assert tok["input_tokens"] == 140 and tok["output_tokens"] == 80
        assert tok["total_tokens"] == 250, \
            "restated token_count rows must not double-count (cumulative deltas)"
        assert meta["total_tokens"] == 250
        azure = "azureml://registries/azure-openai/models/gpt-5.3-codex/versions/2026-02-24"
        assert azure in meta["tokens_by_model"], \
            "declared-but-tokenless model must survive (trap 7)"
        assert meta["tokens_by_model"][azure]["total_tokens"] == 0
        assert meta["models"] == sorted([azure, "gpt-5.5"])
        assert meta["error_count"] == 2, "mcp+patch errors; interrupted excluded"
        assert meta["started_at"] and meta["ended_at"] > meta["started_at"]
        assert meta["signals_partial"] and meta["cost_usd"] is None
        assert meta["src"]["sha256"]
        for line in (t / "sessions" / _CODEX_SID / "events.ndjson").read_text().splitlines():
            ev = json.loads(line)
            assert ev["harness"] == "codex" and ev["src_sha256"], "row provenance"
    _with_codex_fixture(body)


def test_codex_bodies_and_secrets_never_stored():
    from llmsnitch import ingest
    def body(t, fx):
        ingest.sweep()
        for p in Path(t).rglob("*"):
            if p.is_file() and p.name != "rollout-fixture.jsonl":
                raw = p.read_text()
                assert "sk-test1234567890abcdef" not in raw, p
                assert "MUSTNOTCOPY" not in raw, p
    _with_codex_fixture(body)


def test_codex_cursor_idempotent_and_incremental():
    from llmsnitch import ingest
    def body(t, fx):
        assert ingest.sweep() == 1
        assert ingest.sweep() == 0, "unchanged file must be skipped"
        row = ('{"timestamp":"2026-08-20T10:06:00.000Z","type":"event_msg",'
               '"payload":{"type":"token_count","info":{"total_token_usage":'
               '{"input_tokens":150,"cached_input_tokens":20,"output_tokens":120,'
               '"reasoning_output_tokens":10,"total_tokens":300}}}}\n')
        with open(fx, "a") as f:
            f.write(row)
        assert ingest.sweep() == 1
        meta = json.loads((t / "sessions" / _CODEX_SID / "meta.json").read_text())
        assert meta["total_tokens"] == 300, "re-ingest must not double-count"
    _with_codex_fixture(body)


def test_codex_store_modes_and_list_column():
    import io as _io
    from llmsnitch import cli, ingest
    def body(t, fx):
        ingest.sweep()
        sdir = t / "sessions" / _CODEX_SID
        assert oct(sdir.stat().st_mode)[-3:] == "700"
        for f in ("meta.json", "events.ndjson"):
            assert oct((sdir / f).stat().st_mode)[-3:] == "600", f
        out = _io.StringIO()
        cli.cmd_list(out)
        text = out.getvalue()
        assert "HARNESS" in text and "codex" in text
        out = _io.StringIO()
        cli.cmd_show(_CODEX_SID, out)
        assert "harness   codex" in out.getvalue()
        assert "partial" in out.getvalue(), "degraded error signal must be visible"
        from llmsnitch import gate
        out = _io.StringIO()
        gate.cmd_check(dict(gate.DEFAULTS), out)
        assert "health: partial" in out.getvalue(), \
            "check must surface partial signals (contract C4)"
    _with_codex_fixture(body)


def test_codex_sweep_never_touches_ledger():
    import hashlib
    from llmsnitch import ingest
    def body(t, fx):
        before = (hashlib.sha256(fx.read_bytes()).hexdigest(),
                  sorted(os.listdir(fx.parent)), fx.stat().st_mtime_ns)
        ingest.sweep()
        after = (hashlib.sha256(fx.read_bytes()).hexdigest(),
                 sorted(os.listdir(fx.parent)), fx.stat().st_mtime_ns)
        assert before == after, "sweep must never write into harness territory"
    _with_codex_fixture(body)


def test_codex_hostile_native_id_cannot_escape_store():
    from llmsnitch import ingest
    def body(t, fx):
        evil = fx.parent / "rollout-evil.jsonl"
        evil.write_text('{"timestamp":"2026-08-20T10:00:00.000Z",'
                        '"type":"session_meta","payload":'
                        '{"id":"../../../ESCAPED","cwd":"/tmp"}}\n')
        ingest.sweep()
        assert not list(Path(t).rglob("ESCAPED")), "traversal escaped the store"
        names = [d.name for d in (t / "sessions").iterdir()]
        assert all("/" not in n and ".." not in n for n in names), names
        assert (t / "sessions" / "codex-rollout-evil").is_dir(), \
            "hostile id must fall back to sanitized filename stem"
    _with_codex_fixture(body)


def test_no_network_imports():
    pkg = Path(__file__).resolve().parent.parent / "llmsnitch"
    for p in pkg.glob("*.py"):
        src = p.read_text()
        for banned in ("urllib", "socket", "http.client", "requests"):
            assert f"import {banned}" not in src, (p.name, banned)


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
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
