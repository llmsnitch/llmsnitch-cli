# Dep-Audit — Wayfinder Map

`label: wayfinder:map`
`status: DONE (charted 2026-09-11, closed 2026-09-12 — destination reached)`

## Destination

The **dep-audit surface live on this machine as a working MVP**: every
**intake** (a Python package an agent session provably installed) matched
daily against a weekly-refreshed **bulletin**, findings gated on
machine-local abuse evidence (only evidenced abuse pages as critical —
everything else is lesser and stays quiet), **waivers** honored, findings
routed through the notify layer like `scan_finding`. The bulletin *schema
contract* is published (`docs/bulletin-spec.md`); the provider server that
produces bulletins is explicitly not built here. The map closes when
[T508](tickets/T508-activate.md)'s done criteria hold.

## Notes

- **Tracker location (standing rule)**: this map and its tickets live in
  `wayfinder/dep-audit/` inside the feature worktree
  (`~/.supacode/repos/llmsnitch-cli/feature/scanner-venv-mvp`), committed
  to branch `feature/scanner-venv-mvp`.
- **Skills**: `mattpocock-skills:grilling`, `mattpocock-skills:domain-modeling`;
  repo review gates (`review` two-axis, `ponytail:ponytail-review`) after
  execution tickets.
- **Plan-vs-do override**: T506–T508 carry execution — the destination is a
  working surface, not a spec (same override as scan-rollout).
- **Repo policy**: local-only git; `trash`, never `rm`; never run
  `install.sh`; stdlib-only + no-network-*imports* are test-enforced —
  the bulletin refresh is a `curl` subprocess, the package stays
  import-clean (ADR 0001).
- **Research policy**: research agents use `curl`, never WebFetch/WebSearch
  (user global rule); findings land in `docs/research/` per precedent.
- **Vocabulary**: **Bulletin**, **Intake**, **Waiver** (charting) and
  **Exercised** (T505) are canon in CONTEXT.md.
- **Grounding doctrine**: every page passes AGENTS.md Decision/Actor/Novelty.
  The criticality model is evidence-centric, not advisory-centric: an
  advisory label alone never pages.
