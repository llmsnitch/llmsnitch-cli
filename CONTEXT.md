# llmsnitch

Local-only tracing, cost/health gating, and filesystem tripwires for AI
coding agents. This glossary is the canonical vocabulary for the notify
layer (`docs/notifier-spec.md`); code, config, ledger, and docs all use
these words.

## Language

**Surface**:
An alert-producing subsystem: `fs-coil-light`, `fs-coil-deep`,
`session-shed`, `agent-flick`, or a future watcher.
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
