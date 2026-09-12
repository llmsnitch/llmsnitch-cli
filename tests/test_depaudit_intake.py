#!/usr/bin/env python3
"""Dep-audit intake extraction (T504): install-command grammar, env
resolution chain, cursor-gated sweep into <base>/intakes.ndjson.

Run: python3 tests/test_depaudit_intake.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from llmsnitch import intake, store  # noqa: E402


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


def _mk_venv(root, name):
    d = Path(root) / name
    d.mkdir(parents=True)
    (d / "pyvenv.cfg").write_text("home = /usr/bin\n")
    return d


def _seed_session(sid, commands, cwd=""):
    """events.ndjson with install commands plus noise every extractor must
    ignore: non-Bash PreToolUse, PostToolUse install, corrupt + truncated
    tail lines."""
    sdir = store.session_dir(sid)
    with open(sdir / "events.ndjson", "w") as f:
        f.write(json.dumps({"ts": 1.0, "event": "session_start"}) + "\n")
        for i, c in enumerate(commands):
            f.write(json.dumps({"ts": 10.0 + i, "event": "PreToolUse",
                                "tool": "Bash", "input": {"command": c}}) + "\n")
        f.write(json.dumps({"ts": 90.0, "event": "PreToolUse", "tool": "Read",
                            "input": {"file_path": "/etc/hosts"}}) + "\n")
        f.write(json.dumps({"ts": 91.0, "event": "PostToolUse", "tool": "Bash",
                            "input": {"command": "pip install ghost"}}) + "\n")
        f.write("not-json{{{\n")
        f.write('{"ts": 92.0, "event": "PreToolUse", "tool": "Ba')  # cut tail
    store.write_meta(sid, {"session_id": sid, "harness": "claude-code",
                           "cwd": cwd})


# --- parse_install_command: grammar ---------------------------------------

def test_parse_grammar_hits():
    cases = {
        "pip install requests": ("pip", "requests"),
        "pip3 install requests": ("pip", "requests"),
        "python -m pip install requests": ("pip", "requests"),
        "python3 -m pip install requests": ("pip", "requests"),
        "uv add requests": ("uv", "requests"),
        "uv pip install requests": ("uv", "requests"),
        "uv tool install ruff": ("uv-tool", "ruff"),
        "pipx install ruff": ("pipx", "ruff"),
    }
    for cmd, (kind, pkg) in cases.items():
        recs = intake.parse_install_command(cmd)
        assert len(recs) == 1, (cmd, recs)
        r = recs[0]
        assert r["kind"] == kind and r["package"] == pkg, (cmd, r)
        assert r["bulk"] is False and r["env_path"] is None, (cmd, r)


def test_parse_grammar_misses():
    for cmd in ("pip download requests", "pip uninstall requests",
                "npm install left-pad", "uv run script.py", "pipx run ruff",
                'echo "pip install x"', "echo hello", "cargo install ripgrep"):
        assert intake.parse_install_command(cmd) == [], cmd


def test_parse_compound_segments():
    recs = intake.parse_install_command(
        "cd /tmp && pip install alpha ; echo hi | pip3 install beta")
    assert [r["package"] for r in recs] == ["alpha", "beta"], recs


def test_parse_specs_normalized():
    recs = intake.parse_install_command(
        "pip install Requests==2.31 Foo_Bar[socks]>=1.0 A.B.C~=2 x!=3 y<4")
    assert [r["package"] for r in recs] == \
        ["requests", "foo-bar", "a-b-c", "x", "y"], recs


def test_parse_bulk_triggers():
    for cmd, kind in (("pip install -r requirements.txt", "pip"),
                      ("pip install --requirement reqs.txt", "pip"),
                      ("pip install -e .", "pip"),
                      ("uv sync", "uv"),
                      ("pip install ./pkg", "pip"),
                      ("pip install /tmp/x-1.0.whl", "pip"),
                      ("pip install dist-1.0.tar.gz", "pip"),
                      ("pip install git+https://github.com/a/b", "pip"),
                      ("pip install https://files.example/x.zip", "pip")):
        recs = intake.parse_install_command(cmd)
        assert len(recs) == 1, (cmd, recs)
        r = recs[0]
        assert r["package"] is None and r["bulk"] is True, (cmd, r)
        assert r["kind"] == kind, (cmd, r)


def test_parse_bulk_swallows_named():
    # Bulk attributes the whole env — a superset of any named spec alongside.
    recs = intake.parse_install_command("pip install -r reqs.txt requests")
    assert recs == [{"package": None, "bulk": True, "env_path": None,
                     "kind": "pip"}], recs


def test_parse_value_flag_skipping():
    recs = intake.parse_install_command(
        "pip install -i https://mirror.example/simple requests")
    assert recs == [{"package": "requests", "bulk": False, "env_path": None,
                     "kind": "pip"}], recs
    recs = intake.parse_install_command("pip install --target /tmp/site pkg")
    assert [r["package"] for r in recs] == ["pkg"] and not recs[0]["bulk"], recs


def test_parse_explicit_env_path():
    for cmd in ("/proj/.venv/bin/pip install x",
                "/proj/.venv/bin/python -m pip install x",
                "/proj/.venv/bin/python3.12 -m pip install x"):
        recs = intake.parse_install_command(cmd)
        assert recs == [{"package": "x", "bulk": False,
                         "env_path": "/proj/.venv", "kind": "pip"}], (cmd, recs)
    recs = intake.parse_install_command(
        "uv pip install --python /proj/.venv/bin/python3 x")
    assert recs[0]["env_path"] == "/proj/.venv", recs


def test_parse_truncation_degrades_final_segment():
    cmd = "pip install early && echo " + "x" * 2100 + " && pip install late"
    recs = intake.parse_install_command(cmd)
    assert len(recs) == 2, recs
    assert recs[0] == {"package": "early", "bulk": False, "env_path": None,
                       "kind": "pip"}, recs
    assert recs[1]["package"] is None and recs[1]["bulk"] is True, recs
    # Short commands keep final-segment packages.
    recs = intake.parse_install_command("echo hi && pip install ok")
    assert recs[0]["package"] == "ok" and recs[0]["bulk"] is False, recs


def test_parse_never_crashes():
    for junk in ("", "&&&&;;||", "pip install", "pip install -r", "uv",
                 "pipx", "|| | ;", "pip install " + "-" * 50, None, 42):
        assert isinstance(intake.parse_install_command(junk), list), junk


# --- env resolution chain --------------------------------------------------

def test_resolve_prefers_dot_venv():
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "proj"
        _mk_venv(proj, ".venv")
        _mk_venv(proj, "venv-alt")
        for cmd in ("pip install x", "uv add x", "uv sync"):
            rec = intake._parse(cmd)[0]
            got = intake._resolve_env(rec, str(proj))
            assert got == str(proj / ".venv"), (cmd, got)


def test_resolve_single_nonstandard_candidate():
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "proj"
        env = _mk_venv(proj, ".venv-dashboard")
        rec = intake._parse("pip install x")[0]
        assert intake._resolve_env(rec, str(proj)) == str(env)


def test_resolve_two_candidates_unresolved():
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "proj"
        _mk_venv(proj, "envA")
        _mk_venv(proj, "envB")
        rec = intake._parse("pip install x")[0]
        assert intake._resolve_env(rec, str(proj)) == "unresolved"


def test_resolve_uv_lock_is_not_an_env():
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "proj"
        proj.mkdir()
        (proj / "uv.lock").write_text("")
        rec = intake._parse("uv add x")[0]
        assert intake._resolve_env(rec, str(proj)) == "unresolved"


def test_resolve_python_arg_dir_with_pyvenv_cfg():
    with tempfile.TemporaryDirectory() as td:
        env = _mk_venv(td, "ex-env")
        rec = intake._parse("uv pip install --python %s x" % env)[0]
        assert intake._resolve_env(rec, "") == str(env)
        bare = Path(td) / "not-an-env"
        bare.mkdir()
        rec = intake._parse("uv pip install --python %s x" % bare)[0]
        assert intake._resolve_env(rec, "") == "unresolved"


def test_resolve_pipx_hit_and_fallthrough():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "pipx-venvs"
        (base / "cow-say").mkdir(parents=True)
        old = intake._PIPX_BASES
        intake._PIPX_BASES = (str(base),)
        try:
            rec = intake._parse("pipx install Cow_Say")[0]
            assert intake._resolve_env(rec, "") == str(base / "cow-say")
            intake._PIPX_BASES = (str(Path(td) / "nope"),)
            # No pipx venv dir: unresolved even with a cwd venv present.
            proj = Path(td) / "proj"
            _mk_venv(proj, ".venv")
            assert intake._resolve_env(rec, str(proj)) == "unresolved"
        finally:
            intake._PIPX_BASES = old


def test_resolve_uv_tool_hit_and_fallthrough():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "uv-tools"
        (base / "ruff").mkdir(parents=True)
        old = intake._UV_TOOL_BASES
        intake._UV_TOOL_BASES = (str(base),)
        try:
            rec = intake._parse("uv tool install ruff")[0]
            assert intake._resolve_env(rec, "") == str(base / "ruff")
            intake._UV_TOOL_BASES = (str(Path(td) / "nope"),)
            assert intake._resolve_env(rec, "") == "unresolved"
        finally:
            intake._UV_TOOL_BASES = old


# --- read_intakes / sweep ----------------------------------------------------

def test_read_intakes_missing_and_tolerant():
    def body(t):
        assert intake.read_intakes() == []
        (t / "intakes.ndjson").write_text(
            json.dumps({"package": "x"}) + "\ngarbage{{{\n[1,2]\n")
        assert intake.read_intakes() == [{"package": "x"}]
    _with_tmp_store(body)


def test_sweep_end_to_end_record_shape():
    def body(t):
        proj = t / "proj"
        _mk_venv(proj, ".venv")
        _seed_session("s1", ["pip install Requests==2.31.0", "ls -la"],
                      cwd=str(proj))
        assert intake.sweep() == 1
        rows = intake.read_intakes()
        assert rows == [{"ts": 10.0, "ecosystem": "PyPI",
                         "package": "requests", "bulk": False,
                         "env_hint": str(proj / ".venv"),
                         "session_id": "s1", "harness": "claude-code",
                         "cwd": str(proj)}], rows
        raw = (t / "intakes.ndjson").read_text()
        assert "ghost" not in raw, "PostToolUse install leaked into intakes"
        mode = (t / "intakes.ndjson").stat().st_mode & 0o777
        assert mode == 0o600, oct(mode)
    _with_tmp_store(body)


def test_sweep_cursor_second_run_noop():
    def body(t):
        _seed_session("s1", ["pip install alpha"])
        assert intake.sweep() == 1
        before = (t / "intakes.ndjson").read_bytes()
        assert intake.sweep() == 0
        assert (t / "intakes.ndjson").read_bytes() == before
    _with_tmp_store(body)


def test_sweep_changed_session_replaces_rows():
    def body(t):
        _seed_session("s1", ["pip install alpha"])
        _seed_session("s2", ["pip install beta"])
        assert intake.sweep() == 2
        _seed_session("s1", ["pip install gamma", "pip install delta"])
        assert intake.sweep() == 1
        rows = intake.read_intakes()
        s1 = sorted(r["package"] for r in rows if r["session_id"] == "s1")
        s2 = [r["package"] for r in rows if r["session_id"] == "s2"]
        assert s1 == ["delta", "gamma"], rows
        assert s2 == ["beta"], rows
    _with_tmp_store(body)


def test_sweep_no_cwd_unresolved():
    def body(t):
        _seed_session("s1", ["pip install x"], cwd="")
        intake.sweep()
        rows = intake.read_intakes()
        assert rows[0]["env_hint"] == "unresolved" and rows[0]["cwd"] == ""
    _with_tmp_store(body)


def test_sweep_failsoft_bad_session():
    def body(t):
        (store.session_dir("bad") / "events.ndjson").mkdir()
        _seed_session("good", ["pip install ok-pkg"])
        n = intake.sweep()
        assert n == 2, n
        assert [r["package"] for r in intake.read_intakes()] == ["ok-pkg"]
        assert intake.sweep() == 0
    _with_tmp_store(body)


if __name__ == "__main__":
    from tests._seams import run
    sys.exit(run(globals()))
