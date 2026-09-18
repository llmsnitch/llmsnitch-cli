# Quiet Patrol — Wayfinder Map

`label: wayfinder:map`
`status: OPEN (charted 2026-09-18; T701–T703 resolved 2026-09-18, T705 on the frontier, T704 blocked)`

## Destination

A **patrol on a triaged, healthy machine ledgers zero non-waived
findings**. Rule and scope bugs are fixed at the rule — hook state stops
drifting, `~/.claude.json` drifts only when its MCP servers change,
installed plugins are actually scanned, a finding resolves only when its
artifact was in scope — and correct-but-accepted findings are recorded in
the tool as config-audit **Waivers**, not in `.remember/`. The map closes
when [T704](tickets/T704-activate-quiet-patrol.md)'s done criteria hold:
the first 09:30 patrol after activation (and after the newly covered
plugin artifacts are triaged) ledgers zero non-waived findings and the
digest's open-findings line reads `0c/0h/0l · 2 waived`.

## Notes

- **Tracker location**: `wayfinder/quiet-patrol/` on branch
  `review/patrol-findings-2026-09-18` in the worktree
  `~/.supacode/repos/llmsnitch-cli/review/patrol-findings-2026-09-18`.
  Commit here; merging to `main` (canonical, `~/llmsnitch-cli`) is the
  user's call, not a ticket.
- **Plan-vs-do override**: T701–T704 carry execution — the destination is
  an observable patrol result, not a spec.
- **Origin**: triage of patrol `scan-20260918-093005` per
  `~/.claude/plans/synchronous-tumbling-dusk.md`; verdict trail and accept
  reasons in `~/llmsnitch-cli/.remember/now.md` (2026-09-18 section).
- **Skills**: `tdd` for dev agents; repo review gates (`code-review`
  two-axis, `ponytail:ponytail-review`) after each execution ticket.
- **Repo policy**: local-only git; `trash`, never `rm`; never run
  `install.sh`; stdlib only, Python 3.9+; no network imports
  (test-enforced); files 0600 / dirs 0700; `hook.handle` never raises;
  gate exit codes `0/1/2`; `python3 tests/all.py` is the gate. 250-line
  cap per `fs_coil` file.
- **Vocabulary (CONTEXT.md, updated at charting)**: **Waiver** now covers
  any surface (config-audit re-raise = the matched evidence set changes);
  **Hook state** added. Use them.
- **Machine facts (2026-09-18)**: patrol runs from `$HOME`; `~/.claude`
  holds 10,348 files, 7,224 under `plugins/` with 686 classifiable
  artifacts of which the patrol reaches 74 (`_MAX_DEPTH = 6` from
  `~/.claude`, plugin skills sit at depth 8; `_MAX_FILES = 4000` overflowed
  by 2 because `file-history` and `projects` are walked first). Fingerprint
  grain is `(rule_id, artifact)`; drift salts with the content sha, so all
  nine `hook_unquoted_var` rows share one fingerprint and a drift row can
  never be waived by fingerprint. `drift_changed` on
  `~/.claude/hooks/claude-signal` and `~/.claude.json` appeared in every
  patrol since 2026-08-27 / 08-26. Residual after triage: 14 findings
  (9 `hook_unquoted_var`, 2 `skill_instruction_override`, 1 `secret_shape`
  on vendored docs, 2 one-shot drift). Dep-audit already has
  `~/.llmsnitch/waivers.json` + `--waive ID PACKAGE --reason`.

## Decisions so far

<!-- one line per closed ticket: gist + link -->

- Grilling rounds 1–2 (charting, all recommendations accepted 2026-09-18):
  **D01 scope** = scan waivers, hook-state churn, `.claude.json` churn,
  plugin coverage + scope-aware resolution; the `settings-snapshot-*.json`
  test leak is a plan, not this map. **D02** carry execution (house
  pattern). **D03** extend **Waiver** to any surface rather than coin a
  scan-side term. **D04 waiver key** = `(rule_id, artifact)`, re-raise when
  the sorted set of matched evidence strings changes — not on file sha
  (settings.json is rewritten constantly). **D05 storage** = the shared
  `~/.llmsnitch/waivers.json`, rows carry `surface`, each loader filters
  its own shape; verb `llmsnitch scan --waive RULE_ID ARTIFACT --reason
  TEXT`, artifact in tilde form as `--report` prints it. **D06 effect** =
  mirror dep-audit: row kept with `waived: true`, excluded from the breach
  test, routed `record_only`, flagged in `--report`, `findings_waived` in
  meta, digest line gains `· N waived`. **D07 no regex tightening** for
  `skill_instruction_override` — doctrine says false negatives cost more,
  a quoted phrase still injects; waive the two `improve/SKILL.md` rows and
  let the evidence-set re-raise guard them. **D08 Hook state** = non-exec
  file without a script extension under a hooks dir; scanned for secrets
  only, never drift-fingerprinted (referenced-from-settings was rejected:
  it misses `_lib/*.js`). **D09 semantic drift** on `~/.claude.json` =
  salt is the sha of canonical JSON of `mcpServers` +
  `projects[*].mcpServers`; excluding the file was rejected (it is the
  file that matters most). **D10 plugin coverage** = `plugins` becomes a
  fourth walked sub per territory, depth measured from each plugin root
  (`plugins/cache/*/*/*`, `plugins/marketplaces/*`); no global depth or
  budget raise. **D11 scope-aware resolution** = a finding resolves only
  if its artifact was in this run's discovered set; out-of-scope findings
  carry forward silently. **D12 closing criterion** = as in Destination;
  the two residual waivers are granted from the CLI in T704 and the
  `.remember` accept records become history.
