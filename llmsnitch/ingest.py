"""Ledger ingest sweep (contract C8): lazy + explicit, incremental, no daemon.

Cursors live in <base>/ingest-state.json: path -> {mtime, size}. A changed
file is re-parsed whole and its store entry rewritten in place (idempotent,
keyed by the namespaced session id) — correctness over byte-offset cleverness
while parsers need whole-file context (first session_meta, running model).
Corrupt/missing state means a full re-sweep, never a crash.
"""

import glob
import json
import os

from . import harness, store
from .hook import _clean


def _state_path():
    return store.base_dir() / "ingest-state.json"


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


def _session_files(entry):
    env = entry.get("home_env")
    home = os.environ.get(env) if env else None
    for pat in entry.get("session_paths", ()):
        if home:
            pat = pat.replace(entry["home_default"], home, 1)
        yield from glob.glob(os.path.expanduser(pat))


def _write_session(name, path, parsed):
    sid = f"{name}-{parsed.get('native_id') or os.path.basename(path).rsplit('.', 1)[0]}"
    src = harness.src_info(path)
    sdir = store.session_dir(sid)
    ev_path = sdir / "events.ndjson"
    rows = [{"ts": parsed.get("started_at"), "event": "session_start"}]
    rows += parsed["events"]
    rows.append({"ts": parsed.get("ended_at"), "event": "session_end"})
    with open(ev_path, "w") as f:
        for r in rows:
            r.update({"harness": name, "src": src["path"], "src_sha256": src["sha256"]})
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    store._chmod_private(ev_path)
    models = parsed["models"]
    store.write_meta(sid, {
        "v": 1, "session_id": sid, "harness": name,
        "native_id": parsed.get("native_id"),
        "cwd": _clean(str(parsed.get("cwd") or "")),
        "provider": _clean(str(parsed.get("provider") or "")),
        "models": sorted(models),
        "tokens_by_model": models,
        "total_tokens": sum(m.get("total_tokens", 0) for m in models.values()),
        "started_at": parsed.get("started_at"),
        "ended_at": parsed.get("ended_at"),
        "error_count": parsed.get("error_count", 0),
        "signals_partial": parsed.get("signals_partial"),
        "cost_usd": None,
        "cost_note": "unpriced: no vendor-cited rates for this provider yet",
        "src": src,
    })


def sweep():
    """Ingest new/changed ledger files. Returns count updated. Fail-soft."""
    state = _load_state()
    updated = 0
    for name, entry in harness.HARNESSES.items():
        parser = entry.get("parser")
        if not parser:
            continue
        for path in _session_files(entry):
            try:
                st = os.stat(path)
                cur = state.get(path)
                if cur and cur.get("mtime") == st.st_mtime and cur.get("size") == st.st_size:
                    continue
                parsed = parser(path)
                if parsed:
                    _write_session(name, path, parsed)
                    updated += 1
                state[path] = {"mtime": st.st_mtime, "size": st.st_size}
            except Exception:  # noqa: BLE001 — one bad file never kills the sweep
                continue
    _save_state(state)
    return updated
