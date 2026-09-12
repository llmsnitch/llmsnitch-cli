"""Intake extraction (T504): mine stored session NDJSON for Python-package
install evidence, materialized to <base>/intakes.ndjson behind an mtime/size
cursor (<base>/intake-state.json, ingest-state pattern).

An intake is the *claim* ("agent ran an install at time T") — the scan-time
dist-info join is the success oracle. Bulk intakes (-r/-e/uv sync/path/VCS
specs) attribute the whole env. env_hint resolves: explicit path in the
command → pipx/uv-tool dirs → venv discovered under session cwd →
"unresolved", which matches no env at scan time (quiet, never a global guess).
"""

import glob
import json
import os
import re

from . import store
from .bulletin import normalize_name
from .hook import _MAX_STR

# Stored commands cap at hook._MAX_STR; at that length the tail is
# untrustworthy (truncated mid-command).
_TRUNC_LIMIT = _MAX_STR

_VALUE_FLAGS = {"-r", "--requirement", "-c", "--constraint", "-t", "--target",
                "--prefix", "--python", "-p", "-i", "--index-url",
                "--extra-index-url", "-f", "--find-links"}
_BULK_FLAGS = {"-r", "--requirement", "-e", "--editable"}

# Tool-install env locations (chain 2). Module-level so tests can repoint.
_PIPX_BASES = ("~/.local/pipx/venvs",
               "~/Library/Application Support/pipx/venvs")
_UV_TOOL_BASES = ("~/.local/share/uv/tools",)


def _strip_spec(tok):
    tok = re.split(r"===|==|>=|<=|~=|!=|<|>", tok, 1)[0]
    return tok.split("[", 1)[0]


def _is_path_spec(tok):
    return (tok.startswith((".", "/")) or tok.startswith("git+")
            or "://" in tok or tok.endswith((".whl", ".tar.gz", ".zip")))


def _head_env(head):
    """…/bin/<tool> head token: the env is the grandparent dir."""
    if os.path.basename(os.path.dirname(head)) == "bin":
        return os.path.dirname(os.path.dirname(head))
    return None


def _segment_install(toks):
    """(kind, args, env_path) when the segment is an install, else None."""
    if not toks:
        return None
    bn = os.path.basename(toks[0])
    if bn in ("pip", "pip3") and toks[1:2] == ["install"]:
        return "pip", toks[2:], _head_env(toks[0])
    if ((bn == "python" or bn.startswith("python3"))
            and toks[1:4] == ["-m", "pip", "install"]):
        return "pip", toks[4:], _head_env(toks[0])
    if bn == "uv":
        if toks[1:2] == ["add"]:
            return "uv", toks[2:], None
        if toks[1:3] == ["pip", "install"]:
            return "uv", toks[3:], None
        if toks[1:2] == ["sync"]:
            return "uv-sync", toks[2:], None
        if toks[1:3] == ["tool", "install"]:
            return "uv-tool", toks[3:], None
    if bn == "pipx" and toks[1:2] == ["install"]:
        return "pipx", toks[2:], None
    return None


def _parse(command):
    """Public record shape plus 'python_arg': a raw --python/-p value whose
    env needs a pyvenv.cfg check at resolution time (parse itself does no I/O)."""
    if not isinstance(command, str):
        return []
    truncated = len(command) >= _TRUNC_LIMIT
    segments = re.split(r"&&|;|\|", command)
    out = []
    for idx, seg in enumerate(segments):
        hit = _segment_install(seg.split())
        if not hit:
            continue
        kind, args, env = hit
        bulk = kind == "uv-sync"
        if bulk:
            kind = "uv"
        pkgs, python_arg = [], None
        i = 0
        while i < len(args):
            tok = args[i].strip("\"'")
            i += 1
            if tok.startswith("-"):
                if tok in _BULK_FLAGS:
                    bulk = True
                if tok in _VALUE_FLAGS:
                    if tok in ("--python", "-p") and i < len(args):
                        python_arg = args[i].strip("\"'")
                    i += 1
                continue
            if _is_path_spec(tok):
                bulk = True
            else:
                name = _strip_spec(tok)
                if name:
                    pkgs.append(normalize_name(name))
        if truncated and idx == len(segments) - 1:
            bulk, pkgs = True, []   # untrustworthy tail: degrade to bulk
        if python_arg and env is None:
            bn = os.path.basename(python_arg)
            if bn.startswith("python") and \
                    os.path.basename(os.path.dirname(python_arg)) == "bin":
                env, python_arg = _head_env(python_arg), None
        base = {"bulk": bulk, "env_path": env, "kind": kind,
                "python_arg": python_arg}
        if bulk:
            out.append(dict(base, package=None))
        else:
            for p in pkgs:
                out.append(dict(base, package=p))
    return out


