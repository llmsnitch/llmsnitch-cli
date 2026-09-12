# Plan 007: Close the three small redaction/permissions gaps in llmsnitch

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat db238b9..HEAD -- llmsnitch/hook.py llmsnitch/store.py llmsnitch/ingest.py llmsnitch/scan.py tests/test_llmsnitch.py`
> On any change, compare the "Current state" excerpts against live code; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/004 (verification gate)
- **Category**: security
- **Planned at**: commit `db238b9`, 2026-09-12

## Why this matters

Three independent, small gaps in the "secrets are redacted before disk /
files are 0600" doctrine:

1. **Dict keys are never redacted.** `_clean` redacts string *values* but
   maps keys through `str(k)[:100]` with no `_SECRET.sub` — a secret used as
   a mapping key lands on disk verbatim.
2. **Truncate-then-redact strands fragments.** `_clean` cuts strings at 2000
   chars *before* redacting; a secret straddling the cut leaves an unmatched
   head (up to ~40 chars of a JWT) unredacted. Same for the 400-char error
   excerpt.
3. **0600 is applied after content is on disk.** `append_event`/`write_meta`/
   ingest-state/baseline/scan-meta create files at umask default, then
   chmod — a first-write window at 0644 on typical umasks.
   `fs_coil/notify.py:152` already does it right.

None is urgent; all three are one-sitting fixes that keep the doctrine exact.

## Current state

- `llmsnitch/hook.py:72-91` (`_clean`):
  ```python
  if isinstance(obj, str):
      s = obj[:_MAX_STR]
      ...
      return _SECRET.sub("<redacted>", s)
  if isinstance(obj, dict):
      return {str(k)[:100]: _clean(v, depth + 1) for k, v in list(obj.items())[:50]}
  ```
  `_MAX_STR = 2000` (line 34).
- `llmsnitch/hook.py:123-124` (error excerpt):
  ```python
  ev["error_excerpt"] = _clean(json.dumps(resp)[:400] if resp else "")
  ```
- Chmod-after-write sites:
  - `llmsnitch/store.py:42-46` `append_event` — `open(p, "a")` then
    `_chmod_private(p)`
  - `llmsnitch/store.py:49-52` `write_meta` — `p.write_text(...)` then chmod
  - `llmsnitch/ingest.py:44-48` `_save_state` — same pattern
  - `llmsnitch/ingest.py:68-72` `_write_session` — `open(ev_path, "w")` then chmod
  - `llmsnitch/scan.py:257-261` `_save_baseline`, `scan.py:379-387`
    findings/meta writes — same pattern
- The exemplar (already in-repo), `fs_coil/notify.py:152`:
  ```python
  fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
  ```
- Redaction doctrine (project CLAUDE.md): high-specificity patterns; the hot
  path must stay cheap — `_clean`'s truncation exists to bound regex cost.
  Preserve that: never redact an unbounded string.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Full suite | `python3 tests/all.py` | all pass, exit 0 |

## Scope

**In scope**: `llmsnitch/hook.py`, `llmsnitch/store.py`,
`llmsnitch/ingest.py`, `llmsnitch/scan.py`, `tests/test_llmsnitch.py`.

**Out of scope**: `fs_coil/` (its logger gap is plan 008), the `_SECRET`
pattern itself (shapes are settled), `setup_cmd.py` snapshots (user-readable
settings copies, not secret stores).

## Git workflow

Local-only repo: never push, no PRs. Commit on the current branch, imperative
subject, `Co-Authored-By:` line per recent `git log`. Use `trash`, never `rm`.

## Steps

### Step 1: Redact dict keys in `_clean`

Change the dict branch to route keys through the string path:

```python
if isinstance(obj, dict):
    return {_clean(str(k)[:100], depth + 1): _clean(v, depth + 1)
            for k, v in list(obj.items())[:50]}
