# Harness Team — Orchestrator Playbook

You are the orchestrating session for **one harness run**: taking one
harness from `roster.md` through six phases to "supported" per the
contract. Read these before phase 1 — they are the sources of truth this
playbook points at and never restates:

- `docs/harness-adapter-contract.md` — the contract (C1–C9 + acceptance
  checklist). Purpose doctrine: llmsnitch is a **tripwire, not a meter**.
- `dossiers/claude-code.md` — the dossier exemplar (T103 format).
- `team/roster.md` — the queue.
- `AGENTS.md` — the Decision / Actor / Novelty doctrine.

Standing rules for every phase: repo is local-only (no remote, no push);
delete with `trash`, never `rm`; never write into any harness's own
directories; one git commit **per phase** (phases 2–5 each end in a commit;
the journal cites its hash as gate evidence).

## The run

Create `team/runs/<harness>/journal.md` at phase 1. Append one entry per
phase; a phase without a closing entry is where a resuming session picks
up. Entry template:

```markdown
## Phase N — <name>
started: <ts>   finished: <ts>
evidence: <commit hash / pasted output / file paths>
verdict: PASS | FAIL(reason)
```

### Phase 1 — Triage (you)

Pick the highest-ranked `pending` row in `roster.md` (or the harness the
user names). Re-confirm admission: its session files exist on disk at the
dossier-cited or expected paths — for a harness not installed on this
machine, cite the format documentation instead. Set the row `in-run`.
Gate: roster updated, journal created.

If the row has `derived-of`, run the base harness first (or confirm it is
`done`); the derived run reuses the base code hook and produces only a
delta-dossier, its own registry entry, and its own roster row closure.

### Phase 2 — Dossier

Spawn a subagent with `team/roles/dossier-researcher.md` as its prompt plus
the harness name. Gate (verify yourself, don't trust the report): all 9
sections present in `dossiers/<harness>.md`, facts evidence-dated, C1 entry
draft complete, every signal mapping carries a confidence. Commit.

### Phase 3 — Adapter

Spawn `team/roles/adapter-implementer.md` + harness name. Gate: declarative
entry, code hook (only if the dossier shows the format needs one), and a
fixture test exist in the working tree; `git status` shows no path outside
this repo. Commit.

### Phase 4 — Verify

Spawn `team/roles/test-verifier.md` + harness name. Gate: the journal
contains the **pasted output** of `python3 tests/test_llmsnitch.py` (all
tests, including the no-network grep guard and the new fixture test) and,
where the harness is installed here, a real-session parse showing the
signal set. A verdict without pasted output is a FAIL. Commit.

### Phase 5 — Doctrine audit

Spawn `team/roles/doctrine-auditor.md` + harness name. Gate: the contract's
acceptance checklist ticked item-by-item in the journal, each tick citing
evidence (file:line, commit, or pasted output). Commit.

### Phase 6 — Close (you)

Roster row → `done` (record tier). Final journal entry. Commit. Report the
run's outcome to the user: harness, commits, one-line signal-set proof.

## Failure handling

A failed gate stays in its phase: fix and re-gate, or append a
`verdict: FAIL` entry with the reason and stop for the user. Never advance
past a failed gate; never mark a gate passed on a role's say-so without the
evidence in the journal.
