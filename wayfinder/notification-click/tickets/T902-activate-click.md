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

Done when: a banner posted by the **installed** tree, clicked, opens the
current `digest-YYYY-MM-DD.html` in the default browser, and the next
10:00 digest run writes both the `.txt` and its `.html` twin. (The
system-log criterion is dropped — D08: a real click logged nothing.)
Then close the map.

Evidence so far (banners posted from the repo tree, not the install):
2026-09-23 — `.txt` target clicked, opened VS Code (led to D01-amended);
2026-09-26 — browser-twin banner clicked, opened `digest-2026-09-26.html`
in the default browser (user confirmed). Mechanism proven; what remains
is the installed-tree click after merge + reinstall.

## Answer

<!-- filled at resolution -->
