# llmsnitch

See what your AI coding agent actually did. llmsnitch records every tool
call your agent makes — what ran, what failed, what it cost — into plain
local files you own. Nothing to sign into, nothing leaves your machine.

- **Zero network code.** No telemetry, no phone-home — a test greps the
  package and fails the build if a network import ever appears.
- **Secrets never reach disk.** API keys, tokens, and JWTs are redacted at
  capture time.
- **Plain files.** NDJSON under `~/.llmsnitch/`, readable with the CLI or
  any text tool. No database, no daemon.
- **Zero dependencies.** Stdlib-only Python 3.9+.

## Install

From a clone of this repo:

```bash
# with uv
uv tool install .

# or with pip in a virtualenv
python3 -m venv .venv && source .venv/bin/activate
pip install .
```

## Set up

```bash
llmsnitch setup          # preview the Claude Code hooks block
llmsnitch setup --write  # install it (snapshots settings.json first)
```

Run `setup --write` from a plain terminal, not from inside a Claude Code
session. Start a new agent session and it's recording.

## Use

```bash
llmsnitch list             # sessions: tools, errors, health, cost
llmsnitch show <id>        # one session in detail
llmsnitch check            # gate: exit 0 pass / 1 breach / 2 error
llmsnitch scan             # audit agent configs for risky artifacts
llmsnitch ingest           # pull in non-Claude harnesses (codex, ...)
llmsnitch patrol           # print/--write the daily-scan LaunchAgent
```

A companion CLI, `fs-coil`, reads the notification ledger:

```bash
fs-coil digest --show      # print today's digest
fs-coil noise              # recall notifications, grouped
fs-coil status             # watcher health
```

The daily digest lands in `~/Library/Logs/llmsnitch/notify/`.

## Configure

Thresholds live in `~/.config/llmsnitch/config`:

```ini
[gate]
cost_ceiling = 5.00        # dollars per session (transcript estimate)
max_tool_fail_rate = 15    # percent
health_floor = 70          # health = max(0, 100 - 3*errors - fail_rate)
range = latest             # latest | today | all
billing_mode = subscription  # subscription | per_token

[scan]
discover_roots = ~:~/Library/Application Support  # colon-separated roots the scan probes for agent homes
```

On Claude Max/Pro you don't pay per token, so in `subscription` mode
(the default) cost is shown as an estimate (`~$X`) and the cost gate is
off — errors and health still gate. Switch to `per_token` for
pass-through billing and the cost ceiling enforces.

## Development

```bash
python3 tests/all.py
```

## License

MIT. Reimplements ideas from
[Siddhant-K-code/agent-trace](https://github.com/Siddhant-K-code/agent-trace),
[luoyuctl/agenttrace](https://github.com/luoyuctl/agenttrace), and
[tensorstax/agenttrace](https://github.com/tensorstax/agenttrace) —
acknowledged as prior art, no code copied.
