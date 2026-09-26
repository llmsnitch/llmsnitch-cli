# T1001 — ② lists decisions only

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: —`
`blocks: T1002`
`status: CLAIMED (digest-rollup/T1001, 2026-09-26)`

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

<!-- filled on completion -->
