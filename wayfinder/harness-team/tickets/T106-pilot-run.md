# T106 — Pilot run: top-roster harness end-to-end

`labels: wayfinder:task, destination`
`parent: ../map.md`
`blocked by: T101, T105`
`blocks: —`
`status: DONE (2026-08-25) — pilot complete; map destination reached`

## Question

Prove the team: run it once on the top-ranked unsupported harness from
[T101](T101-roster-ranking.md)'s roster, through every phase gate — dossier,
adapter, registry entry, tests green (stdlib suite + no-network grep guard),
doctrine audit, local commit. Where the harness is installed on this machine,
verify tracing against a real session (no-skipping doctrine: run the
verification, don't assume it).

Done = the pilot harness is "supported" per map D02, and the map closes: the
team is real and repeatable.

## Resolution

Resolved 2026-08-25. Pilot harness: **codex** (T101's pick). The team ran
all six phases; full evidence in `team/runs/codex/journal.md`.

- **Commits**: b224e86 (dossier), 9ec3850 (adapter + ingest engine),
  f2de841 (verify-driven fix), 291d709 (verify journal), 23898e7
  (audit-driven fixes), plus the closing commit.
- **Verification against real sessions** (no-skipping doctrine): all 84
  real rollouts ingested; `total_tokens` oracle-exact against
  `state_5.sqlite` on **84/84**; models-per-session {0:4, 1:79, 2:1};
  suite 22/22 incl. no-network guard; store 0600/0700; zero writes into
  `~/.codex`.
- **The gates earned their keep**: phase 4 caught a token overcount (up to
  +72.9% — codex restates token_count rows; my fixture was green over it),
  phase 5 caught the untranscribed registry half, a silent partial-health
  gate, and a REPRODUCED path traversal via hostile session ids. Two
  fix-cycles later, every new test provably discriminates.
- **Codex is "supported" per map D02, tier `ledger`**: tracing (ledger
  ingestion), cost (tokens + honest unpriced note pending C7 rates),
  health (visible-partial error signal), redaction (structural C6 +
  _clean on scalars), notification-readiness (registry half with
  OBSERVED signing id `codex` / team `2DC432GLL2`, cache_paths
  suppression list), list/show/check rendering.

The team is real and repeatable — this closes the map.
