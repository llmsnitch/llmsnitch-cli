# T505 — "Exercised" evidence: definition + detection

`labels: wayfinder:grilling`
`parent: ../map.md`
`blocked by: T504`
`blocks: T507`
`status: OPEN`

## Question

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
