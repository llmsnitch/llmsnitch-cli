# T602 — Activate the digest outlet

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: T601`
`blocks: —`
`status: CLAIMED (2026-09-14, session 60f63e38)`

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
