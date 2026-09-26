# Plan 014 — `~/.config/llmsnitch/` created at 0755, not 0700

- **Status:** TODO
- **Priority:** P2 (live perms gap on a dir that has held copies of the user's
  `settings.json`; no remote exposure on a single-user Mac)
- **Effort:** XS
- **Written against commit:** `0dc7e29`
- **Depends on:** 013 (DONE) — its `snap_dir` kwarg is the test seam this plan needs.
- **Grounding:** observed live 2026-09-26 while verifying the 013 orphan sweep.
  `README.md` / `CLAUDE.md` constraint 5: "Files `0600`, dirs `0700`."

---

## Context — what's actually wrong

The perms doctrine is real and it is tested — but only over `~/.llmsnitch/`.
A survey of every dir-creation site (2026-09-26) found the store tree and the
log tree are correct in practice:

| Dir | Live mode | Enforced by |
|-----|-----------|-------------|
| `~/.llmsnitch/` | `0700` ✅ | `store._mkdir_private` |
| `~/Library/Logs/llmsnitch/{,notify,fs-coil}` | `0700` ✅ | `logger.py:87-92`, `notify._mkdir_owned(d, 0o700)` |
| **`~/.config/llmsnitch/`** | **`0755` ❌** | **nothing** |

One directory is wrong, and it is the one that until last week held 199
verbatim copies of `~/.claude/settings.json` — hook command lines included.
Those snapshots were themselves `0644`. Both facts trace to a single bare
`mkdir` with no mode and a `write_text` at default umask.

**No test covers `~/.config/llmsnitch/` at all.** That is why "enforced"
was true in CLAUDE.md and false on disk: the tests pin the store tree, and
the config tree grew a second home for our data without picking up the rule.

## Offender sites

1. **`llmsnitch/setup_cmd.py:48`** — `sd.mkdir(parents=True, exist_ok=True)`
   creates the snapshot dir with no mode. The live 0755. *(Post-013 this is
   the `sd` local, seamed by `snap_dir`.)*
2. **`llmsnitch/setup_cmd.py:50`** — `snap.write_text(sp.read_text())` writes
   the snapshot at umask default (0644 observed), not 0600.
3. **`fs_coil/notifier.py:50`** — `self._icon_dir.mkdir(parents=True,
   exist_ok=True)` for `~/.config/llmsnitch/icons`. Latent: the dir does not
   exist on this machine yet, but it would be created 0755 **and would create
   the 0755 parent** on a machine where setup never ran.

## Explicitly NOT in scope

- **`~/.config/llmsnitch/config` at 0644.** Nothing in `llmsnitch` or
  `fs_coil` ever writes this file — every reference is a read (`gate.py:28`,
  `scan.py:259`, `notify.py:98`, `fs_coil/cli.py:53`). It is the user's own
  hand-authored INI. Do not chmod a file we do not create. A `0700` parent
  gates read access to everything inside regardless of the file's own mode —
  fixing the dir is what makes the file private. *(Left deliberately: if a
  future reader "notices" this 0644 and fixes it, they are touching user
  data for no gain.)*
- **`setup_cmd.py:67` `sp.parent.mkdir(...)`** — that is `~/.claude/`, owned
  by Claude Code. Never force our mode onto another tool's directory.
- **`patrol.py:58` / `digest_agent.py:52` plist parent** — that is
  `~/Library/LaunchAgents/`, owned by macOS. Same rule.
- Any broad "walk the tree and chmod everything" sweep. Three call sites,
  three fixes.

---

## Fix

Use the helpers that already exist. No new abstraction (`store._mkdir_private`
and `store._open_private` are exactly this, and `logger.py` already carries
the in-package pattern for `fs_coil`).

### `llmsnitch/setup_cmd.py`

Add the import (same package, no layering concern — `setup_cmd` is a
human-facing command, `store` is the disk module):

```python
from llmsnitch import store
```

Then swap both lines inside the `if sp.exists():` branch:

