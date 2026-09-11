# T502 — Client-side matching with stdlib only

`labels: wayfinder:research`
`parent: ../map.md`
`blocked by: —`
`blocks: T503`
`status: CLAIMED (research subagent, 2026-09-11)`

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
