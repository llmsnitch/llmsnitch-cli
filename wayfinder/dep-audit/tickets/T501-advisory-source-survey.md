# T501 — Advisory-source survey: what can a bulletin carry?

`labels: wayfinder:research`
`parent: ../map.md`
`blocked by: —`
`blocks: T503`
`status: CLAIMED (research subagent, 2026-09-11)`

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
