# T1002 — Activate digest rollup

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: T1001`
`blocks: —`
`status: ACTIVATED (2026-09-26 13:05) — closes on two consecutive scheduled 10:00 digests (09-27, 09-28)`

## Resolution (activation, 2026-09-26)

- **Executed by the orchestrator** (user asked for T1001 → T1002 in-session):
  `main` ff'd to `3bcd53e` (T1001 + map), `pipx install --force
  ~/llmsnitch-cli` at 13:05:44 — installed `fs_coil/digest.py` mtime
  13:05:44, `diff` clean against main. The digest LaunchAgent already runs
  `~/.local/bin/fs-coil`, so no plist work.
- **Foreground `fs-coil digest`** (rewrote today's file over the window
  2026-09-25 10:00 → 2026-09-26 13:05, 306 rows): ② header **`(2 · 131
  digest-only, see ③)`**, body = `[HIGH] scan_finding` (playwright
  `drift_added`) + `[HIGH] watcher_health` (bulletin stale); **no
  `agent_plugin_cache` / `agent_self` lines**. ③ `agent_plugin_cache ·
  claude-code 242 101/0/66`, `agent_self · claude-code 46 30/1/0` — 101 +
  30 = 131, the header reconciles. ④ unchanged in shape (four
  `…/.git/config` at 15 rows). Ledger tail: `watcher_health ·
  window_repeat · notified=false` — the health banner rule did not re-page.
- **Pending**: close criteria need the scheduled 10:00 digests of 09-27
  and 09-28 (window now starts at today's 13:05 rewrite — no gap, no
  double count). `fs-coil noise --category agent_plugin_cache --days 1`
  recall unchanged (read side of the ledger, not the digest).

## Question

Execution. The 10:00 digest LaunchAgent (`com.slav-it.llmsnitch-digest`)
already runs `~/.local/bin/fs-coil digest --prune` — the pipx shim — so
activation is a reinstall, no plist work.

1. Merge into `main` (`~/llmsnitch-cli`), then `pipx install --force
   ~/llmsnitch-cli`. Verify with a file mtime, not the shell's word:
   `ls -laT "~/Library/Application Support/pipx/venvs/llmsnitch/lib/python3.14/site-packages/fs_coil/digest.py"`
   must show today's time and the file must diff clean against main.
2. Optional same-day check: `fs-coil digest` (foreground, writes today's
   file again over the same window; the health banner rule is unchanged,
   so it banners only if a watcher is unhealthy) then `fs-coil digest
   --show` — ② should have no `agent_plugin_cache` / `agent_self` lines
   and a `digest-only, see ③` header.
3. Close criteria (close the map when all hold):
   - two consecutive scheduled 10:00 digests whose ② contains no
     no-decision category lines, whose header shows `· M digest-only,
     see ③` with M matching ③'s new counts for those categories, and
     whose decision-bearing lines (`scan_finding`, `deny_write`,
     `depaudit_finding` …) are all visible above the cap;
   - ③ still lists `agent_plugin_cache · claude-code` with its daily
     count; `fs-coil noise --category agent_plugin_cache --days 1` still
     recalls the individual subjects;
   - `python3 tests/all.py` green from the installed source;
   - map status → CLOSED, fog carried forward, resolution on T1001–T1002.

## Resolution

<!-- filled on completion -->
