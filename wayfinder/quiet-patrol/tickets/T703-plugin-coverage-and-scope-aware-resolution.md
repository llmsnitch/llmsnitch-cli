# T703 — Plugin coverage and scope-aware resolution

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: —`
`blocks: T704`
`status: OPEN — unclaimed`

## Question

Nothing left to decide — execution of D10 and D11 in `llmsnitch/scan.py`.
Build:

1. **Plugins as a walked sub** in `discover()`: for each territory root
   `t`, in addition to `hooks/skills/commands`, enumerate plugin roots
   with `glob` — `t/plugins/cache/*/*/*` and `t/plugins/marketplaces/*` —
   and `_walk(root, budget)` each, so `_MAX_DEPTH` is measured from the
   plugin, not from `~/.claude`. Symlinked roots skipped (existing `add`
   rule). No change to `_MAX_DEPTH` or `_MAX_FILES`. Measure before/after
   from `$HOME`: expected ≈ 74 → ≈ 686 classifiable plugin artifacts
   reached, budget not exhausted (the map's Notes hold the baseline
   numbers).
2. **Scope-aware resolution** in the novelty diff: a previous fingerprint
   is marked `resolved` only if its artifact is in this run's discovered
   set; otherwise it is neither re-emitted nor tombstoned (carried
   forward). `_previous_fingerprints` must therefore return artifacts
   alongside fingerprints. `--report` is unaffected.
3. **Docs**: `docs/notifier-spec.md` §2.2 (or wherever discover roots are
   listed) gains the plugin roots; CLAUDE.md architecture line for
   `scan.py` if it enumerates walked subs.
4. **Tests**: a temp territory with a plugin skill at depth 8 is
   discovered; a scan from cwd A then cwd B does not resolve A-only
   findings; a genuinely deleted artifact still resolves.

Expect the first live scan after this lands to surface new findings from
previously unscanned plugin files — that triage is T704's job (or a new
ticket if a class needs a decision), not this ticket's. Done when the
suite is green and the before/after count is recorded in the resolution.
Review gates as in T701.
