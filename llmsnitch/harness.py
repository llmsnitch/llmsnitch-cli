"""Harness registry + ledger parsers (contract: docs/harness-adapter-contract.md).

An adapter is a declarative entry plus an optional parser (code hook).
Parsers read ONLY usage/lifecycle/error fields from a harness's own session
files — message/tool bodies are skipped unread (contract C6). Facts come
from dossiers/<name>.md; do not invent fields the dossier doesn't cite.
"""

import hashlib
import json
from datetime import datetime, timezone

from .hook import _clean

# Token fields tracked from codex's CUMULATIVE total_token_usage (dossier
# trap 1, verifier-corrected: codex restates token_count rows, so summing
# last_token_usage double-counts — 15/84 real sessions wrong, up to +73%.
# Cumulative deltas are oracle-exact 84/84 against state_5.sqlite and
# attribute spend to the model current at each row).
_CODEX_TOKEN_FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens",
                       "reasoning_output_tokens", "total_tokens")


def _zeros():
    return dict.fromkeys(_CODEX_TOKEN_FIELDS, 0)


def _iso_epoch(s):
    if not isinstance(s, str):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _codex_error(pt, p):
    """Dossier §3: only three markers exist, and the signal is partial."""
    if pt == "patch_apply_end":
        return p.get("success") is False
    if pt == "mcp_tool_call_end":
        r = p.get("result")
        if isinstance(r, dict):
            ok = r.get("Ok")
            return "Err" in r or (isinstance(ok, dict) and bool(ok.get("isError")))
    if pt == "exec_command_end":                # pre-0.140 files only
        return p.get("status") == "failed"
    return False


def parse_codex(path):
    """One rollout file -> normalized session dict, or None if empty/alien."""
    native_id = cwd = provider = None
    model = None
    models = {}
    prev = {}                                   # last-seen cumulative per field
    events = []
    errors = 0
    first = last = None
    with open(path, errors="replace") as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue                        # fail-soft: truncated tail etc.
            if not isinstance(row, dict):
                continue
            ts = _iso_epoch(row.get("timestamp"))
            if ts is not None:
                first = ts if first is None else min(first, ts)
                last = ts if last is None else max(last, ts)
            p = row.get("payload")
            if not isinstance(p, dict):
                continue
            t, pt = row.get("type"), p.get("type")
            if t == "session_meta" and native_id is None:
                # trap 3: the first session_meta is this session; later ones
                # can carry the parent's id.
                native_id = p.get("id")
                cwd = p.get("cwd")
                provider = p.get("model_provider")
            elif t == "turn_context":
                if p.get("model"):
                    model = _clean(str(p["model"]))[:200]   # harness-controlled string
                    # verifier defect 2b: a declared model must survive even
                    # with no attributed spend (e.g. a superseded azureml://
                    # turn — trap 7's detection signal).
                    models.setdefault(model, _zeros())
                cwd = cwd or p.get("cwd")
            elif pt == "token_count":
                info = p.get("info")
                tot = info.get("total_token_usage") if isinstance(info, dict) else None
                if isinstance(tot, dict):
                    m = models.setdefault(str(model or "unknown"), _zeros())
                    delta_total = 0
                    for k in _CODEX_TOKEN_FIELDS:
                        v = tot.get(k)
                        if not isinstance(v, (int, float)):
                            continue
                        d = v - prev.get(k, 0)
                        prev[k] = v
                        if d > 0:               # restated row -> zero delta
                            m[k] += d
                            if k == "total_tokens":
                                delta_total = d
                    if delta_total:
                        events.append({"ts": ts, "event": "usage",
                                       "model": str(model or "unknown"),
                                       "tokens": delta_total})
            elif _codex_error(pt, p):
                errors += 1
                events.append({"ts": ts, "event": "harness_error", "kind": str(pt)})
            # trap 13: turn_aborted/interrupted is NOT an error.
            # trap 12: everything else (messages, tool outputs) skipped unread.
    if native_id is None and not models:
        return None
    return {"native_id": native_id, "cwd": cwd, "provider": provider,
            "models": models, "events": events, "error_count": errors,
            "started_at": first, "ended_at": last,
            "signals_partial": ("codex records tool errors only for MCP calls "
                                "and patch-apply; shell tool results carry no "
                                "error flag")}


def src_info(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return {"path": _clean(str(path)), "sha256": h.hexdigest()}


HARNESSES = {
    # dossiers/claude-code.md §8 — live capture ships today; ledger parser
    # for its transcripts is a future team run (contract C2 diff-check).
    "claude-code": {
        "session_paths": ["~/.claude/projects/*/*.jsonl"],
        "session_format": "jsonl",
        "config_paths": ["~/.claude/settings.json", "~/.claude.json"],
        "registry": {
            "paths": ["~/.claude"],
            "exes": ["claude"],
            "signing_ids": ["com.anthropic.claude-code"],  # observed 2026-08-24, team Q6L2SF6YDW
            "cache_paths": ["~/.claude/plugins/cache"],
        },
        "parser": None,
        "tier": "live+ledger",
        "provider_families": {"": "anthropic"},
    },
    # dossiers/codex.md §8
    "codex": {
        "session_paths": ["~/.codex/sessions/*/*/*/rollout-*.jsonl"],
        "home_env": "CODEX_HOME",               # trap 9: relocates ~/.codex
        "home_default": "~/.codex",
        "session_format": "jsonl",
        "config_paths": ["~/.codex/config.toml", "~/.codex/hooks.json",
                         "/etc/codex/config.toml"],
        "registry": {
            "paths": ["~/.codex"],
            "exes": ["codex"],
            "signing_ids": ["codex"],           # observed 2026-08-25, team 2DC432GLL2
            "cache_paths": ["~/.codex/cache", "~/.codex/.tmp", "~/.codex/tmp",
                            "~/.codex/log", "~/.codex/shell_snapshots",
                            "~/.codex/thread-writer-locks",
                            "~/.codex/models_cache.json",
                            "~/.codex/cloud-config-bundle-cache.json"],
        },
        "parser": parse_codex,
        "tier": "ledger",
        "provider_families": {"gpt-": "openai", "o1": "openai", "o3": "openai",
                              "o4": "openai", "codex-": "openai",
                              "azureml://": "openai", "": "openai"},
    },
}
