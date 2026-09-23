# Quiet Light — Wayfinder Map

`label: wayfinder:map`
`status: CHARTED (2026-09-22); T801 DONE, T802 activate is the user's — map closes on T802's criteria`

## Destination

**Every fs-coil light banner passes the three actionability gates.** The
light watcher's deny hits flow through `fs_coil.notify.notify()` like every
other surface: a Claude Code plugin-cache write is an `agent_plugin_cache`
row in the ledger and a line in the daily digest, never a banner; a write to
`~/.zprofile` or `~/.ssh/config` by an unattributable actor is one
`deny_write` banner per hour, not one per file. The map closes when
[T802](tickets/T802-activate-quiet-light.md)'s done criteria hold: a full
day of plugin-cache churn produces zero light banners, the same events are
visible in `fs-coil noise` and digest ③, and a synthetic out-of-territory
write still pages.

## Notes

- **Tracker location**: `wayfinder/quiet-light/` on branch
  `feature/reduce-notification-noise` in the worktree
  `~/.supacode/repos/llmsnitch-cli/feature/reduce-notification-noise`.
  Merging to `main` (canonical, `~/llmsnitch-cli`) is the user's call.
- **Origin**: 2026-09-22 19:00 — Notification Center full of
  `🐍 fs-coil (light) · W` banners for
  `~/.claude/plugins/cache/temp_git_*/.git/hooks/*.sample`, `event: created`.
  The exact class `AGENTS.md` names as the grounding failure (2026-08-18,
  five pages for the plugin installer). Four weeks later it is 534 in a day.
- **Machine facts (2026-09-22, read-only)**:
  - Live light agent: `com.slav-it.fs-coil` → `/usr/local/bin/fs-coil
    light-agent` under system Python 3.9, importing the **root-owned Aug 26
    tree** `/usr/local/share/llmsnitch/fs_coil/` (still has the deleted
    `agent_registry.py`, `bridge.py`). `light_watcher.py` there is
    byte-identical to the repo's — the file never changed after vendoring.
    Deep daemon `com.slav-it.llmsnitch` is **not loaded**.
  - pipx install `~/.local/bin/fs-coil` (plan 010) tracks main and is
    user-owned; the LaunchAgent does not use it.
  - Light log `~/Library/Logs/llmsnitch/fs-coil/fs-coil-2026-09-22.log`:
    542 DENY-MATCH rows, 542 unsuppressed → 542 banners. By pattern:
    308 `/**/.git/hooks/**`, 200 `/**/.git/config`, 26
    `/**/.github/workflows/**`, 8 `/**/.claude/settings.json`. 534 under
    `~/.claude/plugins/cache/` (14 distinct `temp_git_*` clones, bursts at
    11:50 / 12:xx / 15:xx / 19:0x = plugin auto-update). Prior days:
    613 / 149 / 96 / 201 / 150 / 296 unsuppressed. Only three
    out-of-territory hits all week: `~/.zprofile`, `~/.profile`, one
    project `.claude/settings.json` — those are the rows worth a banner.
  - Notify ledger `events-2026-09-22.ndjson`: 17 rows, **all
    `config-audit`**. Zero `fs-coil-light` rows have ever been written. Hot
    state `install_ts` = 2026-08-26 (cold start long over); tuples are
    `scan_finding|*` only.
- **Why (root cause)**: `docs/notifier-spec.md` T005 — "wire fs-coil light
  + deep through `notify()`" — was parked as "Track B, needs sudo"
  (`wayfinder/scan-rollout/map.md`, `rd-triage/map.md`) and never executed.
  The light watcher still calls the legacy `Notifier` directly: 60 s
  in-memory cooldown keyed on the full path (every `.sample` is a new key),
  no category, no actor, no novelty window, no ledger row. The ponytail
  audit (`53b1ab4`) then deleted `agent_registry.py` as dead code because
  nothing called it. The T001 stopgap (`[notify] suppress_*` globs) was
  deleted from live config by T602 with nothing wired in its place — so
  since 2026-09-14 the light surface has had **no gate at all**.
