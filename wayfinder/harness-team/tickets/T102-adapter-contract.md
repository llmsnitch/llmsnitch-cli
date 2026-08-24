# T102 — Harness-adapter contract

`labels: wayfinder:grilling`
`parent: ../map.md`
`blocked by: —`
`blocks: T103, T104`
`status: OPEN`

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

*(append decision summary here, close, and index on the map)*
