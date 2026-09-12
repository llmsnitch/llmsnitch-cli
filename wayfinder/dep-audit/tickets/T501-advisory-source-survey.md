# T501 — Advisory-source survey: what can a bulletin carry?

`labels: wayfinder:research`
`parent: ../map.md`
`blocked by: —`
`blocks: T503`
`status: DONE (2026-09-11)`

## Resolution

Findings: [docs/research/dep-audit-advisory-sources.md](../../../docs/research/dep-audit-advisory-sources.md)
(all claims cited; measured against 2026-09-11 live OSV PyPI zip, KEV
JSON, EPSS CSV, pypa/advisory-database). Load-bearing for T503:

1. **Severity is optional, never a gate** — only GHSA reliably ships it
   (95%); PYSEC 62%; MAL 0%; databases disagree on the same bug. Schema:
   optional `{label, vectors[], source}`; client renders "unknown", never
   pages on it.
2. **"Actively exploited" = two fields, never merged** — KEV membership is
   curated past-exploitation *evidence* (CC0, one 1.7MB JSON, no auth);
   EPSS is a 30-day *forecast* (daily CSV, free). Both CVE-keyed → join
   via OSV `aliases[]`. KEV satisfies the map's exploited clause; EPSS
   cannot. Bulletin: `kev:{listed,date_added,ransomware}` +
   `epss:{score,percentile,date}`. Parse KEV tolerantly (live feed has
   fields beyond CISA's schema).
3. **Exact-version lists work, with one marker** — 73% of the PyPI corpus
   already ships enumerated versions; ~8k records (nearly all MAL) are
   open-ended. Schema: `versions:[]` + `open_ended` flag (or introduced
   floor); client PEP 440-normalizes intake versions before matching.
4. **Indicator fog confirmed** — no source ships machine-checkable IOCs
   (PyPA `imports` field: zero adoption). Don't reserve indicator fields;
   "exercised" stays local (T505).
5. **NEW — malicious-package class**: 46% of the PyPI OSV corpus is MAL-*
   (typosquats etc.) — no severity, no fix, no CVE, and for an
   agent-installed population the most page-worthy records. Schema needs
   `class: vulnerability|malicious`; criticality gate implications pushed
   to T503/T505.
6. **Multi-ecosystem**: OSV is the single aggregation point (per-ecosystem
   `all.zip` + incremental CSV, no auth, no rate limits; GHSA re-exported
   inside). KEV OSS-library coverage is a sliver — good selectivity.
   Weekly curl refresh comfortably feasible; licenses redistribution-friendly.

## Question

Survey the primary advisory sources — OSV (schema + bulk data), CISA KEV,
EPSS, GHSA, PyPA advisory-db — to ground the bulletin schema contract:

1. Severity conventions per source (labels vs CVSS) and how they disagree.
2. Exploited-in-the-wild evidence: what KEV/EPSS actually assert, update
   cadence, formats, license/access terms (bulk download, rate limits).
3. Affected-version-range encodings (OSV `ranges`/`versions`, GHSA vrange
   strings) and how lossy a distillation to exact-version lists would be.
4. Indicator feasibility: do any sources ship machine-checkable indicators
   (file hashes, paths, behaviors) usable for local abuse-evidence matching,
   or is that fog confirmed?
5. Multi-ecosystem coverage: PyPI now, npm/NuGet/Maven later — same
   sources, or per-ecosystem gaps?

Output: `docs/research/dep-audit-advisory-sources.md`. Use `curl`, never
WebFetch/WebSearch.
