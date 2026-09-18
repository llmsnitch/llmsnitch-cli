# T703 — Plugin coverage and scope-aware resolution

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: —`
`blocks: T704`
`status: DONE (2026-09-18)`

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

## Resolution

Branch `quiet-patrol/T703` (forked at e9e58b8). Suite: `python3 tests/all.py`
186/186 (182 at dispatch + 4).

**Built (`llmsnitch/scan.py`)**

- `discover()`: two passes over the territories — every territory's singles
  + `hooks/skills/commands` first, then every territory's plugin roots
  (`plugins/marketplaces/*`, then `plugins/cache/*/*/*`), each `_walk`ed
  from the plugin root so `_MAX_DEPTH` counts from the plugin. Symlinked
  roots skipped; a root nested inside a `_SKIP_DIRS` member is skipped
  (the cache glob otherwise lands in `cache/temp_git_*/.git/hooks` and
  classifies `*.sample` git hooks as `hook_script`). Two passes because a
  single pass exhausted the budget inside the claude-code plugin cache
  before `~/.codex/skills/*` was ever walked. Marketplaces before cache
  because a marketplace is one artifact-dense clone while the cache holds
  a copy per installed version (six `remember` versions = 2,187 files for
  31 artifacts). No `_MAX_DEPTH` / `_MAX_FILES` change.
- `_previous_fingerprints()`: folds every stored scan oldest→newest into
  `{fingerprint: artifact}` — a finding row opens, a tombstone closes.
  Reading only the newest scan would forget a carried-forward finding
  after one out-of-scope run and re-flag it `new` on the next in-scope
  run; the fold makes D11's "carry forward" hold across any number of
  scans with no new row shape. `--report` reads one scan dir, unaffected.
- `run_scan` resolve block: a previous fingerprint tombstones only if its
  artifact is in this run's `targets` (tilde form; a size-skipped file is
  in `targets`, so it still counts) **or** no longer exists on disk — the
  same test `_drift` uses for `drift_removed`, so a genuinely deleted
  artifact resolves from any cwd. Otherwise: not re-emitted, not
  tombstoned.

**Measured — in-process read-only `discover()` from `$HOME`, no scan run**

| | total artifacts | under `~/.claude/plugins/` | budget overflow |
|---|---|---|---|
| before (e9e58b8) | 204 | 74 | 2 |
| after | 723 | 596 | 17 |

Classifiable ceiling under `plugins/` on this machine is 672 (map said
≈686), across 4,709 walkable files — above the 4,000 cap, so "budget not
exhausted" cannot hold under D10's two globs here. Lost vs before (8):
three cwd-walk files under `~/.claude` (`.claude/settings.local.json`,
`.mcp.json`, `plans/.claude/settings.local.json` — exist, so D11 carries
their findings and `_drift` keeps their baseline rows), four plugin files
behind the budget wall (`remember/0.32.0`, `0.33.0` `CLAUDE.md`,
`ponytail/4.7.0/AGENTS.md`), and `~/.claude/plugins/ralph-wiggum/hooks/*`
(a plugin installed directly under `plugins/`, outside D10's two globs —
see requests).

**Real-tree check** — repo entry point (`llmsnitch.cli.main(["scan"])`)
from `$HOME` with `LLMSNITCH_DIR`, `LLMSNITCH_NOTIFY_DIR`,
`LLMSNITCH_HOT_STATE`, `LLMSNITCH_CONFIG` all on a scratch dir (live store
untouched, 35 scan dirs before and after):
`scan scan-20260918-190708: 720 files, 20 skipped` · exit 1 ·
`findings: critical=3, high=1, low=11` · ~13 s. New plugin-origin rows:
`skill_instruction_override` on
`marketplaces/claude-plugins-official/plugins/receipts/skills/receipts/SKILL.md:142`
and `secret_shape` on
`marketplaces/anthropic-agent-skills/skills/claude-api/SKILL.md:463` —
T704 triage as the ticket predicted.

**Tests** (`tests/test_scan_scope.py`, 4): depth-8 plugin skill +
marketplace skill discovered, symlinked and `.git`-nested roots skipped,
budget untouched; scan A→B→A carries A's finding (absent from B's scan,
`new: false` on return); deleted artifact tombstones from cwd B and stays
closed; size-skipped artifact still resolves. Red-checked against the
e9e58b8 package: the first two fail there, the last two pass (invariants
D11 must keep).

**Files**: `llmsnitch/scan.py`, `tests/test_scan_scope.py`, `tests/all.py`,
`docs/research/scanner-survey-mvp.md` (§2.2 seed table row — that is
where `discover`'s "spec §2.2" lives; `docs/notifier-spec.md` has no
discover-roots section and the `CLAUDE.md` `scan.py` line does not
enumerate walked subs, so neither was edited), this ticket.

**Requests / decisions surfaced (not made here)**

1. `~/.claude/plugins/<name>/` (e.g. `ralph-wiggum`) is a third plugin
   layout D10 does not name; a `plugins/*` glob excluding `cache` and
   `marketplaces` is one line, but it is a D10 amendment.
2. Stale plugin cache versions are 42 % of walked files for 4 % of
   artifacts; walking only the newest version per
   `cache/<marketplace>/<plugin>/` (or reading `installed_plugins.json`)
   would bring the walk under budget without a cap raise. Decision, not
   mine.
3. Orchestrator: `review/patrol-findings-2026-09-18` already carries T702;
   my regions (`discover`, `_previous_fingerprints`, the `run_scan`
   resolve block) do not overlap T702's, so the merge should be clean.
