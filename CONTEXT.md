# llmsnitch

Local-only tracing, cost/health gating, and filesystem tripwires for AI
coding agents. This glossary is the canonical vocabulary for the notify
layer (`docs/notifier-spec.md`); code, config, ledger, and docs all use
these words.

## Language

**Surface**:
An alert-producing subsystem: `fs-coil-light`, `fs-coil-deep`,
`session-shed`, `agent-flick`, `config-audit`, or a future watcher.
_Avoid_: source, channel, tool

**Outlet**:
A consumption path a decided notification reaches the user through:
Notification Center, `fs-coil noise`, the daily digest, the TUI badge.
_Avoid_: channel, delivery surface

**Category**:
A code-defined enum value classifying what happened (`deny_write`,
`agent_self`, …). The unit of notification policy.
_Avoid_: type, class, kind

**Actor bucket**:
Normalized short name for who did it (`claude-code`, `bash`, `unknown`).
Drives novelty math.
_Avoid_: process name, agent name

**Actor raw**:
The verbatim executable path of the acting process, recorded for forensics
only.
_Avoid_: exe, binary path

**Novelty tuple**:
The pair `(category, actor bucket)` — the key the novelty gate
deduplicates on.
_Avoid_: dedup key, event key

**Novelty window**:
Per-tuple duration during which repeats are suppressed (logged, not paged).
`0` means edge-triggered.
_Avoid_: cooldown, debounce

**Cold trail**:
The persistent append-only NDJSON event ledger; every successfully
processed event lands there, paged or not — a failing call leaves the
degraded flag as its trace instead.
_Avoid_: event log, history

**Hot state**:
The small locked JSON novelty index consulted on the hot path
(`notify-state.json`).
_Avoid_: cache, state file

**Degraded flag**:
Persistent marker set when the notify layer itself fails; discoverable via
`fs-coil status` and the dashboard, never pushed.
_Avoid_: error flag, health bit

**Cold start**:
The 24-hour learning window after install during which everything is
ledgered but only `critical` severity pages.
_Avoid_: grace period, warmup

**Edge-triggered**:
Fires only on a verdict transition (pass→breach, breach→pass), never on a
repeated state.
_Avoid_: on-change, delta alert

**Actor mismatch**:
A registered agent touching a different registered agent's directory; a
metadata flag on `deny_write`, always `critical`.
_Avoid_: cross-agent contamination

**Agent registry**:
The table of known agents and their identifying signals (paths, exe
basenames, signing ids); built-ins in code, extended via `[agent.*]` config.
_Avoid_: agent list, whitelist

**Actionability gates**:
The three tests from `AGENTS.md` every page must pass: Decision, Actor,
Novelty.
_Avoid_: notification rules

**Harness**:
An AI coding agent product whose activity llmsnitch traces (Claude Code,
Codex CLI, Cursor, …). The thing an adapter supports.
_Avoid_: agent (ambiguous with registry actors), tool

**Harness adapter**:
The per-harness declarative entry plus optional code hook that ledger-ingests
a harness's sessions into the store — coupled with that harness's
agent-registry entry (contract: `docs/harness-adapter-contract.md`).
_Avoid_: plugin, integration, connector

**Ledger**:
The session/trace files a harness already writes on its own; ledger
ingestion parses them after the fact — the universal capture mode, requiring
no hook install and leaving the harness unmodified.
_Avoid_: transcript sweep, log scraping

**Signal set**:
The closed per-session list every adapter must produce: model ids, token
counts per model, session start/end, cwd/project, error count. Anything
beyond it is optional enrichment.
_Avoid_: metrics, telemetry

**Ingest cursor**:
Per-source-file incremental state (path, mtime, size, offset or hash) in
`ingest-state.json` that keeps ledger sweeps cheap and idempotent.
_Avoid_: checkpoint, watermark

**Provenance**:
The `src` fields on a ledger-derived row — source file path, SHA-256,
mtime — pointing back at the original the row was normalized from.
_Avoid_: origin, source ref

**Deferred (tier)**:
Support state for a harness whose local traces exist but are not
stdlib-readable yet (e.g. zstd before Python 3.14); admission still passes,
only ingestion waits.
_Avoid_: unsupported, blocked

**Dossier**:
The single per-harness fact sheet (trace locations, config paths, hook
system, pricing source, exes/signing ids, admission verdict) that feeds the
adapter, the registry entry, and later the scan seed table.
_Avoid_: profile, spec, survey

**Roster**:
The ordered list of harnesses queued for support: union of Ori's and the
OpenRouter cookbook's lists, popularity-ranked, admission-tested.
_Avoid_: backlog, matrix

**Admission test**:
The roster gate: a harness is adapter-eligible iff it writes local
trace/session files on disk; cloud-only harnesses fall to the companion
browser extension.
_Avoid_: eligibility check, filter
