# T503 — Bulletin schema contract v1

`labels: wayfinder:grilling`
`parent: ../map.md`
`blocked by: T501, T502`
`blocks: T506, T507`
`status: OPEN`

## Question

Design the distilled-bulletin contract (`docs/bulletin-spec.md`): the
schema the out-of-scope provider must emit and the CLI consumes. Grounded
on T501/T502 findings. Must express: per-`ecosystem` entries (PyPI now,
npm/NuGet/Maven without schema change), package identity + affected
versions (ranges vs pre-chewed exact lists per T502), severity, the
exploited-evidence flag the criticality gate needs, optional indicator
slots (fog placeholder), bulletin metadata (issued-at, hash for
verification, staleness stamping). HITL grilling: format (JSON? NDJSON?),
size budget, versioning of the contract itself.
