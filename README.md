# llmsnitch

Local-only tracing and cost/health auditing for AI coding agents. One tool,
one name, zero network code, zero dependencies.

Own reimplementation of ideas from three MIT-licensed projects — none vendored,
none wrapped, no upstream to get abandoned or to flip telemetry on:

| Idea | Inspired by | What we kept | What we dropped |
|---|---|---|---|
| Hook-based tool-call capture | [Siddhant-K-code/agent-trace](https://github.com/Siddhant-K-code/agent-trace) | PreToolUse/PostToolUse/Stop → NDJSON | 60+ subcommands, server/SSO/RBAC, default-ON PostHog telemetry |
| Session health gate + exit codes | [luoyuctl/agenttrace](https://github.com/luoyuctl/agenttrace) | cost/fail-rate/health thresholds, edge-friendly `check` | Rust toolchain, inverted exit codes (2=breach) |
| Cost accounting | [tensorstax/agenttrace](https://github.com/tensorstax/agenttrace) | per-model token→dollar math | in-process SDK coupling |

## Design constraints (non-negotiable)

- **No network code.** No `urllib`, no `socket`, no exceptions — a test greps
  the package and fails the build if one appears. Telemetry isn't opt-out;
  it doesn't exist.
- **Stdlib only, Python 3.9+.** `dependencies = []` is a constraint, not a status.
- **Flat files.** NDJSON events + one meta.json per session under
  `~/.llmsnitch/sessions/` (override: `LLMSNITCH_DIR`). Files `0600`,
  dirs `0700`. No database, no daemon.
- **The hot path never blocks the agent.** The hook handler always exits 0,
  prints nothing, and swallows its own failures.
- **Secrets are redacted at capture time** (API keys, GitHub/Slack tokens,
  AWS key ids, JWTs) — what never lands on disk can't leak later.
- **Sane exit codes:** `check` returns 0 pass / 1 breach / 2 operational.

## Install

```bash
pip install .            # or: pip install --user .
llmsnitch setup      # prints the Claude Code hooks block
llmsnitch setup --write   # installs it (snapshots settings.json first)
```

`setup --write` refuses to run from inside a Claude Code session: the settings
file that wires the hooks is exactly the file a monitored agent must never
edit about itself.

## Use

```bash
llmsnitch list             # sessions: tools, errors, health, cost
llmsnitch show <id>        # one session in detail
llmsnitch check            # gate: exit 0 pass / 1 breach / 2 error
```

Thresholds in `~/.config/llmsnitch/config`:

```ini
[gate]
cost_ceiling = 5.00        # dollars per session (transcript estimate)
max_tool_fail_rate = 15    # percent
health_floor = 70          # health = max(0, 100 - 3*errors - fail_rate)
range = latest             # latest | today | all
billing_mode = subscription  # subscription | per_token
```

Cost comes from the Claude Code transcript's own `usage` records, priced by
the table in `transcript.py` — an offline estimate you can edit, not a
metered bill.

**`billing_mode`** — most users are on Claude Max/Pro and don't pay per token.
In `subscription` mode (default) the cost figure is labeled as an estimate
(`~$X`) and the cost gate is disabled — errors and health still gate. Switch
to `per_token` for pass-through billing, and the cost ceiling enforces.
Anthropic hasn't published Fable pricing; unknown models fall to sonnet-tier
with a note rather than an invented rate.

## Test

```bash
python3 tests/test_llmsnitch.py
```

## License

MIT. The three projects above are acknowledged as prior art; no code was
copied from any of them.