- **Machine facts (census 2026-09-11)**: 9 scannable Python envs (6 project
  venvs in ~/Repos, llmsnitch's pipx venv, 1 uv tool env); one venv uses a
  non-standard name (`.venv-dashboard`); `uv.lock` does not imply an
  installed env; no scanner binaries (pip-audit/osv-scanner/grype/trivy)
  installed.

## Decisions so far

<!-- one line per closed ticket: gist + link -->

- [T501 — Advisory-source survey](tickets/T501-advisory-source-survey.md) —
  OSV is the sole aggregation point (all four ecosystems, no-auth bulk);
  exploited = KEV evidence + EPSS forecast as separate fields; severity
  optional and never a gate; exact-version lists viable with an
  `open_ended` marker; indicator fog confirmed; **new**: 46% of PyPI
  corpus is malicious-package (MAL) records → bulletin needs a
  `vulnerability|malicious` class (feeds T503/T505).
- [T502 — Client-side matching with stdlib only](tickets/T502-stdlib-matching.md) —
  bulletin carries **pre-chewed enumerated affected versions +
  `all_versions` boolean, not ranges**; client = PEP 503 normalize +
  canonicalize + strip `+local` + set membership (zero PEP 440
  comparison); `importlib.metadata.distributions(path=…)` reads foreign
  envs from one interpreter (verified live, stdlib 3.9+).

- [T503 — Bulletin schema contract v1](tickets/T503-bulletin-schema.md) —
  `docs/bulletin-spec.md` published: single JSON `{meta, entries[]}`, gzip +
  sidecar `.sha256` (integrity only, signing = v2 fog); full-ecosystem only
  (intake list never leaves the machine); one entry per (advisory-group ×
  package), `id` = CVE-first, waivers match `{id} ∪ aliases`; re-raise on
  severity-band escalation or `kev.listed` flip, never EPSS; `all_versions`
  boolean (no `open_ended`), withdrawn dropped, `fixed_in`/`summary`/`url`
  display-only.
- [T504 — Intake extraction design](tickets/T504-intake-extraction.md) —
  Claude Code hook events only (codex = fog); pip/uv/pipx grammar with
  **bulk intakes** for file-based installs (env-level attribution);
  materialized `intakes.ndjson` + cursor (ingest pattern); env-resolution
  chain ending in unresolved-stays-quiet; retroactive sweep = first run,
  all history; no success filtering — the scan-time `dist-info` join is
  the success oracle.
- [T506 — Interim bulletin](tickets/T506-interim-bulletin.md) —
  `tools/distill_bulletin.py` (out-of-package, `uv run`, curl-only egress)
  distills OSV+KEV+EPSS into a full-PyPI v1 bulletin at
  `~/.llmsnitch/bulletins/pypi.json.gz` + `.sha256` (19,033 entries, 11,717
  malicious, 21 KEV-listed, 1.1 MB gz); manual weekly re-run is the provider
  stand-in; ticket's "this machine's 9 envs" scope superseded by T503's
  full-ecosystem rule.
- [T505 — "Exercised" evidence](tickets/T505-exercised-evidence.md) —
  exercised = source-import scan ∨ project-ran-after-install (bytecode
  evidence dropped: installer-dependent); binary tiers, no middle;
  **malicious ∧ intake pages critical immediately, bypassing the gate**;
  full predicate: `critical = (malicious ∧ intake) ∨ (intake ∧ kev.listed
  ∧ exercised)`; "Exercised" now canon in CONTEXT.md.
- [T507 — Build the dep-audit MVP](tickets/T507-build-mvp.md) —
  shipped: `intake.py`/`bulletin.py`/`depaudit.py` + `llmsnitch depaudit`
  CLI (`--waive`), findings route as `depaudit_finding`; 117/117 tests;
  survived two-axis + ponytail + security-sentinel gates (9 security
  findings fixed); live-verified on this machine (8 real intakes, clean
  scan vs the 19k bulletin, seeded MAL→waiver round-trip). Only T508
  (activate) remains.
- [T508 — Activate dep-audit](tickets/T508-activate.md) — merged to main
  (`31027a6`, plan-004 collision → renumbered 011) + pipx reinstall;
  patrol wiring = lazy in-process (`scan --patrol` also runs dep-audit,
  worst-verdict-wins with breach dominant, tested; 118/118); weekly
  refresh = documented manual distiller re-run (no provider URL yet, no
  scheduling machinery); live-verified: patrol kickstart ledgers
  dep-audit (12 intakes, bulletin age 0.5d, clean), seeded MAL→critical→
  waiver round-trip via installed binary. All four done criteria hold —
  **map closed**.
- Grilling rounds 1+2 (pre-charting, recorded here since they shaped the
  map): destination = working MVP; lost transcripts dropped (enough seen);
  population = **(c) agent-installed only** — proof from ledgers, with
  retroactive sweep; provider model — llmsnitch consumes a **distilled
  bulletin**, server build out of scope, schema contract in scope; fetch =
  weekly `curl` subprocess, hash-verified cache under `~/.llmsnitch/`,
  scans run offline against cache and stamp payload age; scan rides the
  daily patrol; critical = intake **and** bulletin says actively-exploited
  **and** exercised on this machine (indicator forensics is fog); waivers
  loose and personal-machine-scoped — (advisory × package) + reason, no
  TTL, re-raise on severity escalation; schema is multi-ecosystem from day
  one and OSV-derived; names: surface `dep-audit`, payload **bulletin**,
  evidence record **intake**, exception **waiver**.

## Not yet specified

- **Indicator-based abuse forensics** — bulletins shipping machine-checkable
  indicators that fs-coil/ledger evidence is matched against (Q10 signal b).
  Graduates after schema v1 lands and MVP behavior is observed.
- **Non-Python ecosystems** (npm, NuGet, Maven) — the schema carries
  `ecosystem` from day one; client-side intake grammar and env discovery
  per ecosystem graduate one at a time, npm likely first.
- **fs-coil site-packages attribution** — filesystem-write evidence as a
  secondary intake source for installs the ledger grammar misses.
- **Codex command enrichment** — codex ledgers carry `exec_command`
  records but `parse_codex` drops the text; emitting command events would
  extend intake coverage to ledger-only harnesses (T504 decision 1).
- **Bulletin authenticity (signing)** — the sidecar hash is integrity-only;
  a signed manifest with real key management is the v2 candidate once a real
  provider exists (T503, spec's "Out of contract" list).
- **Bulletin staleness alerting** — "no refresh in >2 weeks" is invisible
  until an outlet exists; same problem as patrol staleness (scan-rollout
  fog), likely graduates together.
- **Reporting panel depth** — how findings read in the weekly digest / TUI;
  fog until the digest outlet exists.

## Out of scope

- **Building the bulletin provider** — the aggregation server that distills
  OSV/KEV/EPSS into bulletins. Only its consumption contract
  (`docs/bulletin-spec.md`) is this effort's business.
- **Non-agent-installed packages** — populations (a) "everything on disk"
  and (b) "agent-territory venvs"; dep-audit watches intakes only.
- **Corp/DevOps exception governance** — approval chains, TTL policy,
  audit trails; waivers stay personal-machine loose.
