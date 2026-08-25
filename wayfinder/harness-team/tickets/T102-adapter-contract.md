# T102 — Harness-adapter contract

`labels: wayfinder:grilling`
`parent: ../map.md`
`blocked by: —`
`blocks: T103, T104`
`status: DONE (2026-08-24) — contract at ../../docs/harness-adapter-contract.md, glossary updated in ../../CONTEXT.md`

## Question

Define what "a harness adapter" IS — the contract every team run implements.
Today Claude Code knowledge is smeared across four seams with no abstraction
(map Notes); this ticket decides the seam boundaries and the adapter's
required surface:

1. **Ingestion**: hook-based capture (Claude-style) vs transcript-file
   parsing vs both — and whether hook-less harnesses form a documented lower
   tier (currently fog; resolve it here).
2. **Cost**: per-provider offline pricing tables, unknown-model fallback
   semantics (today: sonnet-tier + flag), cache-token conventions.
3. **Health/gate**: what error/fail-rate signals each harness can supply to
   `gate.evaluate()`.
4. **Installer**: per-harness setup (settings/hook wiring where hooks exist),
   self-edit refusal sentinel (Claude's `CLAUDECODE` analog).
5. **Registry coupling** (map D14): the agent-registry entry (paths, exes,
   signing ids observed-not-guessed) required alongside the adapter.
6. **Non-negotiables as contract terms**: zero network, stdlib-only, 0600/0700,
   redact-at-capture, hot path never blocks, Decision/Actor/Novelty.

HITL: grill + domain-model with the user; new terms land in `CONTEXT.md`.

## Inputs from T101

- **zstd collision**: DeepSeek Harness defaults to zstd-compressed session
  logs (`.jsonl.zstd`); Python 3.9 stdlib has no zstd decoder
  (`compression.zstd` arrives in 3.14). The contract must say what happens
  when a harness's traces exist locally but aren't stdlib-readable — a tier,
  an exclusion, or a documented wait-for-3.14.
- **Pilot context**: Codex CLI has both plain JSONL sessions
  (`~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` + `session_index.jsonl`)
  and a `~/.codex/hooks.json` — a live specimen for the hook-vs-transcript
  tier decision.

## Resolution

Resolved 2026-08-24 via 16 grilling questions over 3 rounds (Q1–Q16, HITL).
Full contract: `docs/harness-adapter-contract.md` (C1–C9 + acceptance
checklist). The decisions, gisted:

- **Purpose reframe (the big one)**: llmsnitch is a *tripwire, not a meter*.
  Cost = detection signal for model use without the user's knowledge
  (low-resolution by design); errors = suspicion proxy, not troubleshooting;
  an unknown model id is itself a first-class signal (Q4, Q5, Q8).
- **Form**: data-first hybrid — declarative built-in entry per harness +
  optional code hook only where formats diverge (SQLite, odd JSONL);
  registry fields ride the same entry (Q1, map D14).
- **Ledger-first, no installer seam**: parsing what the harness already
  wrote is the universal required mode; adapters never install hooks or
  modify the harness (read-only, stealth-friendly). Claude's hook path
  stays as out-of-contract bootstrap/enrichment, and Claude also gets a
  ledger adapter — hook-vs-ledger diff is a standing correctness check
  (Q2, Q7, Q11, Q16).
- **zstd/DeepSeek**: admission PASS, tier `deferred` until stdlib zstd
  (Python 3.14) — decoder problem, not cloud problem (Q3).
- **Signal set (closed)**: model ids, tokens per model, session start/end,
  cwd/project, error count. Test-verifier gates on it mechanically;
  unsupplied gate signals are skipped *visibly* in `check` (Q9, Q5).
- **Store**: full normalization into the existing events.ndjson + meta.json
  shape — additive `harness` field (absent ⇒ claude-code), provenance on
  ledger rows, namespaced session ids. Tool events/lifecycle/usage only —
  **message bodies are never copied** (structural PII sanitization);
  copied fields get _clean + _SECRET + NFKC + caps (Q10, Q14, Q15, Q6).
- **Pricing**: one coarse shared table, provider-family rates, design-time
  generation with citations, no invented prices, unknown-model flag (Q8).
- **Ingestion**: lazy sweep on list/show/check + explicit `ingest`
  subcommand; cursors in `ingest-state.json`; idempotent; no daemon (Q13).
- **Contract location**: `docs/harness-adapter-contract.md`; six new terms
  in `CONTEXT.md` (Ledger, Signal set, Ingest cursor, Provenance,
  Deferred tier; Harness adapter redefined) (Q12).

Deferred: `[gate.<harness>]` overrides (trimmed in Q6), watcher-triggered
ingestion, notifier category for unknown-model.
