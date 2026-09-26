# Digest Rollup — Dispatch configuration (2026-09-26)

Orchestrator + **one** task agent. This file is the record of that
configuration: a dead agent is respawned from its section here, never from
memory.

## Why one agent, not a swarm

The organization is sized to the diff, not to the machine. T1001 is ≤ 5 net
lines in one 231-line file plus two tests and one spec sentence; every
part of it touches `digest.py`'s ② block, so a second builder would only
conflict. T1002 is live activation (reinstall + read the next digests),
which the orchestrator executes itself — it is verification, not code.
Splitting further would add coordination cost and remove nothing from the
critical path. The rule this map records for future dispatches:

| Diff size (net lines) | Builders | Review |
|---|---|---|
| ≤ 30, one file | 1 | orchestrator reviews inline against the ticket's done criteria + ponytail review by the builder |
| 30–300, disjoint files | 1 per disjoint region, spawned in one message | two-axis `code-review` (Standards / Spec) sub-agents in parallel, then orchestrator merges in dependency order |
| > 300 or cross-cutting | chart another map first | — |

## Orchestrator (the charting session)

- Spawns T1001 as `general-purpose`, `isolation: worktree`, **no model
  override** (memory `subagent-connection-drops`: smaller models die on
  ECONNRESET during parallel reads; agents inherit the parent model, read
  one file at a time, commit early).
- Base for the agent worktree is `main` HEAD (memory
  `agent-worktree-base-is-main`). At dispatch `main == feature/
  reduce-notification-noise == 4efcac8`; the brief carries that sha and
  the orchestrator checks `git merge-base --is-ancestor 4efcac8 <agent
  branch>` before trusting anything.
- Trusts no agent report until `git log` and `git diff --stat
  4efcac8..<agent branch>` show the claimed work, and `python3
  tests/all.py` is green **in the agent's worktree**, run by the
  orchestrator. Never resumes an agent whose work it has superseded.
- Merge: agent branch → `feature/reduce-notification-noise` (ff if
  possible), rerun the gate, inline review against T1001's done criteria
  (diff is ≤ 30 lines: table row 1), append one Decisions-so-far line to
  `map.md`, `git worktree remove` the agent worktree, ff `main`.
- T1002: executes the reinstall itself (the user has asked for activation
  in this session), verifies by file mtime + `diff` against main, runs
  `fs-coil digest` foreground once to read the new ② shape today, marks
  T1002 ACTIVATED. The map closes on two scheduled 10:00 digests — that
  wait is the user's, not a ticket.

## Common brief (the agent)

**You are one wayfinder session resolving exactly one ticket.** Read, in
this order and one file at a time: your section below; your ticket
(`wayfinder/digest-rollup/tickets/T1001-section-two-decisions-only.md`);
`map.md` Decisions so far (D01, D02, D05, D06); `CLAUDE.md`; then only
`fs_coil/digest.py` lines 20–30 and 85–180 and `tests/test_digest.py`
lines 1–45 and 89–135. Do not read the whole repo.

**Doctrine (test-enforced, non-negotiable):** stdlib only, Python 3.9
syntax (no `match`, no `X | Y` types); no network imports; never edit
`fs_coil/notify.py`, `hook.py`, `CONTEXT.md`, or any wayfinder file except
your own ticket; never `rm` (use `trash`); never run `install.sh`; never
push, never add a remote. 250-line cap per `fs_coil` file — `digest.py` is
231, your budget is ≤ 5 net lines there. Every printed subject goes
through `ledger.clean()` (already the case in ②; keep it).

**Git protocol:** first command `git switch -c digest-rollup/T1001`.
Confirm `git merge-base --is-ancestor 4efcac8 HEAD` succeeds before
editing; if it fails, stop and report. Commit after every green step with
the prefix `T1001:`. Final commit ends with
`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Never commit
to any other branch.

**Wayfinder protocol:** claim first — set your ticket's status line to
`status: CLAIMED (digest-rollup/T1001, 2026-09-26)` and commit. On
completion append a `## Resolution` section to your ticket (what was
built, the replay numbers from done criterion 2, files touched, test
count) and set `status: DONE (2026-09-26)`. Do not edit `map.md`.

**Tests:** extend `tests/test_digest.py` (stdlib runner style, `test_*`
functions, plain `assert`; use the existing `_render(...)` helper and
`_seams.row(ts, category, subject, actor_bucket, **kw)`; fixtures are
invented subjects, never real paths). Gate: `python3 tests/all.py` green
(208 at dispatch). Then the read-only replay in done criterion 2: load the
live ledger files `~/Library/Logs/llmsnitch/notify/events-2026-09-1[7-9].ndjson`
and `events-2026-09-2[0-5].ndjson` in-process via `fs_coil.ledger.iter_rows`,
call `render()` directly for the 2026-09-24 10:00 → 2026-09-25 10:00 window
with the 7-day lookback and equal-length prior, pass a `health` dict built
from `health_report()` — **never call `notify()` or `cmd_digest()`**, never
write under `~/Library/Logs/llmsnitch/`. Compare ③ to
`~/Library/Logs/llmsnitch/notify/digest-2026-09-25.txt` ③ (read-only).
Record ② line counts before/after and the header line in your Resolution.

**Style:** ponytail — shortest diff that works; deliberate shortcuts
marked `# ponytail: <ceiling, upgrade path>`. After green, invoke the
`ponytail:ponytail-review` skill on `git diff 4efcac8..HEAD`, apply the
cuts, rerun the gate, commit.

**Report back (final message, nothing else):** branch, worktree path,
final sha, `tests/all.py` total, `wc -l fs_coil/digest.py`, files
changed, the replay before/after numbers, and any cross-ownership request.

## Agent T1001 — ② lists decisions only

Ticket: `tickets/T1001-section-two-decisions-only.md`. Decisions D01, D02,
D05, D06.

`digest.py` regions owned:
- module level next to `_CAP` (line ~26): add `_NO_DECISION`, derived
  from `notify.CATEGORIES` — action string starts with `none`;
- inside `render`, the ② block only (from `L += ["", f"② new since last
  digest …"]` through `L.append("  nothing new")`): filter `items` by
  category not in `_NO_DECISION`; header shows `(N · M digest-only, see
  ③)` when M > 0, else `(N)`; `nothing new` when N == 0. Do **not** touch
  `new` (③ depends on it), `_key`, `_tier`, ③, ④, or the health block.

Other files: `tests/test_digest.py` (two new tests per done criterion 1);
`docs/notifier-spec.md` §3 ② — one sentence after "Known repeats are
never listed individually." Nothing else.
