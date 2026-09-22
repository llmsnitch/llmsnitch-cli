# T802 — Activate quiet light

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: T801`
`blocks: —`
`status: OPEN — the user's to run (plist edit + launchctl from a plain terminal)`

## Question

Execution (D06). The live light agent must run the gated code. It currently
runs the root-owned Aug 26 tree via `/usr/local/bin/fs-coil`; the fix is to
point the user LaunchAgent at the pipx install, which tracks `main`. No
sudo, no `install.sh`.

1. Merge `feature/reduce-notification-noise` into `main` (`~/llmsnitch-cli`)
   and reinstall: `pipx install --force ~/llmsnitch-cli`. Check
   `~/.local/bin/fs-coil --help` runs.
2. Edit `~/Library/LaunchAgents/com.slav-it.fs-coil.plist`:
   `ProgramArguments[0]` from `/usr/local/bin/fs-coil` to
   `$HOME.local/bin/fs-coil` (launchd does not expand `~`).
3. Reload the agent:

   ```bash
   launchctl bootout gui/$(id -u)/com.slav-it.fs-coil
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.slav-it.fs-coil.plist
   ps -axo pid,command | grep '[f]s-coil light-agent'     # must show .local/bin
   ```

   Expect **no** "armed" banner (D05); the startup line appears in
   `fs-coil logs`.
4. Smoke, from a plain terminal:
   - `touch ~/.claude/settings.json` → `fs-coil noise` shows
     `agent_self · claude-code`, no banner.
   - `touch ~/.ssh/quiet-light-probe && trash ~/.ssh/quiet-light-probe` →
     one `deny_write · unknown` banner naming the path and the action; the
     second touch within the hour is `window_repeat`, no banner.
5. Close criteria (close the map when all hold):
   - the next day with plugin auto-update churn (`temp_git_*` bursts in
     `fs-coil logs`) produces **zero** `fs-coil (light)` banners;
   - the same day's `events-*.ndjson` holds `fs-coil-light` rows for those
     writes, and the 10:00 digest's ③ counts show
     `agent_plugin_cache · claude-code`;
   - the `deny_write` probe above banners exactly once;
   - `fs-coil status` shows `degraded none`;
   - map status → CLOSED, fog carried forward, resolution on T801–T802.

## Resolution

<!-- filled on completion -->
