# T802 — Activate quiet light

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: T801`
`blocks: —`
`status: ACTIVATED (2026-09-22 21:30) — closes when the next day of plugin churn produces zero light banners`

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

## Resolution (activation, 2026-09-22 21:30)

- **Two corrections to the steps above, learned live.** (a) `launchctl
  kickstart -k` restarts the process but does **not** re-read the plist —
  launchd kept `program = /usr/local/bin/fs-coil` and the Sep 15 pid.
  The reload is `bootout` + `bootstrap`. (b) `~/.ssh/**` is a read-only
  deny rule; a write probe there never matches in light mode. The live
  `deny_write` probe is `touch ~/.config/gh/quiet-light-probe && trash …`
  (`~/.config/**` is RW and `~/.config/gh` is watched).
- **The user's first attempt did not land**: pipx venv untouched since
  09-19 12:11, launchd definition stale, pid 24035 from 09-15. Re-ran from
  this session: `pipx install --force ~/llmsnitch-cli` (21:30:27, installed
  `light_watcher.py` byte-identical to main), `bootout` + `bootstrap`
  (21:30:41 stopping / 21:30:44 starting). `launchctl print` now shows
  `program = $HOME.local/bin/fs-coil`, pid 24990 under
  Homebrew Python 3.14; fswatch child respawned. No armed banner
  (`terminal-notifier -list ALL | grep -c armed` → 0).
- **Smoke** (ledger `events-2026-09-22.ndjson`, first `fs-coil-light` rows
  ever): `touch ~/.claude/settings.json` → `agent_self · claude-code ·
  first_seen · notified=false · record_only=true`, no banner. Probe in
  `~/.config/gh` → `deny_write · unknown · first_seen · notified=true`, one
  banner `🐍 unknown · deny_write` naming path, event, rule, action; the
  removal 3 s later → `window_repeat · notified=false`. Hot state has
  `agent_self|claude-code` and `deny_write|unknown`; `degraded none`.
  Criteria 3 and 4 ✓ tonight.
- **Observation, not a defect**: the trash of the probe logged
  `event=created` — `kind = flags[0]` and fswatch put `Created` first on a
  create+remove pair. Cosmetic; fog if it ever misleads a decision.
- **Pending**: criteria 1–2 need a day of `temp_git_*` churn (bursts land
  around 11:50 / 12:xx / 15:xx / 19:xx) with zero light banners and the
  10:00 digest ③ showing `agent_plugin_cache · claude-code`. Close the map
  then.
