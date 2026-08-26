# Plan 002: Make walk-budget truncation visible (skipped count is always 0)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat a7a83bb..HEAD -- llmsnitch/scan.py tests/test_llmsnitch.py`
> On any in-scope change since `a7a83bb`, compare the "Current state"
> excerpts against live code first; mismatch = STOP.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `a7a83bb`, 2026-08-26

## Why this matters

On any tree with more than `_MAX_FILES` (4000) files, the discovery walk
stops — by design — but the "skipped" counter that is supposed to make the
truncation visible is arithmetically incapable of going above zero. A
security audit that silently stopped scanning looks identical to a clean
scan. This contradicts the module's own stated invariant
(`llmsnitch/scan.py:32`: "walk cap; overflow is counted, never silent").

## Current state

- `llmsnitch/scan.py:96-104` (`_walk`) — the budget check runs BEFORE the
  decrement, so `budget[0]` bottoms out at exactly 0:

  ```python
  for fn in sorted(filenames):
      if budget[0] <= 0:
          return
      budget[0] -= 1
      yield Path(dirpath) / fn
  ```

- `llmsnitch/scan.py:146` (`discover`) — returns
  `list(seen.values()), max(0, -budget[0])`; since `budget[0]` is never
  negative, the second element is always 0.
- Dead consumers of the always-zero count: `scan.py` `run_scan` seeds
  `skipped` from it (feeds `meta["files_skipped"]`), and `cmd_scan`'s
  inventory branch prints `", {skipped} skipped (budget)"` — a line that
  can never print.
- Convention: comments state constraints (see the `_MAX_FILES` comment at
  `scan.py:32`); tests are stdlib-runner style in `tests/test_llmsnitch.py`
  (`_with_tmp_store` harness, plain `assert`).

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Scan tests | `python3 tests/test_llmsnitch.py` | all pass (count grows by 1) |
| Wiring tests | `python3 tests/test_scan_notify.py` | `8/8 passed` |

## Scope

**In scope**:
- `llmsnitch/scan.py` (`_walk`, `discover` — the accounting only)
- `tests/test_llmsnitch.py` (one new test)

**Out of scope**:
- Raising `_MAX_FILES` or changing which files are walked — the cap is a
  deliberate bound; only its *visibility* is broken.
- `llmsnitch/scan.py` `run_scan`/`cmd_scan` display code — it already
  plumbs the count correctly; it just never receives a nonzero one.

## Git workflow

- Current branch `research/scanner-survey-mvp`; local-only repo — never
  add a remote or push. One commit, style `scan: <summary>` +
  `Co-Authored-By: Claude <noreply@anthropic.com>`.

## Steps

### Step 1: Failing test

In `tests/test_llmsnitch.py`, add a test that monkeypatches the cap small
instead of creating 4000 files:

```python
def test_scan_walk_budget_overflow_is_counted():
    """Truncated discovery must be visible, not silent (scan.py:32)."""
    from llmsnitch import scan
    def body(t):
        root = t / "proj" / ".claude" / "skills" / "s"
        root.mkdir(parents=True)
        for i in range(12):
            (root / f"SKILL{i}.py").write_text("print()\n")
        (root / "SKILL.md").write_text("---\nname: s\n---\nhi\n")
        old = scan._MAX_FILES
        scan._MAX_FILES = 5
        try:
            targets, skipped = scan.discover([str(t / "proj")])
        finally:
            scan._MAX_FILES = old
        assert skipped > 0, "budget overflow was silent"
        assert len(targets) <= 5
    _with_tmp_store(body)
```

Note: `discover` reads `_MAX_FILES` at call time (`budget = [_MAX_FILES]`),
so the monkeypatch works. The walk yields every file (13 here) but only 5
survive the budget; `skipped` must reflect the overflow.

**Verify**: `python3 tests/test_llmsnitch.py` → the new test FAILS with
"budget overflow was silent".

### Step 2: Fix the accounting

In `_walk`, decrement first so exhaustion goes negative — and keep
consuming the iterator cheaply, or simpler: count what was *seen but not
yielded*. Minimal shape — change `_walk` to:

```python
        for fn in sorted(filenames):
            budget[0] -= 1
            if budget[0] < 0:
                return
            yield Path(dirpath) / fn
```

`budget[0]` now ends at `-1` when the walk was cut short (it stops at the
first over-budget file, so the count is "truncation happened", not "how
many were missed" — that is fine; a nonzero flag is the requirement). Then
in `discover`, `max(0, -budget[0])` already turns `-1` into `1`.

If you prefer an exact missed-file count, count instead of returning early
— but that walks the whole tree after the budget is spent; the flag
approach is the intended fix. Whichever you choose, update the `_MAX_FILES`
comment (`scan.py:32`) to say what the count means.

**Verify**: `python3 tests/test_llmsnitch.py` → new test passes, all
others still pass.

### Step 3: Confirm the display path lights up

Run the inventory branch against an over-budget tree by hand:

**Verify**:
`LLMSNITCH_DIR=$(mktemp -d) python3 - <<'EOF'`-style check or simply rely
on the unit test; then `python3 tests/test_scan_notify.py` → `8/8 passed`.

## Test plan

- `test_scan_walk_budget_overflow_is_counted` (step 1) — the regression
  lock: skipped > 0 when the budget is exceeded.
- Existing `test_scan_*` tests unchanged — they run under budget and must
  keep `skipped` semantics for unreadable files intact (note `run_scan`
  ALSO increments `skipped` for unreadable/binary files; don't conflate).

## Done criteria

- [ ] `python3 tests/test_llmsnitch.py` exits 0 with the new test passing
- [ ] `python3 tests/test_scan_notify.py` exits 0
- [ ] `git status` — only in-scope files modified
- [ ] `plans/README.md` status row updated

## STOP conditions

- `_walk`/`discover` don't match the excerpts (drift).
- The new test passes before the fix (already fixed elsewhere).
- Fixing the counter changes any existing test's pass/fail — the fix must
  be purely additive accounting.

## Maintenance notes

- `meta["files_skipped"]` mixes two causes (budget overflow + unreadable/
  oversized/binary files). If that ever needs disambiguating, split it into
  `files_skipped` and `walk_truncated` in meta — deferred here because no
  consumer needs the distinction yet.
- If `_MAX_FILES` is ever raised, the test's monkeypatch keeps working
  (it pins its own cap).
