# T105 — Author the team under `team/`

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: T104`
`blocks: T106`
`status: DONE (2026-08-24) — team authored under ../../team/, commit hash in resolution`

## Question

Write the team files exactly as T104 designed them, in the feature worktree
(`~/.supacode/repos/llmsnitch/feature/installation-mac/team/`), and commit
locally (never push — map Notes). Done when a fresh Claude Code session can
read `team/README.md` and start a harness run without further clarification
from the user.

## Resolution

Resolved 2026-08-24. Six files, transcribed from T104's design:

- `team/README.md` — orchestrator playbook: six phases with gates, journal
  template, failure handling ("never advance past a failed gate; never
  accept a verdict without evidence in the journal").
- `team/roster.md` — the 12-harness queue from T101, with status vocabulary
  (`pending|in-run|done|deferred|needs-probe|out-of-scope`), `derived-of`
  column, and the rule that `needs-probe` rows take a researcher errand,
  not a full run.
- `team/roles/{dossier-researcher,adapter-implementer,test-verifier,
  doctrine-auditor}.md` — one role per pipeline stage; each points at the
  contract/exemplar/roster (single sources of truth, never restated), each
  states constraints (read-only toward harnesses, no git — orchestrator
  commits) and a checkable done-criterion.

Baseline verified before authoring: `python3 tests/test_llmsnitch.py` →
16/16 passed (the exact invocation now cited in test-verifier).

Commit hash: recorded by the closing commit of this ticket (see map/git
log — the team files and this resolution land together).
