# T504 — Intake extraction design

`labels: wayfinder:grilling`
`parent: ../map.md`
`blocked by: —`
`blocks: T505, T507`
`status: DONE (2026-09-12)`

## Resolution

HITL grilling, one round, six decisions — all recommendations accepted:

1. **Evidence source (MVP)**: Claude Code hook sessions only — the
   extractor consumes any stored event carrying command text
   (`PreToolUse` → `input.command`), so codex support later is parser
   enrichment (`parse_codex` currently drops `exec_command` text), not a
   design change. Fog line added to the map.
2. **Grammar**: `pip install` / `python -m pip install`, `uv add` /
   `uv pip install` / `uv sync`, `pipx install`. Poetry/conda skipped
   (absent from this machine; add when first seen). File-based installs
   (`-r requirements.txt`, `uv sync`) produce a **bulk intake**: "agent
   installed into env X at time T" — at scan time every distribution in
   that env is intake-attributed. Coarser but honest; without it the most
   common agent install pattern is invisible.
3. **Materialized**: `intakes.ndjson` under `~/.llmsnitch/` + an
   extraction cursor (ingest-state pattern). The retroactive sweep is
   just the first extraction run. Record shape: `{ts, ecosystem, package
   (PEP 503-normalized) | bulk:true, env_hint, session_id, harness, cwd}`.
4. **Env resolution chain**: explicit interpreter/venv path in the
   command → venv discovered under session cwd (glob wider than `.venv`;
   `uv.lock` ≠ installed env) → pipx/uv-tool locations for tool installs
   → `env_hint: unresolved`, which matches no env at scan time (quiet,
   never a global guess). Intake is the *claim*; `dist-info` at scan time
   is the *fact* (version truth, still-installed truth).
5. **Retroactive sweep**: all history, no window; idempotent behind the
   cursor.
6. **No success filtering**: PreToolUse proves attempt only, and that's
   fine — the scan-time `dist-info` join is the success oracle; a package
   that never landed can't produce a finding. Pairing logic would change
   no outcome.

Unblocks T505; T507's intake sweep (item 1) is now fully specified.

How an **intake** (agent-installed package evidence) is extracted from
what's already on disk. HITL grilling over:

1. Install-command grammar: which commands count (`pip install`,
   `uv add`, `uv pip install`, `pipx install`, `python -m pip …`,
   requirements-file installs) and how loose the parse is — a missed
   install is a silent hole, an over-match pollutes intakes.
2. Retroactive sweep: mining existing session NDJSON + harness ledgers
   (ingest-cursor style) vs from-now-on only; idempotency.
3. Intake record shape + storage: package × project × session × time,
   flat file under `~/.llmsnitch/` per house style.
4. Version truth: intake stores the *claim*; the env's `dist-info` at
   scan time is authoritative (command says `requests`, disk says which
   version landed — and whether it's still installed).
