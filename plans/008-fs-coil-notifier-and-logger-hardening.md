# Plan 008: fs_coil — sanitize the icon-cache key, create logs 0600

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat db238b9..HEAD -- fs_coil/notifier.py fs_coil/logger.py tests/test_notify.py`
> On any change, compare the "Current state" excerpts against live code; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P3
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/004 (verification gate)
- **Category**: security
- **Planned at**: commit `db238b9`, 2026-09-12

## Why this matters

Two hardening gaps in fs_coil, both defense-in-depth (no known trigger today):

1. `Notifier._resolve_icon` uses the raw actor string as a **filename**:
   `key = actor.lower()` then `self._icon_dir / f"{key}.png"` and
   `self._icon_override_dir / f"{key}{ext}"`. Today `icon_actor` is always a
   normalized actor bucket, but nothing enforces that at this boundary — a
   separator-bearing actor would read and *write* (as root, in daemon mode,
   followed by a chown) at attacker-influenced paths.
2. `Logger._open_today` creates the daily log with `open(..., "a")` then
   chmods 0600 — the same first-write umask window plan 007 closes in
   llmsnitch. The daemon can run as root; its log lines contain event paths.

## Current state

- `fs_coil/notifier.py:58-104` (`_resolve_icon`):
  ```python
  key = actor.lower()
  ...
  o = self._icon_override_dir / f"{key}{ext}"
  ...
  cached = self._icon_dir / f"{key}.png"
  ```
- `fs_coil/logger.py:108-118` (`_open_today`):
  ```python
  logfile = self.dir / f"fs-coil-{day}.log"
  self._fp = open(logfile, "a", buffering=1)
  try:
      os.chmod(logfile, 0o600)
  ```
- The in-repo exemplar for create-0600: `fs_coil/notify.py:152`
  (`os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)`).
- fs_coil tests live in `tests/test_notify.py` (assert-style, run via
  `python3 tests/all.py`); `re` is already imported in `notifier.py`? —
  check: it is NOT; add the import if you use it.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Full suite | `python3 tests/all.py` | all pass, exit 0 |

## Scope

**In scope**: `fs_coil/notifier.py`, `fs_coil/logger.py`,
`tests/test_notify.py`.

**Out of scope**: `fs_coil/notify.py` (already correct), `fs_coil/icons.py`,
all `render_*.py`, `fs_coil/monitor.py` / `light_watcher.py` call sites (they
pass bucket names; the fix belongs at the boundary).

## Git workflow

Local-only repo: never push, no PRs. Commit on the current branch, imperative
subject, `Co-Authored-By:` line per recent `git log`. Use `trash`, never `rm`.

## Steps

### Step 1: Factor and sanitize the icon key

In `fs_coil/notifier.py`, add a module-level helper and use it as the single
key source in `_resolve_icon`:

```python
import re  # with the other imports

def _icon_key(actor):
    """Filename-safe cache key for an actor string."""
    return re.sub(r"[^a-z0-9._-]", "_", (actor or "").lower())[:64]
```

In `_resolve_icon`, replace `key = actor.lower()` with
`key = _icon_key(actor)` and early-return `None` when `key` is empty. All
later uses of `key` (cache dict, override path, cached path) stay unchanged.

**Verify**: `python3 -c "import sys; sys.path.insert(0,'.'); from fs_coil.notifier import _icon_key; print(_icon_key('../../Evil Actor'))"` → `.._.._evil_actor`

### Step 2: Create the daily log 0600

In `Logger._open_today`, replace the `open(...)` line with:

```python
fd = os.open(logfile, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
self._fp = os.fdopen(fd, "a", buffering=1)
```

Keep the following `os.chmod` block (repairs pre-existing files) and the
root-chown block unchanged. Note `logfile` is a `Path` — `os.open` accepts it.

**Verify**: `python3 tests/all.py` → all pass.

### Step 3: One assert for the key sanitizer

Add `test_icon_key_is_filename_safe` to `tests/test_notify.py` (a plain
function, no scaffolding needed):

```python
def test_icon_key_is_filename_safe():
    from fs_coil.notifier import _icon_key
    assert _icon_key("../../Evil Actor") == ".._.._evil_actor"
    assert "/" not in _icon_key("a/b\\c")
    assert _icon_key("") == ""
    assert _icon_key("claude-code") == "claude-code"
```

**Verify**: `python3 tests/all.py` → all pass including the new test.

## Test plan

Step 3 covers the sanitizer (hostile, empty, benign). The logger change is
exercised by any test that triggers `_log_error` → `Logger.write`; the suite
passing is the regression gate (a perms assert would need to control
`Logger`'s home-dir resolution — not worth scaffolding for one chmod-order
change; the pattern is proven in `notify.py`).

## Done criteria

- [ ] `python3 tests/all.py` exits 0, includes `test_icon_key_is_filename_safe`
- [ ] `grep -n "actor.lower()" fs_coil/notifier.py` → no matches
- [ ] `grep -n 'open(logfile, "a"' fs_coil/logger.py` → no matches
- [ ] `git status` — only in-scope files changed
- [ ] `plans/README.md` status row updated

## STOP conditions

- `_resolve_icon` has been refactored so `key` is no longer the single path
  component (drift) — report.
- Any test fails on the `os.fdopen` buffering behavior (`buffering=1` on a
  text-mode fdopen is expected to work exactly like `open`; if not, report
  rather than switching to unbuffered).

## Maintenance notes

- `_icon_key` collisions (two actors sanitizing to the same key) share an
  icon — cosmetic and acceptable; actors are normalized buckets in practice.
- If `icon_actor` ever starts carrying raw process names, the sanitizer is
  already the boundary — no call-site changes needed.
