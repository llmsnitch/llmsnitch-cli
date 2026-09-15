# T602 — Activate the digest outlet

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: T601`
`blocks: —`
`status: DONE (2026-09-14)`

## Question

Execution: reinstall (`pipx install --force ~/llmsnitch-cli` — never the
stale `~/Repos/llmsnitch` clone), install the digest LaunchAgent from a
plain terminal (`fs-coil digest --install-agent --write`), and verify live.
Also finish T007's one live-config step if still pending: `grep -E
"^\s*suppress_" ~/.config/llmsnitch/config` must return nothing (delete
the keys, write no replacements). Done criteria (close the map when all
hold):

1. `launchctl print gui/$(id -u)/com.slav-it.llmsnitch-digest` exits 0
   and a kickstart writes today's digest file (0600) with the 09:30 patrol
   visible in ① health; the user has read one real digest.
2. A healthy day posts no banner; a seeded unhealthy condition (temp dirs)
   posts exactly one `watcher_health` banner, ledgered.
3. `fs-coil prune --target notify` ran (via `--prune`) and left the
   45-day window intact; `fs-coil noise` and `fs-coil status` work from
   the installed binary.
4. Map status → DONE; fog items carried forward as recorded.

## Resolution

Activated 2026-09-14 23:10 EDT, same session as T601 at the user's
direction ("continue"), from the Claude Code session — the digest agent
does not wire the monitored agent's own hook config, so no plain-terminal
guard applies (same reasoning as `llmsnitch patrol`).

- **Merge**: `main` fast-forwarded to the T601 branch (7501264 at claim,
  this commit on top). `pipx install --force ~/llmsnitch-cli` → `fs-coil`
  and `llmsnitch` shims refreshed; `fs-coil --help` lists `digest`.
- **LaunchAgent**: `fs-coil digest --install-agent --write` wrote
  `~/Library/LaunchAgents/com.slav-it.llmsnitch-digest.plist` and
  bootstrapped it; `launchctl print gui/$(id -u)/com.slav-it.llmsnitch-digest`
  exits 0 (program `~/.local/bin/fs-coil`, daily 10:00). Kickstart wrote
  `~/Library/Logs/llmsnitch/notify/digest-2026-09-14.txt` (0600, 74 rows),
  `digest.out` = "digest written … / pruned 0 notify file(s) older than 45
  day(s)", `digest.err` empty. ① shows `patrol ran 2026-09-14 09:30`,
  `dep-audit ran 18:48 · bulletin 2.7d`, `degraded none`, no banner, no
  `watcher_health` row in the real ledger.
- **Banner both ways (installed binary, temp dirs)**: stale bulletin →
  exactly one `watcher_health` row, `notified: true`, banner posted;
  healthy re-run → no new row.
- **Retention / recall / status** from the installed binary: `--prune` ran
  inside the kickstart and kept all 21 files (oldest `events-2026-08-26`);
  `fs-coil noise --days 2` grouped 33 claude-code rows with dated
  timestamps; `fs-coil status` prints `degraded none`; `llmsnitch depaudit`
  stamped the state file (15 intakes, bulletin 2.9d).
- **T007 live-config step**: the `suppress_claude_self` key and its
  comment block are deleted from `~/.config/llmsnitch/config` `[notify]`
  (grep for `^\s*suppress_` returns nothing); no replacement keys written.
  Pre-edit copy kept in the session scratchpad only.

Human step left: read one real digest — `fs-coil digest --show`. The next
scheduled run is 10:00 tomorrow, half an hour after the patrol.

Map → DONE. Fog carried forward unchanged: phase-2 anomaly section
(2026-10 at the earliest), digest-hosted waiver review, `noise` UX.
