# Plan 006: Session ids are sanitized at the store boundary, not just in ingest

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat db238b9..HEAD -- llmsnitch/store.py llmsnitch/ingest.py tests/test_llmsnitch.py`
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

The repo's own doctrine (`llmsnitch/ingest.py:18-20`): "The watched harness
is the adversary: a hostile session id must not steer our writes (no
separators, no traversal)." Ingest enforces that with `_SAFE_ID`. The hook
path does not: `hook.handle` takes `session_id` straight from the hook
payload (`llmsnitch/hook.py:111`) into `store.session_dir(sid)`, which does
`sessions_root() / str(session_id)` with `mkdir(parents=True)`
(`llmsnitch/store.py:31-32`) — a traversal-shaped id creates directories and
appends NDJSON outside the store. Exploitability is low (the payload author
already runs as the user), but the same adversary doctrine is applied
inconsistently, and the fix is a choke-point one-liner.

## Current state

- `llmsnitch/store.py:27-32`:
  ```python
  def sessions_root():
      return _mkdir_private(base_dir() / "sessions")

  def session_dir(session_id):
      return _mkdir_private(sessions_root() / str(session_id))
  ```
  Read paths build the same way: `read_meta` (line 56), `iter_events`
  (line 65) — `sessions_root() / str(session_id) / ...`.
- `llmsnitch/ingest.py:21-29` — the exemplar to mirror:
  ```python
  _SAFE_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")

  def _safe_native_id(parsed, path):
      nid = parsed.get("native_id")
      if isinstance(nid, str) and _SAFE_ID.fullmatch(nid):
          return nid
      stem = os.path.basename(path).rsplit(".", 1)[0]
      return re.sub(r"[^A-Za-z0-9._-]", "_", stem)[:64] or "unnamed"
  ```
- Ingest-produced store ids are `f"{name}-{native}"` (`ingest.py:61`) — up to
  70 chars (`codex-` + 64). **The store-level pattern must therefore allow
  more than 64 chars** or every long ingested id would be rewritten and
  orphan its existing directory.
- Existing traversal test to model after: the codex-ingest traversal test at
  the end of `tests/test_llmsnitch.py` (asserts no `ESCAPED` path outside the
  tmp store and sanitized dir names).

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Full suite | `python3 tests/all.py` | all pass, exit 0 |

## Scope

**In scope**: `llmsnitch/store.py`, `tests/test_llmsnitch.py`.

**Out of scope**: `llmsnitch/hook.py` (no change needed — the guard lives at
the store boundary), `llmsnitch/ingest.py` (already sanitizes; leave its
namespacing alone).

## Git workflow

Local-only repo: never push, no PRs. Commit on the current branch, imperative
subject, `Co-Authored-By:` line per recent `git log`. Use `trash`, never `rm`.

## Steps

### Step 1: Add the choke-point sanitizer to `store.py`

```python
import re  # add to imports

_SAFE_SID = re.compile(r"[A-Za-z0-9._-]{1,128}")

def _safe_sid(session_id):
    s = str(session_id)
    if _SAFE_SID.fullmatch(s):
        return s
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)[:128] or "unnamed"
```

Note `{1,128}`, not 64 — see Current state (ingest ids reach 70 chars).
Also note `.` alone can't traverse: with `/` mapped to `_`, `..` is a plain
name, not a parent reference — matching ingest's accepted alphabet.

**Verify**: `python3 -c "import sys; sys.path.insert(0,'.'); from llmsnitch import store; print(store._safe_sid('../../evil'), store._safe_sid('abc-123'))"` → `.._.._evil abc-123`

### Step 2: Apply it in the three path builders

In `session_dir`, `read_meta`, and `iter_events`, replace
`str(session_id)` with `_safe_sid(session_id)`.

**Verify**: `python3 tests/all.py` → all pass (the existing suite covers
normal ids and ingest ids end-to-end; any id churn fails here — see STOP).

### Step 3: Traversal regression test

Add `test_hook_session_id_traversal_contained` to `tests/test_llmsnitch.py`,
modeled on the codex traversal test beside it: inside a tmp `LLMSNITCH_DIR`,
call `hook.handle("PreToolUse", stdin=io.StringIO(json.dumps({...})))` with
`"session_id": "../../ESCAPED/x"`, then assert:
- no path containing `ESCAPED` exists outside `<tmp>/sessions/`
  (`rglob` over the tmp root's parent scope like the existing test does),
- exactly one new directory exists under `<tmp>/sessions/` and its name
  contains no `/` and no `..` as a path element (it will be `.._.._ESCAPED_x`).

**Verify**: `python3 tests/all.py` → all pass including the new test.

## Test plan

Step 3 covers the attack shape. Benign coverage rides the existing suite:
UUID session ids and `codex-*` ingest ids must round-trip unchanged (this is
implicitly asserted by every existing store/ingest test).

## Done criteria

- [ ] `python3 tests/all.py` exits 0, includes the new traversal test
- [ ] `grep -n "_safe_sid" llmsnitch/store.py` → 4 hits (def + 3 call sites)
- [ ] `git status` — only in-scope files changed
- [ ] `plans/README.md` status row updated

## STOP conditions

- Any existing test fails after Step 2 (a legitimate id got rewritten — the
  pattern is too tight; report rather than widening it ad hoc).
- You find another module building `sessions/<id>` paths directly (grep
  `sessions_root()` first) — report the extra call site instead of patching
  it unreviewed.

## Maintenance notes

- Prior audit rejected baseline HMAC on the "attacker inside the trust
  boundary" argument; this plan is narrower — it's consistency of the
  already-adopted adversary doctrine, not a new trust boundary.
- Future harness adapters get this guard for free by going through
  `store.session_dir`.