- [T702 — Hook state class and semantic drift](tickets/T702-hook-state-and-semantic-drift.md)
  — `hook_state` class (non-exec, non-script-ext under hooks): secret pass
  only, never drift-tracked, stale `hook_script` baseline rows dropped;
  `~/.claude.json` drift salt = sha of canonical `mcpServers` +
  `projects[*].mcpServers`, evidence `mcpServers changed`. Three live scans
  across a session: no drift on either file. First patrol after landing
  emits one re-salt `drift_changed` on `~/.claude.json`, then quiet. +8 tests.
- [T703 — Plugin coverage and scope-aware resolution](tickets/T703-plugin-coverage-and-scope-aware-resolution.md)
  — plugin roots (`plugins/cache/*/*/*`, `plugins/marketplaces/*`) walked
  in a second pass after all territories' core subs (a single pass starved
  `~/.codex`); junk-nested roots skipped. Coverage from `$HOME` 74 → 596 of
  672 plugin artifacts, total 204 → 723; budget overflow 2 → 17 — D10's
  "budget not exhausted" was wrong, spun out as T705. Resolution folds every
  stored scan into `{fingerprint: artifact}` and tombstones only when the
  artifact was in scope or is gone from disk. +4 tests.
- [T701 — Config-audit waivers](tickets/T701-config-audit-waivers.md) —
  shared `waivers.json`, rows `{surface, rule_id, artifact, reason,
  evidence[], waived_at}`; `scan --waive RULE_ID ARTIFACT --reason` (exit 2
  on misuse, drift rules unwaivable, no rescan); waived rows kept, excluded
  from breach, `record_only`, `known waived` / `known RERAISED` in text,
  `findings_waived` in meta, digest `· N waived`. Orchestrator follow-up:
  dep-audit's `add_waiver` rewrote the file from its filtered view and
  would have dropped every scan row — fixed to append to the raw list
  (+1 test). +6 tests. Suite 182 → 201.

## Not yet specified

- **Triage of the newly covered plugin artifacts** — T703 brings ~612
  SKILL.md / skill scripts / hooks into scope for the first time; what
  they surface is unknown until the first patrol after it lands. Handled
  as ordinary findings inside T704, or ticketed if a class of them needs
  a decision.
- **Waiver expiry / re-review** — whether a config-audit waiver should
  carry a review-by date and resurface in the digest when stale. Fog until
  waivers have existed for a few weeks.
- **Digest-hosted waiver granting** — a copy-pasteable `llmsnitch scan
  --waive …` line per open finding in the digest (inherits the
  digest-outlet map's "digest as the home for lesser-finding review" fog).
  Sharper once T701 exists; still fog until read in practice.
- **Harness-managed hook blocks as an attribution question** — all nine
  `hook_unquoted_var` rows are Supacode-injected; whether hooks written by
  a terminal/wrapper deserve their own actor bucket or territory entry.
- **Codex plugin layout** — D10 is carried by the territory table; if
  `~/.codex` grows a plugins tree its root pattern is a one-line addition,
  but its shape is unknown today.

## Out of scope

- **`settings-snapshot-*.json` test-run leak** into
  `~/.config/llmsnitch/` — test hygiene, belongs in `plans/`, no decision
  in it (D01).
- **Global `_MAX_DEPTH` / `_MAX_FILES` raise** — rejected in D10; makes
  every scan slower for a one-subtree problem.
- **Excluding `~/.claude.json` from drift** — rejected in D09.
- **Rule-tightening for quoted injection examples** — rejected in D07;
  returns only if the waiver mechanism proves insufficient.
