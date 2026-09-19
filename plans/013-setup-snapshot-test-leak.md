# Plan 013 — Stop `setup_cmd` from leaking snapshots into the real `~/.config/llmsnitch/`

- **Status:** TODO
- **Priority:** P3 (housekeeping; no live vuln, no shipped behavior change)
- **Effort:** XS
- **Written against commit:** `3f3f387`
- **Depends on:** none.
- **Grounding:** handoff-note observation from the digest-outlet session
  (2026-09-15 11:25): "Second same-shape leak, untouched: ~120
  `~/.config/llmsnitch/settings-snapshot-*.json` files stamped during test
  runs (`setup_cmd` snapshot path). Plan candidate." Same-shape as the
  `/var/folders/<tmp>` scan leak fixed in `16ac284`
  (`tests/test_llmsnitch._with_tmp_store` → `_seams.with_tmp(store=True)`).

---

## Context — the leak

`llmsnitch/setup_cmd.py:46-49` hard-codes the snapshot dir:

```python
snap_dir = Path("~/.config/llmsnitch").expanduser()
snap_dir.mkdir(parents=True, exist_ok=True)
snap = snap_dir / f"settings-snapshot-{time.strftime('%Y%m%d%H%M%S')}.json"
snap.write_text(sp.read_text())
```

`tests/test_llmsnitch.py:602 test_setup_refuses_inside_claude_and_snapshots`
correctly parameterizes `settings_path=str(...)` to a tmp file, but nothing
parameterizes the snapshot dir. Every test run that hits line 612 (and
again line 615) writes a real snapshot into the user's `~/.config/llmsnitch/`.

Present state on this machine: **151 leaked snapshot files** stamped
2026-08-16 → 2026-09-18. Not causing harm (never routed through notify) but
they will accumulate forever and one day someone will grep `~/.config` for
something and be surprised. Fixing the leak also fixes the last known
test-isolation hole in the suite.

---

## Fix

Add a `snap_dir` parameter to `setup_cmd.run()` in the shape already used by
`settings_path`. Default `None` → keep current production behavior. Test
passes it. No env seam (would add one more `LLMSNITCH_*` var to remember; the
kwarg matches the existing signature). No behavior change for real users.

**`llmsnitch/setup_cmd.py` (~5-line diff):**

```python
def run(write, out, settings_path=None, env=None, snap_dir=None):
    ...
    if sp.exists():
        sd = Path(snap_dir).expanduser() if snap_dir else \
             Path("~/.config/llmsnitch").expanduser()
        sd.mkdir(parents=True, exist_ok=True)
        snap = sd / f"settings-snapshot-{time.strftime('%Y%m%d%H%M%S')}.json"
        snap.write_text(sp.read_text())
        out.write(f"[OK] snapshot: {snap}\n")
        ...
```

**`tests/test_llmsnitch.py:602` (change two call sites):**

```python
assert setup_cmd.run(True, out, settings_path=str(sp),
                     env={}, snap_dir=str(Path(t) / "snaps")) == 0
...
assert setup_cmd.run(True, io.StringIO(), settings_path=str(sp),
                     env={}, snap_dir=str(Path(t) / "snaps")) == 0
```

That is the whole fix.

---

## Files in scope

- `llmsnitch/setup_cmd.py` — one new kwarg, three lines inside the branch.
- `tests/test_llmsnitch.py` — two call sites in
  `test_setup_refuses_inside_claude_and_snapshots`.

**Out of scope:** `cli.py` dispatch (no need to expose `--snap-dir`; the
kwarg is a test seam, not a user knob). Any semantic change to where
production snapshots live.

---

## Verification

1. `python3 tests/all.py` — all pass (still 174+ tests; no count change).
2. `SNAP_BEFORE=$(ls ~/.config/llmsnitch/settings-snapshot-*.json 2>/dev/null | wc -l); python3 tests/all.py > /dev/null; SNAP_AFTER=$(ls ~/.config/llmsnitch/settings-snapshot-*.json 2>/dev/null | wc -l); [ "$SNAP_BEFORE" = "$SNAP_AFTER" ]` — the count is unchanged across a full suite run. This is the regression check.
3. Manual: `python3 -c "from llmsnitch import setup_cmd; import io, tempfile, pathlib; ..." ` — production path (no `snap_dir`) still writes to `~/.config/llmsnitch/` (don't actually run this — it would leak one more file; the test covers the seam, real production is unchanged by construction).
4. `git status` after the diff — only `llmsnitch/setup_cmd.py` and `tests/test_llmsnitch.py` modified.

## One-time cleanup (optional, separate commit)

Once the leak is closed, sweep the 151 orphans:

```
trash ~/.config/llmsnitch/settings-snapshot-*.json
```

House rule: `trash`, never `rm`. This is the user's private data — the files
are snapshots of `~/.claude/settings.json` at test-run timestamps. Nothing
downstream reads them; they were only ever a rollback aid for the `--write`
path. Sweeping them is safe.

## Escape hatches

- If any other callsite of `setup_cmd.run()` shows up in a `grep` (currently
  only `cli.py setup` dispatch + the one test), and it also passes a tmp
  path, plumb `snap_dir` through it too.
- If the test seam breaks because `sp` doesn't exist on the first call (the
  refused-CLAUDECODE branch returns before touching disk), leave the
  kwarg optional — it's fine for `snap_dir` to be `None` on that path.