```python
        sd = Path(snap_dir).expanduser() if snap_dir else \
            Path("~/.config/llmsnitch").expanduser()
        store._mkdir_private(sd)                      # was: sd.mkdir(parents=True, exist_ok=True)
        snap = sd / f"settings-snapshot-{time.strftime('%Y%m%d%H%M%S')}.json"
        with open(store._open_private(snap, os.O_WRONLY | os.O_TRUNC), "w") as fh:
            fh.write(sp.read_text())                  # was: snap.write_text(...)
```

`_open_private` creates at 0600 with no umask window — the same reason the
store uses it. `os` is already imported in this module.

### `fs_coil/notifier.py:50`

Do **not** import `fs_coil.notify` here for `_mkdir_owned` — `notify` is the
delivery layer and importing it from the notifier risks a cycle. Use the
inline pattern `fs_coil/logger.py:87-92` already establishes in this package:

```python
            try:
                self._icon_dir.mkdir(parents=True, exist_ok=True)
                for p in (self._icon_dir, self._icon_dir.parent):
                    try:
                        os.chmod(p, 0o700)
                    except OSError:
                        pass
                self._chown_user(self._icon_dir)
            except OSError:
                pass
```

The parent is included deliberately: on a machine where `setup --write` never
ran, this is the call that first creates `~/.config/llmsnitch/`.

---

## Test plan

The gap that let this through is that **no test asserts anything about the
config tree**. Close that, not just the perms.

Add to `tests/test_llmsnitch.py`, next to the existing `test_files_are_0600`
(line 499) / `test_new_files_created_0600` (line 764) family — mirror their
style:

1. **`test_setup_snapshot_dir_is_0700_and_file_0600`** — the core regression.
   Use plan 013's `snap_dir` seam so nothing touches the real home:
   ```python
   def test_setup_snapshot_dir_is_0700_and_file_0600():
       with tempfile.TemporaryDirectory() as t:
           sp = Path(t) / "s.json"
           sp.write_text('{"model": "opus"}')
           sd = Path(t) / "cfg" / "llmsnitch"
           assert setup_cmd.run(True, io.StringIO(), settings_path=str(sp),
                                env={}, snap_dir=str(sd)) == 0
           assert oct(sd.stat().st_mode & 0o777) == "0o700", oct(sd.stat().st_mode)
           snaps = list(sd.glob("settings-snapshot-*.json"))
           assert len(snaps) == 1, snaps
           assert oct(snaps[0].stat().st_mode & 0o777) == "0o600", oct(snaps[0].stat().st_mode)
   ```
   Note the dir is created fresh under `t` (not pre-made), so the assertion
   pins `_mkdir_private`'s mode, not the tmpdir's inherited mode.

2. **`test_icon_dir_created_0700`** (in whichever file covers `notifier.py` —
   confirm with `grep -rl "notifier" tests/`). Construct the notifier with a
   `home` pointing at a tmp dir, assert both `<home>/.config/llmsnitch` and
   `<home>/.config/llmsnitch/icons` come out `0700`. If the notifier's
   constructor is awkward to drive in isolation, **STOP** and report rather
   than reshaping production code to be testable — the setup_cmd test is the
   one that pins the live bug; this one is defense in depth.

## Done criteria (machine-checkable)

- `python3 tests/all.py` → all pass (182 + 1 or 2 new).
- `python3 -m compileall -q llmsnitch fs_coil` → clean.
- Snapshot-leak regression from 013 still holds: snapshot count in
  `~/.config/llmsnitch/` unchanged across a full suite run.
- `git status` → only `llmsnitch/setup_cmd.py`, `fs_coil/notifier.py`, and the
  test file(s) modified.

## One-time cleanup (user runs; not part of the commit)

The code fix only governs dirs created from here on. The existing dir keeps
its mode until changed:

```sh
chmod 700 ~/.config/llmsnitch
```

Verify: `stat -f '%Sp %N' ~/.config/llmsnitch` → `drwx------`.

## Maintenance note

The reason this drifted is worth recording: the perms rule was enforced by
tests that all live over `~/.llmsnitch/`, and `~/.config/llmsnitch/` became a
second data home later without inheriting the rule. **Any future third
location for llmsnitch-owned state needs a perms assertion at the same time
it is introduced** — the doctrine line in `README.md` is not self-enforcing.
