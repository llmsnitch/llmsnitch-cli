# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo doctrine (read before editing)

- **`README.md`** — design constraints. All test-enforced, all non-negotiable.
- **`AGENTS.md`** — the Decision/Actor/Novelty test every user-facing alert must pass.
- **`CONTEXT.md`** — canonical vocabulary (Surface, Outlet, Category, Cold trail, Hot state, …). Use these words in code, config, and docs.
- **`docs/notifier-spec.md`** — the notify-layer destination.
- **`wayfinder/*/map.md`** — decision records per effort (harness-team D01–D15, scan-rollout, submodule-clearout, rd-triage). Closed maps are history — never rewritten.

## Non-negotiable constraints

These are enforced by `tests/test_llmsnitch.py` — a change that breaks any of them fails the build:

1. **No network code.** No `urllib`, `socket`, `http.client`, `requests`. `test_no_network_imports` greps the package.
2. **Stdlib only, Python 3.9+.** `pyproject.toml` declares `dependencies = []` — this is a constraint, not a status. Never add a dep.
3. **The hot path (`hook.handle`) never blocks or raises.** Always returns 0, prints nothing, swallows every exception. If you're editing `hook.py`, preserve this contract.
4. **Redaction happens before disk.** `_SECRET` regex in `hook.py` covers `sk-*`, `gh[pousr]_*`, `xox[baprs]-*`, `AKIA*`, JWTs, `Bearer …`, PEM headers. Adding a shape: prefer high-specificity patterns — a false negative is worse than a false positive, but a too-generic alphabet (bare 52-char base32) is worse still.
5. **Flat files.** NDJSON events + `meta.json` per session under `~/.llmsnitch/sessions/`. Files `0600`, dirs `0700`. No SQLite, no daemon.
6. **Gate exit codes: `0 pass / 1 breach / 2 operational`.** Not inverted like some upstreams — do not "fix" this.

## Architecture

Two packages ship in the wheel: `llmsnitch` (12 modules, ~1,800 LOC) and
`fs_coil` (the notify layer — the scan's finding routing imports it).

- `cli.py` — argparse-free dispatch. `hook <event>` is the hot path; everything else is human-facing.
- `hook.py` — reads one Claude Code hook payload from stdin, redacts, appends one NDJSON line. On `Stop`, folds transcript usage into `meta.json`.
- `store.py` — the only module that touches disk. Append-only NDJSON; tolerates a truncated tail (in-progress sessions).
- `transcript.py` — offline cost estimate from the Claude Code transcript's own `usage` records. Pricing table lives here; unknown models fall to sonnet-tier with a `cost_note`, never an invented rate.
- `gate.py` — pure `evaluate(cfg, summaries)` returning `(verdict, findings)`. Cost gate is disabled in `subscription` mode (default) — most users are on Max/Pro and aren't billed per token; errors and health still gate.
- `setup_cmd.py` — prints or writes the Claude Code hooks block. `--write` **refuses to run inside a Claude Code session** (`CLAUDECODE` env set): the monitored agent must not edit its own hook wiring. Snapshots `settings.json` first.
- `harness.py` / `ingest.py` — multi-harness support per `docs/harness-adapter-contract.md`: declarative registry + lazy ledger-first ingestion with cursors (codex is the first non-Claude harness, T106).
- `scan.py` / `scanrules.py` — the config-audit surface: rule-pack audit over agent config artifacts; findings route through `fs_coil.notify` as `scan_finding`.
- `patrol.py` — LaunchAgent plist print/`--write` for the daily unattended scan (`com.slav-it.llmsnitch-patrol`); `scan --patrol` stamps `meta.trigger`.
- `__init__.py` — `__version__`.

Data flow: Claude Code hook → `cli hook <event>` → `hook.handle` → `store.append_event` → NDJSON. On `Stop`, `transcript.usage_from_transcript` + `estimate_cost` → `meta.json`. `list`/`show`/`check` re-read from disk — no cached counters to drift.

## Commands

```bash
python3 tests/test_llmsnitch.py       # the whole suite; stdlib runner, no pytest
pip install -e .                       # dev install; entry point: llmsnitch
llmsnitch setup                        # print hooks block
llmsnitch setup --write                # install (from a plain terminal, not inside CC)
llmsnitch list | show <id> | check     # read-side
LLMSNITCH_DIR=/tmp/foo llmsnitch …     # override base dir (used by tests)
```

Run one test: there is no framework, just call it — `python3 -c "from tests.test_llmsnitch import test_hook_records_and_redacts as t; t()"`.

## House rules (from user global instructions and repo memory)

- **Published under the owner's `llmsnitch` GitHub account** (`github.com/llmsnitch/llmsnitch-cli`, public since 2026-08-21; local-only rule retired 2026-08-27). Pushing requires the `llmsnitch` account — the `llmsnitch` token is pull-only. The pre-publication working repo at `~/Repos/llmsnitch` remains remote-less.
- **Never run `install.sh`.**
- **Never use `rm` / `rm -rf`.** Use `trash` (no fallback).
- Every notification design decision grounds on the map at `wayfinder/map.md` (D01–D27) and the actionability test in `AGENTS.md` — Decision, Actor, Novelty.
