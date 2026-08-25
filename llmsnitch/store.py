"""Flat-file session store: <base>/sessions/<session-id>/{events.ndjson,meta.json}.

NDJSON, append-only, no database, no daemon. Files 0600 in dirs 0700.
The last line of an in-progress session may be truncated — every reader
tolerates a bad tail (skip, never crash).
"""

import json
import os
import time
from pathlib import Path


def base_dir():
    return Path(os.environ.get("LLMSNITCH_DIR", "~/.llmsnitch")).expanduser()


def _mkdir_private(d):
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    return d


def sessions_root():
    return _mkdir_private(base_dir() / "sessions")


def session_dir(session_id):
    return _mkdir_private(sessions_root() / str(session_id))


def _chmod_private(path):
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def append_event(session_id, event):
    p = session_dir(session_id) / "events.ndjson"
    with open(p, "a") as f:
        f.write(json.dumps(event, separators=(",", ":")) + "\n")
    _chmod_private(p)


def write_meta(session_id, meta):
    p = session_dir(session_id) / "meta.json"
    p.write_text(json.dumps(meta, indent=2))
    _chmod_private(p)


def read_meta(session_id):
    p = sessions_root() / str(session_id) / "meta.json"
    try:
        m = json.loads(p.read_text())
        return m if isinstance(m, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def iter_events(session_id):
    p = sessions_root() / str(session_id) / "events.ndjson"
    try:
        lines = p.read_text().splitlines()
    except OSError:
        return
    for line in lines:
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue  # truncated in-progress tail
        if isinstance(ev, dict):
            yield ev


def list_sessions():
    """[(session_id, mtime)] newest first."""
    root = sessions_root()
    out = []
    for d in root.iterdir():
        if d.is_dir():
            out.append((d.name, d.stat().st_mtime))
    out.sort(key=lambda t: t[1], reverse=True)
    return out


def summarize(session_id):
    """Aggregate counters from events + whatever meta recorded. Cheap enough
    to recompute on read — no counter caching to drift."""
    first_ts = last_ts = None
    tool_calls = errors = 0
    tools = {}
    for ev in iter_events(session_id):
        ts = ev.get("ts") or 0
        first_ts = ts if first_ts is None else min(first_ts, ts)
        last_ts = ts if last_ts is None else max(last_ts, ts)
        if ev.get("event") == "PostToolUse":
            tool_calls += 1
            name = ev.get("tool") or "?"
            tools[name] = tools.get(name, 0) + 1
            if ev.get("error"):
                errors += 1
    meta = read_meta(session_id)
    if "error_count" in meta:   # ledger sessions: errors come from meta (C4)
        errors = meta["error_count"]
    return {
        "session_id": session_id,
        "harness": meta.get("harness", "claude-code"),
        "signals_partial": meta.get("signals_partial"),
        "started_at": meta.get("started_at") or first_ts,
        "ended_at": meta.get("ended_at") or last_ts,
        "duration_s": round((last_ts - first_ts), 1) if first_ts and last_ts else 0,
        "tool_calls": tool_calls,
        "errors": errors,
        "tools": tools,
        "cost_usd": meta.get("cost_usd"),
        "total_tokens": meta.get("total_tokens"),
        "cwd": meta.get("cwd", ""),
        "ended": bool(meta.get("ended_at")),
    }


def now():
    return time.time()
