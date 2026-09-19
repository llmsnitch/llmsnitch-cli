# T704 — Activate quiet patrol

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: T701, T702, T703, T705`
`blocks: —`
`status: ACTIVATED (2026-09-19 12:13) — closes when the 2026-09-20 09:30 patrol and 10:00 digest meet criteria 1–2`

## Question

Execution. Once T701–T703 are merged where the user wants them (main is
canonical; `pipx install --force ~/llmsnitch-cli` — never the stale
`~/Repos/llmsnitch` clone):

1. Run `llmsnitch scan --patrol` from `$HOME` (cwd matters — D11 makes it
   matter less, but the LaunchAgent runs from `$HOME` and verification
   must match it). Triage whatever the newly covered plugin artifacts
   surface: fix at the rule if a rule is wrong, `--waive` with a reason if
   the finding is correct but accepted, report as an incident if real.
2. Grant the two standing waivers from the CLI, reasons from
   `~/llmsnitch-cli/.remember/now.md` (2026-09-18 section):
   `hook_unquoted_var ~/.claude/settings.json` (Supacode-managed hook
   preamble, shell-locals only) and `secret_shape
   ~/.claude/plugins/marketplaces/anthropic-agent-skills/skills/claude-api/SKILL.md`
   (key-prefix description in vendored docs). Then the two
   `skill_instruction_override ~/…/improve/SKILL.md` rows (D07).
   Expected one-time migration noise on that first patrol, not defects:
   one `drift_changed · mcpServers changed` on `~/.claude.json` (re-salt,
   D09) and a `drift_removed` for any pre-D08 hook-state path that was
   baselined as `hook_script` and deleted before the run (per-session
   `claude-notifier-active.d/<pid>` markers; spec review 2026-09-18).
3. Done criteria (close the map when all hold):
   - the next 09:30 patrol's `findings.ndjson` has zero rows that are
     neither `waived` nor `resolved`;
   - the 10:00 digest's open-findings line reads `0c/0h/0l · N waived`
     with N = the waivers granted, and ① shows both watchers healthy;
   - no `drift_changed` on `claude-signal` or `~/.claude.json` across
     two patrols with sessions in between;
   - `python3 tests/all.py` green from the installed source;
   - map status → CLOSED, fog carried forward as recorded, resolution
     comments on T701–T704.

## Resolution (activation, 2026-09-19)

- **Merge**: the user's `--ff-only` merge had been refused — `main` had
  diverged by three plan-013 commits (`5f4907e..0dc7e29`) — and pipx had
  reinstalled the old code (first live run: 203 files, hook-state drift,
  whole-file `.claude.json` sha). Merged as `2711b8b` (clean: plan 013
  touched `setup_cmd.py`, `plans/`, six lines of `test_llmsnitch.py`),
  main suite 204/204, `pipx install --force ~/llmsnitch-cli`; installed
  help lists `scan --waive`.
- **First patrol on the new code** (`scan-20260919-121154`, 848 files,
  3 skipped): 3 critical / 42 high / 584 low. All but three non-drift rows
  were the expected one-shot `drift_added` for 613 newly covered plugin
  artifacts plus the D09 re-salt `drift_changed · mcpServers changed`.
  Triage of the three new rows: `skill_instruction_override` on the
  receipts skill (marketplace clone) is the same defensive-prose shape as
  the improve skill → waive (D07); two `skill_undeclared_bash` on the
  telegram skills (marketplace clone, plugin not installed) are the
  YAML-list `allowed-tools` parser gap → waive, gap recorded as fog.
- **Waivers granted from the CLI** (7 pairs, 15 rows): `hook_unquoted_var
  · settings.json`, `secret_shape · claude-api/SKILL.md`,
  `skill_instruction_override · improve/SKILL.md` ×2 (claude, codex) and
  `· receipts/SKILL.md`, `skill_undeclared_bash · telegram/{access,configure}`.
  `~/.llmsnitch/waivers.json` 0600, 7 config-audit rows.
- **Second patrol** (`scan-20260919-121321`): `findings: waived=15`,
  614 tombstones, `[OK] no findings`, `--report` exit 0. No `drift_changed`
  on `claude-signal` or `~/.claude.json` across the two patrols with this
  session active between them (criterion 3 ✓). Suite green from the
  installed source (criterion 4 ✓).
- **Digest** (`fs-coil digest`, 12:14): ① all watchers healthy; `open
  findings: none · 15 waived`. ② lists 620 "new since last digest" — the
  one-time coverage flood; tomorrow's 10:00 window still contains it.
- **Pending**: criteria 1–2 need the scheduled 2026-09-20 09:30 patrol and
  10:00 digest (`0c/0h/0l`-equivalent `none · 15 waived`, no new
  criticals). Close the map then.
