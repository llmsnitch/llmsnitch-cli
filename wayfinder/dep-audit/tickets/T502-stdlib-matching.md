# T502 — Client-side matching with stdlib only

`labels: wayfinder:research`
`parent: ../map.md`
`blocked by: —`
`blocks: T503`
`status: DONE (2026-09-11)`

## Resolution

Findings: [docs/research/dep-audit-stdlib-matching.md](../../../docs/research/dep-audit-stdlib-matching.md)
(cited, primary sources, measured against the live OSV PyPI corpus).

**Verdict (Q3, load-bearing): the bulletin carries pre-chewed enumerated
affected versions per (ecosystem, package) plus an `all_versions: true`
boolean — not ranges.** Client needs zero PEP 440 comparison: PEP 503 name
normalization (one regex), a ~30-line version canonicalizer, strip
`+local`, set membership. Clinchers:

1. OSV already pre-chews server-side — enumerated versions present in 77%
   of the 30,615 PyPI affected-blocks; osv-scanner's offline matcher
   checks that array by string equality first; pip-audit does no
   client-side matching at all.
2. Bounded: median 11 affected versions per block, p95 243, max 2,458.
   The ranges-only remainder is ~90% MAL "all versions affected" → the
   `all_versions` boolean; the server enumerates the few hundred real
   stragglers via PyPI JSON API.
3. PEP 440 corner cases: epochs appear zero times in the corpus;
   pre/post/dev bounds (~2,300 range events — where naive comparison
   breaks) are sidestepped entirely by membership; locals occur on the
   *installed* side (torch `+cuXXX`) → client strips `+local` first.
4. `importlib.metadata.distributions(path=[…])` verified live against
   foreign envs (incl. `.venv-dashboard`, a 3.12 venv read from 3.14, the
   uv tool env): pure filesystem parsing, in stdlib since 3.9. Use
   `dist.metadata['Name']` (then PEP 503-normalize) + `dist.version`.

Multi-ecosystem holds: membership is ecosystem-agnostic; only the
server-side enumerator is per-ecosystem. Ranges at most as provenance
metadata the client never evaluates.

## Question

The client must map installed distributions (`site-packages/*.dist-info`)
to bulletin entries using **stdlib only, Python 3.9+** — no `packaging`
dependency, so no off-the-shelf PEP 440 range comparison.

1. How do pip-audit / osv-scanner / grype resolve installed-dist →
   advisory today (name normalization, version comparison, extras)?
2. PEP 440 corner cases that break naive tuple comparison (epochs,
   pre/post/dev releases, local versions) — how common are they in real
   advisory ranges?
3. Can distillation pre-chew ranges server-side so the client stays
   trivially dumb — e.g. enumerate exact affected versions per package
   (bounded? PyPI version counts?), or emit normalized comparator keys?
4. `importlib.metadata` sufficiency for env enumeration given census
   facts: non-standard venv names (`.venv-dashboard`), uv tool envs,
   pipx venvs.

Output: `docs/research/dep-audit-stdlib-matching.md`. Use `curl`, never
WebFetch/WebSearch. The pre-chew question (3) is the load-bearing one —
it decides whether the bulletin schema carries ranges or verdicts.
