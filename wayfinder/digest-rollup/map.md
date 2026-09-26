# Digest Rollup — Wayfinder Map

`label: wayfinder:map`
`status: ACTIVATED (2026-09-26 13:05; T1001 done, T1002 live on the pipx tree) — closes on the 09-27 and 09-28 10:00 digests`

## Destination

**Section ② of the digest lists only subjects that carry a decision.** A
day of Claude Code plugin-cache churn shows up in the digest as one ③
count line and, at most, ④ noisiest entries — never as twenty ② lines
that push a real `deny_write` or `scan_finding` under the `--full` cap. The
map closes when [T1002](tickets/T1002-activate-digest-rollup.md)'s done
criteria hold: two consecutive 10:00 digests whose ② contains no
`agent_plugin_cache` / `agent_self` lines, whose header still accounts for
them, and whose ③ still counts them.

## Notes

- **Tracker location**: `wayfinder/digest-rollup/` on branch
  `feature/reduce-notification-noise` in the worktree
  `~/.supacode/repos/llmsnitch-cli/feature/reduce-notification-noise`.
  Merging to `main` (canonical, `~/llmsnitch-cli`) is the user's call.
- **Origin**: the first fog item of `wayfinder/quiet-light/map.md`
  (closed 2026-09-26), measured at its close: four digests (09-23 → 09-26)
  each spend 22–23 of ~50 lines on one `temp_git_<ts>_<rand>/.git/{config,
  hooks/*.sample,…}` clone under `[LESSER] agent_plugin_cache`, then
  `… 47 more (fs-coil digest --full)`. The 20-row cap holds; ② is
  unreadable for lesser rows, and a real HIGH line sits one screen above
  twenty benign ones.
- **Machine facts (2026-09-26, read-only)**: digest 09-25 — 171 rows in
  window; ② header `(67)` of which 66 are `agent_plugin_cache`; ③
  `agent_plugin_cache · claude-code 154 66/0/132`, `scan_finding ·
  claude-code 16 1/7/2`, `deny_write · unknown 0 0/0/2`; ④ four
  `temp_git_*/.git/config` lines at 14–15 rows each plus one
  `hook_unquoted_var`. The "resolved" 132 is the previous window's clones
  being trashed — meaningless for churn, cosmetic. The one HIGH ② line
  that day was `scan_finding · drift_added:
  ~/.claude/plugins/cache/claude-plugins-official/playwright/<hash>/.mcp.json`
  — a plugin version bump creating a new versioned root, which is a
  **config-audit** question (see Out of scope).
- **Renderer facts**: `fs_coil/digest.py` is 231 / 250 lines. ② is built
  from `new = {k for k in first if k not in seen}` with
  `_key(r) = (category, actor_bucket, subject)`; `items` sorted by
  `_tier`; the same `new` set feeds ③'s `new/known/resolved` counts, so
  any ② filter must be applied at `items`, not at `new`. Category
  decision lines come from `notify.CATEGORIES[cat][2]`; three categories
  have an action string beginning `none` (`agent_self`,
  `agent_plugin_cache`, `agent_signed_self_read`). Test helpers:
  `tests/test_digest._render(window, lookback, prior, full, **health)`,
  `_seams.row(ts, cat, subject, actor_bucket, **kw)`.
- **Spec anchor**: `docs/notifier-spec.md` §3 ② — "ordered critical →
  high → lesser (low severity / `record_only`, i.e. new unattested
  agents, dep-audit lesser findings)". Lesser rows *with* a decision
  (waive or act) are ② material by design; the rollup must not drop
  them.
- **Repo policy**: local-only git; `trash`, never `rm`; never run
  `install.sh`; stdlib only, Python 3.9+; `python3 tests/all.py` is the
  gate (208 at charting); 250-line cap per `fs_coil` file; every rendered
  digest line passes AGENTS.md's Decision / Actor / Novelty test;
  subjects are hostile → `ledger.clean()` on anything printed.

## Decisions so far

<!-- one line per closed ticket: gist + link -->

