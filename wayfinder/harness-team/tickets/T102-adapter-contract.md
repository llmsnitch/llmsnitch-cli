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

## Resolution

*(append decision summary here, close, and index on the map)*
