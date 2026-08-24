# T104 — Team design

`labels: wayfinder:prototype`
`parent: ../map.md`
`blocked by: T102, T103`
`blocks: T105`
`status: OPEN`

## Question

Design the team itself (map D09/D10): the file layout under `team/`, one
definition per role in the harness pipeline (roster-triage →
dossier-researcher → adapter-implementer → test-verifier → doctrine-auditor →
local-commit gate), the orchestrating entry point, phase gates (what evidence
lets a run advance — e.g. test-verifier must show the stdlib suite + the
no-network grep guard passing), cross-run state/resume convention, and the
local-commit gate rules that replace AgentSys's ship/PR phases (map D07).

Borrow patterns from `~/Repos/agent-sh/next-task/agents/*.md` (file-based
definitions, single responsibility, declared inputs/outputs) and
`audit-project`'s spawn logic — but the team is self-contained in this repo,
no plugin install (map D09). Prompts reference the T102 contract and T103
dossier format by path. Consult `mattpocock-skills:writing-for-agents`.

## Resolution

*(append the settled design — layout, roles, gates, state — then close;
T105 authors it)*
