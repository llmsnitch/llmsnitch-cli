# T801 — Wire the light watcher through the doctrine gate

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: —`
`blocks: T802`
`status: DONE (2026-09-22)`

## Question

Execution (D01–D05, D08). Make every fs-coil light deny hit a `notify()`
call so the three gates apply, and remove the two things the gate
replaces.

Owned regions, `fs_coil/light_watcher.py` only:

- **delete** `load_notify_suppress`, `match_suppress`, the `configparser` /
  `fnmatch` imports they needed, the `suppress_rules` load and the
  `suppressed=` log tag, and the startup `notifier.notify("… armed", …)`
  call (log line stays);
- **add** a territory table mirroring `llmsnitch/scanrules.TERRITORIES`
  plus `claude-code`'s cache path, `classify_light(path, home) →
  (category, actor_bucket)`, and `route_hit(path, kind, hit, home, *,
  stdout_only, now=None)` that builds the subject/title/message and calls
  `notify("fs-coil-light", …, deny_pattern=hit, record_only=<low>)`; the
  event loop calls `route_hit` where it used to call `notifier.notify`;
- the DENY-MATCH log line gains `category=… actor=…` so
  `fs-coil logs` and the ledger agree.

Other files: `tests/test_light_gate.py` (new), `tests/all.py`
registration, `CONTEXT.md` **Territory** (done at charting),
`docs/notifier-spec.md` T005 heading gets an "executed by T801 (light
half)" note like T007's, `CLAUDE.md` Architecture line for `fs_coil` if it
enumerates the light watcher.

## Done criteria

1. `python3 tests/all.py` green; new module covers: the classify table
   (plugin cache → `agent_plugin_cache`/`claude-code`;
   `~/.claude/settings.json` → `agent_self`/`claude-code`; `~/.codex/x` →
   `agent_self`/`codex`; `~/.zprofile` and `~/.ssh/config` → `deny_write`/
   `unknown`); a low-category hit writes a ledger row with
   `notified=false`, `record_only=true` and delivers nothing even on
   `first_seen`; a `deny_write` hit delivers once then `window_repeat`s;
   `stdout_only=True` still ledgers. `load_notify_suppress` /
   `match_suppress` gone — verified by grep, not a test (ponytail review).
2. Replay of the real 2026-09-22 log through `classify_light` (read-only,
   in-process, scratch seams): 534 → `agent_plugin_cache`, 8 →
   `agent_self`, 0 → `deny_write`. Numbers recorded below.
3. `light_watcher.py` shorter than at charting (241 lines).
4. ponytail review over the diff applied; no `notify.py` change.

## Resolution (2026-09-22)

- **Built**: `light_watcher.py` — `_TERRITORIES` / `_CACHE_PATHS` table,
  `_inside`, `classify_light`, `route_hit`; the event loop calls `route_hit`
  and logs `category= actor= notified=` per hit. Deleted
  `load_notify_suppress`, `match_suppress`, the `configparser` / `fnmatch` /
  `re` imports, the `Notifier` import, the armed banner. File 241 → 228
  lines. `notify.py` untouched.
- **Tests**: `tests/test_light_gate.py` (4 tests: territory table incl.
  the `~/.claude-evil` non-segment case; low category → ledger row
  `record_only=true, notified=false` on `first_seen`, nothing delivered;
  `deny_write` delivers once then `window_repeat` on a different path
  inside the hour; `stdout_only` ledgers without banner). Registered in
  `tests/all.py`. Suite 204 → 208, green.
- **Replay of the live log** (read-only, in-process `classify_light`, no
  notify call): 2026-09-22 — 684 `agent_plugin_cache · claude-code`, 13
  `agent_self · claude-code`, **0 `deny_write`** (the count grew past the
  542 at charting; the 19:0x burst was still landing). All of September:
  the only `deny_write` rows would have been `~/.zprofile`, `~/.profile`,
  `~/.zshrc` on 09-02, 09-09, 09-11, 09-14, 09-18 — one to four a day,
  one banner per hour at most. That is the surface's real signal.
- **Ponytail review** applied: `_inside` as `any(...)`, two comments cut,
  the stopgap-absence test dropped (grep: no references in `fs_coil/` or
  `tests/`). Docs: `CONTEXT.md` **Territory**, spec T005 execution note.
- **Not done here**: activation (T802) — the live agent still runs the
  Aug 26 tree until the user repoints the plist.