def parse_install_command(command):
    """Pure install-command grammar, no I/O. Segments split naively on
    && ; | — a quoted 'pip install x' inside another command is not a hit."""
    return [{"package": r["package"], "bulk": r["bulk"],
             "env_path": r["env_path"], "kind": r["kind"]}
            for r in _parse(command)]


def _absolutize(p, cwd):
    p = os.path.expanduser(p)
    if not os.path.isabs(p) and cwd:
        p = os.path.normpath(os.path.join(cwd, p))
    return p


def _cwd_venv(cwd):
    """Chain 3: dirs directly under cwd with a pyvenv.cfg marker — wider than
    .venv (.venv-dashboard is real); uv.lock does NOT imply an env."""
    cands = []
    for pat in ("*/pyvenv.cfg", ".*/pyvenv.cfg"):
        cands += [os.path.dirname(c) for c in
                  glob.glob(os.path.join(glob.escape(cwd), pat))]
    preferred = os.path.join(cwd, ".venv")
    if preferred in cands:
        return preferred
    if len(cands) == 1:
        return cands[0]
    return None


def _tool_env(bases, name):
    for b in bases:
        cand = os.path.join(os.path.expanduser(b), name)
        if os.path.isdir(cand):
            return cand
    return None


def _resolve_env(rec, cwd):
    if rec.get("env_path"):
        return _absolutize(rec["env_path"], cwd)
    pa = rec.get("python_arg")
    if pa:
        pa = _absolutize(pa, cwd)
        if os.path.exists(os.path.join(pa, "pyvenv.cfg")):
            return pa
    kind, name = rec["kind"], rec.get("package")
    if kind == "pipx":
        return (name and _tool_env(_PIPX_BASES, name)) or "unresolved"
    if kind == "uv-tool":
        return (name and _tool_env(_UV_TOOL_BASES, name)) or "unresolved"
    if cwd:
        hit = _cwd_venv(cwd)
        if hit:
            return hit
    return "unresolved"


def _state_path():
    return store.base_dir() / "intake-state.json"


def _load_state():
    try:
        s = json.loads(_state_path().read_text())
        return s if isinstance(s, dict) else {}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _save_state(state):
    store._mkdir_private(store.base_dir())
    p = _state_path()
    p.write_text(json.dumps(state, separators=(",", ":")))
    store._chmod_private(p)


def _intakes_path():
    return store.base_dir() / "intakes.ndjson"


def read_intakes():
    """Tolerant NDJSON read of <base>/intakes.ndjson; [] if missing."""
    try:
        lines = _intakes_path().read_text().splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _extract_session(sid):
    meta = store.read_meta(sid)
    cwd = meta.get("cwd", "") or ""
    harness = meta.get("harness", "claude-code")
    rows = []
    for ev in store.iter_events(sid):
        if ev.get("event") != "PreToolUse" or ev.get("tool") != "Bash":
            continue
        inp = ev.get("input")
        cmd = inp.get("command") if isinstance(inp, dict) else None
        if not isinstance(cmd, str):
            continue
        ts = ev.get("ts")
        ts = float(ts) if isinstance(ts, (int, float)) else 0.0
        for rec in _parse(cmd):
            rows.append({"ts": ts, "ecosystem": "PyPI",
                         "package": rec["package"], "bulk": rec["bulk"],
                         "env_hint": _resolve_env(rec, cwd),
                         "session_id": sid, "harness": harness, "cwd": cwd})
    return rows


def sweep():
    """(Re)extract intakes from new/changed session files; a changed session's
    previous rows are replaced (idempotent). Returns count of sessions
    (re)extracted. First run is the retroactive sweep — all history. Fail-soft:
    one bad file never kills the sweep."""
    state = _load_state()
    updated, fresh = 0, {}
    for d in sorted(store.sessions_root().iterdir()):
        if not d.is_dir():
            continue
        path = d / "events.ndjson"
        try:
            st = os.stat(path)
            cur = state.get(str(path))
            if cur and cur.get("mtime") == st.st_mtime \
                    and cur.get("size") == st.st_size:
                continue
            fresh[d.name] = _extract_session(d.name)
            state[str(path)] = {"mtime": st.st_mtime, "size": st.st_size}
            updated += 1
        except Exception:  # noqa: BLE001 — one bad file never kills the sweep
            continue
    if fresh:
        kept = [r for r in read_intakes() if r.get("session_id") not in fresh]
        p = _intakes_path()
        store._mkdir_private(store.base_dir())
        with open(p, "w") as f:
            for r in kept + [r for rows in fresh.values() for r in rows]:
                f.write(json.dumps(r, separators=(",", ":")) + "\n")
        store._chmod_private(p)
    _save_state(state)
    return updated
