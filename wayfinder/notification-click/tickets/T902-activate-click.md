# T902 — Activate the click action

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: T901`
`blocks: —`
`status: OPEN`

## Question

The user's ticket (merge and reinstall are theirs, not the orchestrator's).

1. Merge `feature/notification-click-action` to `main`; `pipx install
   --force ~/llmsnitch-cli`.
2. **One installed tree** (shared with quiet-light T802): the light
   LaunchAgent `com.slav-it.fs-coil` runs `/usr/local/bin/fs-coil
   light-agent` (root-owned tree, 2026-08-26). Either repoint its
   `ProgramArguments` at `~/.local/bin/fs-coil` and `launchctl kickstart
   -k gui/$(id -u)/com.slav-it.fs-coil`, or re-sync the `/usr/local`
   tree from the repo. Decide once with T802; record the policy in
   whichever map activates first.
3. Wait for a real banner (the next `scan_finding` page, or the digest's
   `watcher_health` if a health condition holds), click it.

Done when: the current `digest-YYYY-MM-DD.txt` opens in the default text
editor; `log show --predicate 'process == "terminal-notifier"' --last
1h` records the open; `terminal-notifier -list ALL` shows no banner
carrying the old `com.apple.Terminal` sender behaviour (i.e. every
post-reinstall banner is clickable). Then close the map.

## Answer

<!-- filled at resolution -->
