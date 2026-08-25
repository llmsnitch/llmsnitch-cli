# T104 — Team design

`labels: wayfinder:prototype`
`parent: ../map.md`
`blocked by: T102, T103`
`blocks: T105`
`status: DONE (2026-08-24) — design settled below; T105 authors it`

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

## Inputs from T101

- Pi and Prime Agent are near-identical codebases (Prime is Pi-derived;
  byte-identical session docs modulo naming). The pipeline should support
  "derived harness" runs where one adapter covers two roster entries — do Pi
  first and Prime Agent nearly falls out.

## Resolution

Resolved 2026-08-24 (prototype design presented HITL; 4 confirmations, all
per recommendation). T105 transcribes this design into files.

### Layout

```
team/
  README.md               — orchestrator playbook: one harness run, six phases
  roster.md               — queue from T101: rank | tier | status | derived-of
  roles/
    dossier-researcher.md
    adapter-implementer.md
    test-verifier.md
    doctrine-auditor.md
  runs/<harness>/journal.md — append-only phase log; resume = first
                              unfinished phase
```

### Principles (writing-for-agents)

- Contract (`docs/harness-adapter-contract.md`), dossier exemplar
  (`dossiers/claude-code.md`), and roster are the single sources of truth —
  role files POINT at them, never restate them.
- Four agent roles only. Roster-triage is a README step; the local-commit
  gate is the orchestrator committing. Borrowed from next-task: single
  responsibility, declared tools, state updates for resume — reduced to one
  flat journal file, no JSON machinery.

### Six phases, checkable gates

1. **Triage** (orchestrator) — roster row → `in-run`; admission
   re-confirmed.
2. **Dossier** (dossier-researcher; AFK, curl-only network allowed at
   design time) — all 9 sections, evidence-dated facts, complete C1 draft,
   per-signal confidence.
3. **Adapter** (adapter-implementer) — declarative entry + code hook +
   fixture in working tree; zero writes into the harness's directories.
4. **Verify** (test-verifier) — full stdlib suite + no-network grep guard +
   new fixture test pass with output pasted into the journal; real-session
   parse where the harness is installed.
5. **Doctrine audit** (doctrine-auditor) — contract acceptance checklist
   ticked item-by-item with evidence refs; redaction spot-check.
6. **Commit** (orchestrator) — local commits landed; roster row → `done`;
   journal closed.

### Confirmed choices (Q1–Q4)

- **One commit per phase** — bisectable; journal cites commit hashes as
  gate evidence.
- **One orchestrating session per harness run**, roles spawned as subagents
  with the role file as prompt + harness name. Journal makes any phase
  resumable by a fresh session.
- **Researcher network policy**: curl-only at design time; shipped code
  stays under the grep guard (enforced at phase 4).
- **Derived harnesses**: one run covers Pi + Prime Agent — shared code
  hook, thin delta-dossier for the derived harness, own registry entry and
  roster row; `derived-of` column encodes it.
