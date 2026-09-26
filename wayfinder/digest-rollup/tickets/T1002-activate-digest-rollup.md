# T1002 — Activate digest rollup

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: T1001`
`blocks: —`
`status: OPEN — the user's to run (merge + reinstall from a plain terminal)`

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
