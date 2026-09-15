# Plan 012 — Digest finding-recall (standing open-findings readout)

- **Status:** DONE
- **Priority:** P2 (coverage gap in the digest; no live vuln)
- **Effort:** M
- **Written against commit:** `15727b2`
- **Depends on:** none. Builds on the digest outlet (T601–T602, DONE) and the
  dep-audit surface (T501–T508, DONE).
- **Grounding:** `wayfinder/digest-outlet/map.md` (decided content order + the
  "known repeats never listed individually" and "digest is pull, health-only
  push" constraints), `docs/notifier-spec.md` §Delivery outlets.

---

## Context — why this exists

The daily digest (`fs_coil/digest.py`, `fs-coil digest`) renders the notify
ledger's trailing 24h in four sections: ① health, ② new since last digest,
③ counts, ④ noisiest. Section ② is the only place individual findings appear,
and it lists only rows that are **new vs the trailing 7 days**
(`render()`, `digest.py:105-111`: `new = {k for k in first if k not in
seen}`).

**The gap:** the patrol re-ledgers the *same* findings every day (map machine
facts, 2026-09-14: "~140 rows/day, nearly all 'known' findings re-ledgered by
each patrol"). After 7 days a persistent finding — e.g. a `wildcard_bash_grant`
sitting in `~/.claude/settings.json` — is no longer "new", drops out of section
②, and the digest reads **"nothing new"** while the problem is still open and
unaddressed. There is no standing recall of *what is currently flagged*.
Section ③ shows category×actor **row counts**, not finding severity or an
open-finding tally. Separately, dep-audit findings have **never rendered** in
the digest (map: "Zero dep-audit or fs-coil rows in the window"; live
`depaudit-state.json` shows `findings: 0`), so that path is unexercised.

**Why now:** the digest outlet exists, which is exactly the blocker the
scan-rollout and dep-audit maps named ("digest recall of scan findings…until
T007"; "reporting panel depth…fog until the digest outlet exists").

**In-bounds check (do not skip — this touches decided ground):**
- The digest-outlet map's OUT OF SCOPE bars *re-paging* findings through the
  digest ("pull, health-only push"). This plan adds a **pull-only readout** —
  no banner, no `notify()` call — so it is consistent.
- The grilling decision "② new since last digest… known repeats never listed
  individually" is **respected**: this plan renders **counts from producer
  state files**, never a dump of known ledger rows into ②.
- `fs_coil` must not import `llmsnitch` (`digest.py:6-8`). Respected:
  `health_report()` already reads the producer state files
  (`scans/*/meta.json`, `depaudit-state.json`); this plan carries two extra
  fields off those same reads.

The deferred fog item "digest as the home for lesser-finding review" is about
**waiver-granting from the digest** (copy-pasteable `--waive` lines) — a
different feature. This plan does not touch waivers.

---

## What "done" looks like

The digest carries a standing **"open findings"** readout sourced from the
last patrol's `scan/meta.json` (`findings_by_severity`) and
`depaudit-state.json` (`findings`), so persistent scan and dep-audit findings
stay visible every day until resolved — independent of the 7-day novelty
window. Dep-audit's ② render path is exercised by a test. Zero findings →
one clean "no open findings" line. All suites green.

---

## Design decisions

### D1 — Recall is a state-file readout, not a ledger re-dump

Source the standing counts from the **producer state files** the digest
already reads, not from re-scanning the ledger. `scan/meta.json` carries
`findings_by_severity` (`scan.py:372-376`, e.g. `{"critical":1,"high":4,
"low":11}`); `depaudit-state.json` carries a `findings` count (`depaudit.py:
280-283`). This keeps `fs_coil` free of any `llmsnitch` import and honors
"known repeats never listed individually" — it is a tally + pointer, not a
row list.

### D2 — Placement: a readout block right after ① health

`health_report()` (`digest.py:52-76`) already walks `scans/*/meta.json` (for
patrol timing) and reads `depaudit-state.json`. Extend it to also return the
latest patrol's severity breakdown and the dep-audit finding count, and
render an "open findings" block immediately after the ① health lines (before
②). This reuses the existing producer read — no new file walk, no new
section-number churn to ②/③/④ (the grilling-fixed order stays; the readout is
part of the health/posture head, not a new numbered section).

### D3 — dep-audit severity enrichment (small, worthwhile)

`depaudit-state.json` today has only a total `findings` count, no severity
split, so the readout could only say "dep-audit: N". Extend `_stamp_state`
(`depaudit.py:273-283`) to also write `findings_critical` (unwaived
criticals) so the readout can distinguish "1 critical malicious package" from
"3 lesser". This is the one `llmsnitch/`-side change; everything else is
`fs_coil/`.

---

## Files in scope

- `fs_coil/digest.py` — extend `health_report()` return + `render()` output.
- `llmsnitch/depaudit.py` — `_stamp_state()` writes `findings_critical`.
- `tests/test_fs_coil_digest.py` (or wherever digest tests live — confirm with
  `grep -rl "def test_.*digest\|from fs_coil import digest" tests/`) — new
  cases.
- `docs/notifier-spec.md` — one line documenting the readout in the digest
  layout (§Delivery outlets, digest section).

**Out of scope (do not touch):** the ② new-findings logic, waivers, the
notify/banner path, section order ②③④, any `notify()` call from the readout.

---

## Steps

### Step 1 — `health_report()` carries the open-findings tally

In `fs_coil/digest.py`, `health_report()` (`digest.py:52-76`) already computes
`patrol` as the newest patrol `meta.json`'s `ended_at`. Capture that meta's
`findings_by_severity` at the same time, and the dep-audit counts from the
`dep` dict it already loads (`digest.py:60`). Add to the returned dict:

```python
    # inside the scans/*/meta.json loop — keep the meta of the newest patrol
    #   patrol_meta = m   (when m["ended_at"] is the running max)
    ...
    scan_sev = (patrol_meta or {}).get("findings_by_severity") or {}
    return {..., "problems": problems,
            "scan_findings": scan_sev,              # {"critical":n,"high":n,"low":n}
            "dep_findings": _num(dep.get("findings")) or 0,
            "dep_critical": _num(dep.get("findings_critical")) or 0}
```

Guard every read with the existing `_json`/`_num` helpers — a missing or
malformed meta must yield zeros, never raise (`health_report` "Never raises"
contract, `digest.py:53`).

### Step 2 — `render()` prints the "open findings" block

In `render()` (`digest.py:99`), after the ① health lines (`L += [...] or
["  → all watchers healthy"]`, `digest.py:127-128`) and before `L += ["", f"②
…"]` (`digest.py:130`), insert:

```python
    sev = health.get("scan_findings", {})
    sc, sh, sl = (int(sev.get("critical", 0)), int(sev.get("high", 0)),
                  int(sev.get("low", 0)))
    dc, dtot = int(health.get("dep_critical", 0)), int(health.get("dep_findings", 0))
    if sc or sh or sl or dtot:
        parts = []
        if sc or sh or sl:
            parts.append(f"scan {sc}c/{sh}h/{sl}l (llmsnitch scan --report)")
        if dtot:
            parts.append(f"dep-audit {dc}c/{dtot} (llmsnitch depaudit)")
        L += ["", "open findings (last patrol): " + " · ".join(parts)]
    else:
        L += ["", "open findings: none"]
```

Numbers come only from producer state (D1). This block persists regardless of
the 7-day novelty window — the recall the plan exists for.

### Step 3 — dep-audit writes a critical count

In `llmsnitch/depaudit.py`, `_stamp_state()` (`depaudit.py:273-283`) writes
the state dict. Add `findings_critical`:

```python
                "findings": len(findings),
                "findings_critical": sum(1 for f in findings if f.get("critical")),
                "note": note}))
```

`f["critical"]` is the finding's own gated criticality (`depaudit.py:398`
reads it). No behavior change beyond one extra integer field.

### Step 4 — docs

`docs/notifier-spec.md`, the digest-layout description: add one line noting the
"open findings" readout sits after ① health, sourced from the last patrol's
`meta.json findings_by_severity` and `depaudit-state.json`, pull-only (never
banners). Match the existing terse spec style.

---

## Test plan

Confirm the digest test file first: `grep -rl "from fs_coil import digest\|
def test.*digest" tests/`. Follow its existing fixture pattern (the digest
tests seed producer state files + a synthetic ledger via
`tests/_seams.seed_ledger`, per commit `6fb9f7b`).

1. `test_open_findings_readout_from_scan_meta` — seed a `scans/<id>/meta.json`
   with `trigger:"patrol"`, `ended_at:<recent>`,
   `findings_by_severity:{"critical":1,"high":2,"low":3}`; render a digest;
   assert the output contains `open findings (last patrol): scan 1c/2h/3l`.
2. `test_open_findings_readout_dep_audit` — seed `depaudit-state.json` with
   `ts:<recent>, findings:4, findings_critical:1`; assert the line contains
   `dep-audit 1c/4 (llmsnitch depaudit)`.
3. `test_open_findings_none_when_clean` — seed a patrol meta with empty
   `findings_by_severity` and dep `findings:0`; assert `open findings: none`.
4. `test_open_findings_survives_novelty_window` — seed the ledger so a
   `scan_finding` row is **known** (present in the 7-day lookback, so absent
   from ②) while the patrol meta still reports `findings_by_severity` with a
   critical; assert ② says "nothing new" **and** the open-findings block still
   shows the critical. This is the core regression the plan targets.
5. `test_depaudit_finding_renders_in_section_two` — seed a **new**
   `depaudit_finding` ledger row (category `depaudit_finding`, unwaived
   critical, not in lookback); assert it appears under ② with the
   `depaudit_finding` decision line (`uninstall if unexpected; detail:
   llmsnitch depaudit`) and tier `[CRITICAL]`. Exercises the never-run path.
6. `test_stamp_state_writes_critical_count` (in the dep-audit test file) —
   run a dep-audit that produces one critical + one lesser finding; assert
   `depaudit-state.json` has `findings_critical == 1` and `findings == 2`.
7. `test_health_report_missing_meta_is_zero` — no scan meta, no dep state;
   assert `health_report()` returns `scan_findings=={}`/`dep_findings==0` and
   does not raise (the never-raises contract).

## Done criteria (machine-checkable)

- `python3 tests/all.py` → all pass (was 174 at digest charting; now 174+7).
- `python3 -m compileall -q fs_coil llmsnitch` → clean.
- `python3 -m pyflakes fs_coil/digest.py llmsnitch/depaudit.py` → clean
  (or the repo's lint equivalent).
- Live smoke: with a temp `LLMSNITCH_DIR` seeded with a patrol `meta.json`
  carrying a critical, `python3 -c "from fs_coil import digest; import io;
  b=io.StringIO(); digest.cmd_digest(out=b); print(b.getvalue())"` shows the
  `open findings (last patrol):` line; grep the real
  `~/.llmsnitch/notify/digest-*.txt` after a `fs-coil digest` run and confirm
  the line is present and correct against
  `~/.llmsnitch/scans/<newest-patrol>/meta.json`.
- No-import invariant intact: `grep -n "import llmsnitch\|from llmsnitch"
  fs_coil/digest.py` → empty.

## Maintenance notes

- **Interacts with `run_scan`'s `findings_by_severity`** (`scan.py:368-376`):
  it counts non-resolved findings, which is exactly the open set — if that
  ever changes to count resolved rows too, the readout inflates. Watch in
  review of any `run_scan` change.
- **`patrol_meta` selection:** must track the meta whose `ended_at` is the
  running max **and** `trigger=="patrol"` (mirror the existing filter at
  `digest.py:58`), so a manual `scan`'s meta never shadows the patrol's.
- **Do not** let the readout call `notify()` — it is pull-only by design
  (digest-outlet OUT OF SCOPE). If a future request wants an open-critical to
  *banner*, that is a separate decision against the "health-only push" rule.

## Escape hatches

- If the digest test file does not already seed producer state files (only a
  synthetic ledger), and wiring `scans/*/meta.json` fixtures balloons past a
  small helper — **STOP** and report; the fixture seam may want its own tiny
  plan.
- If `findings_by_severity` is absent from real patrol `meta.json` on the live
  machine (schema drift since `scan.py:372`) — **STOP**, re-verify the meta
  schema, and do not ship a readout that silently always says "none".
