# Harness Adapter Contract

Status: **accepted** — resolution of wayfinder ticket
[T102](../wayfinder/harness-team/tickets/T102-adapter-contract.md)
(16 decisions across 3 grilling rounds, 2026-08-24). This document is the
contract every harness adapter implements and every team run
([T104](../wayfinder/harness-team/tickets/T104-team-design.md)'s pipeline)
is gated against. Vocabulary is canonical in `CONTEXT.md`; read it first.

## Purpose doctrine

llmsnitch is a **tripwire, not a meter**. The objective of tracing a harness
is to notice when a model is being used without the user's knowledge —
something sneaky going on — never cost control, never troubleshooting.
Every contract term below serves detection:

- **Cost is a detection signal.** Low-resolution, high-level "how much is
  being spent" exists to make unnoticed usage visible. No precision
  pretense.
- **Errors are a suspicion proxy.** Error counts indicate activity the user
  didn't consent to, not bugs to fix.
- **An unknown model id is itself a signal.** A model name never seen before
  appearing in a harness's sessions names a decision (investigate), an actor
  (the harness), and is novel by definition — it passes all three
  actionability gates from `AGENTS.md`.

## Non-negotiables (inherited, test-enforced)

Every adapter, without exception:

1. **Zero network code** — the no-network grep guard in
   `tests/test_llmsnitch.py` must pass. Pricing data, dossier facts, and
   registry values are gathered at design time by humans/agents; shipped
   code only reads local files.
2. **Stdlib only, Python 3.9+** — `sqlite3` is stdlib and permitted
   (OpenCode, Hermes). No subprocess for parsing (no shelling out to
   decoders).
3. **Flat files** — `~/.llmsnitch/` NDJSON + JSON, files 0600, dirs 0700.
4. **Read-only toward the harness** — adapters never write into a
   harness's directories, never modify its config, never install hooks
   (C2). The watched harness is not told it is being watched.
5. **Redact before disk** — nothing lands in our store unredacted (C6).
6. **Fail soft** — a malformed or truncated foreign session file is
   skipped/partially read, never a crash; consistent with
   `store.py`'s truncated-tail tolerance.

## Contract terms

### C1 — Adapter form: data-first hybrid

An adapter is a **built-in declarative entry** plus an **optional code
hook**, registered under the harness's canonical name (the actor-bucket
name from the notifier spec's registry — `codex`, `opencode`, …).

The declarative entry (one dict per harness, in code; the shape T103
finalizes against the dossier format) carries at least:

| Field | Purpose |
|---|---|
| `name` | canonical harness name = actor bucket |
| `session_paths` | glob(s) for local session/trace files |
| `session_format` | `jsonl` \| `sqlite` \| `jsonl.zstd` \| … |
| `config_paths` | harness config locations (context, not scanned here) |
| `registry` | paths / exes / signing_ids for the agent registry (C9) |
| `provider_families` | model-id pattern → provider family, for pricing (C7) |
| `tier` | support state: `live+ledger` \| `ledger` \| `deferred` (C3) |

The optional code hook exists only where formats genuinely diverge (SQLite
schema readers, unusual JSONL shapes). Path/field-name differences are
data, not code.

### C2 — Ledger-first, no installer seam

**Ledger ingestion — parsing the session files the harness already writes —
is the universal, required mode for every adapter.** There is no installer
seam in this contract: adapters never wire hooks into a harness.

Claude Code's existing hook path (`llmsnitch/hook.py`,
`llmsnitch/setup_cmd.py`) stays exactly as shipped — it is Claude-specific
bootstrap and live enrichment *outside* this contract. Claude Code also
gets a ledger adapter like every other harness (its
`~/.claude/projects/**/*.jsonl` transcripts); diffing its ledger output
against its hook output is a standing correctness check.

### C3 — Tiers and deferral

- `live+ledger` — ledger adapter plus pre-existing live capture
  (Claude Code only, today).
- `ledger` — the normal state for every new harness.
- `deferred` — traces exist locally but are not stdlib-readable. Admission
  test still PASSES (the blocker is a decoder, not the cloud). Current
  case: DeepSeek Harness's `.jsonl.zstd` defaults — deferred until
  `compression.zstd` lands in the stdlib (Python 3.14). A deferred entry
  ships with its dossier and registry data; only ingestion waits.

### C4 — The signal set (closed list)

Every ledger adapter MUST produce, per session:

1. model ids seen
2. token counts per model (input / output / cache where the format has them)
3. session start / end timestamps
4. session cwd / project identity
5. error count (suspicion proxy)

