# Plan 009: The untested guard branches get tests

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat db238b9..HEAD -- llmsnitch/cli.py llmsnitch/scan.py llmsnitch/patrol.py llmsnitch/harness.py tests/test_llmsnitch.py`
> Plans 005–007 legitimately touch some of these files — that diff being
> non-empty is EXPECTED if they ran first. Only treat it as a STOP condition
> when a "Current state" excerpt below no longer matches the live code.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Depends on**: plans/004 (runner); run AFTER 005–007 if those are queued, so these tests pin final behavior
- **Category**: tests
- **Planned at**: commit `db238b9`, 2026-09-12

## Why this matters

The four most-churned modules of the last quarter (`scan`, `cli`, `harness`,
`ingest`) have their entry dispatch and guard branches unexercised: a change
that broke `cli.main`'s command routing, `_walk`'s junk-dir/depth guards, the
patrol launchctl branch, or the alien-ledger rejection would pass the whole
suite. These are cheap, high-leverage characterization tests — plus one
composition assert that pins the `hook._SECRET`-inside-`scan._SECRET_ALL`
embedding a prior audit flagged as a fragile cross-module contract.

## Current state

All in `tests/test_llmsnitch.py` style: plain `test_*` functions, `assert`
statements, tmp dirs via `LLMSNITCH_DIR` env (see existing tests and
`tests/_seams.py`). Targets:

- `llmsnitch/cli.py:91-125` — `main(argv)`: `--version` → writes version,
  returns 0; no args → writes `__doc__`, returns 0 (cmd defaults to "help");
  unknown cmd → writes `__doc__`, returns 2. `list`/`show`/`check` run a
  lazy `ingest.sweep()` wrapped in try/except first.
- `llmsnitch/scan.py:85-101` — `_walk` prunes `_SKIP_DIRS`
  (`.git, node_modules, __pycache__, .venv, venv, dist, build, target`),
  prunes dot-dirs except an allowlist, and stops descending at
  `_MAX_DEPTH = 6` below the root.
- `llmsnitch/scan.py:104-146` — `discover(roots)` classifies files
  (`classify`, lines 64-82: `SKILL.md` → `skill_manifest`, `CLAUDE.md` →
  `instruction_file`, etc.) and returns `(targets, skipped)`.
- `llmsnitch/patrol.py:48-78` — `run(write, out, plist_path=None)`:
  `default = plist_path is None`; the default branch mkdirs
  `~/Library/LaunchAgents` + `~/Library/Logs/llmsnitch`, writes the plist,
  then `subprocess.run(["launchctl", "bootout", ...])` and
  `["launchctl", "bootstrap", ...]`; bootstrap rc != 0 → returns 2. Paths
  come from `Path("~/...").expanduser()` and `os.path.expanduser("~")` —
  both honor the `HOME` env var.
- `llmsnitch/harness.py:115-116` — `parse_codex` returns `None` when the
  file yields neither a `session_meta` id nor any model
  (`if native_id is None and not models: return None`); `ingest.sweep`
  then records the cursor but writes no session.
- `llmsnitch/scan.py:152-154` — `_SECRET_ALL` embeds `hook._SECRET.pattern`
  inside `(?<![A-Za-z0-9])(?:...)`. The composition invariant to pin:
  everything `hook._SECRET` matches at a non-alnum left edge,
  `_SECRET_ALL` must also match.
- Fixture exemplar: `_with_codex_fixture` in `tests/test_llmsnitch.py`
  (builds a fake `CODEX_HOME` tree) — reuse it for the alien-file test.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Full suite | `python3 tests/all.py` | all pass, exit 0 |

## Scope

**In scope**: `tests/test_llmsnitch.py` only (additive tests). No production
file changes — if a test reveals a real bug, that is a STOP condition, not a
license to fix it here.

**Out of scope**: everything under `llmsnitch/` and `fs_coil/`;
`tests/_seams.py` (add local helpers in the test file instead).

## Git workflow

Local-only repo: never push, no PRs. Commit on the current branch, imperative
subject, `Co-Authored-By:` line per recent `git log`. Use `trash`, never `rm`.

## Steps

### Step 1: `test_cli_main_dispatch`

With `LLMSNITCH_DIR` pointed at a tmp dir (so the lazy sweep touches nothing
real) and an `io.StringIO()` out... note `main` writes to `sys.stdout`
directly — capture via `contextlib.redirect_stdout`. Assert:
`main(["--version"])` returns 0 and output contains `llmsnitch`;
`main([])` returns 0 and output contains `llmsnitch CLI` (the docstring);
`main(["frobnicate"])` returns 2.

**Verify**: run the single test →
`python3 -c "import sys; sys.path.insert(0,'.'); from tests.test_llmsnitch import test_cli_main_dispatch as t; t()"` → exit 0.

### Step 2: `test_scan_walk_skips_junk_and_depth`

Build a tmp tree: `root/node_modules/CLAUDE.md`, `root/.git/CLAUDE.md`,
`root/a/b/c/d/e/f/g/CLAUDE.md` (8 levels — beyond `_MAX_DEPTH`), and
`root/keep/CLAUDE.md`. Call `scan.discover([str(root)])` and assert exactly
one target (the `keep` one) and that no returned path contains
`node_modules`, `.git`, or the depth-8 leaf.

**Verify**: single-test run as in Step 1 → exit 0.

### Step 3: `test_patrol_write_default_path_and_launchctl`

Monkeypatch by assignment (repo style — see `_seams.with_tmp` restoring
globals in `finally`):

- Point `HOME` at a tmp dir via `os.environ` (save/restore in `finally`) so
  both `expanduser` call styles land in the sandbox.
- Replace `patrol.subprocess.run` with a recorder returning an object with
  `returncode=0`, `stdout=""`, `stderr=""` (a tiny `types.SimpleNamespace`).

Call `patrol.run(True, io.StringIO())` (no `plist_path` → default branch).
Assert: return 0; the plist exists at
`<tmp>/Library/LaunchAgents/com.slav-it.llmsnitch-patrol.plist`;
`<tmp>/Library/Logs/llmsnitch/` exists; the recorder saw a `bootout` call
then a `bootstrap` call. Second case: recorder returns `returncode=1` for
bootstrap → `run` returns 2.

**Verify**: single-test run → exit 0. Also confirm nothing was written to the
real `~/Library/LaunchAgents` (assert before/after mtime or just eyeball
`ls -la ~/Library/LaunchAgents | grep slav-it` unchanged).

### Step 4: `test_ingest_skips_alien_ledger`

Using `_with_codex_fixture` (or its pattern): drop a rollout-named file whose
lines are valid JSON but carry no `session_meta` and no `token_count`/model
rows. Run `ingest.sweep()`. Assert: return counts 0 new sessions for that
file, no `sessions/codex-*` dir was created for it, and a second `sweep()`
also skips it (cursor recorded).

**Verify**: single-test run → exit 0.

### Step 5: `test_secret_pattern_composition`

```python
def test_secret_pattern_composition():
    from llmsnitch import scan
    from llmsnitch.hook import _SECRET
    for canary in ("sk-abcdefgh1234", "ghp_abcdefghij12",
                   "xoxb-1234567890-ab", "AKIAABCDEFGHIJKLMNOP",
                   "eyJ" + "a" * 40, "Bearer " + "a" * 20,
                   "-----BEGIN RSA PRIVATE KEY-----"):
        assert _SECRET.search(canary), canary
        assert scan._SECRET_ALL.search(" " + canary), canary
