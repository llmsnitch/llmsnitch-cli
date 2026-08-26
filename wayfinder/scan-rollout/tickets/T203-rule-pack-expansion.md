# T203 — Rule-pack expansion: SD-020 + SD-022 ports

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: —`
`blocks: —`
`status: DONE (2026-08-26)`

## Resolution

Shipped as `2da768b`. Both rules read from upstream source before writing
(`pkg/rules/dns_exfil.go`, `pkg/rules/hooks.go`) and reimplemented in the
house regex idiom.

Two deviations from this ticket's sketch, both siding with upstream over
the sketch:
1. **SD-020 scope**: `claude_settings` only, not `hook_script` — upstream
   gates on `IsClaudeSettings`; unquoted `$VAR` in shell scripts is normal
   shell and would flood.
2. **SD-020 category**: `scan_hygiene`/low, not `config_compromise` — the
   page's Decision is "quote the variable", which is hygiene by the
   AGENTS.md gate. Bump it if injection-in-hooks ever proves exploitable
   here.

SD-022 landed per ticket (conjunction rule, `config_compromise`, classes
`hook_script`/`skill_script`; upstream severity HIGH noted in comment).

Verification: 34/34 + 8/8 + 18/18; ReDoS payloads extended (dig-repeat,
long command-string) and green; real-machine smoke — DNS rule silent,
`hook_unquoted_var` 9 hits on Supacode-installed hooks (unquoted
`$__ppid` shapes), true by upstream semantics, all low/record_only. No
exemption added; the severity is the damper.

## Question

Nothing to decide; execution ticket. Port the two highest-value surveyed
shapes into `llmsnitch/scanrules.py` (independent reimplementation from the
MIT skill-detector source — cite, don't copy):

1. **Hook shell-metachar interpolation** (skill-detector SD-020, CRITICAL —
   `pkg/rules/hooks.go:53-58` in
   `submodule/security-scanners/skilltrust-skill-detector/`): hook command
   strings interpolating untrusted fields through shell metacharacters.
   Classes: `claude_settings`, `hook_script`. Category `config_compromise`.
2. **DNS exfiltration** (SD-022, `exfiltration.go:147-152`): data smuggled
   into DNS lookups (`dig`/`nslookup` with variable-interpolated
   subdomains). Classes: `hook_script`, `skill_script`. Category
   `config_compromise`.

Constraints (non-negotiable):

- **Bounded quantifiers** — every new rule faces attacker-sized lines; no
  `X*`/`X+` adjacent to an overlapping class, unbounded `.*` only anchored
  (see plan 001's maintenance note). Extend
  `test_scan_rules_resist_redos`'s payload list with a pathological input
  per new rule.
- High-specificity over recall (hook.py doctrine: too-generic alphabets are
  worse than misses).
- Positive + negative test per rule in `tests/test_llmsnitch.py`; smoke the
  ruleset against this machine's real `~/.claude` before committing and
  triage any new false positives (the wildcard-grant lesson).

Done when: suites green including extended ReDoS payloads; real-machine
smoke shows no new FP class; review gates run.
