# Quiet Patrol — Dispatch configuration (2026-09-18)

Orchestrator + three task agents, one frontier ticket each, run as
parallel subagent sessions in isolated git worktrees. This file is the
record of that configuration: a dead agent is respawned from its section
here, never from memory.

## Orchestrator (the charting session)

- Spawns T701, T702, T703 in one message, each `general-purpose`,
  `isolation: worktree`, no model override (memory
  `subagent-connection-drops`: haiku/sonnet die on ECONNRESET during
  parallel reads — agents inherit the parent model, read one file at a
  time, commit early).
- Trusts no agent report until `git log quiet-patrol/T70x` and
  `git diff --stat review/patrol-findings-2026-09-18..quiet-patrol/T70x`
  show the claimed work. Never resumes an agent whose work it has
  superseded.
- Merge order into `review/patrol-findings-2026-09-18`: **T702 → T703 →
  T701** (drift/classify first, then discover/novelty, then the waiver
  block that sits between them in `run_scan`). Resolves conflicts, reruns
  `python3 tests/all.py`, runs the two-axis `code-review` over the
  combined diff, appends one Decisions-so-far line per ticket to
  `map.md`, removes the agent worktrees with `git worktree remove`.
- T704 stays blocked until the user merges to `main` and reinstalls
  (`pipx install --force ~/llmsnitch-cli`); the orchestrator does not do
  that (map Notes, Q4).

## Common brief (every agent)

**You are one wayfinder session resolving exactly one ticket.** Read, in
this order and one file at a time: your section below; your ticket
(`wayfinder/quiet-patrol/tickets/T70x-*.md`); `map.md` Decisions so far
(the D-numbers your ticket cites); `CLAUDE.md`; then only the line ranges
of `llmsnitch/scan.py` your section names. Do not read the whole repo.

**Doctrine (test-enforced, non-negotiable):** stdlib only, Python 3.9
syntax (no `match`, no `X | Y` types); no network imports; files 0600 /
dirs 0700 via `store._open_private` / `_mkdir_private`; exit codes
`0 pass / 1 breach / 2 operational`; `hook.py` untouched; never `rm` (use
`trash`); never run `install.sh`; never push, never add a remote; never
edit `CONTEXT.md` (already updated) or any wayfinder file except your own
ticket. Vocabulary from `CONTEXT.md`: **Waiver**, **Hook state**,
**Patrol**, **Actor bucket**.

**Git protocol:** first command `git switch -c quiet-patrol/T70x`. Commit
after every green step with the prefix `T70x:`. Final commit ends with
`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Never commit
to any other branch.

**Wayfinder protocol:** claim first — change your ticket's status line to
`status: CLAIMED (quiet-patrol/T70x, 2026-09-18)` and commit. On
completion append a `## Resolution` section to your ticket (what was
built, measured numbers, files touched, test count) and set
`status: DONE (2026-09-18)`. Do not edit `map.md` — the orchestrator
records the decision line.

**Ownership:** edit only the files and `scan.py` regions your section
lists, plus a one-line registration in `tests/all.py` (add your module to
both the import list and the run tuple, at the end). Everything else is
another agent's; if you need a change there, write it in your Resolution
as a request and stop short of making it.

**Tests:** a new module `tests/test_<yours>.py`, stdlib runner style
(functions named `test_*`, plain `assert`), using `tests/_seams.with_tmp`
for the env seams (read `_seams.py` once — it sets `LLMSNITCH_DIR`,
`LLMSNITCH_NOTIFY_DIR`, `LLMSNITCH_HOT_STATE`, `LLMSNITCH_CONFIG` and
stubs `notify._deliver`; a test that leaks rows into the real
`~/.llmsnitch` is a bug). Gate: `python3 tests/all.py` green (182 at
dispatch). Then run one real-tree check from the repo entry point with
`LLMSNITCH_DIR` pointed at a scratch dir under your worktree's
`/tmp`-equivalent (never the live store), and record its output in your
Resolution.

