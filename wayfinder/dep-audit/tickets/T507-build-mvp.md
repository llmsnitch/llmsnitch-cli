# T507 — Build the dep-audit MVP

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: T503, T504, T505, T506`
`blocks: T508`
`status: DONE (2026-09-12)`

## Question

Nothing left to decide once blockers close — execution per the map's
plan-vs-do override. Build, on branch `feature/scanner-venv-mvp`:

1. Intake sweep (T504 design) incl. retroactive pass.
2. Bulletin cache read + hash verify + payload-age stamping (fetch wiring
   itself is T508; scan must work offline against a stale cache).
3. Matching: intakes × bulletin (T502/T503 encoding), waiver filter,
   exercised gate (T505) → findings. Critical = intake ∧ exploited-flag ∧
   exercised; everything else lesser and quiet.
4. Waivers: flat file under `~/.llmsnitch/`, (advisory × package) +
   required reason, no TTL, re-raise on severity escalation.
5. Findings route through `fs_coil.notify`; hot path untouched; suites
   green; review gates (two-axis + ponytail) over the diff.

## Resolution

Shipped (orchestrator + two parallel TDD dev agents on frozen seams; all
five items done):

**Modules** — `llmsnitch/intake.py` (280 L: install grammar for
pip/`python -m pip`/uv add/uv pip/uv sync/uv tool/pipx; bulk intakes for
file/path/VCS/truncated installs; `intakes.ndjson` + mtime/size cursor,
session rows replaced on re-extract; 4-step env chain ending
unresolved-stays-quiet), `llmsnitch/bulletin.py` (134 L: sidecar sha256
verify over raw gz bytes, 200 MB decompression cap, schema set {1},
tolerant indexer that degrades poisoned optional fields, PEP 503/PEP 440
canonicalization, set-membership-only matching),
`llmsnitch/depaudit.py` (441 L: dist-info join as success oracle,
exercised gate = source-import (`top_level.txt`→`RECORD` fallback) ∨
head-token-verified run-after-install, waivers with waive-time
severity/kev snapshots and the two re-raise transitions, predicate
`critical = (malicious ∧ intake) ∨ (intake ∧ kev ∧ exercised)`, notify
routing where only unwaived criticals banner and everything lands as
ledger rows (`record_only` for lesser/waived, finding tier travels in the
subject per scan.py discipline), `--waive ID PKG --reason`, exit 0/1/2).
Wiring: `cli.py` `depaudit` dispatch; `fs_coil` `depaudit_finding`
category (24h/critical — pierces cold start by design) + `dep-audit`
surface section.

**Tests** — 117/117 green (`python3 tests/all.py`, exit 0): 34 core + 14
notify + 8 scan-notify + 23 intake + 18 bulletin + 20 depaudit
integration (predicate end-to-end, both exercised evidence paths,
waiver round-trip/alias-match/both re-raises, operational bulletin paths,
truncation, hostile-shape regressions).

**Review gates** (2 fix rounds) — two-axis: standards clean (no hard
violations), spec found one real bug (run-after regex counted
`pip install python-dateutil` as a python run — fixed with head-token
matching + regression test). Ponytail: 4 of 6 cuts applied (dedup
`_pep503`→`normalize_name`, `_Parser` from scan, dropped memo caches,
1-line schema check); declined 2 with cause (grammar wrapper is the
public seam pinned by exact-shape tests; the tmp-store test helper is the
existing house pattern in test_llmsnitch.py). Security-sentinel: 2
high/3 medium/4 low, all fixed and re-verified against its repro
harness — hostile bulletin entry shapes now degrade instead of crashing
(crash-as-evasion closed, plus belt-and-braces exit-2 wrap), FIFO/`*.py`
non-regular files skipped via lstat (hang closed), gzip bomb capped,
control chars flattened out of terminal/notify output, str-ts tolerated,
glob metachars escaped, walk budget counts directories. Waiver trust
boundary and 0600/0700 writers verified clean.

**Live verification (this machine)** — retroactive sweep over real
ledgers: 8 intakes (4 sessions; all bulk, env unresolved → correctly
quiet; includes the naive-segment-split over-match of a quoted grep
pattern — harmless by design, bulk+unresolved matches nothing). Real
scan vs the 19,033-entry bulletin: 0 findings, exit 0, `bulletin age
0.5d` stamped. Seeded round-trip in a temp `LLMSNITCH_DIR`: MAL entry +
intake → `[CRITICAL]`, exit 1, one banner + critical ledger row; CLI
waiver (reason required) → waived, exit 0, `record_only` row, no banner.

**Recorded deferrals** — stale-bulletin *gating* deliberately absent (no
threshold decided; map fog "Bulletin staleness alerting"); `depaudit`
has no stored-report analog to `scan --report` (re-running mutates no
evidence — findings recompute from scratch, T503 d11 — so the action
string re-runs the audit); hand-added waivers without snapshot fields
never re-raise (written eyes-open at current state).

T508 (activate: patrol wiring + weekly fetch) is the map's last ticket.
