"""Cost / fail-rate / health gate over recorded sessions.

Exit codes (NOT inverted like some upstreams):
  0 = pass, 1 = breach, 2 = operational error (nothing to check / bad config).

Health is a transparent heuristic, not a black box:
  health = max(0, 100 - 3*errors - fail_rate)
where fail_rate = errors / tool_calls * 100. A session with no tool calls
scores 100 (nothing failed).
"""

import configparser
import os
from datetime import datetime

from . import store

EXIT_PASS, EXIT_BREACH, EXIT_OPERATIONAL = 0, 1, 2

DEFAULTS = {
    "cost_ceiling": 5.0,         # dollars per session (transcript estimate)
    "max_tool_fail_rate": 15.0,  # percent
    "health_floor": 70,          # 0-100
    "range": "latest",           # latest | today | all
}

CONFIG_PATH = "~/.config/llmsnitch/config"
_CASTERS = {"cost_ceiling": float, "max_tool_fail_rate": float, "health_floor": int}


def load_cfg():
    """[gate] section with per-key fallback: one malformed value never
    resets its siblings."""
    cfg = dict(DEFAULTS)
    path = os.path.expanduser(CONFIG_PATH)
    if not os.path.exists(path):
        return cfg
    cp = configparser.ConfigParser(inline_comment_prefixes=("#",))
    try:
        cp.read(path)
    except configparser.Error:
        return cfg
    if cp.has_section("gate"):
        s = cp["gate"]
        for key in DEFAULTS:
            raw = s.get(key)
            if raw is None or not raw.strip():
                continue
            caster = _CASTERS.get(key)
            try:
                cfg[key] = caster(raw) if caster else raw.strip()
            except (ValueError, TypeError):
                pass
    return cfg


def health(tool_calls, errors):
    rate = errors * 100.0 / tool_calls if tool_calls else 0.0
    return max(0, round(100 - 3 * errors - rate))


def _in_range(summaries, rng):
    if rng == "all":
        return summaries
    if rng == "today":
        midnight = datetime.now().replace(hour=0, minute=0, second=0,
                                          microsecond=0).timestamp()
        return [s for s in summaries if (s["started_at"] or 0) >= midnight]
    return summaries[:1]   # latest


def evaluate(cfg, summaries):
    """(verdict, findings). Pure — no I/O, fully testable."""
    findings = []
    for s in summaries:
        reasons = []
        rate = round(s["errors"] * 100.0 / s["tool_calls"], 1) if s["tool_calls"] else 0.0
        h = health(s["tool_calls"], s["errors"])
        cost = s.get("cost_usd")
        if cost is not None and cost > cfg["cost_ceiling"]:
            reasons.append(f"cost ${cost:.2f} > ${cfg['cost_ceiling']:.2f}")
        if rate > cfg["max_tool_fail_rate"]:
            reasons.append(f"tool-fail {rate}% > {cfg['max_tool_fail_rate']}%")
        if h < cfg["health_floor"]:
            reasons.append(f"health {h} < {cfg['health_floor']}")
        if reasons:
            findings.append({"session_id": s["session_id"], "reasons": reasons,
                             "tool_calls": s["tool_calls"], "errors": s["errors"],
                             "health": h})
    return ("breach" if findings else "pass"), findings


def cmd_check(cfg, out):
    ids = [sid for sid, _ in store.list_sessions()]
    if not ids:
        out.write("[ERROR] no recorded sessions — run `llmsnitch setup` first\n")
        return EXIT_OPERATIONAL
    summaries = [store.summarize(sid) for sid in ids]
    summaries = _in_range(summaries, cfg["range"])
    if not summaries:
        out.write(f"[ERROR] no sessions in range={cfg['range']}\n")
        return EXIT_OPERATIONAL

    verdict, findings = evaluate(cfg, summaries)
    if verdict == "pass":
        out.write(f"[OK] {len(summaries)} session(s) under thresholds "
                  f"(range={cfg['range']})\n")
        return EXIT_PASS
    for f in findings:
        out.write(f"[CRITICAL] session {f['session_id'][:12]}: "
                  f"{', '.join(f['reasons'])} "
                  f"(tools {f['tool_calls']}, errors {f['errors']}, "
                  f"health {f['health']})\n")
    return EXIT_BREACH
