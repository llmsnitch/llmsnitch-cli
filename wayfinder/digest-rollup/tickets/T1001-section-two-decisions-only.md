# T1001 — ② lists decisions only

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: —`
`blocks: T1002`
`status: DONE (2026-09-26)`

## Question

Execution (D01, D02, D05, D06). Make section ② skip subjects whose
category names no decision, keep ③/④ untouched, and account for the
skipped count in the ② header.

Owned regions, `fs_coil/digest.py` only (231 / 250 lines — budget ≤ 5 net):

- module level, next to `_CAP`: `_NO_DECISION = {c for c, (_, _, a) in
  notify.CATEGORIES.items() if a.startswith("none")}` — derived, not
  listed;
- in `render`, the ② block only: build `items` from `new` minus
  `_NO_DECISION` categories; header `② new since last digest (N)` becomes
  `② new since last digest (N · M digest-only, see ③)` when M > 0 (N =
  decision-bearing new subjects, M = skipped). `new` itself is untouched —
  ③'s `new/known/resolved` still counts them. "nothing new" prints when
  N == 0 even if M > 0.

Other files: `tests/test_digest.py` (extend, use `_render` + `_seams.row`),
`docs/notifier-spec.md` §3 ② one sentence after "Known repeats are never
listed individually": *Subjects of categories whose decision line is
`none — digest only` are not listed either — their count appears in the ②
header and in ③.* No `CLAUDE.md` / `README.md` change (no command changed).

## Done criteria

1. `python3 tests/all.py` green; new test: a window with 3 new
   `agent_plugin_cache` subjects, 1 new `agent_self`, 1 new `deny_write`
   and 1 new `depaudit_finding` (`record_only=True`) renders ② with the
   `deny_write` and `depaudit_finding` lines, none of the four
   no-decision subjects, header `(2 · 4 digest-only, see ③)`, and ③ still
   shows `agent_plugin_cache · claude-code 3 3/0/0`. A second test: only
   no-decision new subjects → ② header `(0 · 3 digest-only, see ③)` then
   `nothing new`. Existing `test_depaudit_finding_renders_in_section_two`
   and `test_render_cap_and_full` stay green unchanged (the cap now
   counts decision lines only).
2. Replay (read-only, in-process, no `notify()` call): `render()` over the
   live ledger rows for the 09-24 10:00 → 09-25 10:00 window with the real
   7-day lookback — ② goes from 22 `temp_git_*` lines + `… 47 more` to the
   single `scan_finding` group; header reads `(1 · 66 digest-only, see ③)`;
   ③ byte-identical to the shipped `digest-2026-09-25.txt` ③. Record both
   line counts below.
3. `digest.py` ≤ 236 lines.
4. ponytail review over the diff applied.

## Resolution

Resolved 2026-09-26 on branch `digest-rollup/T1001` (base b25ce61, 4efcac8 an
ancestor). Built exactly what D01/D02/D05/D06 name, +3 net lines in
`digest.py` (231 → 234):

- `fs_coil/digest.py` — module level: `_NO_DECISION = {c for c, (_, _, a) in
  notify.CATEGORIES.items() if a.startswith("none")}` (derived; today that
  is `agent_self`, `agent_plugin_cache`, `agent_signed_self_read`). ② block:
  `items` filtered by `k[0] not in _NO_DECISION`; `m = len(new) - len(items)`;
  header `② new since last digest (N · M digest-only, see ③)` when M > 0,
  `(N)` otherwise; `nothing new` when N == 0. `new`, `_key`, `_tier`, ③, ④,
  health untouched — ③ still counts the skipped subjects as new.
- `tests/test_digest.py` — `test_render_section_two_skips_no_decision_categories`
  (3 `agent_plugin_cache` + 1 `agent_self` + 1 `deny_write` + 1
  `depaudit_finding` record_only → header `(2 · 4 digest-only, see ③)`,
  only the two decision lines listed, ③ `agent_plugin_cache · claude-code  3
  3/0/0`) and `test_render_section_two_only_no_decision_is_nothing_new`
  (header `(0 · 3 digest-only, see ③)` then `nothing new`).
  `test_depaudit_finding_renders_in_section_two` and `test_render_cap_and_full`
  unchanged and green.
- `docs/notifier-spec.md` §3 ② — the one sentence from this ticket, verbatim,
  after "Known repeats are never listed individually."

Done criteria:

1. `python3 tests/all.py` — 210/210 (208 at dispatch + 2), exit 0.
2. Replay (read-only, in-process: `ledger.iter_rows` + `render()` with
   `health_report()`; no `notify()`, no `cmd_digest()`, nothing written under
   the notify dir). Window 2026-09-24 10:00 → 2026-09-25 10:00 reconstructed
   from the 09-24 digest mtime and the 09-25 digest mtime: 171 rows, 0 skipped,
   lookback 1248 rows, prior 322 rows — same 171/0 as the shipped header.
   - before (4efcac8 `render`): header `② new since last digest (67)`; ② body
     25 lines — `[HIGH] scan_finding` group (1 subject) + `[LESSER]
     agent_plugin_cache` group with 19 `temp_git_*` lines at the 20-subject
     cap, then `… 47 more (fs-coil digest --full)`.
   - after: header `② new since last digest (1 · 66 digest-only, see ③)`;
     ② body 3 lines — the single `scan_finding` group (`drift_added: …
     playwright/…/.mcp.json`).
   - ③ byte-identical to `digest-2026-09-25.txt` ③ before and after
     (`agent_plugin_cache · claude-code  154  66/0/132` still there); ④
     byte-identical too.
3. `wc -l fs_coil/digest.py` = 234 (≤ 236).
4. Ponytail review over the diff since 4efcac8: one cut (spec sentence
   carried a redundant header-format parenthetical; -1 line, now verbatim
   from the ticket). Code and tests judged lean.

Files touched: `fs_coil/digest.py`, `tests/test_digest.py`,
`docs/notifier-spec.md`, this ticket. No `map.md`, `notify.py`, `CLAUDE.md`,
or `README.md` change. Cross-ownership requests: none.
