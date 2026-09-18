# T702 — Hook state class and semantic drift on `~/.claude.json`

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: —`
`blocks: T704`
`status: OPEN — unclaimed`

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
