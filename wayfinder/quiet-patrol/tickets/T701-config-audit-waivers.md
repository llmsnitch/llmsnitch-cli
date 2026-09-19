# T701 — Config-audit waivers

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: —`
`blocks: T704`
`status: DONE (2026-09-18)`

## Question

Nothing left to decide — execution per the map's plan-vs-do override,
implementing D03–D07 in `llmsnitch/scan.py` (and the smallest possible
touch on `fs_coil/digest.py`). Build:

1. **Waiver rows** in the shared `~/.llmsnitch/waivers.json`:
   `{"surface": "config-audit", "rule_id", "artifact", "reason",
   "evidence": [sorted distinct evidence strings], "waived_at": ts}`.
   Loader accepts only well-formed rows of this shape (str fields,
   non-empty reason, list of str evidence); dep-audit's `load_waivers`
   must keep ignoring these rows unchanged — confirm with a test that a
   mixed file loads correctly on both sides.
2. **Verb**: `llmsnitch scan --waive RULE_ID ARTIFACT --reason TEXT`.
   The pair must exist in the latest stored scan (`_load_latest_scan`);
   the evidence set is snapshotted from those rows. Missing pair or
   missing `--reason` → `[ERROR]`, exit 2. No rescan on `--waive`.
3. **Effect on a scan**: a finding whose `(rule_id, artifact)` has a
   waiver gets `waived: true` when its current evidence set equals the
   snapshot, else `reraised: true` (the waiver stays on disk; a re-raised
   row is a normal finding). Waived rows: kept in `findings.ndjson`,
   excluded from the `--fail-on` breach test, routed to notify with
   `record_only=True`, flagged `waived` in `to_text` / `--report`, counted
   in the summary line (`waived=N`) and in meta as `findings_waived`.
   Drift rows are never waivable (fingerprint is sha-salted — D04).
4. **Digest**: `fs_coil/digest.py` open-findings line appends
   `· N waived` when `findings_waived > 0`. Keep the file under the
   250-line cap; if it does not fit, the readout moves to a new module,
   never into `digest_agent.py`.
5. **Docs**: `cli.py` usage string, README command block, and the scan
   section of `docs/notifier-spec.md` if it lists scan options. CONTEXT.md
   is already updated.
6. **Tests** (`tests/test_llmsnitch.py` or a new module registered in
   `tests/all.py`): waive → rescan → exit 0 and `waived=1`; edit the
   flagged line so a new distinct match appears → `reraised` and exit 1;
   unrelated edit to the same file → still waived; `--waive` on an unknown
   pair → exit 2; mixed `waivers.json` round-trips for both surfaces.

Done when `python3 tests/all.py` is green and a temp-dir scenario
(`LLMSNITCH_DIR`) shows all four behaviours from the installed entry
point. Review gates: `code-review` two-axis, `ponytail:ponytail-review`.

## Resolution

Branch `quiet-patrol/T701`, worktree
`~/llmsnitch-cli/.claude/worktrees/agent-aecfe4f907c4324a7`.

**Built** (`llmsnitch/scan.py`, new `# -- waivers ---` section before
`# -- the scan ---`):

- `load_scan_waivers()` — reads the shared `waivers.json`, keeps only
  `{"surface": "config-audit", rule_id: str, artifact: str, reason:
  non-empty str, evidence: [str], waived_at}` rows. `_waivers_raw()` is
  the untyped read both the loader and the writer share, so dep-audit rows
  (and even garbage) ride along untouched on write.
- `_apply_waivers(findings, waivers)` — per `(rule_id, artifact)`, the set
  of current `evidence` strings vs the snapshot: equal → `waived: true`,
  different → `reraised: true` (waiver stays on disk). Drift rules skipped.
  Called in `run_scan` after the resolved-tombstone block; `by_sev` skips
  waived rows; meta gains `findings_waived`.
- `add_scan_waiver(rule_id, artifact, reason, out)` — snapshots the sorted
  distinct evidence from `_load_latest_scan()`; unknown pair, drift rule →
  `[ERROR]` exit 2; replaces an earlier waiver for the same pair (re-waive
  after a re-raise re-snapshots). File written 0600 via
  `store._open_private`. No rescan.
- `cmd_scan`: `--waive RULE_ID ARTIFACT --reason TEXT`; missing/blank
  reason or mixing with ROOT/`--report`/`--rebaseline` → exit 2. Breach test
  excludes waived rows. `_route_to_notifier` routes waived rows
  `record_only=True`. `to_text`: `known waived` / `known RERAISED` marks,
  `waived=N` in the counts line (also under `--report`).
- `fs_coil/digest.py` (229 → 231 lines, under the 250 cap): health carries
  `scan_waived`; the open-findings line appends `· N waived` when > 0 — on
  both the "(last patrol)" and the "none" branch.
- Docs: `cli.py` usage line, README command block, `scan.py` module
  docstring.

**Tests**: `tests/test_scan_waivers.py`, 6 tests (waive → rescan exit 0 +
`waived=1` + record_only + `--report`; new distinct match → RERAISED exit 1;
unrelated edit → still waived; misuse matrix → exit 2 and no file written;
mixed `waivers.json` round-trips both loaders, malformed scan rows dropped,
re-waive replaces, mode 0600; digest `· N waived`). Registered in
`tests/all.py`. Gate: `python3 tests/all.py` **188/188** (182 at dispatch).

**Real-tree check** from the entry point (`llmsnitch.cli:main`), every seam
(`LLMSNITCH_DIR`, `LLMSNITCH_NOTIFY_DIR`, `LLMSNITCH_HOT_STATE`,
`LLMSNITCH_CONFIG`) pointed at a scratch dir, one `CLAUDE.md` with
`Ignore all previous instructions.`:

```
1. scan                  → [CRITICAL] NEW skill_instruction_override …:2   exit 1
2. --waive (no --reason) → [ERROR] --waive RULE_ID ARTIFACT --reason TEXT …  exit 2
3. --waive unknown pair  → [ERROR] no finding … in the latest stored scan    exit 2
4. --waive … --reason    → waived skill_instruction_override x … (1 evidence) exit 0
                           scans stored: 1 (no rescan)
5. rescan                → [CRITICAL] known waived …   findings: waived=1    exit 0
6. unrelated edit, scan  → known waived … findings: low=1, waived=1          exit 0
                           (low = drift_changed on the new sha, unwaivable)
7. new distinct match    → known RERAISED …:2 / …:5  findings: critical=2    exit 1
8. --report              → same RERAISED view, no rescan                     exit 1
waivers.json: 1 row, -rw------- ; ledger: 7 scan_finding rows, 2 record_only
```

**Files touched**: `llmsnitch/scan.py`, `llmsnitch/cli.py`,
`fs_coil/digest.py`, `README.md`, `tests/test_scan_waivers.py` (new),
`tests/all.py`, this ticket.

**Cross-ownership requests** (not made here):

1. `llmsnitch/depaudit.py` `add_waiver` (≈L250–268) rewrites `waivers.json`
   from `load_waivers()` — its *filtered* dep-audit view — so a later
   `llmsnitch depaudit --waive …` silently drops every config-audit waiver
   row from the shared file. It should append to the raw list the way
   `scan._waivers_raw()` does. Data-loss bug once T704 grants scan waivers;
   one-line fix, owner: whoever holds depaudit (not in any T70x list).
2. `docs/notifier-spec.md` (T702's file): the digest example at ≈L662
   (`open findings (last patrol): scan Nc/Nh/Nl …`) should show the
   `· N waived` suffix, and the `scan_finding` row could note waived rows
   are `record_only`.
