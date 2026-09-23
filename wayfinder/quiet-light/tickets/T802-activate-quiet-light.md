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

1. ✅ 2026-09-22 20:25 — `main` fast-forwarded to T801 (`~/llmsnitch-cli`),
   suite green from main, wheel builds. ✅ Plist
   `~/Library/LaunchAgents/com.slav-it.fs-coil.plist` `ProgramArguments[0]`
   repointed to `$HOME.local/bin/fs-coil` (launchd does not
   expand `~`). The running process is still the old tree until step 3.
2. Before-picture (optional): `terminal-notifier -list ALL | grep -c
   'fs-coil (light)'` — ~100 undismissed plugin-cache banners from today.
   Reinstall: `pipx install --force ~/llmsnitch-cli`; check
   `~/.local/bin/fs-coil --help` lists `light-agent`.
3. Restart the agent so launchd re-reads the plist:

   ```bash
   launchctl kickstart -k gui/$(id -u)/com.slav-it.fs-coil
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
