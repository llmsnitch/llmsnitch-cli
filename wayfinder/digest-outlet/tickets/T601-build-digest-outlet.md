# T601 — Build the digest outlet

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: —`
`blocks: T602`
`status: DONE (2026-09-14)`

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

## Resolution

Built on branch `digest-outlet/T601` (worktree off `main` fe00634), eight
commits 80f2d07..5f93e75; merge to `main` is T602's first step.

**Modules.** `fs_coil/ledger.py` (reader `iter_rows` + `fs-coil noise`),
`fs_coil/digest.py` (`health_report`, `render`, `cmd_digest`),
`fs_coil/digest_agent.py` (plist / `--install-agent`, split for the
250-line cap), `fs_coil/commands.py` (`prune --target`, `status` degraded
line), `fs_coil/cli.py` (dispatch + USAGE), `fs_coil/notify.py`
(`CATEGORIES["watcher_health"]`), `llmsnitch/depaudit.py` (stamps
`depaudit-state.json` on every completed run), `tests/_seams.py`
(`row`, `seed_ledger`), tests `test_notify_outlets` (19), `test_digest`
(15), `test_fs_coil_cli` (5). Spec amended first (00af9ab): §3 digest, §4
status, T007 executed, `digest_banner_threshold` removed.

**Suite.** `python3 tests/all.py` 174/174 (135 at charting; the ponytail
round folded 7 tests into 2 without losing a shape).

**Live evidence (2026-09-14, repo entry points, not the stale pipx shim).**
- `llmsnitch depaudit` stamped `~/.llmsnitch/depaudit-state.json` (0600,
  bulletin 2.7d); `fs-coil digest` wrote
  `~/Library/Logs/llmsnitch/notify/digest-2026-09-14.txt` (0600, 74 rows);
  `--show` rendered all four sections with `patrol ran 2026-09-14 09:30`
  in ①, `→ all watchers healthy`, no `watcher_health` row.
- Seeded stale bulletin (30d) under temp `LLMSNITCH_DIR` /
  `LLMSNITCH_NOTIFY_DIR` / `LLMSNITCH_HOT_STATE`: exactly one
  `watcher_health` row, `notified: true`, `first_seen`, subject
  `bulletin stale (30d)`, banner posted; healthy re-run: no new row.
- `fs-coil noise --days 7` grouped 1,041 real rows by category · actor;
  `--all --actor codex` filtered to 11. `prune --target notify --days
  3650`: 0 files pruned, 21 before / 21 after. `status` prints `degraded
  none`. `digest --install-agent` printed the plist (Hour 10, `--prune`);
  nothing installed.

**Review gates.** Standards (Sonnet): 1 hard — stamp created at umask
before chmod → `store._open_private`; 3 naming nits applied; "watchers"
vocabulary kept (CONTEXT.md's Digest entry uses it). Security (Sonnet):
MEDIUM — `noise` printed ledger subjects raw (root-observed paths can
carry escape sequences) → `ledger.clean()` shared with the digest; LOW —
degraded reason sanitized before the banner; LOW — `O_NOFOLLOW` on the
digest write. Reader, prune, health-file trust boundary, plist and
launchctl argv confirmed sound. Spec axis and ponytail: both Sonnet
reviewers died on connection drops (ECONNRESET, three times across the
session); the orchestrator ran both — spec items 1–7 checked line by line
against §2–§4, ponytail cut 140 lines (validation cascade, prune table,
test dedup). Docs agent (Haiku) delivered a mechanically verified diff.

**Deviations from the spec text, recorded in the amended spec.** The
banner goes through `notify()`, so `outlet_nc`/`enabled`/cold start gate
it too (the old text said `outlet_nc` did not); `--date` is replaced by an
injectable `now=` on the Python API; `cmd_noise` lives in `ledger.py`;
new/known/resolved are subject-level from row presence, not
`novelty_reason` (tuple-level); ② caps at 20 subjects without `--full`.

**Found along the way.**
- Fixed here (16ac284): `tests/test_llmsnitch._with_tmp_store` set only
  `LLMSNITCH_DIR`, so every suite run routed scan findings into the REAL
  notify ledger and hot state — the first real digest showed 48 "new"
  `/var/folders` subjects. Delegates to `_seams.with_tmp(store=True)` now;
  a suite run adds 0 rows. The historical tmp-path rows stay in the
  ledger and will age out at 45 days.
- Plan candidate: `~/.config/llmsnitch/` holds ~120
  `settings-snapshot-*.json`, many stamped during test runs — the
  `setup_cmd` snapshot path has the same isolation leak shape.
- Fog stays as recorded: phase-2 anomaly section, digest-hosted waiver
  review, `noise` UX after the rewrite.

Next: **T602 — Activate** (merge, `pipx install --force ~/llmsnitch-cli`,
`fs-coil digest --install-agent --write` from a plain terminal, live done
criteria, `suppress_*` config cleanup, close the map).