- **Repo policy**: local-only git; `trash`, never `rm`; never run
  `install.sh`; stdlib only, Python 3.9+; no network imports
  (test-enforced); files 0600 / dirs 0700; `hook.handle` never raises;
  gate exit codes `0/1/2`; `python3 tests/all.py` is the gate (204 at
  charting); 250-line cap per `fs_coil` file (`notify.py` is a pre-existing
  418 — do not grow it); `fs_coil` never imports `llmsnitch`.
- **Vocabulary (CONTEXT.md, added at charting)**: **Territory** — the
  registered path prefixes an agent owns; light mode's only actor signal.

## Decisions so far

<!-- one line per closed ticket: gist + link -->

- Charting (2026-09-22, recommendations recorded; the user can overturn any
  before T802): **D01 the fix is the missing gate, not a new rule.** No
  suppress glob, no `.sample` special case, no `plugins/cache` in
  `NOISE_PATH_SUBSTRINGS` — a `.git/hooks/**` write by an unattributable
  actor is exactly the backdoor the rule exists for; what makes today's
  rows silent is *who* (Claude Code, in its own territory), which only the
  notify layer can express. **D02 wire light through `notify()`** (spec
  T005, light half): every deny hit becomes one `notify("fs-coil-light",
  category, subject=tilde path, actor_bucket, deny_pattern=hit)` call.
  Attribution is path-only (spec's named ceiling): path inside a
  territory → that agent; inside its cache paths → `agent_plugin_cache`;
  else `agent_self`; outside every territory → `deny_write`, bucket
  `unknown`. **D03 low severity never banners**: the spec's category table
  says "none — digest only" for `agent_self` / `agent_plugin_cache` but the
  engine's step 6 does not consult severity; the caller passes
  `record_only=True` when the category's default severity is `low`, the
  same precedent `scan.py` set for info/low findings. Engine untouched.
  **D04 no registry resurrection**: 170 lines of `agent_registry.py`
  (config merge, `ps` lookups, signing ids) served deep mode's process
  signals, which light never has. A seven-line territory table lives in
  `light_watcher.py`, mirroring `llmsnitch/scanrules.TERRITORIES`
  (`fs_coil` may not import `llmsnitch`); `[agent.<name>]` config merge
  returns only if a second agent's territory ever needs adding without a
  release. **D05 delete the stopgap and the armed banner**:
  `load_notify_suppress` / `match_suppress` go (dead since T602 removed the
  keys; the category is the suppression now); the startup "armed" banner
  goes (spec: liveness is pull — `fs-coil status`; under `KeepAlive` a
  crash loop would page on every respawn). Startup *log line* stays.
  **D06 activation is a plist edit, not sudo**: the LaunchAgent's
  `ProgramArguments` moves from the root-owned `/usr/local/bin/fs-coil` to
  the user-owned `$HOME.local/bin/fs-coil` (pipx, tracks main
  via `pipx install --force`). Track B's "needs sudo" premise was true for
  deep mode only; the light agent never needed it. `install.sh` is not
  edited (never run; fog). **D07 deep mode stays on the legacy path**: the
  daemon is not loaded; its rewiring (spec T005 deep half, `_low_noise` →
  a signing-id predicate) is filed as fog with the exact spec pointer, not
  half-done here. **D08 legacy `Notifier` cooldown stays**: `notify()`'s
  `_deliver` already constructs a fresh `Notifier` per call (D24), so the
  cooldown is inert on the gated path; deleting `_should_emit` would touch
  the deep-mode caller this map does not own.

- [T801 — Wire the light watcher through the doctrine gate](tickets/T801-wire-light-through-notify.md)
  — done 2026-09-22: territory table + `classify_light` + `route_hit` in
  `light_watcher.py` (241 → 228 lines), stopgap and armed banner deleted,
  4 tests (suite 204 → 208). Replay of the live log: today's 697 hits →
  684 `agent_plugin_cache` + 13 `agent_self`, 0 banners; all September's
  would-be banners are `~/.zprofile` / `~/.profile` / `~/.zshrc` writes,
  one to four a day. Live agent unchanged until T802.
- **D06 sharpened — one installed tree (2026-09-22 20:25)**: the pipx
  install `~/.local/bin/fs-coil` (→ `~/Library/Application
  Support/pipx/venvs/llmsnitch`) is the *only* tree launchd runs; the
  root-owned `/usr/local/share/llmsnitch/` + `/usr/local/bin/fs-coil` are
  retired from the light agent and stay on disk as history until a sudo
  session trashes them (fog). Cross-map: `wayfinder/notification-click/`
  (branch `feature/notification-click-action`, `21f9e8c`) verified the same
  facts — its T902 defers to whichever activation lands first; its T901
  edits `notifier.py` / `notify._deliver` only, so no conflict with T801.
  Reload verb is `launchctl kickstart -k gui/$(id -u)/com.slav-it.fs-coil`
  (plist already loaded; bootout/bootstrap only if the label is missing).
  Plist repointed by this session; `pipx install --force` + kickstart are
  the user's.

## Tickets

- [T801 — Wire the light watcher through the doctrine gate](tickets/T801-wire-light-through-notify.md)
- [T802 — Activate quiet light](tickets/T802-activate-quiet-light.md)

## Not yet specified

- **Digest ② under plugin churn** — every `temp_git_<ts>_<rand>/…` path is
  a new subject key, so the first digest after activation will list up to
  the 20-row cap of lesser "new since last digest" lines that are all one
  event class. The digest-outlet handoff already holds this fog
  ("known-churn rule or path-class rollup"); sharper once one real digest
  has been read with light rows in it. Candidate answer: subject for
  `agent_plugin_cache` collapses `temp_git_*` to `temp_git_*`.
- **Deep-mode wiring** — spec T005's deep half: `monitor.py` deny hits →
  `notify()` with `pinfo`, `keychain_access` direct, `_low_noise` →
  `is_signed_self_read` predicate (OS signing-id prefix only, never a
  path substring — `fs_coil/AGENTS.md`). Blocked on the daemon being
  wanted again (needs sudo + FDA). Until then `monitor.py` keeps the
  legacy `Notifier` and `AGENTS.md`'s "dedupe key must not contain a
  timestamp" rule still applies to it.
- **`install.sh` plist template and `/usr/local/share/llmsnitch/`** — the
  installer still lays down the root-owned tree and points the light
  plist at it. After T802 the live machine no longer depends on that tree;
  whether to retire it (trash with sudo) or teach `install.sh` the pipx
  path is a Track B question, not this map's.
- **`[light-watch] paths` includes `~/.claude`** — the whole tree is
  watched so a foreign write to `~/.claude/settings.json` can be seen; the
  price is FSEvents volume from `plugins/cache` and `projects/`. Once the
  gate ledgers these as `agent_*`, the volume is a ledger-size question
  (45-day prune exists), not a paging one. Revisit only if
  `events-*.ndjson` growth is felt.
- **One `deny_write|unknown` tuple for every out-of-territory path** —
  spec D12: the window is per `(category, actor_bucket)`, so a second
  distinct sensitive path written within the hour is ledger-only. Accepted
  from the spec; if a real incident is ever masked by it, the per-tuple
  override `window_deny_write@unknown = 0` is one config line.

## Out of scope

- **Rule tightening** — dropping `.sample`, `.git/config`, or
  `plugins/cache` from the deny list (D01). Silence comes from actor ×
  territory, not from weakening what is watched.
- **Resurrecting `agent_registry.py`** (D04) and **engine changes** to
  `notify.py` (D03) — no new behavior the spec does not already name.
- **Deep mode** (D07) and **`install.sh`** (D06) — filed as fog.
- **The 7-day-old backlog of 2,000+ un-ledgered light events** — they
  exist only in the daily fs-coil logs; no backfill into the notify ledger.
