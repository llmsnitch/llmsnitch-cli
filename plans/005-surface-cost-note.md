# Plan 005: `cost_note` actually reaches the user

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat db238b9..HEAD -- llmsnitch/store.py llmsnitch/cli.py tests/test_llmsnitch.py`
> On any change, compare the "Current state" excerpts against live code; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/004 (verification gate)
- **Category**: bug
- **Planned at**: commit `db238b9`, 2026-09-12

## Why this matters

Two writers store an honesty caveat in `meta.json` that no reader can ever
display. `hook._finalize` writes `cost_note: "unknown model priced at sonnet
tier"` (`llmsnitch/hook.py:150`) and `ingest._write_session` writes
`cost_note: "unpriced: no vendor-cited rates…"` (`llmsnitch/ingest.py:87`).
But `store.summarize()` omits the key from its dict, and `cli.cmd_show` reads
`s.get("cost_note")` *inside* a block gated on `cost_usd is not None` — which
is always `None` for ingested (codex) sessions. Net effect: cost figures
display uncaveated, breaking the README's "labeled as an estimate" promise.

## Current state

- `llmsnitch/store.py:109-123` — `summarize()` returns a dict including
  `cost_usd`, `total_tokens`, … but **no `cost_note`** even though
  `meta = read_meta(session_id)` is in scope.
- `llmsnitch/cli.py:69-77`:
  ```python
  if s.get("cost_usd") is not None:
      ...
      if s.get("cost_note"):
          out.write(f"          {s['cost_note']}\n")
  ```
  The inner read is doubly dead: the key never exists, and codex rows never
  enter the outer block.
- Repo convention: `cmd_show` writes aligned two-column lines
  (`f"harness   {…}"`); match that.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Full suite | `python3 tests/all.py` | all pass, exit 0 |
| One test | `python3 -c "import sys; sys.path.insert(0,'.'); from tests.test_llmsnitch import <name> as t; t()"` | no output, exit 0 |

## Scope

**In scope**: `llmsnitch/store.py`, `llmsnitch/cli.py`,
`tests/test_llmsnitch.py`.

**Out of scope**: `llmsnitch/hook.py`, `llmsnitch/ingest.py` (the writers are
correct), `cmd_list` (the note is per-session detail; the list view already
carries the `~$`/`EST.COST` labeling).

## Git workflow

Local-only repo: never push, no PRs. Commit on the current branch, imperative
subject, `Co-Authored-By:` line per recent `git log`. Use `trash`, never `rm`.

## Steps

### Step 1: Carry `cost_note` through `summarize()`

In `llmsnitch/store.py`, add to the returned dict (beside `cost_usd`):

```python
"cost_note": meta.get("cost_note"),
```

**Verify**: `python3 -c "import sys; sys.path.insert(0,'.'); from llmsnitch import store; print('cost_note' in store.summarize('nonexistent'))"` → `True`

### Step 2: Print the note independently of the cost block

In `llmsnitch/cli.py` `cmd_show`, move the `cost_note` output OUT of the
`if s.get("cost_usd") is not None:` block so it prints whenever present —
after the cost block, as its own line matching the column style:

```python
if s.get("cost_note"):
    out.write(f"note      {s['cost_note']}\n")
```

Delete the now-dead inner `if s.get("cost_note"):` lines.

**Verify**: `python3 tests/all.py` → all pass (regression check before new test).

### Step 3: Regression test

Add `test_cost_note_shown_in_show` to `tests/test_llmsnitch.py`, modeled on
the existing `test_codex_store_modes_and_list_column` (which builds a store
via `_seams.with_tmp(..., store=True)` and calls `cmd_show` with an
`io.StringIO`). Arrange: write a session whose `meta.json` has
`cost_usd: None` and `cost_note: "unpriced: no vendor-cited rates for this provider yet"`
(the ingest shape). Assert the `show` output contains `unpriced`. Second
assert: a meta with `cost_usd: 1.23` and
`cost_note: "unknown model priced at sonnet tier"` shows both the cost line
and the note.

**Verify**: `python3 tests/all.py` → 57 tests total, all pass.

## Test plan

Covered by Step 3: the two real writer shapes (note-without-cost, note-with-
cost). No other cases exist — `cost_note` has exactly two producers.

## Done criteria

- [ ] `python3 tests/all.py` exits 0, includes `test_cost_note_shown_in_show`
- [ ] `grep -n "cost_note" llmsnitch/store.py` → one hit inside `summarize`
- [ ] In `llmsnitch/cli.py`, the `cost_note` write is not nested under the
      `cost_usd is not None` branch
- [ ] `git status` — only in-scope files changed
- [ ] `plans/README.md` status row updated

## STOP conditions

- `summarize()` no longer reads `meta` (refactored away) — the one-line carry
  doesn't apply; report.
- Any existing test asserts the exact line count/format of `cmd_show` output
  and fails for a reason other than the added `note` line.

## Maintenance notes

- If a third `cost_note` producer appears (e.g. a future harness parser),
  nothing else is needed — the display path is now generic.
- Reviewer: check the note line renders sensibly in `show` for a codex
  session (`cost_usd` absent) — that was the fully-dead path.
