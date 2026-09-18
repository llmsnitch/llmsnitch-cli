# T702 — Hook state class and semantic drift on `~/.claude.json`

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: —`
`blocks: T704`
`status: DONE (2026-09-18)`

## Question

Nothing left to decide — execution of D08 and D09 in `llmsnitch/scan.py`
and `llmsnitch/scanrules.py`. Build:

1. **`hook_state` class** in `classify()`: a file under a `hooks` dir
   inside a territory that is not executable (`os.access(X_OK)` false) and
   whose suffix is not in `_SCRIPT_EXTS`. Everything else under `hooks`
   stays `hook_script`. `hook_state` is not in `CONTROL_CLASSES`, is
   skipped by `_drift` entirely (not tracked, not tombstoned — remove any
   existing baseline entries for paths that now classify as state), and is
   scanned only by the secret-shape pass (`_SECRET_ALL`), not by `RULES`.
   Verify against the live tree: `claude-signal`, `claude-notifier-focus`,
   `claude-notifier-config.json`, `claude-notifier-active.d/*`,
   `claude-notifier-task-start/*.json` → state; `*.js`, `*.sh`,
   `pre-commit`, `_lib/*.js` → script.
2. **Semantic drift for `~/.claude.json`**: the drift salt for this one
   artifact is the sha256 of `json.dumps(subset, sort_keys=True,
   separators=(",", ":"))` where `subset = {"mcpServers": top-level,
   "projects": {path: proj["mcpServers"]} for projects that have one}`.
   Unparseable JSON falls back to the whole-file sha (never raises). The
   drift finding's evidence says `mcpServers changed` so the digest line
   is self-explaining. Rules still run over the full file text.
3. **Docs**: `docs/notifier-spec.md` / scanner spec wherever artifact
   classes are enumerated; the `classify` docstring.
4. **Tests**: classification table for the live-tree names above via a
   temp fixture; two scans across a `claude-signal` rewrite → no drift
   row; two scans across a `.claude.json` edit that only touches
   `numStartups` → no drift; an edit adding an MCP server → one
   `drift_changed` with the new evidence string; malformed `.claude.json`
   → whole-file fallback.

Done when the suite is green and two consecutive live scans from `$HOME`
(with a session in between) show no `drift_changed` on either file.
Review gates as in T701.

## Resolution

Branch `quiet-patrol/T702`, 2026-09-18.

**Built.**

- `scan.classify`: under a `hooks` dir, `path.suffix in _SCRIPT_EXTS or
  os.access(path, os.X_OK)` → `hook_script`, else `hook_state` (D08).
  Docstring enumerates the seven classes and the split.
- `scan._drift`: `hook_state` keys in `current` are skipped (never
  baselined); a baseline key whose path still exists but now classifies as
  `hook_state` is dropped silently (no `drift_removed`). Baseline entries
  now hold the drift *salt* under `sha256` (documented in the docstring).
- `scan._drift_salt(art, sha)` (new, drift section): for a file named
  `.claude.json`, sha256 of `json.dumps(subset, sort_keys=True,
  separators=(",", ":"))` with `subset = {"mcpServers": top-level,
  "projects": {path: proj["mcpServers"]}}` for projects carrying one;
  any parse failure returns the whole-file sha. Other artifacts: the sha
  unchanged. `_drift_finding` gained `evidence=None`; a semantic
  `drift_changed` carries `evidence: "mcpServers changed"`.
- `scan_file` untouched: no `RULES` entry lists `hook_state`, so the class
  already receives only the `_SECRET_ALL` pass. Locked by
  `test_hook_state_outside_control_and_rules`; comment on
  `scanrules.CONTROL_CLASSES` says why the class is absent.
- Docs: `classify` docstring. `docs/notifier-spec.md` does not enumerate
  artifact classes anywhere (grep for every class name: no hit), so no
  spec edit was needed; `CONTEXT.md` **Hook state** entry was already
  landed at charting.

**Measured.** Live `~/.claude/hooks` (read-only `ls -la`): 5 state names
(`claude-signal`, `claude-notifier-focus`, `claude-notifier-config.json`,
`claude-notifier-active.d/20375`, `claude-notifier-task-start/*.json`),
4 script shapes (`*.js` 0755, `*.sh`, `pre-commit`, `_lib/*.js` 0644) — all
classify as the ticket lists. Live `~/.claude.json`: 134,652 bytes, 0
top-level `mcpServers`, 34 projects all carrying `mcpServers`; semantic
salt `6eee7dc6…` ≠ whole-file sha `14edc0e5…`, stable across re-reads.

Real-tree check (entry point `llmsnitch.cli.main`, `LLMSNITCH_DIR` +
notify seams at a scratch store under the session scratchpad, cwd
`$HOME` via `os.chdir`, filesystem read-only — the live `~/.llmsnitch` was
never touched): three no-roots scans at 18:50:00 / 18:50:22 / 18:51:43.
`claude-signal` mtime moved 18:49:40 → 18:50:17, `~/.claude.json` mtime
18:49:31 → 18:51:32 between scans. Each: `201 files, 5 skipped`, drift
rows `[]`; baseline classes `{claude_settings 4, mcp_config 25,
instruction_file 13, hook_script 38, skill_manifest 85, skill_script
26}` — zero `hook_state` keys, `~/.claude.json` tracked. Copy of the live
`.claude.json` content in a scratch root: seed → `numStartups`/`tipsHistory`
churn → no drift; add a top-level MCP server → one `drift_changed`,
evidence `mcpServers changed`. Before this ticket the same two files
produced `drift_changed` on every patrol since 2026-08-26/27 (map Notes).

**Migration note.** The first patrol after this lands re-salts
`~/.claude.json` (baseline holds a whole-file sha, new salt differs) —
expect exactly one `drift_changed · mcpServers changed`, then quiet. Stale
`hook_script` baseline rows for state files are dropped silently on that
same run.

**Files touched.** `llmsnitch/scan.py` (classify; drift section),
`llmsnitch/scanrules.py` (comment), `tests/test_hook_state.py` (new, 8
tests), `tests/all.py` (registration), this ticket. **Cross-ownership, one
line:** `tests/test_llmsnitch.py::test_drift_removed_keeps_agent_attribution`
wrote a 0644 extension-less `task-start` fixture, which is Hook state under
D08 and would no longer baseline; added `hook.chmod(0o755)` so it stays a
hook_script. Nobody else owns that file in the dispatch; flagged for the
orchestrator.

**Tests.** `python3 tests/all.py`: 190/190 (182 at dispatch + 8).
Ponytail review: one cut applied (`_drift_salt` keys on the artifact name
alone; `cls` check was redundant).
