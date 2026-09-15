# Execution handoff — Plan 012 (digest finding-recall)

**For:** a fresh Claude Code session with zero prior context.
**Task:** execute `plans/012-digest-finding-recall.md` end-to-end, on a new
worktree, leaving a clean reviewed branch for the maintainer to merge. Do
**not** merge or push (local-only repo).

---

## 0. TL;DR

Build the standing "open findings" readout in the daily digest. The full spec
is `plans/012-digest-finding-recall.md` — **read it completely before
touching anything**; it has exact code excerpts, a 7-case test plan, done
criteria, and two STOP conditions. This note is the *orchestration* wrapper:
worktree setup, team shape, loop, house rules.

Written against `main` @ `15727b2` (2026-09-15).

## 1. Collision status — clear to proceed

Checked 2026-09-15: `feature/scanner-venv-mvp` is **fully merged** (0 commits
ahead of main). The worktree at
`~/.supacode/repos/llmsnitch-cli/feature/scanner-venv-mvp` is parked on branch
`digest-outlet/T601` at `15727b2` (identical to main), holding only untracked
scratch (`docs/local/`, `graphify-out/`). Both the dep-audit and digest-outlet
efforts are CLOSED. **No active work competes with plan 012** — even though it
touches `llmsnitch/depaudit.py`, that file is fully merged and quiescent.
Proceed standalone. Do not reuse the locked worktree or the
`digest-outlet/T601` branch name.

## 2. Worktree + branch

```bash
cd $HOMEllmsnitch-cli
git worktree add ~/.supacode/repos/llmsnitch-cli/feature/digest-finding-recall -b feature/digest-finding-recall main
cd ~/.supacode/repos/llmsnitch-cli/feature/digest-finding-recall
python3 tests/all.py     # baseline green (expect ~174) BEFORE any edit
```

Branch: **`feature/digest-finding-recall`** · path:
**`~/.supacode/repos/llmsnitch-cli/feature/digest-finding-recall`**.

## 3. Team organization

Plan 012 is small and **tightly coupled** — three code touch-points
(`fs_coil/digest.py`, `llmsnitch/depaudit.py`, docs) whose steps are
sequential (state file → render → test), not independent. A large parallel
swarm would add coordination cost for ~zero parallelism. Use the lean shape
below (matches this repo's own dev→review rhythm).

| Role | Who | Does | Owns |
|---|---|---|---|
| **Orchestrator** | the lead session (you) | Sets up the worktree, reads plan 012, dispatches the implementer, runs the review loop, re-checks done criteria, writes the final report. Does **not** edit source directly. | the loop + verdict |
| **Implementer** | 1 task agent | TDD plan 012 steps 1–4 + all 7 tests. Reports the diff + `tests/all.py` output. | **all** touched files (single owner → no intra-team file conflict): `fs_coil/digest.py`, `llmsnitch/depaudit.py`, `tests/test_digest.py`, `tests/test_depaudit.py`, `docs/notifier-spec.md` |
| **Reviewer** | 1 task agent | After green, runs the two repo review gates on the diff (see §5). Returns findings only. | review verdict |

One implementer owns every file, so there is no file-conflict risk. Do **not**
split files across parallel implementers here — the render depends on what
`health_report()` produces; splitting would thrash the interface.

## 4. Execution loop

1. **Baseline:** `python3 tests/all.py` green on the fresh worktree.
2. **Implement (TDD):** implementer writes the failing tests from plan 012's
   test plan first, then steps 1–4, until `tests/all.py` is green (was ~174 →
   ~181). Test files: `tests/test_digest.py` (cases 1–5,7),
   `tests/test_depaudit.py` (case 6). Fixtures: `tests/_seams.py` already has
   `seed_ledger()` and `row()` — reuse them, do not reinvent.
3. **Review:** dispatch the reviewer (§5). Orchestrator triages findings.
4. **Fix loop:** implementer addresses accepted findings; re-run
   `tests/all.py`. Cap at **3 rounds** — if not converged, STOP and report.
5. **Verify done criteria** (plan 012 §"Done criteria"): `tests/all.py`,
   `compileall`, pyflakes, the no-import grep
   (`grep -n "import llmsnitch\|from llmsnitch" fs_coil/digest.py` → empty),
   and the live smoke (seed a temp `LLMSNITCH_DIR` patrol meta with a
   critical; confirm the `open findings (last patrol):` line renders).
6. **Report** (do not merge): summarize the diff, the test delta, review
   outcome, and the exact `git worktree` path + branch for the maintainer to
   merge via `/worktree-merge` or manual FF. Leave the branch committed and
   clean.

## 5. Review gates (repo convention)

Run both on the final diff, as separate reviewer passes:
- `code-review` (two-axis: **Standards** — does it match repo conventions? +
  **Spec** — does it do what plan 012 asked?).
- `ponytail:ponytail-review` (over-engineering only — the readout must be a
  few lines off producer state, not a new subsystem).

Treat the implementer's diff as untrusted until reviewed: every hunk must
trace to a plan 012 step. Reject out-of-scope changes (the plan forbids
touching the ② new-logic, waivers, and any `notify()`/banner path).

## 6. House rules (bind every agent — non-negotiable)

- **Local-only repo.** Never add a remote, never `git push`, no GitHub/PRs.
  Leave the branch for the maintainer.
- **`trash`, never `rm`/`rm -rf`** (no fallback).
- **Never run `install.sh`.** Never `pipx install`/reinstall — this is a
  worktree build, not an activation.
- **Stdlib only, no network imports** — test-enforced; do not add a dep.
- **`fs_coil` must not import `llmsnitch`** (plan 012 D1). The readout reads
  *producer state files*, not llmsnitch modules.
- **Files 0600, dirs 0700** where the code creates them.
- Gate is `python3 tests/all.py` (the whole suite). A single file still runs
  standalone: `python3 tests/test_digest.py`.

## 7. Subagent caution (learned the hard way)

Spawned agents on this box have died on `ECONNRESET` during **parallel file
reads**. Mitigations: keep subagent scopes **small**, have agents read **one
file at a time** (no fan-out of many concurrent Reads), and prefer the
orchestrator doing broad reads in-line over delegating a wide read sweep. The
work here is sequential anyway — lean into that.

## 8. Definition of done

- `tests/all.py` green, ~7 new tests, done-criteria commands all pass.
- Diff limited to the five files in plan 012's scope.
- Both review gates applied; findings resolved or explicitly deferred.
- Branch `feature/digest-finding-recall` committed, clean, **unmerged**.
- Final report names the worktree path + branch and how to merge.
