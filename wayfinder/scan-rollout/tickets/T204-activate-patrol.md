# T204 — Activate the patrol on this machine

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: T201, T202`
`blocks: —`
`status: DONE (2026-08-26) — destination reached`

## Resolution

- Second merge: `decc7dc` (T202+T203) then the T204-found fix merged on
  top; **T203 rode the activation merges** — fog item "second-merge
  rhythm" resolves as: batch pending branch work into activation merges.
- **Live finding, fixed en route**: the pipx venv shipped only
  `llmsnitch/`, so the installed patrol degraded to ledger-only
  (`notify_routed: false` — the visibility we built worked). Fix: package
  `fs_coil` in the wheel (pyproject `packages`); both fs_coil copies
  converge on the same flock'd on-disk state.
- Activation: `llmsnitch patrol --write` → wrote
  `~/Library/LaunchAgents/com.slav-it.llmsnitch-patrol.plist`,
  bootstrapped `gui/502`. Kickstart verified all four criteria:
  1. scan `scan-20260826-162738`, `trigger: patrol`, 182 files.
  2. 239 `scan_finding` rows, buckets {claude-code, codex, unknown};
     **0 banners** — `cold_start_suppressed` (first day; high never
     pierces, by design); 49 hygiene rows record_only.
  3. `patrol.err` exists, 0 bytes.
  4. `scan --report` renders the patrol's findings — including a LIVE
     `drift_changed` on `~/.claude.json` between kickstarts and one
     resolved finding. Drift detection observed working in production.
- Process note: one mislabeled commit briefly landed on main (cwd slip,
  captured the user's uncommitted `.gitmodules`); reset with
  `git reset --mixed HEAD~1`, local modification preserved untouched.

## Question

Nothing to decide; the destination ticket. When T201 (merged + reinstall
mechanism known) and T202 (patrol subcommand exists) are closed:

1. If the branch advanced since T201's merge, merge to main again and
   reinstall (record whether T203 rode along — map fog "second-merge
   rhythm" resolves here; note the decision in the resolution).
2. `llmsnitch patrol` — eyeball the printed plist. Then
   `llmsnitch patrol --write` (plain terminal is fine; no sudo needed —
   user LaunchAgent).
3. Verify activation without waiting a day:
   `launchctl kickstart gui/$(id -u)/com.slav-it.llmsnitch-patrol`, then
   confirm ALL of:
   - a new scan dir exists with `meta.trigger == "patrol"`;
   - `scan_finding` rows for the run are in the notify ledger
     (`~/Library/Logs/llm-snitch/notify/events-*.ndjson`), at most one
     banner per territory bucket;
   - `~/Library/Logs/llm-snitch/patrol.err` exists and is empty (or
     explains itself);
   - `llmsnitch scan --report` renders the patrol's findings.

Done when all four verifications hold — that is the map's destination.
Record in the resolution: the kickstart output, the patrol scan-id, and
banner count observed.
