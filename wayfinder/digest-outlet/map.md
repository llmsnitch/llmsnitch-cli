# Digest Outlet — Wayfinder Map

`label: wayfinder:map`
`status: DONE (charted and closed 2026-09-14)`

## Destination

The **daily digest outlet live on this machine**: once a day, after the
patrol, `fs-coil digest` renders the notify ledger's trailing 24 hours into
a digest file the user reads at a time of their choosing — health first,
then what is *new*, then counts, then the noisiest subjects. It banners
only when the watchers themselves are unhealthy (degraded flag, patrol
missed, bulletin stale), never to re-page findings. Alongside it, the
outlet work the notifier spec's T007 left unexecuted lands: `fs-coil noise`
over the ledger, `fs-coil prune --target notify`, `fs-coil status` showing
the degraded flag. The map closes when
[T602](tickets/T602-activate-digest.md)'s done criteria hold.

## Notes

- **Tracker location**: `wayfinder/digest-outlet/` on `main` in
  `~/llmsnitch-cli` (main is canonical since the dep-audit merge; no
  feature worktree for tracker docs).
- **Spec lineage**: `docs/notifier-spec.md` §"Delivery outlets" (2–4) and
  migration ticket T007 designed this outlet before the patrol, pipx,
  dep-audit, and discovery existed. T007 was never executed. This map
  **amends** the spec (T601 Phase 0) rather than re-deriving it; where the
  two disagree the ticket resolutions win and the spec is updated to match.
- **Plan-vs-do override**: T601–T602 carry execution — the destination is
  a working outlet.
- **Skills**: repo review gates (`code-review` two-axis,
  `ponytail:ponytail-review`) after execution tickets; `tdd` for dev
  agents.
- **Repo policy**: local-only git; `trash`, never `rm`; never run
  `install.sh`; stdlib only; no network imports (test-enforced); files
  0600 / dirs 0700; `python3 tests/all.py` is the gate (135 at charting).
- **Vocabulary**: **Digest** is canon in CONTEXT.md (added at charting).
- **Machine facts (2026-09-14)**: notify ledger = 20 daily files since
  2026-08-26, 546 KB; last 7 days = 1,000 rows, all `scan_finding` from
  `config-audit`, 14 paged; ~140 rows/day, nearly all "known" findings
  re-ledgered by each patrol plus a daily `drift_changed` on session hook
  files. Zero dep-audit or fs-coil rows in the window. Patrol runs 09:30
  (`com.slav-it.llmsnitch-patrol`); `fs-coil` is a pipx entry point at
  `~/.local/bin/fs-coil` (plan 010) — the spec's `/usr/local/bin` path is
  stale. `fs-coil noise` today greps old `fs-coil-*.log` files, not the
  ledger.

## Decisions so far

<!-- one line per closed ticket: gist + link -->

- Grilling round 1 (charting, all recommendations accepted 2026-09-14):
  **scope** = digest + banner + scheduling, `prune --target notify`,
  `noise` over the ledger, `status` shows degraded — dashboard TUI pane out
  of scope; **scheduling** = its own LaunchAgent at 10:00 (after the 09:30
  patrol) covering the trailing 24h — chosen over riding the patrol because
  only an independent run can report "the patrol didn't run"; **banner
  policy** = operational conditions only (degraded flag, patrol missed,
  bulletin stale) — findings never re-page via the digest, the spec's
  20-rows/category threshold is dropped; **content order** = ① health
  ② new since last digest (criticals → high → new unattested / dep-audit
  lesser findings, each with its decision line) ③ counts per category ×
  actor with new/known/resolved ④ five noisiest subjects; known repeats
  never listed individually; one screen by default, `--full` for all;
  **retention** = 45-day default kept, prune runs unattended after the
  digest; **phase-2 anomaly section** = fog until 30+ days of ledger;
  **vocabulary** = add **Digest** only (no "digest window" — say trailing
  24h).
- [T601 — Build the digest outlet](tickets/T601-build-digest-outlet.md) —
  built and live-verified from the repo entry point: `fs-coil digest`
  (health / new / counts / noisiest, 0600 file, health-only banner via
  `watcher_health`), `ledger.py` reader, `noise` over the ledger, `prune
  --target notify`, `status` degraded line, `digest --install-agent`; spec
  amended first; suite 135 → 174; three review gates applied. Not
  installed — T602 activates.
- [T602 — Activate the digest outlet](tickets/T602-activate-digest.md) —
  main fast-forwarded, pipx reinstalled, `com.slav-it.llmsnitch-digest`
  bootstrapped (10:00 daily, `fs-coil digest --prune`), kickstart wrote
  the first real digest with the 09:30 patrol in ① and no banner; seeded
  unhealthy → one `watcher_health` banner; `suppress_*` stopgap key
  deleted from the live config. Destination reached; map closed.

## Not yet specified

- **Content-based anomaly section (spec phase 2)** — μ+2σ per-tuple volume
  anomalies inside the digest; the spec holds the full design. Graduates
  once the ledger has 30+ days and the digest has been read for a couple
  of weeks (2026-10 at the earliest).
- **Digest as the home for lesser-finding review** — whether waivers /
  "known" acknowledgements should be grantable from the digest text (e.g.
  a copy-pasteable `llmsnitch depaudit --waive` line per lesser finding).
  Fog until real dep-audit lesser findings exist to look at.
- **`fs-coil noise` UX after the ledger rewrite** — whether it keeps a
  separate identity or becomes `fs-coil digest --noise`; decide after both
  exist.

## Out of scope

- **Dashboard TUI pane** (`fs_coil/render_notify.py`, spec outlet 4) —
  fs-coil deep's TUI is not how this user reviews; the digest file is.
- **Re-paging findings through the digest** — the per-event novelty gates
  already decided; the digest is pull, health-only push (D18 amended).
- **Notification Center redesign / new outlets** (email, Slack…) —
  personal-machine tool; the file plus a health banner is the outlet.
