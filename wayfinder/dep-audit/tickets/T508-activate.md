# T508 — Activate dep-audit

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: T507`
`blocks: —`
`status: CLAIMED (session 6098b27b, 2026-09-12)`

## Question

Execution: merge + reinstall (pipx, per scan-rollout's second-merge
rhythm), wire the surface into the daily patrol, wire the weekly bulletin
refresh (`curl` subprocess; interim: T506's re-run path), and verify live.
Done criteria (close the map when all hold):

1. Daily patrol run executes dep-audit and ledgers its result.
2. A weekly refresh path exists and has run once (hash-verified cache,
   payload age stamped).
3. The retroactive intake sweep has run over historical ledgers.
4. A finding (real or seeded) routed through the notify layer; a waiver
   demonstrably silences it; only evidence-gated criticals may page.
