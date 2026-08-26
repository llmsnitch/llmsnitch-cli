# Scan Rollout — Wayfinder Map

`label: wayfinder:map`
`status: OPEN`

## Destination

The **config-audit surface running unattended on this machine**: branch
merged to main and reinstalled, a daily **patrol** (LaunchAgent
`com.slav-it.llmsnitch-patrol`) firing `llmsnitch scan --patrol` from
`$HOME`, its first run recorded in the scan ledger with
`trigger: patrol` and its findings riding the notify layer as
`scan_finding` rows. The map closes when
[T204](tickets/T204-activate-patrol.md)'s done criteria hold.

## Notes

- **Tracker location (standing rule)**: this map and its tickets live in
  `wayfinder/scan-rollout/` inside the feature worktree
  (`~/.supacode/repos/llmsnitch/research/scanner-survey-mvp`), committed to
  branch `research/scanner-survey-mvp`. Never work in `~/Repos/llmsnitch`.
- **Skills**: `mattpocock-skills:grilling`,
  `mattpocock-skills:domain-modeling`, plus the repo's review gates
  (`review` two-axis, `ponytail:ponytail-review`) after execution tickets.
- **Plan-vs-do override**: T201–T204 carry execution — the destination is a
  working patrol, not a spec (same override as the harness-team map).
- **Repo policy**: local-only git (no remote/push — memory
  `llmsnitch-git-local-only`); `trash`, never `rm`; never run `install.sh`;
  stdlib-only + no-network are test-enforced.
- **Vocabulary**: **Patrol** is canon (CONTEXT.md) — an unattended scheduled
  run of the config-audit surface. A manual `scan` is not a patrol.
- **Grounding doctrine**: every page passes AGENTS.md Decision/Actor/Novelty;
  scan_finding stays quiet-by-design (spec category table) — the patrol adds
  cadence, never volume.

## Decisions so far

<!-- one line per closed ticket: gist + link -->

- Grilling round 1+2 (pre-charting, recorded here since they shaped the map):
  destination = operational rollout (a); track B out of scope; scheduled
  scans + rule-pack in, redact-retroactive out; merge is the first ticket;
  effort name `scan-rollout`; patrol = daily StartCalendarInterval from
  `$HOME` with default roots; installer = new `llmsnitch patrol`
  subcommand (print / `--write`, no inside-CC guard needed — the plist does
  not wire the monitored agent's own hooks); ledger stamps
  `meta.trigger = patrol|manual`; plist logs to
  `~/Library/Logs/llm-snitch/patrol.err`; staleness detection deferred to
  fog.

## Not yet specified

- **Patrol staleness detection** — "no patrol in >48h" is invisible until an
  outlet exists to surface it; graduates when track B's digest/dashboard
  (T007) lands. The plist's stderr log is the interim breadcrumb.
- **Project-directory patrols** — per-repo scanning (cwd-scoped) beyond the
  home territories; question isn't sharp until home patrol behavior is
  observed for a while (noise level, runtime).
- **Second-merge rhythm** — whether T202/T203 merge to main individually or
  ride T204's activation merge; decide when T204 is claimed.

## Out of scope

- **Track B (T005–T007 live-install migration)** — own handoff, own rhythm,
  needs sudo; scan findings' digest recall arrives with it independently.
- **`redact-retroactive`** — session-ledger hygiene, not config-audit; a
  future effort (PORT_INDEX rank-2 keeps the pointer).
- **Digest recall of scan findings** — consequence of track B being out of
  scope: NC banners + `scan --report` are the outlets until T007 exists.
- **`llm-snitch` → `llmsnitch` namespace rename** — a full migration handoff
  exists (scratchpad `handoff-drop-dash.md`, session
  `99b5a6f6-d9b4-4b7d-9218-413cca01f7bb`); recommended sequencing is AFTER
  track B. T202/T204 deliberately use the hyphenated live paths
  (`~/Library/Logs/llm-snitch/`) — the rename effort migrates them.
