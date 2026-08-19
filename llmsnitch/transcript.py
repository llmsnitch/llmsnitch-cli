"""Token usage + cost from a Claude Code transcript (JSONL).

The transcript path arrives in every hook payload; assistant messages carry
`message.usage` and `message.model`. Cost is an OFFLINE estimate from the
pricing table below — edit it when prices change, or override per-call.
No network, ever.
"""

import json

# $ per million tokens: (input, output). Cache read bills at 10% of input,
# cache creation at 125% of input (Anthropic's published ratios).
# Matched by substring of the model id, first hit wins.
PRICING = [
    ("opus", 15.0, 75.0),
    ("sonnet", 3.0, 15.0),
    ("haiku", 0.80, 4.0),
]
# Fable, and any future model, has no entry until Anthropic publishes rates —
# fall to _DEFAULT (sonnet-tier) with an "unknown model" note. Cheaper to
# under-report than to invent a price.
_DEFAULT = (3.0, 15.0)  # unknown model -> sonnet-tier estimate, flagged in output


def _prices(model):
    m = (model or "").lower()
    for key, inp, out in PRICING:
        if key in m:
            return inp, out, False
    return _DEFAULT[0], _DEFAULT[1], True


def usage_from_transcript(path):
    """{model: {input, output, cache_read, cache_create}} summed over the
    transcript. Tolerates unreadable files and bad lines (returns {})."""
    totals = {}
    try:
        with open(path) as f:
            lines = f.readlines()
    except OSError:
        return totals
    for line in lines:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = obj.get("message") if isinstance(obj, dict) else None
        if not isinstance(msg, dict):
            continue
        u = msg.get("usage")
        if not isinstance(u, dict):
            continue
        model = msg.get("model") or "unknown"
        t = totals.setdefault(model, {"input": 0, "output": 0,
                                      "cache_read": 0, "cache_create": 0})
        t["input"] += int(u.get("input_tokens") or 0)
        t["output"] += int(u.get("output_tokens") or 0)
        t["cache_read"] += int(u.get("cache_read_input_tokens") or 0)
        t["cache_create"] += int(u.get("cache_creation_input_tokens") or 0)
    return totals


def estimate_cost(totals):
    """(cost_usd, total_tokens, any_unknown_model) from usage totals."""
    cost = 0.0
    tokens = 0
    unknown = False
    for model, t in totals.items():
        inp, out, was_default = _prices(model)
        unknown = unknown or was_default
        cost += (t["input"] * inp
                 + t["output"] * out
                 + t["cache_read"] * inp * 0.10
                 + t["cache_create"] * inp * 1.25) / 1_000_000
        tokens += t["input"] + t["output"] + t["cache_read"] + t["cache_create"]
    return round(cost, 4), tokens, unknown
