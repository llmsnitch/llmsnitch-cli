# T201 — Merge scan MVP to main + reinstall

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: —`
`blocks: T204`
`status: DONE (2026-08-26)`

## Resolution

- Merge commit on main: `1dc6dc2` (no conflicts; `.gitmodules` identical
  both sides, no untracked collisions — verified pre-merge).
- Suites on main: 31/31 + 8/8 + 18/18 green.
- **Install mechanism (fact later tickets depend on)**: **pipx** — venv at
  `~/Library/Application Support/pipx/venvs/llmsnitch` (Python 3.14.7),
  shim at `~/.local/bin/llmsnitch`. Reinstall command that worked:
  `pipx install --force $HOMERepos/llmsnitch`.
- Installed-binary proof: `llmsnitch version` → 0.1.0; help lists `scan`;
  `llmsnitch scan --inventory | tail -1` → `123 artifacts`.
- Note for T202/T204: the plist's ProgramArguments path
  `~/.local/bin/llmsnitch` is the pipx shim — correct and stable across
  reinstalls.

## Question

Nothing to decide — this task unblocks the rollout: the shipped binary must
contain the scan MVP before any patrol can call it.

Do: merge `research/scanner-survey-mvp` into `main` (local merge only —
never add a remote or push), then reinstall so `~/.local/bin/llmsnitch`
serves the merged code, then verify.

Facts to record in the resolution (later tickets depend on them):

- **How llmsnitch is actually installed** — the binary exists at
  `~/.local/bin/llmsnitch` but `pip3 show llmsnitch` returns nothing;
  determine the mechanism (pipx? `pip install --user` under a different
  python?) and record the exact reinstall command that worked.
- Post-merge main test results: `python3 tests/test_llmsnitch.py` (31),
  `tests/test_scan_notify.py` (8), `tests/test_notify.py` (18) — all green
  in the main checkout.
- `llmsnitch scan --inventory | tail -1` output from the installed binary
  (proves the installed CLI has the scan subcommand).

Done when: merge commit on main, all three suites green there, and the
installed `llmsnitch version` + `scan --inventory` run the merged code.
