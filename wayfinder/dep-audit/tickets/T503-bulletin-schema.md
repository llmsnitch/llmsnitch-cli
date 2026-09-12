# T503 — Bulletin schema contract v1

`labels: wayfinder:grilling`
`parent: ../map.md`
`blocked by: T501, T502`
`blocks: T506, T507`
`status: DONE (2026-09-11)`

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

From T501: severity must be optional (`{label, vectors[], source}`) and
never load-bearing; exploited-evidence = `kev:{…}` + `epss:{…}` as two
fields, never merged; `versions:[]` + `open_ended` marker; and a
`class: vulnerability|malicious` discriminator — MAL records (46% of the
PyPI corpus) have no severity/fix/CVE yet are the most page-worthy for an
agent-installed population.

## Resolution

Contract published as `docs/bulletin-spec.md` (v1). Settled by HITL
grilling, two rounds, 14 decisions — all recommendations accepted:

**Round 1 (format & identity):**
1. **Single JSON object** `{meta, entries[]}`, not NDJSON — the bulletin is
   an atomic snapshot; a truncated file should *fail* verification, not be
   tolerated.
2. **Full-ecosystem distillation, never package-scoped** — the intake list
   never leaves the machine. Soft budget: SHOULD ≤ 10 MB gzipped/ecosystem.
3. **Schema permits mixed ecosystems per file**; MVP deploys one PyPI-only
   file. URL layout is client fetch-config, not contract.
4. **Sidecar `.sha256` of raw served bytes** — integrity only; authenticity
   rides on TLS; signing named as v2 candidate, no field reserved.
5. **Versioning**: bare integer `meta.schema_version`, client supports an
   explicit set ({1}), tolerant reader, additive = no bump, breaking = bump,
   unknown version = operational condition (scan runs on last good cache).
6. **One entry per (advisory-group × package)**; `id` = CVE if any alias has
   one else lexicographically-first source id; `aliases[]` carries all ids.
   Dedup is provider work.
7. **No MAL-specific machine fields** (PyPA `imports` has zero adoption);
   optional `summary` on every entry for display.
8. **`meta.sources`** provenance block (osv/kev/epss snapshot stamps),
   informational only; staleness gating stays on `issued_at` alone.

**Round 2 (waiver joints & residuals):**
9. **Waiver matches against `{id} ∪ aliases`** — waivers written against
   any alias survive canonical-id churn across rebuilds.
10. **Re-raise triggers**: `severity.label` band escalation OR `kev.listed`
    false→true; EPSS never (forecast, would flap).
11. **Withdrawn advisories dropped at distillation** — findings are
    recomputed from scratch each scan, nothing to clear.
12. **Optional `fixed_in[]`** display-only upgrade targets (serves the
    Decision gate); never compared against.
13. **`all_versions` boolean only, no `open_ended` marker** — the client
    can't order versions; the enumerated-but-unfixed gap is bounded by the
    weekly rebuild (≤ 7 days), and "possibly affected" fails the Decision
    gate.
14. **Optional `url`, no `entry_count`** — the hash already proves the file
    is whole.

Unblocks T506 (interim bulletin must conform) and partially T507 (client
matcher + fetch/verify path are now specified).
