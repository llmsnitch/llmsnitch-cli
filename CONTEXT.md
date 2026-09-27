# llmsnitch

Local-only tracing, cost/health gating, and filesystem tripwires for AI
coding agents. This glossary is the canonical vocabulary for the notify
layer (`docs/notifier-spec.md`); code, config, ledger, and docs all use
these words.

## Language

**Surface**:
An alert-producing subsystem: `fs-coil-light`, `fs-coil-deep`,
`config-audit`, `dep-audit`, or a future watcher. (The `session-shed` / `agent-flick`
wrapper surfaces were retired 2026-08-27 — `.wayfinder/rd-triage/map.md`.)
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

**Territory**:
The registered path prefixes an agent owns (`~/.claude` and `~/.claude.json`
for Claude Code, `~/.codex`, …), with an optional cache sub-territory
(`~/.claude/plugins/cache`). In light mode, where events carry no process,
the territory a path falls in is the *only* actor signal: inside → that
agent's `agent_self` / `agent_plugin_cache`; outside every territory →
`deny_write` by `unknown`.
_Avoid_: agent dir, home dir, owned path

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

**Patrol**:
An unattended, scheduled run of the `config-audit` surface (`llmsnitch
scan` fired by a LaunchAgent). A manual `scan` is not a patrol.
_Avoid_: cron scan, sweep, scheduled job

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

**Bulletin**:
The distilled advisory payload a provider publishes and the CLI consumes:
per-ecosystem package/version entries with severity and exploited-evidence
flags, cached locally and refreshed weekly.
_Avoid_: feed, CVE database, advisory list

**Intake**:
The evidence record that a specific package entered the machine through an
agent session — the population the `dep-audit` surface watches. Merely
being installed is not an intake; agent provenance is.
_Avoid_: install event, dependency (ambiguous), provenance (taken)

**Exercised**:
A package with machine-local evidence of use after intake: project source
imports it, or the project ran in an agent session after the install. The
gate that promotes an exploited-vulnerability finding to critical;
`malicious` findings never wait for it.
_Avoid_: reachable, invoked, used (vague)

**Digest**:
The once-daily rendered summary of the notify ledger's trailing 24 hours,
always written to disk after the patrol and read at a time of the user's
choosing; it banners only when the watchers themselves are unhealthy, never
to re-page a finding.
_Avoid_: report (taken by `scan --report`), summary email, daily alert

**Waiver**:
A user-granted exception silencing a specific finding on any surface,
carrying a reason, living until removed or the finding's underlying
condition changes in a way the surface defines as re-raising (dep-audit:
the advisory's severity escalates; config-audit: the set of matched
evidence for the rule × artifact changes).
_Avoid_: exception, allowlist entry, suppression, accept record

**Hook state**:
A non-executable file without a script extension living under a harness's
hooks directory — data a hook writes at runtime (a signal file, a
per-session marker, a config it reads back). Not a control surface: scanned
for secrets at rest, never fingerprinted for drift. Contrast **hook script**,
which runs.
_Avoid_: hook file, state file, session file

**Unattested agent**:
A directory matching agent-home heuristics (`scanrules.DISCOVERY_*`) that
sits outside every registered `TERRITORIES` prefix — a tool present on disk
with no dossier. Distinct from the `unknown` actor-bucket (which also covers
an intruder inside *known* territory). Emitted by the scan as
`unattested_agent_home` (high) / `unattested_agent_worktree` (low).
_Avoid_: rogue agent, unknown agent
