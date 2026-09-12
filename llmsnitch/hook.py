"""Claude Code hook handler — the HOT PATH. Fires on every tool call.

Contract: read the hook payload from stdin, append one NDJSON event, exit 0.
ALWAYS exit 0 and print nothing — a tracing tool must never block or slow the
agent it observes. Any failure here is swallowed by design.

Secrets are redacted BEFORE anything touches disk.
"""

import json
import re
import sys
import unicodedata

from . import store, transcript

# Common credential shapes. Redaction happens at capture time — a secret that
# never lands on disk can't leak later. Patterns are chosen for high
# specificity: a false negative (missed secret) is worse than a false
# positive (redacted innocuous string), so shapes with too-generic
# alphabets (e.g. bare 52-char base32, indistinguishable from hex hashes)
# are intentionally not included until a safer heuristic exists.
_SECRET = re.compile(
    r"(sk-[A-Za-z0-9_-]{8,}"                    # OpenAI / Anthropic (sk-, sk-ant-*)
    r"|gh[pousr]_[A-Za-z0-9]{10,}"              # GitHub tokens
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"            # Slack tokens
    r"|AKIA[0-9A-Z]{16}"                        # AWS access key ids
    r"|eyJ[A-Za-z0-9_-]{40,}"                   # JWTs
    r"|Bearer\s+[A-Za-z0-9._~+/=-]{20,}"        # HTTP Authorization: Bearer
    r"|-----BEGIN[ A-Z]*PRIVATE KEY-----"       # PEM/OpenSSH private key headers
    r")"
)

_MAX_STR = 2000   # per-string cap: traces are for auditing, not archiving blobs

# UTR #36 / UAX #9 invisible + bidi + variation-selector + Tag codepoints.
# Matches Ramparts src/normalize.rs::is_invisible — see
# docs/research/unicode-evasion-redaction.md for the derivation, benchmarks,
# and the honest-limits list (Cyrillic homoglyphs, base64 wrapping, and
# soft-hyphen splits are documented non-goals).
_INV_RE = re.compile(
    "["
    "\u200b-\u200f"          # ZWSP, ZWNJ, ZWJ, LRM, RLM
    "\u2060-\u2064"          # word joiner, invisible operators
    "\u202a-\u202e"          # LRE/RLE/PDF/LRO/RLO (Trojan Source)
    "\u2066-\u2069"          # LRI/RLI/FSI/PDI
    "\ufeff"                  # BOM / zero-width no-break space
    "\ufe00-\ufe0f"          # variation selectors
    "\U000e0000-\U000e007f"  # Unicode Tags block
    "]"
)


def _canonical(s):
    """Fold Unicode evasion into scannable form: strip invisibles, NFKC.

    Cost tiers, measured on 2 KB strings (this machine, CPython 3):
    pure ASCII exits on one C-level `isascii()` call (~0.07 µs — the
    overwhelmingly common case, and the one the hot-path budget is about);
    benign non-ASCII pays a regex search miss + NFKC (~24 µs — rare in
    agent traffic); strings actually carrying an invisible codepoint, i.e.
    attack-shaped input, pay search + strip + fold (~56 µs). Keep it
    tiered: a per-char Python loop costs ~280 µs and must not come back.
    """
    if s.isascii():
        return s
    if _INV_RE.search(s):
        s = _INV_RE.sub("", s)
    return unicodedata.normalize("NFKC", s)


def _clean(obj, depth=0):
    if depth > 6:
        return "<deep>"
    if isinstance(obj, str):
        # 256-char margin past the cap: redact first, cut second, so a
        # secret straddling the cut is matched before the truncation
        # strands an unmatchable fragment. 256 covers every _SECRET shape.
        s = obj[:_MAX_STR + 256]
        canon = _canonical(s)
        if canon != s:
            red_c = _SECRET.sub("<redacted>", canon)
            if red_c != canon:
                # A secret only visible after folding (zero-width split,
                # fullwidth homoglyph, bidi override). Store the redacted
                # canonical view — losing the original bytes is the right
                # trade for a secret; benign non-ASCII takes the raw path.
                return red_c[:_MAX_STR]
        return _SECRET.sub("<redacted>", s)[:_MAX_STR]
    if isinstance(obj, dict):
        return {_clean(str(k)[:100], depth + 1): _clean(v, depth + 1)
                for k, v in list(obj.items())[:50]}
    if isinstance(obj, list):
        return [_clean(v, depth + 1) for v in obj[:50]]
    return obj


def _is_error(resp):
    """Documented heuristic: an explicit error marker in the tool response."""
    if not isinstance(resp, dict):
        return False
    return bool(resp.get("is_error") or resp.get("isError") or resp.get("error"))


def handle(event_name, stdin=None):
    """Process one hook invocation. Returns 0 unconditionally."""
    try:
        payload = json.load(stdin or sys.stdin)
        if not isinstance(payload, dict):
            return 0
    except (json.JSONDecodeError, OSError, ValueError):
        return 0

    try:
        sid = str(payload.get("session_id") or "unknown")
        ev = {"ts": store.now(), "event": event_name}
        tool = payload.get("tool_name")
        if tool:
            ev["tool"] = str(tool)[:100]

        if event_name == "PreToolUse":
            ev["input"] = _clean(payload.get("tool_input"))
        elif event_name == "PostToolUse":
            resp = payload.get("tool_response")
            err = _is_error(resp)
            ev["error"] = err
            if err:  # keep an excerpt only on failure — successes stay lean
                ev["error_excerpt"] = _clean(json.dumps(resp)[:656])[:400] if resp else ""
        elif event_name == "Stop":
            _finalize(sid, payload)

        store.append_event(sid, ev)
    except Exception:   # noqa: BLE001 — hot path must never propagate
        pass
    return 0


def _finalize(sid, payload):
    """On Stop: fold transcript usage/cost into meta.json."""
    meta = store.read_meta(sid)
    meta["session_id"] = sid
    meta.setdefault("started_at", _first_ts(sid) or store.now())
    meta["ended_at"] = store.now()
    meta["cwd"] = _clean(str(payload.get("cwd") or ""))
    tp = payload.get("transcript_path")
    if tp:
        totals = transcript.usage_from_transcript(tp)
        if totals:
            cost, tokens, unknown = transcript.estimate_cost(totals)
            meta["cost_usd"] = cost
            meta["total_tokens"] = tokens
            meta["models"] = sorted(totals)
            if unknown:
                meta["cost_note"] = "unknown model priced at sonnet tier"
    store.write_meta(sid, meta)


def _first_ts(sid):
    for ev in store.iter_events(sid):
        return ev.get("ts")
    return None