This list is closed: anything beyond it is optional, dossier-documented
enrichment. T104's test-verifier gate is mechanical — the adapter emits
the signal set from a real or fixture session file, or the run does not
advance. Gate signals the adapter cannot supply (a format records no
errors) are skipped **visibly** — `check` output says so
(`health: n/a — codex sessions record no error events`), following the
subscription-mode precedent of honest disablement.

### C5 — Canonical event row and store shape

Foreign sessions are **fully normalized into the existing store shape** —
`~/.llmsnitch/sessions/<sid>/events.ndjson` + `meta.json`, via
`store.py`'s primitives. One event vocabulary for all harnesses:

- The row is the existing hook-event NDJSON shape, extended **additively**:
  - `harness`: canonical name; absent ⇒ `claude-code` (back-compat — all
    existing stores stay valid).
  - `src`: provenance for ledger-derived rows — source file path + its
    SHA-256 (+ mtime), so `show` can point back at the original.
- `meta.json` gains the same `harness` field; `llmsnitch list` shows a
  harness column.
- Session ids for ledger sessions are namespaced to avoid collisions
  (`<harness>-<native session id>`).

### C6 — What is (and is never) copied

Normalization ingests **tool events, session lifecycle, and usage/model
records only. Message/prompt/response bodies are never copied into the
store.** What is never copied cannot leak — this is the primary PII
sanitization, by structure rather than by pattern.

Tool inputs/outputs that are copied get the full existing treatment before
disk: `hook._clean` depth-walk, `_SECRET` redaction, the NFKC canonical
fold from `docs/research/unicode-evasion-redaction.md`, 2000-char string
caps. Only the redacted copy exists in our store.

If message-body ingestion is ever wanted, free-text PII redaction becomes
a dedicated research effort first — it is out of this contract.

### C7 — Pricing: one coarse shared table

One shared pricing module serves all adapters. Provider-family rates keyed
by model-id patterns; adapters contribute only their `provider_families`
mapping. Rules:

- Low resolution by design (tripwire, not invoice).
- **No invented prices** — every provider family designates a fallback
  tier; an unmatched model id prices at the fallback **and** raises the
  `unknown model` flag, which is a first-class detection signal (see
  Purpose doctrine). The notifier category wiring for it belongs to the
  notifier effort, not this contract — the contract only names the signal.
- The table is generated at **design time** with cited sources (the team's
  dossier-researcher may use the network; shipped code may not), committed
  as static code like today's Anthropic table in `transcript.py`.

### C8 — Ingestion trigger and cursors

- **Lazy + explicit**: `list`, `show`, and `check` each run an incremental
  ingest sweep first; `llmsnitch ingest [--harness NAME]` is the explicit
  form for cron/scripting. No daemon, ever.
- Incremental state lives in one `~/.llmsnitch/ingest-state.json` (0600):
  per source file — path, mtime, size, byte offset (for append-only
  formats) or content hash (for rewritten formats/SQLite). Corrupt or
  missing state ⇒ full re-sweep, never a crash (fail-tolerant read, same
  pattern as the notifier's hot state).
- Re-ingesting is idempotent: the same native session re-swept updates its
  store entry in place (keyed by the namespaced session id).

### C9 — Registry coupling

"Supported" requires both halves (map D14): the ledger adapter **and** the
agent-registry entry (paths, exe basenames, signing ids) for actor
attribution in the notifier. Both are fields of the same declarative entry
(C1), both filled from the same dossier. Signing ids are
**observed, never guessed** — shipped empty until a pilot/team run records
them via `codesign -dr -` on the real binary.

## Acceptance checklist (T104's gate source)

An adapter PR/commit is complete when:

- [ ] Declarative entry present with every C1 field; dossier linked.
- [ ] Signal set (C4) produced from at least one real session file on this
      machine where the harness is installed, else a committed fixture.
- [ ] Events + meta land via `store.py`, 0600/0700, redacted per C6.
- [ ] Namespaced session ids; `harness` field on every row; provenance on
      ledger rows.
- [ ] `list`/`show`/`check` render the harness without special-casing.
- [ ] Unsupplied gate signals reported visibly (C4).
- [ ] Registry half present; signing ids observed or explicitly empty.
- [ ] Full stdlib test suite passes, including the no-network grep guard
      and a new per-adapter parse test with a fixture.
- [ ] No writes into the harness's own directories (C2) — test-asserted.

## Deferred / open

- Per-harness gate config overrides (`[gate.<harness>]`) — trimmed from
  scope in grilling round 1 (Q6); revisit if per-harness thresholds are
  ever actually wanted.
- fs-coil-watcher-triggered ingestion — fog on the map; C8's lazy sweep is
  the contract until then.
- Notifier category for the `unknown model` signal — notifier effort's
  decision, on this contract's vocabulary.
