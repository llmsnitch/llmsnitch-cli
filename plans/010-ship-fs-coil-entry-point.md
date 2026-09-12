# Plan 010: The wheel's fs_coil code becomes invokable — ship an `fs-coil` entry point

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat db238b9..HEAD -- pyproject.toml bin/fs-coil fs_coil/cli.py`
> On any change, compare the "Current state" excerpts against live code; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P3
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/004 (verification gate)
- **Category**: tech-debt
- **Planned at**: commit `db238b9`, 2026-09-12

## Why this matters

`pyproject.toml` deliberately ships the whole `fs_coil` package (documented
decision: the scan's notify routing imports it — see the comment at
`pyproject.toml:17-21`), but declares no way to run it: the only script is
`llmsnitch`, and `bin/fs-coil` (the dev/`/usr/local/share` dispatcher) is
neither installed nor on `PATH` after `pip install .`. So a pip/pipx install
carries the dashboard/monitor code but can't invoke it. One line in
`[project.scripts]` closes the gap.

## Current state

- `pyproject.toml:14-15`:
  ```toml
  [project.scripts]
  llmsnitch = "llmsnitch.cli:main"
  ```
- `fs_coil/cli.py:67` — `def main():` exists, parses `sys.argv`, dispatches;
  `bin/fs-coil:17-23` already calls exactly `from fs_coil.cli import main` /
  `main()` with a `KeyboardInterrupt` → exit 130 wrapper.
- `bin/fs-coil` stays: it serves the non-pip layout
  (`/usr/local/share/llmsnitch`) and dev checkouts.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Import check | `python3 -c "from fs_coil.cli import main; print(callable(main))"` (from repo root) | `True` |
| TOML validity | `python3 -c "import tomllib; tomllib.load(open('pyproject.toml','rb')); print('ok')"` | `ok` |
| Full suite | `python3 tests/all.py` | all pass, exit 0 |

## Scope

**In scope**: `pyproject.toml` (one line).

**Out of scope**: `bin/fs-coil` (keep as-is), `fs_coil/cli.py`, any
repackaging/slimming of what the wheel ships — a prior audit explicitly
rejected narrowing the `fs_coil` payload (documented decision + convergence
comment in `pyproject.toml`); do not revisit it here.

## Git workflow

Local-only repo: never push, no PRs. Commit on the current branch, imperative
subject, `Co-Authored-By:` line per recent `git log`. Use `trash`, never `rm`.
House rule: **never run `install.sh`**.

## Steps

### Step 1: Declare the script

In `pyproject.toml` `[project.scripts]`:

```toml
[project.scripts]
llmsnitch = "llmsnitch.cli:main"
fs-coil = "fs_coil.cli:main"
```

**Verify**: the TOML-validity and import-check commands above → `ok` / `True`.

### Step 2: Prove the entry point resolves in a throwaway env

Build in an isolated venv **inside the scratch/tmp area, never the repo**:

```bash
python3 -m venv /tmp/llmsnitch-ep-check && /tmp/llmsnitch-ep-check/bin/pip -q install . && /tmp/llmsnitch-ep-check/bin/fs-coil --help
```

Expected: help/usage text from `fs_coil.cli` (any exit code ≤ 2, no
`ModuleNotFoundError`, no traceback). Then remove the venv with
`trash /tmp/llmsnitch-ep-check` (house rule: never `rm`).

**Verify**: as above; plus `python3 tests/all.py` → all pass (nothing in the
suite depends on entry points, so this is the no-collateral check).

## Test plan

No new tests — packaging metadata isn't reachable from the stdlib test
runner; Step 2 is the executable verification.

## Done criteria

- [ ] `grep -n 'fs-coil = "fs_coil.cli:main"' pyproject.toml` → one hit
- [ ] Step 2's `fs-coil --help` ran without traceback in the throwaway venv
- [ ] `python3 tests/all.py` exits 0
- [ ] `git status` — only `pyproject.toml` changed
- [ ] `plans/README.md` status row updated

## STOP conditions

- `fs_coil.cli.main` does anything at import time beyond definitions
  (imports failing outside macOS paths, side effects) that makes `--help`
  traceback — report; the entry point may need a lazy-import shim, which is a
  design call, not an improvisation.
- `pip install .` in the venv fails for a pre-existing packaging reason.

## Maintenance notes

- Alternative considered: delete `bin/fs-coil` and document the split-install
  story instead. The entry point was chosen because it makes shipped bytes
  invokable with one line and keeps both layouts working.
- If the wheel is ever slimmed (rejected for now), this script line is the
  first thing that breaks — they must move together.