**Style:** ponytail — shortest diff that works, no abstractions for one
caller, deliberate shortcuts marked `# ponytail: <ceiling, upgrade
path>`. After green, invoke the `ponytail:ponytail-review` skill on
`git diff review/patrol-findings-2026-09-18..HEAD`, apply the cuts, rerun
the gate, commit. The two-axis code review is the orchestrator's.

**Report back (final message, nothing else):** branch, worktree path,
final sha, `tests/all.py` total, files changed, before/after numbers your
ticket asks for, and any cross-ownership request.

## Agent T701 — Config-audit waivers

Ticket: `tickets/T701-config-audit-waivers.md`. Decisions D03–D07.
Reference implementation to mirror, read once: `llmsnitch/depaudit.py`
lines 207–270 (`load_waivers`, `_waiver_for`, `add_waiver`) and 400–425
(how waived rows print and count).

`scan.py` regions owned:
- a new `# -- waivers ---` section placed directly before
  `# -- the scan ---` (currently line 448): `load_scan_waivers()`,
  `_apply_waivers(findings, waivers)`, `add_scan_waiver(rule_id,
  artifact, reason, out)`;
- inside `run_scan`: one call inserted **after** the resolved-tombstone
  block (`if prev_fps: … "resolved": True})`) and **before** `by_sev = {}`;
  make `by_sev` skip waived rows and add `"findings_waived"` to `meta`.
  Touch no other line of `run_scan`;
- `_route_to_notifier` (record_only for waived), `to_text`, `to_json`,
  `cmd_scan` (`--waive` takes two args, `--reason`, exit 2 on misuse,
  no rescan).
Other files: `llmsnitch/cli.py` usage line for `scan`; `fs_coil/digest.py`
open-findings line (`· N waived`; file is 229/250 lines — if it does not
fit in ~6 lines, say so in the Resolution rather than exceed the cap);
`README.md` command block; `tests/test_scan_waivers.py`; `tests/all.py`.

## Agent T702 — Hook state class and semantic drift

Ticket: `tickets/T702-hook-state-and-semantic-drift.md`. Decisions D08,
D09. Live-tree names to classify are listed in the ticket; verify them
with `ls -la ~/.claude/hooks` (read-only) but never scan the live store.

`scan.py` regions owned: `classify` (lines 64–83), `scan_file` (323–352:
`hook_state` gets the secret pass only, no `RULES`), the drift section
(355–422: `_drift`, `_drift_finding`, plus a new `_drift_salt` helper —
`hook_state` keys are skipped and their stale `hook_script` baseline
entries dropped; `~/.claude.json` salts with the canonical
`mcpServers` subset). Do **not** edit `run_scan`; the salt must be
computable from `(cls, path)` inside the drift section. `scanrules.py`:
class lists / comments only. Docs: `classify` docstring,
`docs/notifier-spec.md` where artifact classes are enumerated.
`tests/test_hook_state.py`; `tests/all.py`.

## Agent T703 — Plugin coverage and scope-aware resolution

Ticket: `tickets/T703-plugin-coverage-and-scope-aware-resolution.md`.
Decisions D10, D11. Baseline numbers in `map.md` Notes (74 of 686
plugin artifacts reached from `$HOME`; budget overflow 2).

`scan.py` regions owned: `discover` (104–155; add the two plugin-root
globs as walked subs per territory, `_walk` from each root),
`_previous_fingerprints` (426–446; return `{fingerprint: artifact}`),
and inside `run_scan` **only** the block from `cur_fps = set()` through
the `"resolved": True})` line (resolve only when the artifact is in this
run's discovered set — build that set from `targets`, not from
`current`, so a size-skipped file still counts as in scope). Docs:
`docs/notifier-spec.md` §2.2 discover roots; the `scan.py` line in
`CLAUDE.md` Architecture only if it enumerates walked subs.
`tests/test_scan_scope.py`; `tests/all.py`. Measure before/after with an
in-process `discover()` from `$HOME` (`os.chdir` in Python, read-only,
no scan run) and record both counts in the Resolution.
