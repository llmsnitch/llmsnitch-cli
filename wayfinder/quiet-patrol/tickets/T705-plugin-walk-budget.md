# T705 — Plugin walk budget and layouts

`labels: wayfinder:grilling`
`parent: ../map.md`
`blocked by: T703`
`blocks: T704`
`status: DONE (2026-09-19)`

## Question

D10 assumed the plugin walk would stay under `_MAX_FILES = 4000` because
only ~686 of ~7,200 plugin files classify. Wrong: the budget counts files
*walked*, not yielded. T703 measured 4,709 walkable files under
`~/.claude/plugins` after junk-dir skipping, so from `$HOME` the walk now
reaches 596 of 672 classifiable artifacts and overflows by 17 files —
which 17 depends on sort order, so coverage is deterministic but
incomplete, and three `~/.claude` singles (`.claude/settings.local.json`,
`.mcp.json`, `plans/.claude/settings.local.json`) fell behind the budget
wall (D11 carries their findings forward; no tombstones).

Stale cache versions are ~42% of the walked files for ~4% of the
artifacts (six `remember` versions = 2,187 files / 31 artifacts). Decide:

1. **Budget** — (a) walk only the newest version per
   `cache/<marketplace>/<plugin>/` (newest by `installed_plugins.json`
   `installPath`, falling back to newest mtime), or (b) raise
   `_MAX_FILES` for the plugin pass only, or (c) accept 596/672 and
   record it. Recommendation at charting: (a) via `installed_plugins.json`
   — Claude Code loads exactly that path; stale dirs are dead code, and a
   planted dir is only live if the manifest points at it, which the
   manifest itself (a `claude_settings`-class artifact?) should then be
   drift-tracked.
2. **Bare layout** — `~/.claude/plugins/<name>/` (e.g. `ralph-wiggum/hooks/*`)
   was reached by the old cwd walk and is not one of D10's two root
   patterns. Add `plugins/*` as a third root (one line), excluding `cache`
   and `marketplaces` themselves?

Resolution amends D10 on the map; the code change (if any) lands as part
of T704's pre-activation step or a small follow-up commit on this branch.

## Resolution

Decided 2026-09-19 by the user (grilling Q15): **(a)** — per cached
plugin, walk only the version the harness loads, read from
`plugins/installed_plugins.json` (`installPath`), newest-mtime fallback
when the manifest is silent or unreadable; plus the bare
`plugins/<name>/` layout as a third root class (`cache`, `marketplaces`
and the harness's own `data/` dir excluded). No cap change. D10 amended.

Built on this branch (`scan._plugin_roots`, +1 test in
`tests/test_scan_scope.py`). Two things surfaced while measuring:

- **cwd == $HOME starved the plugin pass.** The spec-review reorder
  (cwd walk before plugins) meant the patrol's `_walk(~/.claude)` spent
  the whole budget on `file-history/` and `projects/` before any plugin
  root ran (live: plugins back to 74, overflow 26). The cwd `.claude` /
  `.agents` sub-walk is now skipped when that path *is* a territory root
  — the territory passes cover it. Three incidental files the old whole-
  tree walk reached (`~/.claude/.claude/settings.local.json`,
  `~/.claude/.mcp.json`, `~/.claude/plans/.claude/settings.local.json`)
  are now permanently out of scope: none is a file the harness reads,
  D11 carries their open findings forward, no tombstones.
- **Symlink siblings win mtime ties.** A symlinked version dir shares
  its target's mtime and sorted after it; symlinks are excluded from the
  version candidates (they are skipped as roots anyway).

Measured from `$HOME`, read-only `discover()`:

| | before T703 | T703 | T705 |
|---|---|---|---|
| targets | 204 | 723 | 850 |
| plugin artifacts | 74 | 596 | 613 |
| budget overflow | 2 | 17 | 0 |

`ralph-wiggum/hooks/*` (bare layout) reached again. Suite 203 → 204.
