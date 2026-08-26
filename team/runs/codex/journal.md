# Run journal: codex

Pilot run (wayfinder T106). Orchestrator: team-lead session, 2026-08-24.

## Phase 1 — Triage
started: 2026-08-24 22:39 EDT   finished: 2026-08-24 22:41 EDT
evidence: 84 session files under `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`
(observed); `~/.codex/session_index.jsonl` and `~/.codex/hooks.json` present;
roster row `codex` → in-run.
verdict: PASS

## Phase 2 — Dossier
started: 2026-08-24 22:45 EDT   finished: 2026-08-25 00:25 EDT
evidence: `dossiers/codex.md` (310 lines) — gate-checked by orchestrator:
9/9 sections, evidence-dated facts, per-signal confidence (signal 5
honestly low–medium/partial with visible-degradation wording), complete C1
draft, 15 traps incl. cumulative-token trap (#1), local-vs-UTC filename
skew (#2), second-session_meta parent-id trap (#3), decayed shell-error
signal (#5). Observed signing id: identifier `codex`, team `2DC432GLL2`.
Oracle: `state_5.sqlite` threads.tokens_used == ledger totals on 84/84.
verdict: PASS

## Phase 3 — Adapter
started: 2026-08-25 00:35 EDT   finished: 2026-08-25 01:05 EDT
deviation: implementer subagent died twice on API connection drops
(ECONNRESET) with zero files written; orchestrator absorbed the
implementer role per README failure handling. Phases 4–5 stay
independent agents.
evidence: new `llmsnitch/harness.py` (HARNESSES registry + codex parser
honouring dossier traps 1/3/9/12/13), `llmsnitch/ingest.py` (C8 sweep,
cursors in ingest-state.json, idempotent rewrite-on-change),
`llmsnitch/store.py` + `llmsnitch/cli.py` surgical edits (harness column,
`ingest` subcommand, lazy sweep, visible partial-health line),
`tests/fixtures/codex-rollout.jsonl` (synthetic; exercises cumulative-token
trap, parent session_meta, interrupted-not-error, seeded fake secret,
body-class rows) + 4 new tests. Local run: 20/20 passed.
zero writes outside the repo; ~/.codex untouched.
verdict: PASS

## Phase 4 — Verify (attempt 1)
started: 2026-08-25 01:07 EDT   finished: 2026-08-25 01:09 EDT
evidence: independent verifier report (full text preserved in this session's
transcript; key numbers below). Item 1 PASS: suite 20/20 incl. no-network
guard. Item 3 PASS: 168 files 0600 / 85 dirs 0700 across all 84 real
sessions; harness column renders. Item 4 PASS: ~/.codex sessions tree
untouched (0 files newer than marker; the 4 changed files are dossier-listed
caches owned by a live codex process); repo tree clean; real ~/.llmsnitch
never opened (temp LLMSNITCH_DIR).
Item 2 FAIL — two defects:
  2a: total_tokens summed last_token_usage; codex RESTATES token_count rows
      (13 duplicate pairs in worst file; a restated row can carry a
      DIFFERENT last under an unchanged cumulative). Oracle match only
      69/84, overstating up to +72.9%. Correct reading: cumulative
      total_token_usage (oracle-exact 84/84).
  2b: model declared in turn_context with no token row is dropped —
      including a live azureml:// id (trap 7's case). Distribution should
      be {0:4, 1:79, 2:1}, adapter produced {0:5, 1:79}.
Non-blocking note: `list` ID column (14 chars) collides on
prefix+UUIDv7-time ids (17/84 render ambiguously) — follow-up, not C4.
verdict: FAIL → returned to Phase 3 per README failure handling
verdict-note: dossier trap 1 wording also corrected (the two readings are
NOT interchangeable; summing last_token_usage double-counts restated rows)

## Phase 3 (fix) — Adapter
started: 2026-08-25 01:10 EDT   finished: 2026-08-25 01:14 EDT
evidence: commit f2de841 — cumulative-delta token attribution (restated
rows → zero delta), turn_context models registered with zero-token
entries; fixture hardened (restated rows incl. differing-last variant,
declared-only azureml model); dossier trap 1 + §8 corrected. Orchestrator
check: 20/20; oracle 84/84; distribution {0:4, 1:79, 2:1}.
verdict: PASS

## Phase 4 — Verify (attempt 2, re-gate of f2de841)
started: 2026-08-25 01:15 EDT   finished: 2026-08-25 01:18 EDT
evidence: independent verifier re-report. Item 1 PASS: 20/20 pasted.
Fixture-teeth proof: buggy 9ec3850 harness.py against the NEW fixture
fails 18/20 — regression locked. Item 2 PASS: sweep 84/84 sessions,
oracle exact 84/84 (was 69/84), distribution {0:4, 1:79, 2:1} matches
dossier §3, azureml:// id stored with honest zero spend (session total
unchanged 22708). Extra: cumulative never decreases in any real session
(d>0 guard defensive only); usage events sum == meta total on 84/84;
show/check/list render the new zero-token shape, exit 0.
Non-blocking follow-ups: fixture's azureml turn_context ordering differs
from the real (superseded-first) shape; `list` ID column collides at 14
chars on prefixed UUIDv7 ids (17/84) — shared-renderer cosmetic issue.
verdict: PASS

## Phase 5 — Doctrine audit (attempt 1)
started: 2026-08-25 01:20 EDT   finished: 2026-08-25 01:27 EDT
evidence: adversarial auditor report; independently reproduced phase-4
numbers (oracle 84/84, distribution, zero ~/.codex writes) rather than
trusting them. 6/9 checklist items ticked with evidence. Doctrine gates
PASS (nothing pages; signals recorded not paged). Purpose PASS (no
invented prices, no metering drift).
Findings: F1 registry half (C9) never transcribed from dossier §8 into
HARNESSES — actor attribution impossible, cache_paths suppression list
missing; F2 `check` silent about knowingly-partial error signal (health
100 on sessions whose shell errors are invisible); F3 no-writes item not
test-asserted. Non-blocking: N1 path traversal via hostile
session_meta.id (REPRODUCED — writes escaped the sessions root); N2 model
ids bypass _clean; N3 dossier §3 stale token reading; N4 "unknown" bucket
ambiguity; N5 provider_families inert until the pricing module exists;
N6 ID-column collisions (already journaled).
verdict: FAIL → returned to Phase 3 per README failure handling

## Phase 3 (fix 2) — Adapter
started: 2026-08-25 01:28 EDT   finished: 2026-08-25 01:33 EDT
evidence: F1 registry+config_paths transcribed into both HARNESSES entries
(signing ids observed-not-guessed, dated); F2 `check` now prints
`health: partial — <note>` on pass and breach paths; F3 new
test_codex_sweep_never_touches_ledger (hash+listing+mtime_ns before/after);
N1 fixed (_safe_native_id allowlist, fallback sanitized stem) + new
test_codex_hostile_native_id_cannot_escape_store (traversal repro now
caught); N2 model ids through _clean capped 200; N3 dossier §3 corrected.
Local run: 22/22 passed.
verdict: PASS

## Phase 5 — Doctrine re-audit (attempt 2, of 23898e7)
started: 2026-08-25 01:29 EDT   finished: 2026-08-25 01:35 EDT
evidence: auditor re-report. 9/9 checklist items ticked. F1-F3 and N1-N3
closed; every new test proven to DISCRIMINATE (auditor reproduced each
pre-fix behaviour underneath it: traversal test failed, partial-check test
failed, ledger-touch test failed — then all pass on real code). Post-fix
regression sweep: oracle 84/84, distribution {0:4,1:79,2:1}, 0 ~/.codex
writes, 169 store files 0600/0700. Registry ids confirmed observed-not-
guessed (both dossier-dated). Doctrine + purpose PASS.
Residual (non-blocking, follow-up pile): §1-vs-§8 cache_paths gap for
sqlite sidecars (fixed in the phase-6 commit); signing-id prefix-vs-exact
shape divergence vs notifier-spec placeholder — notifier effort's call;
provider_families inert until C7 pricing table; list ID collisions; >64ch
native-id fallback unreachable today.
verdict: PASS

## Phase 6 — Close
started: 2026-08-25 01:36 EDT
evidence: cache_paths sidecar gap reconciled (§8 + harness.py); roster row
codex → done (tier: ledger). Commits this run: b224e86 (dossier), 9ec3850
(adapter), f2de841 (verify fix), 291d709 (verify journal), 23898e7 (audit
fixes), + this closing commit. Signal-set proof: 84/84 real sessions
ingested, total_tokens oracle-exact against state_5.sqlite on all 84.
verdict: PASS — run complete; codex is "supported" per map D02 (ledger
tier). Note: the user's live ~/.llmsnitch has NOT been populated —
deployment is one `llmsnitch ingest` (or any list/show/check) away.
