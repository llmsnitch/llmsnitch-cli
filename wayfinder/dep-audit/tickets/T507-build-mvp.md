# T507 — Build the dep-audit MVP

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: T503, T504, T505, T506`
`blocks: T508`
`status: OPEN`

## Question

Nothing left to decide once blockers close — execution per the map's
plan-vs-do override. Build, on branch `feature/scanner-venv-mvp`:

1. Intake sweep (T504 design) incl. retroactive pass.
2. Bulletin cache read + hash verify + payload-age stamping (fetch wiring
   itself is T508; scan must work offline against a stale cache).
3. Matching: intakes × bulletin (T502/T503 encoding), waiver filter,
   exercised gate (T505) → findings. Critical = intake ∧ exploited-flag ∧
   exercised; everything else lesser and quiet.
4. Waivers: flat file under `~/.llmsnitch/`, (advisory × package) +
   required reason, no TTL, re-raise on severity escalation.
5. Findings route through `fs_coil.notify`; hot path untouched; suites
   green; review gates (two-axis + ponytail) over the diff.
