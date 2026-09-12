# Implementation Plans

Plans 001–003: improve-skill run of 2026-08-26 (branch audit at `a7a83bb`) —
all executed. Plans 004–010: improve-skill run of 2026-09-12 (full audit at
`db238b9`, findings maintainer-selected: all). Plan 011: standalone
(2026-09-09, "Bari AI" coverage-gap incident). Execute in the order below.
Each executor: read the plan fully before starting, honor its STOP
conditions, and update your row when done. House rules that bind every plan:
local-only repo (never push), `trash` never `rm`, never run `install.sh`.

## Execution order & status

| Plan | Title | Priority | Effort | Depends on | Status |
|------|-------|----------|--------|------------|--------|
| 001 | Fix ReDoS in scan rules (+ adversarial tests) | P1 | M | — | DONE |
| 002 | Make walk-budget truncation visible | P1 | S | — | DONE |
| 003 | Frontmatter parse to fence, not 60-line window | P2 | S | — | DONE |
| 004 | One command runs all 56 tests; docs corrected | P1 | S | — | DONE |
| 005 | `cost_note` actually reaches the user | P2 | S | 004 | DONE |
| 006 | Sanitize session ids at the store boundary | P2 | S | 004 | DONE |
| 007 | Redaction/perms hardening (keys, truncation margin, 0600-at-create) | P2 | S | 004 | DONE |
| 008 | fs_coil: icon-key sanitizer + log create-0600 | P3 | S | 004 | DONE |
| 009 | Guard-branch tests (cli dispatch, walk guards, patrol, alien ledger, pattern composition) | P2 | M | 004; after 005–007 if queued | DONE |
| 010 | Ship the `fs-coil` entry point | P3 | S | 004 | DONE |
| 011 | Unattested-agent discovery (close coverage gap) | P2 | M | — | DONE (steps 1–6; step 7 decision-gated) |

Status values: TODO | IN PROGRESS | DONE | BLOCKED (reason) | REJECTED (rationale)

## Dependency notes

- 001–003 are independent (001 first: the only adversary-triggerable one).
- **004 first, always**: it creates `tests/all.py`, the verification gate
  every later plan's done criteria use, and fixes the doc line that would
  otherwise mislead executors into a 34-test "green".
- 005–008 and 010 are mutually independent.
- 009 last among the code plans: its characterization tests should pin the
  *final* behavior (after 005–007), and its STOP conditions assume those
  fixes may already be present.
- 011 (originally numbered 004 on main; renumbered at merge) is independent
  of the rest. Written at commit `53b1ab4` (2026-09-09), prompted by the
  "Bari AI" coverage-gap incident and grounded in
  `docs/research/scanner-survey-mvp.md` §2.1/§2.2/§2.5. Steps 1–6 are the
  low-risk core; Step 7 (cold-start banner) is a decision-gated follow-on
  that touches `fs_coil/notify.py` — do not start it without maintainer
  sign-off.

## Findings considered and rejected

From the 2026-08-26 run:

- **baseline.json integrity (HMAC/stamp)** — an attacker with write access
  to `~/.llmsnitch/` already sits inside the store's trust boundary; drift
  is the only blinded signal. Revisit if the baseline ever gains an
  approval-workflow role beyond drift dedup.
- **`--out` flag removal (ponytail-audit)** — named in the committed MVP
  spec; kept.
- **scan.py 250-line split** — explicitly declined by the maintainer.
- **≥10 same-second scan-id collisions sort -9 above -10** — unreachable in
  practice; recorded in commit 79acbac.

From the 2026-09-12 run:

- **Slim the wheel to the 8-module `fs_coil.notify` import closure** —
  shipping all of `fs_coil` is a documented decision (`pyproject.toml`
  comment; T204 found the degradation live); repackaging risk (dual-tree
  convergence) exceeds the benefit for a local-only tool. Plan 010 makes the
  shipped code invokable instead.
- **ingest whole-file re-parse on change** — tradeoff recorded in
  `ingest.py`'s module docstring ("correctness over byte-offset cleverness
  while parsers need whole-file context"); no measured pain. Revisit if
  `list` latency on long live codex sessions becomes real.
- **scan rule-loop restructuring (rules-by-class index / merged
  alternations)** — no measured hotspot; the pathological-file ceiling test
  already bounds it.
- **adding a linter (ruff)** — deliberate minimalism; the repo enforces its
  invariants as tests (`test_no_network_imports` pattern), which is the
  house style.
- **`_SECRET`/`_SECRET_ALL` composition refactor into a shared module** —
  speculative; replaced by a composition *test* (plan 009 step 5).
- **stale-memory namespace drift (`com.slav-it` vs `org.llmsnitch`)** — the
  repo is internally consistent on `com.slav-it.*`; the migration note in
  session memory was a candidate, not a landed fact. Not a finding.

## Direction

**Maintainer directive (2026-09-12): direction effort stays focused on the
CVE-scanning capability — the dep-audit wayfinder map
(`wayfinder/dep-audit/map.md`).** The map is the roadmap: frontier T504
(intake extraction) → T505 (exercised evidence) → T506 (interim bulletin) →
T507 (build MVP) → T508 (activate). The bulletin contract v1 is published
(`docs/bulletin-spec.md`, T503). No separate direction plans are written
here; dep-audit work is tracked on its map, not in `plans/`.

Deferred direction options (recorded so they aren't re-derived; none
selected):

- **Daily digest outlet** — specced in `docs/notifier-spec.md:632-855`;
  three fog items (reporting-panel depth, bulletin staleness alerting,
  notify-ledger retention) wait on it. Revisit after the dep-audit MVP —
  dep-audit findings will want the digest too.
- **Claude Code ledger adapter** — `team/roster.md` marks it pending
  (contract C2 diff-check); would make primary-harness capture hookless.
- **`llmsnitch redact-retroactive`** — re-redact existing ledgers with the
  Unicode-hardened `_SECRET`; byte-identical backup mandatory. Carried since
  the 2026-08-26 run.
