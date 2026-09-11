# Dep-Audit — Wayfinder Map

`label: wayfinder:map`
`status: OPEN (charted 2026-09-11)`

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
- **Vocabulary**: **Bulletin**, **Intake**, **Waiver** are canon
  (CONTEXT.md, added at charting). "Exercised" is *not* yet canon — T505
  defines it.
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