- Charting (2026-09-26, recommendations recorded; the user can overturn
  before T1001 builds): **D01 the unit of ② is the decision, not the
  subject.** ② is "new since last digest" *for the reader to act on*; a
  category whose decision line reads `none — digest only` has, by its own
  definition, nothing for ② to say — it already names ③ and `fs-coil
  noise` as its home. **D02 the cut is category-level, derived from the
  table**: ② skips subjects whose `CATEGORIES[cat][2]` starts with
  `none` (`_NO_DECISION`, computed, no new list to maintain); the ②
  header becomes `② new since last digest (N · M digest-only, see ③)`
  when M > 0 so the count still reconciles with ③. `record_only` rows of
  other categories (dep-audit lesser findings, `unattested_agent_*`,
  scan info/low) stay in ② — they carry waive-or-act decisions (spec §3).
  **D03 rejected: subject class-collapse** (`temp_git_<ts>_<rand>` →
  `temp_git_*`, versioned plugin roots → `<plugin>/*`) — a read-side regex
  table to maintain, still ~17 lines per clone unless the whole path after
  the class is collapsed too, and the same rule applied to `scan_finding`
  subjects would merge findings that must stay distinct (`(rule_id,
  artifact)` is the waiver key). Kept as the upgrade path for ④ only, if
  ④ ever proves unreadable. **D04 rejected: producer-side subject
  normalization** in `light_watcher.route_hit` — mutates the cold trail;
  the ledger subject is the forensic path. **D05 ③ and ④ unchanged**: ③
  already shows `agent_plugin_cache · claude-code 154 66/0/132` and is
  where the rolled-up count lives; ④ listing four `temp_git_*/.git/config`
  lines *is* ④ doing its job (noisiest subjects). The inflated `resolved`
  for churn is cosmetic — fog. **D06 spec §3 ② amended in one sentence**,
  no other doc moves; `digest.py` grows ≤ 5 lines net. **D07 phase 2 is
  not touched**: the μ+2σ anomaly section (spec, deferred) remains the
  designed home for "volume" questions; this map is about ② readability
  only.

- [T1001 — ② lists decisions only](tickets/T1001-section-two-decisions-only.md)
  — done 2026-09-26 by one task agent per `dispatch.md` (branch
  `digest-rollup/T1001`, `7488fc4`, four commits on base `b25ce61`).
  `_NO_DECISION` derived from `notify.CATEGORIES`; ② filters at `items`,
  header `(N · M digest-only, see ③)`; +3 net lines (`digest.py` 234), 2
  tests (suite 208 → 210), spec §3 ② one sentence. Read-only replay of the
  09-24 → 09-25 window: ② 25 lines → 3, header `(1 · 66 digest-only, see
  ③)`, ③ and ④ byte-identical to the shipped digest. Orchestrator
  re-verified log, base, diff, and gate in the agent worktree before the
  ff-merge; inline review (table row 1) found nothing to change.
- [T1002 — Activate digest rollup](tickets/T1002-activate-digest-rollup.md)
  — activated 2026-09-26 13:05 by the orchestrator: `pipx install --force`
  (installed `digest.py` diff-clean against main `3bcd53e`), one foreground
  `fs-coil digest`: ② `(2 · 131 digest-only, see ③)` with only the two HIGH
  groups; ③ 101 + 30 no-decision new subjects = 131, reconciles; no
  re-page. Closes on the 09-27 / 09-28 scheduled digests.

## Tickets

- [T1001 — ② lists decisions only](tickets/T1001-section-two-decisions-only.md)
- [T1002 — Activate digest rollup](tickets/T1002-activate-digest-rollup.md)

## Not yet specified

- **③ `resolved` under churn** — 132 "resolved" `agent_plugin_cache`
  subjects a day are trashed temp clones, not resolutions. Whether ③
  should print `—` for resolved on no-decision categories, or leave the
  number as a churn indicator. Fog until someone misreads it.
- **④ class rollup** — D03's regex, applied to ④ only, if four
  `temp_git_*/.git/config` lines a day stop being informative. Decide
  after two weeks of reading ④ with light rows in it.
- **Plugin version bumps as `drift_added`** — every
  `plugins/cache/<marketplace>/<plugin>/<hash>/` root a plugin update
  creates fingerprints fresh and lands in ② as HIGH `scan_finding`
  (playwright 09-24, 09-25, 09-26). Correct today (a new control surface
  appeared); whether T705's "installed version only" rule should also
  carry the *previous* version's fingerprints forward is a config-audit
  map's question, not this one's.
- **`fs-coil noise` default filter** — with ② no longer listing
  no-decision categories, `fs-coil noise` (which hides `notified` rows by
  default) is the only place to read them individually; whether its
  default grouping should lead with them is fog until it is used that way.

## Out of scope

- **Any change to what is ledgered** (D04) — the cold trail keeps the
  exact path; rollup is a read-side concern.
- **Any change to `notify.py`** — the category table's action strings
  are already the signal; the digest reads them.
- **Config-audit scope for versioned plugin roots** — a scan surface
  decision (`wayfinder/quiet-patrol` D10/T705 lineage), filed as fog above.
- **Phase-2 anomaly section** (D07).
