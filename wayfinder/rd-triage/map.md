# R&D Triage — Wayfinder Map

`label: wayfinder:map`
`status: CLOSED (2026-08-27) — destination reached: wrapper snakes cleared
(T401), doctrine drift fixed (T402), standing infrastructure kept per
D-RT2 (user-confirmed); suites 34/34 + 18/18 + 8/8 green, zero wrapper
references in code. Residual fog (track B, plans/ archival) inherited.`

## Destination

Main branch contains **only live code, standing infrastructure, and decision
records** — every R&D artifact either proven live (kept), classified as
standing infrastructure (kept, documented), or cleared; README/CLAUDE.md
claims match the tree; suites green. Inherits the fog from
[submodule-clearout](../submodule-clearout/map.md) (closed 2026-08-27).

## Triage verdicts (recon 2026-08-27)

### LIVE — keep, do not touch

| Artifact | Evidence |
|---|---|
| `llmsnitch/` all 12 modules | scan/patrol/scanrules shipped via scan-rollout T201–T204; harness/ingest shipped via codex pilot T106 (84 sessions oracle-exact). Daily patrol LaunchAgent (`com.slav-it.llmsnitch-patrol`) runs the pipx shim → these modules. |
| `fs_coil/` (minus `bridge.py`) | Ships in the wheel (`pyproject.toml packages`); the scan's notify routing imports it (T204 found the degradation live). Second live copy at `/usr/local/share/llmsnitch/` converges on same flock'd state. |
| `bin/fs-coil` | Entry point for the live tree. |
| `docs/notifier-spec.md`, `docs/harness-adapter-contract.md` | Doctrine — CLAUDE.md points at both. |
| `tests/` (3 suites, 60 tests) | All green; enforce the non-negotiables. |

### DEAD R&D — clear

| Artifact | Why dead |
|---|---|
| `bin/agent-flick` | Wrapper around upstream `agent-strace` — **binary not installed** (`which` empty). Contradicts README's "none vendored, none wrapped". Header cites `plans/siddhant-agent-trace-integration.md` which no longer exists. |
| `bin/session-shed` | Wrapper around upstream `agenttrace` — **binary not installed**. Same contradiction. |
| `fs_coil/bridge.py` | "Shared scaffolding for the tool-wrapper snakes" — imported **only** by the two dead wrappers; zero `fs_coil`-internal consumers. |
| Wrapper vocabulary residue | `fs_coil/notify.py:52-53` tool-table rows; `CONTEXT.md:12` mention; `docs/notifier-spec.md` wrapper references; `tests/test_notify.py` uses `session-shed` as a label (generic string — rename, don't delete tests). |

### STANDING INFRASTRUCTURE — keep

| Artifact | Role |
|---|---|
| `team/` (playbook, roster, 4 roles, codex run journal) | The harness-team map's destination *is* this artifact; remaining 10 roster harnesses are future team runs. |
| `dossiers/` (claude-code, codex) | Fact sheets feeding adapters + registry + scan seed (D14/D15). |
| `wayfinder/` | Decision records — never rewritten (house doctrine). |
| `plans/` 001–003 | All DONE; README records rejected findings too. Executed-plan record, cheap to keep. |
| `docs/research/` | Grounding for the closed maps (scanner survey verdict is cited by CONTEXT + spec). |

### DRIFT — fix

| Doc | Stale claim |
|---|---|
| `CLAUDE.md` | "Seven files, ~640 LOC" (now 12 modules + fs_coil); pointer `wayfinder/map.md D01–D27` (real path: `wayfinder/harness-team/map.md`); architecture section omits harness/ingest/patrol/scan/scanrules and fs_coil. |
| `README.md` | "none wrapped" — true again only after the wrappers go; use-section omits `scan`/`patrol`/`ingest`. |

## Decisions

- **D-RT1** The wrapper snakes (agent-flick, session-shed, bridge.py) die
  with their vocabulary rows: upstream binaries absent, zero consumers,
  and their existence falsifies README's core claim. Notify-layer *ledger
  compatibility* is unaffected — tool names are free-form strings.
- **D-RT2** `team/`, `dossiers/`, `plans/`, `wayfinder/`, `docs/research/`
  are records/infrastructure, not blend — keeping them IS the cleanup
  discipline (git history is not a substitute for standing playbooks).
- **D-RT3** Doc drift is fixed in the same effort — a cleanup that leaves
  CLAUDE.md describing a seven-file package hasn't cleaned anything.
- **D-RT4** Runtime residue outside the repo (`~/.llmsnitch/`'s 60
  settings-snapshots, `~/.agent-strace/telemetry.json`) is out of scope —
  not repo content.

## Tickets

- [T401 — Clear the wrapper snakes](tickets/T401-clear-wrapper-snakes.md)
- [T402 — Fix doctrine drift](tickets/T402-fix-doctrine-drift.md)

## Not yet specified

- **Track B** (live-install migration, needs sudo) — still its own future
  effort; `/usr/local/share/llmsnitch/` stays until then.
- Whether `plans/` should archive into `docs/` once a fourth plan appears.