```

Pins the embedding: any future `hook._SECRET` edit that breaks the
`(?:...)`-wrapping in `scan._SECRET_ALL` fails here at pattern level.

**Verify**: single-test run → exit 0.

### Step 6: Full gate

**Verify**: `python3 tests/all.py` → all pass; total count grew by 5.

## Test plan

This plan IS the test plan — five tests listed above, each with its target
branch named in Current state.

## Done criteria

- [ ] `python3 tests/all.py` exits 0; the five new tests all appear as PASS
- [ ] `git status` — only `tests/test_llmsnitch.py` changed
- [ ] Real `~/Library/LaunchAgents` untouched
- [ ] `plans/README.md` status row updated

## STOP conditions

- Any new test exposes a real production bug (e.g. `_walk` doesn't actually
  prune, or `main([])` returns nonzero) — STOP and report the bug; do not
  patch production code under this plan.
- `patrol.py` stops using module-level `subprocess` (import style changed) —
  the monkeypatch seam is gone; report.
- `HOME` override doesn't redirect `expanduser` on this platform — report
  rather than writing to the real home.

## Maintenance notes

- Step 3's recorder is the pattern for any future launchctl-touching test.
- If plan 006 landed, session-id sanitize behavior is already pinned by its
  own test — don't duplicate it here.
