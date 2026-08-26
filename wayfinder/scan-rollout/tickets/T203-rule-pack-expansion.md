# T203 — Rule-pack expansion: SD-020 + SD-022 ports

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: —`
`blocks: —`
`status: OPEN`

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
