# T701 — Config-audit waivers

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: —`
`blocks: T704`
`status: OPEN — unclaimed`

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