```

(`_clean` of a str returns a str, so keys stay hashable. Two redacted keys
can collide to `<redacted>` — acceptable: both were secrets.)

**Verify**: `python3 -c "import sys; sys.path.insert(0,'.'); from llmsnitch.hook import _clean; print(_clean({'sk-aaaaaaaaaaaa': 1}))"` → `{'<redacted>': 1}`

### Step 2: Truncate with a redaction margin

In `_clean`'s string branch, take a 256-char margin, redact, then cut to the
cap so a boundary-straddling secret is matched before the final cut:

```python
s = obj[:_MAX_STR + 256]
...
return _SECRET.sub("<redacted>", s)[:_MAX_STR]
```

Apply the final `[:_MAX_STR]` to **both** return points in the string branch
(the canonical-fold path at line ~85 and the plain path at line ~86). In
`handle`'s PostToolUse branch, widen the pre-cut the same way:

```python
ev["error_excerpt"] = _clean(json.dumps(resp)[:656])[:400] if resp else ""
```

**Verify**: `python3 -c "import sys; sys.path.insert(0,'.'); from llmsnitch.hook import _clean; s='x'*1995+'sk-'+'a'*50; r=_clean(s); print('sk-' not in r, len(r)<=2000)"` → `True True`

### Step 3: Create files 0600, not chmod-later

Add one helper to `llmsnitch/store.py` and use it at every listed site:

```python
def _open_private(path, flags):
    return os.open(str(path), flags | os.O_CREAT, 0o600)
```

- `append_event`: `fd = _open_private(p, os.O_WRONLY | os.O_APPEND)`, write
  the encoded line via `os.write`, close in `finally` (mirror
  `fs_coil/notify.py:143-156`).
- `write_meta`: open via `os.fdopen(_open_private(p, os.O_WRONLY | os.O_TRUNC), "w")`
  and write.
- `ingest._save_state`, `ingest._write_session`, `scan._save_baseline`, and
  the two writes at the end of `scan.run_scan`: same `os.fdopen` pattern
  (import from `store`).

Keep the existing `_chmod_private` calls — they repair pre-existing files
created before this change.

**Verify**: `python3 tests/all.py` → all pass.

### Step 4: Regression tests

Add to `tests/test_llmsnitch.py` (model after `test_hook_records_and_redacts`):

- `test_clean_redacts_dict_keys_and_boundary`: asserts Step 1's and Step 2's
  behaviors (dict-key secret redacted; a secret starting at position 1995 of
  a 2050-char string leaves no `sk-` in output).
- `test_new_files_created_0600`: with a tmp `LLMSNITCH_DIR`, append one event
  and write one meta, then `assert (p.stat().st_mode & 0o777) == 0o600` for
  both files.

**Verify**: `python3 tests/all.py` → all pass including the two new tests.

## Test plan

Covered in Step 4. Existing redaction tests (`test_hook_records_and_redacts`,
unicode-evasion tests) guard against regressions in the canonical-fold path.

## Done criteria

- [ ] `python3 tests/all.py` exits 0, includes the two new tests
- [ ] `grep -n "open(p, \"a\")" llmsnitch/store.py` → no matches
- [ ] `git status` — only in-scope files changed
- [ ] `plans/README.md` status row updated

## STOP conditions

- Any unicode-evasion test fails after Step 2 — the interaction between the
  margin cut and `_canonical` needs review; report, don't tweak blind.
- Timing-sensitive hot-path test (if one exists) regresses measurably.
- A write site turns out to be reached by the hook hot path in a way that
  `os.open` errors would propagate from — hot path must stay swallow-all
  (check the caller has the `except Exception` guard; `hook.handle` does).

## Maintenance notes

- The 256 margin assumes no credential prefix needs more than 256 chars to
  become matchable — true for every `_SECRET` shape (min lengths 8–40). If a
  shape with a longer minimum is ever added, bump the margin with it.
- Deferred (recorded, not planned): retrofitting old files' permissions is
  already handled by the kept `_chmod_private` calls on next touch.
