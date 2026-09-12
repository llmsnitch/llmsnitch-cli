# T505 — "Exercised" evidence: definition + detection

`labels: wayfinder:grilling`
`parent: ../map.md`
`blocked by: T504`
`blocks: T507`
`status: DONE (2026-09-12)`

## Resolution

HITL grilling, one round, four decisions — all recommendations accepted
(grounded on live probes: pip precompiles `__pycache__` at install — 33/44
package dirs in the pip venv vs 10/33 in the uv env where presence really
means imported; `top_level.txt` covers only ~45% of dists in the pip venv,
so import names need a `RECORD`-derived fallback):

1. **Exercised = A∨B**: (A) project source in the session cwd tree imports
   the package's import names (`top_level.txt`, fallback `RECORD`
   top-levels), OR (B) any python/pytest/`uv run`/script execution in that
   project's agent sessions after the intake timestamp. Bytecode evidence
   (C) dropped — installer-dependent (pip's install-time precompile
   poisons it). Recall over precision: the KEV pre-filter (21 KEV-listed
   entries of 19,033) already makes the gate rare.
2. **Binary, no middle tier**: "intake + KEV, exercise unknown" is a
   lesser finding — visible in `scan` output and the future digest, never
   paging. Three tiers is corp-noise machinery.
3. **Malicious bypasses the gate**: `class: malicious` ∧ intake = critical
   immediately — no KEV, no exercised needed. The install *is* the abuse;
   Decision = uninstall now, Actor = the agent, maximally novel. Waivers
   still apply uniformly.
4. **"Exercised" is canon** (CONTEXT.md updated at resolution).

Unblocks T507 entirely — every blocker (T503–T506) is now DONE; the
criticality predicate is fully specified:
`critical = (malicious ∧ intake) ∨ (intake ∧ kev.listed ∧ exercised)`.

The criticality gate requires the vulnerable package was **exercised** on
this machine — not merely installed. Define it and its detection, from
ledger evidence only (no runtime instrumentation):

1. What counts: imported in a later agent session? any `python` run in the
   project after install? project's venv activated? How weak may the
   signal be before "exercised" is meaningless?
2. Detection source: session NDJSON Bash events, harness ledgers, file
   mtimes (`__pycache__` as a cheap exercised-tripwire?).
3. False-negative posture: an exercised package we miss stays a lesser
   (quiet) finding — is that acceptable, or does "installed + exploited
   flag, exercise unknown" deserve a middle tier?
4. Once resolved, "Exercised" enters CONTEXT.md as canon.

From T501: does the `malicious` class bypass this gate entirely? A
typosquat an agent installed is arguably critical on install alone —
"exercised" may only be the gate for the `vulnerability` class.
