# T106 — Pilot run: top-roster harness end-to-end

`labels: wayfinder:task, destination`
`parent: ../map.md`
`blocked by: T101, T105`
`blocks: —`
`status: OPEN`

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

*(append pilot outcome — harness, commits, test output summary; close the
map)*
