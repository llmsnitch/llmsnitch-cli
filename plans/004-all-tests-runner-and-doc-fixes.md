# Plan 004: One command runs all 56 tests; docs stop lying about the suite

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat db238b9..HEAD -- tests/ CLAUDE.md README.md`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none — do this plan FIRST; every later plan uses its runner as the verification gate
- **Category**: dx
- **Planned at**: commit `db238b9`, 2026-09-12

## Why this matters

`CLAUDE.md` line 44 calls `python3 tests/test_llmsnitch.py` "the whole suite",
but that runs only 34 of the repo's 56 tests. `tests/test_notify.py` (14
tests) and `tests/test_scan_notify.py` (8 tests) each need their own
invocation that no doc names. A contributor (or executor of plans 005–010)
sees "34/34 passed" and believes the build is green without ever exercising
the notify layer. Separately, the env-var test seams and the patrol log
locations are discoverable only by reading source.

## Current state

- `tests/test_llmsnitch.py:627-629`, `tests/test_notify.py`,
  `tests/test_scan_notify.py` — each ends with:
  ```python
  if __name__ == "__main__":
      from tests._seams import run
      sys.exit(run(globals()))
  ```
- `tests/_seams.py:55-72` — `run(globs)` executes every callable named
  `test_*` in the dict, prints PASS/FAIL, returns 0/1. Test files insert the
  repo root on `sys.path` and import `tests._seams` as a namespace package
  (there is no `tests/__init__.py` — that is fine on Python 3.9+; do not add
  one).
- `CLAUDE.md:44` — `python3 tests/test_llmsnitch.py       # the whole suite; stdlib runner, no pytest`
- `README.md` "## Test" section — shows only the one file.
- Undocumented env seams (used by tests, listed in `fs_coil/notify.py:9-12`
  and `tests/_seams.py:22-26`): `LLMSNITCH_DIR`, `LLMSNITCH_NOTIFY_DIR`,
  `LLMSNITCH_HOT_STATE`, `LLMSNITCH_CONFIG`; plus `CODEX_HOME`
  (`llmsnitch/harness.py:142`). Patrol logs land at
  `~/Library/Logs/llmsnitch/patrol.{out,err}` (`llmsnitch/patrol.py:33-34`).
- House rule (user global CLAUDE.md): before adding content to any CLAUDE.md,
  check it is under 150 lines / 8 KB. The project `CLAUDE.md` is currently
  ~60 lines — the ~8 lines added here are fine; verify anyway.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Old suite | `python3 tests/test_llmsnitch.py` | `34/34 passed`, exit 0 |
| Notify tests | `python3 tests/test_notify.py` | `14/14 passed`, exit 0 |
| Scan-notify tests | `python3 tests/test_scan_notify.py` | `8/8 passed`, exit 0 |
| New runner (after step 1) | `python3 tests/all.py` | three PASS blocks, exit 0 |

## Scope

**In scope** (the only files you should modify/create):
- `tests/all.py` (create)
- `CLAUDE.md` (two-line command fix + short Environment subsection)
- `README.md` ("## Test" section + one patrol-logs line)

**Out of scope**: `tests/_seams.py`, the three existing test files (keep them
individually runnable), everything under `llmsnitch/` and `fs_coil/`.

## Git workflow

This repo is **local-only**: never push, never add a remote, never open a PR.
Commit on the current branch, imperative subject line, ending with
`Co-Authored-By:` matching recent `git log` entries. Never use `rm` — use
`trash` if a file must go.

## Steps

### Step 1: Create `tests/all.py`

Run each test module through `_seams.run` separately (separate runs, not a
merged dict — merging would let a duplicated `test_*` name shadow silently):

```python
"""Run every test file in one command. Exit nonzero if any test fails."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests import _seams, test_llmsnitch, test_notify, test_scan_notify  # noqa: E402

code = 0
for mod in (test_llmsnitch, test_notify, test_scan_notify):
    print(f"== {mod.__name__} ==")
    code |= _seams.run(vars(mod))
sys.exit(code)
```

**Verify**: `python3 tests/all.py` → three blocks printing
`34/34 passed`, `14/14 passed`, `8/8 passed`; `echo $?` → `0`.

### Step 2: Verify the runner actually fails on failure

Temporarily append `def test_zz_fail(): assert False` to
`tests/test_scan_notify.py`, run `python3 tests/all.py`, confirm exit code 1
and a FAIL line; then remove the temporary test.

**Verify**: after removal, `python3 tests/all.py` → exit 0 and
`git diff tests/test_scan_notify.py` → empty.

### Step 3: Fix the docs

- `CLAUDE.md`: change line 44's command to
  `python3 tests/all.py                 # the whole suite (3 files); stdlib runner, no pytest`
  and keep a line noting single-file runs still work. Add a short
  "Environment" subsection under Commands listing: `LLMSNITCH_DIR`,
  `LLMSNITCH_NOTIFY_DIR`, `LLMSNITCH_HOT_STATE`, `LLMSNITCH_CONFIG` (test
  seams; production never sets the last three), `CODEX_HOME` (relocates
  `~/.codex` for ingest), and patrol logs at
  `~/Library/Logs/llmsnitch/patrol.{out,err}`.
- `README.md`: "## Test" section → `python3 tests/all.py`; add one line to
  the Use section: patrol logs live at `~/Library/Logs/llmsnitch/patrol.{out,err}`.

**Verify**: `wc -l CLAUDE.md` → under 150; `grep -n "tests/all.py" CLAUDE.md README.md` → both hit.

## Test plan

Step 2 is the runner's own check (fails red, passes green). No other new
tests — this plan adds a runner, not behavior.

## Done criteria

- [ ] `python3 tests/all.py` exits 0 with 34+14+8 passes
- [ ] `python3 tests/test_llmsnitch.py` still exits 0 (single-file mode intact)
- [ ] `grep -rn "the whole suite" CLAUDE.md` names `tests/all.py`, not the single file
- [ ] `git status` shows only the three in-scope files changed/added
- [ ] `plans/README.md` status row updated

## STOP conditions

- `from tests import test_notify` fails at import time (namespace-package
  assumption wrong) — report; do not add `tests/__init__.py` on your own.
- Any of the three files does not pass standalone before your change.
- CLAUDE.md is over 150 lines / 8 KB before your edit (house rule: extract
  before adding — report instead).

## Maintenance notes

- Plans 005–010 use `python3 tests/all.py` as their verification gate.
- If a fourth test file is ever added, it must be appended to the tuple in
  `tests/all.py` — nothing discovers files automatically (deliberate: no
  magic, no framework).
