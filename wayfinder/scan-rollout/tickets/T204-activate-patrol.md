# T204 — Activate the patrol on this machine

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: T201, T202`
`blocks: —`
`status: CLAIMED (2026-08-26, session 99b5a6f6)`

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
