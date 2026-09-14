# T601 — Build the digest outlet

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: —`
`blocks: T602`
`status: OPEN`

## Question

Execution (AFK, orchestrator + subagents). Every design decision is made
(map Decisions-so-far); the spec is amended first, then built against.

0. **Spec amendment** (`docs/notifier-spec.md` §"Delivery outlets" 2–3 and
   T007): schedule 10:00 after the patrol; trailing-24h content (since the
   previous digest file's timestamp, else 24h); health-only banner
   (degraded flag / patrol missed / bulletin stale) replacing the
   20-rows/category threshold — `outlet_digest` now gates *that* banner;
   content order ①–④ per the map; pipx path `~/.local/bin/fs-coil`; T007
   marked "executed by T601, dashboard pane dropped". Commit before code.
1. **Shared ledger reader** (`fs_coil/ledger.py` or equivalent): iterate
   rows across daily `events-*.ndjson` files for a time range; tolerant of
   garbage lines (the ledger is 0600 user-owned but treat it as hostile
   input anyway — never raise, count skipped lines).
2. **`fs-coil digest [--full] [--show] [--prune]`**: writes
   `~/Library/Logs/llmsnitch/notify/digest-YYYY-MM-DD.txt` (0600,
   unconditional). Sections: ① health — last patrol time (from the newest
   `~/.llmsnitch/scans/*/meta.json`), dep-audit last run + bulletin age
   (from a small state file the dep-audit run stamps, e.g.
   `~/.llmsnitch/depaudit-state.json` — **fs_coil must not import
   llmsnitch**; producers stamp, the digest reads), degraded flag
   (`notify.get_degraded()`); ② new since last digest with decision lines
   from `CATEGORIES`; ③ counts per category × actor_bucket with
   new/known/resolved; ④ five noisiest subjects. `--show` prints the
   latest digest; `--full` lifts the one-screen cap; `--prune` runs the
   notify prune after writing (so one plist command does both).
3. **Health banner**: iff `[notify] outlet_digest` (default true) and any
   health condition holds, route ONE banner through `notify()` under a new
   `CATEGORIES` row (e.g. `watcher_health`: 24h window, high, action
   `fs-coil digest --show`). Findings never banner from the digest.
4. **T007 leftovers**: `fs-coil noise [--category] [--actor] [--days]
   [--all]` over the ledger (spec §2 signature); `fs-coil prune --target
   notify|logs [--days N]` (notify default 45; no `--target` keeps today's
   meaning); `fs-coil status` prints the degraded flag.
5. **LaunchAgent generator**: `fs-coil digest --install-agent [--write]`
   mirroring `llmsnitch/patrol.py` (print by default; `--write` writes +
   bootstraps `com.slav-it.llmsnitch-digest`, 10:00, runs
   `~/.local/bin/fs-coil digest --prune`).
6. **Tests** (stdlib runner, register in `tests/all.py`): fixture ledgers
   (synthetic — never copy real subjects); renderer returns strings; each
   health condition alone triggers the banner and a healthy day is silent;
   new/known/resolved classification; noise filters compose as AND; prune
   never touches non-matching names or paths outside the dir; digest file
   0600; suite green.
7. **Docs**: README command list, `fs_coil/AGENTS.md`, CLAUDE.md commands
   block.

Done when: suite green with the new modules registered; against the REAL
ledger `fs-coil digest --show` renders the four sections with today's
patrol visible in health; a seeded stale-bulletin state file under temp
`LLMSNITCH_DIR`/`LLMSNITCH_NOTIFY_DIR` produces exactly one
`watcher_health` ledger row + banner, and the healthy re-run produces none;
review gates run (two-axis, ponytail, one security pass on the reader and
prune) with confirmed findings applied; Resolution records module list,
test counts, evidence, and any spec deviations. Do not install the
LaunchAgent or reinstall pipx — that is T602.
