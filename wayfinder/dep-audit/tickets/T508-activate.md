# T508 — Activate dep-audit

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: T507`
`blocks: —`
`status: DONE (2026-09-12)`

## Question

Execution: merge + reinstall (pipx, per scan-rollout's second-merge
rhythm), wire the surface into the daily patrol, wire the weekly bulletin
refresh (`curl` subprocess; interim: T506's re-run path), and verify live.
Done criteria (close the map when all hold):

1. Daily patrol run executes dep-audit and ledgers its result.
2. A weekly refresh path exists and has run once (hash-verified cache,
   payload age stamped).
3. The retroactive intake sweep has run over historical ledgers.
4. A finding (real or seeded) routed through the notify layer; a waiver
   demonstrably silences it; only evidence-gated criticals may page.

## Resolution

All four done criteria hold on this machine (2026-09-12). The map closes.

**Merge + reinstall.** `feature/scanner-venv-mvp` merged into main at
`31027a6` from `~/llmsnitch-cli`. One expected conflict (`plans/README.md`)
plus a plan-number collision: main's independently-committed plan 004
(unattested-agent discovery, `c7ff07b`) renumbered to **plan 011** (least
churn: the feature branch's 004–010 improve-audit block keeps its internal
dependency numbering); both index tables merged, nothing discarded.
`python3 tests/all.py` on main post-merge: **117/117**. Reinstalled with
`pipx install --force ~/llmsnitch-cli` (NOT the stale `~/Repos/llmsnitch`
clone); verified `fs_coil.notify` + all three dep-audit modules import
inside the pipx venv and `llmsnitch depaudit` dispatches from the shim.

**Patrol wiring (criterion 1).** The lazy option: `scan --patrol` now runs
dep-audit in the same process (`scan.cmd_scan` tail calls
`depaudit.cmd_depaudit`), so the existing LaunchAgent
(`com.slav-it.llmsnitch-patrol`, daily 09:30) needs no plist change and no
second agent exists. Exit codes combine worst-verdict-wins with breach
dominant: `1 if 1 in (scan, dep) else max(scan, dep)` — an operational
failure (2) in one surface never masks a breach (1) in the other. Guarded
by `test_patrol_runs_depaudit_worst_verdict_wins` (test_scan_notify.py);
suite now **118/118**. A plain `scan` never runs dep-audit (tested).
Housekeeping: the live plist predated the current generator (logged to
`~/Library/Logs/llm-snitch/`); re-ran `llmsnitch patrol --write` +
re-bootstrap, logs now at the canonical `~/Library/Logs/llmsnitch/`.
Kickstart evidence (canonical log, refreshed agent, installed binary):

    dep-audit: 12 intakes, 0 envs, bulletin age 0.5d
    [OK] no findings

**Weekly refresh (criterion 2).** Choice: **documented manual weekly
re-run** of T506's distiller (`uv run tools/distill_bulletin.py` — the
"weekly manual refresh" line is in its docstring). Rationale: no provider
URL exists for the real curl fetch (ADR 0001), the distiller is the
stand-in, and a scheduling LaunchAgent is machinery the criterion doesn't
demand (ponytail) — especially while "bulletin staleness alerting" is map
fog with no outlet to complain through. The path has run once: bulletin of
2026-09-12 at `~/.llmsnitch/bulletins/pypi.json.gz` + `.sha256`,
hash-verified, 19,033 entries; every audit stamps its age (0.5d above).
A missing/stale-hash bulletin exits 2 with a pointer to the refresh.

**Retroactive sweep (criterion 3).** Ran via the installed CLI over the
real ledgers: **12 intakes** materialized in `~/.llmsnitch/intakes.ndjson`
(was 8 at T507 — new sessions since), all bulk + env-unresolved → 0 envs
audited, correctly quiet. Real audit vs the 19k bulletin: 0 findings,
exit 0.

**Seeded round-trip (criterion 4).** With the installed binary under a
temp `LLMSNITCH_DIR` + notify seams (never the live dirs): fake MAL
bulletin entry × seeded intake × fake env with the package's dist-info →
`[CRITICAL] evilpkg 1.0 MAL-2026-9999 (malicious)`, exit 1,
`depaudit_finding` row in the notify ledger; `llmsnitch depaudit --waive
MAL-2026-9999 evilpkg --reason …` → re-audit exits 0, finding shows
`(malicious, waived)`, ledgered `record_only`. Only the evidence-gated
critical paged; the waiver demonstrably silences.

**Deferred (already map fog):** bulletin staleness alerting (no outlet);
real provider fetch URL (out of scope until a provider exists).
