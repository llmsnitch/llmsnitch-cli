# T704 — Activate quiet patrol

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: T701, T702, T703`
`blocks: —`
`status: OPEN — unclaimed`

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
