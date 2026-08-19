# Notifier Redesign Spec

**Status**: accepted — this is the wayfinder map's destination artifact
(`wayfinder/map.md`, decisions D01–D27). Every design choice below cites the
map decision it derives from. The audience is a fresh Claude Code session
executing the migration; nothing here assumes conversation context.

**Read first**: `AGENTS.md` (the actionability doctrine) and `README.md`
(design constraints: stdlib-only, `dependencies = []`, no network code, flat
files, hot path never blocks). Both are non-negotiable and test-enforced.

## Context

llmsnitch currently ships three unrelated notification mechanisms (D01, D24):

1. **`fs_coil/notifier.py`** — a 60-second in-memory dedup dict
   (`Notifier._should_emit`). Forgets everything on daemon restart; pages the
   same known-benign event forever.
2. **`fs_coil/bridge.py:edge_alert`** — edge-triggered verdict transitions
   for the session-shed / agent-flick wrappers, persisted per-tool in
   `state.json`.
3. **`fs_coil/monitor.py:_low_noise`** — a hardcoded suppression for
   Anthropic-signed processes reading `~/Library/Keychains/`, plus the T001
   stopgap (`[notify] suppress_*` globs in `light_watcher.py`, kept as an
   interim relief valve per D03 and deleted by this migration's final
   ticket).

The doctrine in `AGENTS.md` says every alert must pass three gates —
**Decision** (names an action), **Actor** (names who did it), **Novelty**
(recurring known-benign patterns roll into a digest, never page one at a
time). The grounding failure (2026-08-18): five pages in one day for Claude
Code's own plugin installer, zero pages for the `az` CLI reading a keychain
PAT. This spec replaces all three mechanisms with one notify layer that
enforces the three gates universally across every alert surface (D04).

**Source-of-truth note for the executor**: the original fs-coil source repo
was trashed; the only current code (including the T001 stopgap) is the
root-owned installed tree at `/usr/local/share/llm-snitch/fs_coil/` and the
wrapper scripts `/usr/local/bin/{fs-coil,session-shed,agent-flick}`.
Migration ticket T003 vendors that tree into this repo (user decision,
2026-08-19). Until T003 lands, treat `/usr/local` as read-only reference.

## Scope

In scope — all llmsnitch alert surfaces (D02):

| Surface id | What it is | Runs as |
|---|---|---|
| `fs-coil-light` | fswatch/FSEvents watcher (writes only, no FDA) | user LaunchAgent `com.slav-it.fs-coil` |
| `fs-coil-deep` | eslogger watcher (reads + writes + execs, needs FDA) | root LaunchDaemon `com.slav-it.llm-snitch` |
| `session-shed` | agenttrace health-gate wrapper | user, periodic |
| `agent-flick` | agent-strace cost-gate wrapper | user, periodic |
| *(future)* | any new watcher (e.g. proc-eye) calls the same API | — |

Config groups `fs-coil-light` and `fs-coil-deep` under one policy section
`[notify.fs-coil]`; the ledger keeps them distinct in the `surface` field.

Out of scope: see [§ Out of scope](#out-of-scope) at the end (copied from the
map).

## Domain model

Canonical vocabulary — also recorded in the repo-root `CONTEXT.md`. Use these
words exactly; the code, config, ledger, and docs all share them.

- **Surface** — an alert-producing subsystem (table above). Stored per
  ledger row.
- **Category** — code-defined enum classifying what happened (D05, D06).
  The unit of policy: novelty windows and config overrides key off it.
- **Actor bucket** — normalized short name for who did it (`claude-code`,
  `bash`, `unknown`, …). Drives novelty math (D16).
- **Actor raw** — verbatim executable path, recorded for forensics only
  (D16). Never used in novelty math.
- **Novelty tuple** — the pair `(category, actor_bucket)`. The key the
  novelty gate deduplicates on (D12, D13).
- **Novelty window** — per-tuple duration during which repeats of the same
  tuple are suppressed (logged, not paged). Defaults live in the category
  enum; config can override per category and per tuple (D06, D13).
- **Cold trail** — the persistent NDJSON event ledger. Every event lands
  here, paged or not (D08).
- **Hot state** — the small JSON novelty index consulted on the hot path
  (D12). Different rhythm from the ledger, so a different file.
- **Degraded flag** — persistent marker set when the notify layer itself
  fails; surfaced by `fs-coil status` and the dashboard, never by push (D22).
- **Cold start** — the 24h learning window after install during which
  everything is ledgered but only `critical` severity pages (D23).
- **Edge-triggered** — fires only on a verdict *transition*
  (pass→breach, breach→pass), never on a repeated state (D06:
  `threshold_breach`).
- **Actor mismatch** — a registered agent touching a *different* registered
  agent's directory; a metadata flag on `deny_write`, not a category (D07).
- **Agent registry** — the table of known agents and their identifying
  signals: paths, exe basenames, signing ids (D17).

## Architecture

New code lives in two files inside the vendored `fs_coil` package:

- `fs_coil/notify.py` — category enum, ledger writer, hot-state store,
  novelty gate, cold-start logic, degraded flag, duration parser, and the
  public `notify()` entry point.
- `fs_coil/agent_registry.py` — built-in registry of 7 agents, config-merge
  logic, and `attribute_actor()`.

Everything is Python 3.9+ stdlib. No new dependencies, no network, no
daemon: the notify layer is a library the existing watchers call in-process.

### The `notify()` API

```python
def notify(surface, category, subject, *,
           actor_raw=None,        # verbatim exe path if known
           pinfo=None,            # deep-mode process dict (pid, exe, sign, …)
           ppid=None,             # light-mode best-effort parent pid (D15)
           severity="high",       # "critical" | "high" | "low"
           deny_pattern=None,     # matched deny rule, if any
           actor_mismatch=None,   # target agent name when cross-agent (D07)
           title=None, message=None,   # NC rendering; built from fields if None
           icon_actor=None, exe_path=None, rexe_path=None,  # icon passthrough
           ) -> bool:
    """Single entry point for every alert surface. Returns True iff a
    Notification Center banner was posted. NEVER raises (D21)."""
```

Pipeline, in order:

1. **Attribute** — `attribute_actor()` resolves `(actor_bucket, actor_raw)`
   (see below). Callers that already know the actor pass `actor_raw`/`pinfo`;
   attribution still normalizes to a bucket.
2. **Ledger append** — every call writes one NDJSON row, unconditionally.
   The cold trail is complete even when nothing pages.
3. **Novelty gate** — look up the novelty tuple in hot state under an
   exclusive `fcntl.flock`. Outcomes (recorded as `novelty_reason`):
   - `first_seen` — tuple never seen → page.
   - `window_expired` — last page older than the tuple's window → page.
   - `window_repeat` — inside the window → suppress (count incremented).
   - `edge` — `threshold_breach` only: the caller certifies a verdict
     transition; always page (window is edge-triggered, D06).
3a. **Cold start** — if now < `install_ts + cold_start` and severity is not
   `critical`, suppress regardless of novelty (`novelty_reason` becomes
   `cold_start_suppressed`) (D23).
4. **Deliver** — post via the existing `Notifier` NC mechanics
   (terminal-notifier, unique `-group` per banner, `launchctl asuser` when
   euid is 0). The `Notifier._should_emit` 60s cooldown is deleted (D24) —
   the novelty gate replaces it.

**Fail-closed** (D21, D22): the entire pipeline runs inside one
`try/except Exception`. On any error: no banner, and best-effort —
append `NOTIFIER-ERROR: <reason>` to the daily fs-coil log, set
`degraded = "<reason>"` in hot state. `notify()` returns False. The degraded
flag is cleared by the next fully-successful `notify()` call, or expires
after `degraded_flag_ttl` (default 24h). Broken notifier is discoverable via
`fs-coil status` and the dashboard badge, never assumed from silence.

Startup "armed" banners (`fs-coil armed`, `fs-coil (light) armed`) stay as
direct `Notifier` calls — they are liveness proofs the user opted into by
starting the daemon, not events, and must not be novelty-suppressed.

### Category enum (D06, D07)

`fs_coil/notify.py` defines exactly these at launch. Categories are code, not
config (D05): config selects and tunes, it never invents categories.

| Category | Fires when | Default window | Default severity | Action the page names |
|---|---|---|---|---|
| `agent_self` | An agent writes inside its *own* registered dirs (e.g. Claude Code → `~/.claude/settings.json`) | 24h | low | none — digest only; recall via `fs-coil noise` |
| `agent_plugin_cache` | An agent writes its own plugin/cache dirs (`~/.claude/plugins/cache`, …) | 24h | low | none — digest only |
| `agent_signed_self_read` | Deep mode: an OS-verified agent-signed process reads `~/Library/Keychains/` (absorbs `_low_noise`, D25) | 24h | low | none — digest only; audit trail intact |
| `deny_write` | Write to a watched sensitive path by an unrecognized actor — or by a registered agent into *another* agent's dirs (`actor_mismatch` set, severity `critical`) | 1h | high | investigate the writing process; revoke/kill if unexpected |
| `deny_read` | Deep mode: read of a watched path by an unrecognized actor | 5m | high | investigate; rotate the credential if unexpected |
| `keychain_access` | Deep mode: `security find-generic-password` etc. by a watched process (except when `agent_signed_self_read` matches) | 5m | high | check which item was read; rotate if unexpected |
| `threshold_breach` | session-shed / agent-flick verdict transition | edge-triggered (0) | high | review the session (`session-shed`, `agent-flick` report); kill the runaway session |

Windows are expressed as duration strings: integer + `s`/`m`/`h`/`d`, and
`0` = edge-triggered. Parser lives in `notify.py` (`parse_window("24h") →
86400`).

`agent_signed_self_read` preserves `_low_noise`'s security property (D25):
the *suppressing* predicate trusts only OS-verified signals — the signing id
from the registry (`rsign`/`sign` prefix match), falling back to the genuine
app-bundle executable layout (`/<App>.app/contents/macos/` substring), never
a bare attacker-nameable directory. See `_low_noise` in the vendored
`fs_coil/monitor.py` for the exact semantics being ported.

### Agent registry (D17)

`fs_coil/agent_registry.py` ships this built-in table; `[agent.<name>]`
config sections add new agents or extend an existing agent's lists — no code
change to register an agent.

```python
AGENTS = {
    "claude-code": {
        "paths": ["~/.claude", "~/Library/Application Support/Claude"],
        "exes": ["claude", "Claude"],
        "signing_ids": ["com.anthropic."],   # prefix match
    },
    "codex":    {"paths": ["~/.codex"],      "exes": ["codex"],    "signing_ids": []},
    "aider":    {"paths": ["~/.aider"],      "exes": ["aider"],    "signing_ids": []},
    "copilot":  {"paths": ["~/.copilot"],    "exes": ["copilot", "github-copilot"], "signing_ids": []},
    "cursor":   {"paths": ["~/.cursor"],     "exes": ["cursor", "Cursor"],   "signing_ids": []},
    "windsurf": {"paths": ["~/.windsurf"],   "exes": ["windsurf", "Windsurf"], "signing_ids": []},
    "agy":      {"paths": ["~/.agy"],        "exes": ["agy"],      "signing_ids": []},
}
```

Signing ids for the six non-Claude agents ship empty — real values must be
observed, not guessed (see [§ Open questions](#open-questions)). Discover
with `codesign -dr - /Applications/<App>.app` and add via config.

**`attribute_actor(path=None, pinfo=None, ppid=None) → (bucket, raw)`** —
multi-signal, first match wins (D14):

1. **Signing id** — `pinfo["rsign"]`/`pinfo["sign"]` prefix-matches a
   registered agent's `signing_ids` → that agent. (Checked first among
   process signals because it is OS-verified and unspoofable.)
2. **Exe basename** — basename of `pinfo["rexe"]`/`pinfo["exe"]`, or of the
   `ps -p <ppid> -o comm=` result in light mode (best-effort, races
   accepted, D15), matches a registered agent's `exes` → that agent.
3. **Path prefix** — the *touched* path lies inside a registered agent's
   `paths` → that agent. (Weakest signal: identifies whose territory, not
   who acted. Used alone it can only support `agent_self`-family categories,
   never exonerate a writer.)
4. Otherwise: normalize known tool basenames (`bash`, `git`, `python`,
   `security`, …) to their own buckets; else `unknown`. Digest rollups use
   the reserved bucket `aggregate` (D16).

**Actor-mismatch rule** (D07): when signals disagree — process signals
(1–2) say agent X, path prefix (3) says agent Y's territory, X ≠ Y — the
event is `deny_write` with `actor_mismatch = "<Y>"` and severity `critical`.
Critical severity bypasses cold-start suppression (D23) but still respects
the novelty window (one page per tuple per hour, not one per write).

### Event ledger — the cold trail (D08–D11)

- **Location**: `~/Library/Logs/llm-snitch/notify/events-YYYY-MM-DD.ndjson`
  — one file per day. (D08 named `events.ndjson`; D11's daily rotation
  "matching fs-coil's existing pattern" resolves it to date-stamped daily
  files, exactly like `fs-coil-YYYY-MM-DD.log`. The filename is computed per
  event, so a date roll mid-run needs no rotation daemon.)
- **Permissions**: files `0600`, directory `0700` (matches llmsnitch policy).
- **Write mechanics** (D10): one `json.dumps(...) + "\n"` per event, written
  with unbuffered `O_APPEND`. Rows are < PIPE_BUF (4096 bytes — enforce by
  truncating `actor_raw`/`subject` to 500 chars and dropping `pinfo` if the
  encoded row would exceed 3500 bytes), so concurrent writers (root daemon +
  user agent + wrappers) interleave atomically without locks.
- **Retention** (D11): `fs-coil prune --target notify [--days N]` deletes
  ledger and digest files older than N days (default 30), same date-stamp
  parsing as the existing log prune. `fs-coil prune` without `--target`
  keeps its current meaning (fs-coil logs) — add `--target all` for both.

**Row schema** (D09) — fixed key order, epoch-seconds floats
(`time.time()`), optional keys omitted when empty:

```json
{"v": 1,
 "ts": 1755640000.123,
 "surface": "fs-coil-light",
 "category": "deny_write",
 "actor_bucket": "unknown",
 "actor_raw": "/usr/local/bin/mystery",
 "subject": "~/.ssh/config",
 "severity": "high",
 "first_seen_ts": 1755639000.0,
 "count_in_window": 3,
 "novelty_reason": "window_repeat",
 "notified": false,
 "deny_pattern": "~/.ssh/**",
 "pinfo": {"pid": 123, "ppid": 45, "exe": "...", "sign": "...", "rexe": "...", "rsign": "..."},
 "actor_mismatch": "codex"}
```

`subject` is the tilde-shortened path (or, for `threshold_breach`, the
verdict summary like `"cost 6.10 > ceiling 5.00"`). `novelty_reason` enum:
`first_seen | window_expired | window_repeat | edge | cold_start_suppressed |
degraded_suppressed`. No secret *values* ever land in a row — paths and
credential types only (same rule as the rest of llmsnitch).

### Hot state — the novelty index (D12, D13)

- **Location**: `~/Library/Caches/llm-snitch/notify-state.json` (create the
  directory `0700` on first use; nothing else lives there yet).
- **Schema** (versioned; unknown `version` → move the file aside to
  `notify-state.json.bak` and start fresh — a novelty reset is fail-safe
  because the ledger is untouched):

```json
{"version": 1,
 "install_ts": 1755600000.0,
 "degraded": null,
 "tuples": {
   "deny_write|claude-code": {
     "first_seen_ts": 1755610000.0,
     "count_in_window": 4,
     "last_notified_ts": 1755612000.0
   }
 }
}
```

- Tuple keys are `"<category>|<actor_bucket>"` (neither side can contain
  `|`). `degraded` is `null` or a short reason string with a `degraded_ts`
  sibling for TTL expiry.
- **Locking** (D12): every read-modify-write opens the file, takes
  `fcntl.flock(LOCK_EX)`, reads, mutates, seeks to 0, truncates, writes,
  releases. The file stays small (≤ a few hundred tuples), so whole-file
  rewrite under one lock is simpler and safer than partial updates. Corrupt
  JSON → same move-aside-and-restart as version mismatch.
- `install_ts` is stamped when the file is first created — it anchors the
  cold-start window (D23).

### Window resolution order (D13, D20)

For a tuple `(category, actor_bucket)` on surface S, the effective window is
the first defined of:

1. `[notify]` `window_<category>@<actor_bucket>` — per-tuple override
2. `[notify.<S>]` `window_<category>` — per-surface category override
3. `[notify]` `window_<category>` — global category override
4. the code default from the category enum

(This is the map's merge order — agent-specific → surface-specific → global
→ code, D20.)

## Config schema

Three axes (D20) in the existing INI at `~/.config/llm-snitch/config`,
parsed with the existing `bridge.load_section` pattern (per-key fallback,
one malformed value never resets the others). Full worked example:

```ini
[notify]
# Global cross-cutting knobs.
enabled = true                 # master switch; false = ledger-only, no pages
channel_nc = true              # Notification Center banners
channel_digest = true          # daily digest file + threshold-gated banner
digest_banner_threshold = 20   # NC banner when any category's day-count >= this
degraded_flag_ttl = 24h        # degraded flag auto-expires after this
cold_start = 24h               # learning window after install (D23)
# Category window overrides (see resolution order in the spec):
window_deny_write = 1h
window_agent_self = 24h
# Per-tuple override — category@actor_bucket:
window_deny_write@git = 4h

[notify.fs-coil]               # governs BOTH fs-coil-light and fs-coil-deep
enabled = true
window_deny_read = 5m

[notify.session-shed]
enabled = true

[notify.agent-flick]
enabled = true

[agent.claude-code]            # registry axis — identification, not policy
# Extends/overrides the built-in entry; lists are comma-separated.
paths = ~/.claude, ~/Library/Application Support/Claude
exes = claude, Claude
signing_ids = com.anthropic.

[agent.cursor]                 # example: adding a signing id once observed
signing_ids = com.todesktop.230313mzl4w4u92
```

Registry sections merge onto the built-ins by agent name: a listed key
replaces that key's built-in list; unlisted keys keep the built-in. A
section for an unknown name registers a brand-new agent (D17).

The T001 stopgap key `suppress_claude_self` is deleted in migration T007 —
the `agent_self` category subsumes it.

## Delivery surfaces

Four (D18). Every rendered line obeys the actionability doctrine: name the
decision, name the actor, respect novelty.

### 1. Notification Center (immediate)

Fires only when the pipeline's gates all pass. Rendering (defaults built
from fields when the caller passes no `title`/`message`):

- Title: `🦍 <actor_bucket> · <category>` (deep) / `🐍 …` (light) —
  keeps the existing per-surface glyphs.
- Message: subject (tilde-shortened), actor line (`↳ exe (via rexe)`),
  rule/verdict line, and an action line per the category table (e.g.
  `investigate: fs-coil logs`).
- Mechanics preserved from `notifier.py`: terminal-notifier binary, unique
  `-group` suffix per banner (macOS otherwise collapses repeats),
  `launchctl asuser <uid> sudo -u <user>` when running as root, icon
  resolution unchanged. Delete only `_should_emit`/`_last`/`_cooldown`.

### 2. On-demand CLI recall — `fs-coil noise`

Reimplemented over the ledger (T001's log-grep version is replaced; the
command name survives). Signature:

```
fs-coil noise [--category X] [--actor B] [--days N] [--all]
```

- Default: suppressed rows (`notified == false`) from the last N days
  (default 1), grouped by category, then actor bucket: count + last 10
  rows (`ts  subject  actor_bucket  novelty_reason`).
- `--all`: include notified rows too (full recall).
- Empty result prints the config hint (how to tune windows), mirroring the
  current UX.

### 3. Daily digest

- New `fs-coil digest` subcommand, run by a new user LaunchAgent
  `com.slav-it.llm-snitch-digest.plist` (daily at 09:00,
  `StartCalendarInterval`).
- Reads the *previous day's* ledger file. Always writes
  `~/Library/Logs/llm-snitch/notify/digest-YYYY-MM-DD.txt` (0600).
- Posts one NC banner iff any category's day-count ≥
  `digest_banner_threshold` (default 20) — threshold-gated push, always-on
  pull (D18).
- Content, in order: ① any `actor_mismatch` rows (each with an
  investigate-action line), ② degraded-flag warning if set, ③ per-category
  per-actor counts with first/last timestamps, ④ the anomaly section once
  the content-based digest ships (phase 2, below).

### 4. TUI badge — `fs-coil dashboard`

- New `fs_coil/render_notify.py` pane, following the existing `render_*.py`
  module pattern and the dashboard's 5s refresh.
- Shows: today's per-category counts (critical red / high yellow /
  suppressed dim), a mini-log tail of the last 5 ledger rows, and — if the
  degraded flag is set — a red `⚠ notifier degraded: <reason>` line (D22).
- `fs-coil status` additionally prints the degraded flag as a key-value row
  (good=false styling) so the flag is visible without the dashboard.

## Migration plan

Five sequential tickets (D26), rip-and-replace (D24). Each ticket ends with:
run the full test suite, then install (`sudo cp` the changed files from the
repo into `/usr/local/share/llm-snitch/fs_coil/` / `/usr/local/bin/`, then
restart the affected service), then verify its done criteria. Execute in
order; each ticket leaves the system working.

Restart commands: light agent `launchctl kickstart -k
gui/$(id -u)/com.slav-it.fs-coil`; deep daemon `sudo fs-coil restart`;
wrappers need no restart (invoked per-run).

### T003 — Vendor the fs-coil tree into this repo

- **Create**: `fs_coil/` (verbatim copy of `/usr/local/share/llm-snitch/fs_coil/`,
  minus `__pycache__` at every depth — use `rsync -a --exclude='__pycache__/'`,
  not `cp -R` + a top-level delete), `bin/fs-coil`, `bin/session-shed`,
  `bin/agent-flick` (verbatim from `/usr/local/bin/`, copied with `cp -pL`:
  `-L` vendors file content if any is a symlink, `-p` keeps the exec bit,
  which git records).
- **Touch**: nothing else. No behavior change, no edits — the commit is the
  baseline the later diffs read against.
- **Executor traps**: the source tree is root-owned — try an unprivileged
  copy first; if it needs sudo, `chown -R` the repo copies back to the user
  afterward (root-owned files in the repo break later `git add`). Stage with
  `git add fs_coil bin` only — never `git add -A` (untracked non-ticket dirs
  like `wayfinder/` must stay out). The per-ticket install/restart step is a
  deliberate no-op here: repo and installed files are byte-identical, the
  empty diff is the proof.
- **Done criteria**: `diff -rq --exclude __pycache__ fs_coil /usr/local/share/llm-snitch/fs_coil`
  is empty; same for the three bin scripts;
  `find fs_coil -name __pycache__ -o -name '*.pyc'` is empty;
  `test -x bin/fs-coil -a -x bin/session-shed -a -x bin/agent-flick`;
  the copy is committed and `git log --stat -1` shows only `fs_coil/*` and
  `bin/*`; `python3 tests/test_llmsnitch.py` still passes (the vendored
  package is not imported by the llmsnitch package, so nothing breaks — if
  the no-network-imports grep unexpectedly sweeps the vendored tree, STOP
  and report rather than editing vendored code).
- **Test strategy**: the diff/find/test commands above are the test.

### T004 — Core notify engine (library only, no callers)

- **Create**: `fs_coil/notify.py` (category enum + windows, `parse_window`,
  ledger append, hot-state store with flock, novelty gate, cold start,
  degraded flag, `notify()` pipeline), `fs_coil/agent_registry.py`
  (built-in table, `[agent.*]` merge, `attribute_actor`),
  `tests/test_notify.py`.
- **Touch**: nothing existing.
- **Done criteria**: all new tests pass; no existing test breaks; a REPL
  smoke call `notify("fs-coil-light", "deny_write", "~/.ssh/config")` under
  `LLMSNITCH_NOTIFY_DIR`/`LLMSNITCH_STATE_FILE` overrides writes a ledger
  row and returns True first call / False second call.
- **Test strategy**: unit tests against tmp dirs with env-var overrides for
  ledger dir and state file, and an injectable clock (`notify(..., _now=)`
  or module-level `_now()` monkeypatched). Cover: first_seen pages,
  window_repeat suppresses, window_expired re-pages, edge always pages,
  cold-start suppresses high but not critical, degraded flag set on forced
  ledger IOError and notify() returns False without raising, state-file
  version mismatch moves aside and restarts, concurrent append rows stay
  intact (two processes, 500 rows each, all parse).

### T005 — Wire fs-coil light + deep through `notify()`

- **Touch**: `fs_coil/light_watcher.py` (deny hits → `notify()`; **delete**
  `load_notify_suppress` and `match_suppress` — the stopgap's watcher half),
  `fs_coil/monitor.py` (deny hits → `notify()` with `pinfo`; keychain execs
  → `keychain_access`; **delete** `_low_noise` — its predicate moves into
  the `agent_signed_self_read` rule in `notify.py`/registry per D25),
  `fs_coil/notifier.py` (**delete** `_should_emit`, `_last`, `_cooldown`;
  `Notifier` keeps icon + delivery mechanics only).
- **Done criteria**: `fs-coil light` foreground run: `touch
  ~/.claude/settings.json` produces a ledger row with
  `category=agent_self, notified=false` and no banner; `touch
  ~/.ssh/spec-test && trash ~/.ssh/spec-test` produces `deny_write` and (in
  non-stdout mode) one banner, a second touch within 1h produces
  `window_repeat`; predicate-equivalence tests for `_low_noise` →
  `agent_signed_self_read` pass (same inputs, same suppress verdicts —
  signing-id match, bundle-layout fallback, and the attacker-named
  `/tmp/claude.app/` case still *not* suppressed).
- **Test strategy**: port `_low_noise`'s semantics as table-driven tests
  BEFORE deleting it; foreground smoke on both modes; existing tests green.

### T006 — Wire session-shed + agent-flick

- **Touch**: `bin/session-shed`, `bin/agent-flick` (their `_on_breach` /
  `_on_recover` callbacks call `notify(surface, "threshold_breach", …)`
  instead of `Notifier().notify(...)`), `fs_coil/bridge.py` (unchanged
  logic; `edge_alert` remains the transition detector — the callbacks are
  what changed).
- **Done criteria**: with a hand-edited `state.json` verdict, a simulated
  pass→breach run posts exactly one banner and one ledger row with
  `novelty_reason=edge`; repeating the same breach verdict posts nothing;
  breach→pass posts the recovery once; first-ever healthy run stays silent
  (existing bridge guarantee preserved).
- **Test strategy**: unit-test the callbacks with a stubbed notify;
  end-to-end via `session-shed check` against a fixture state dir.

### T007 — Delivery surfaces + stopgap cleanup + docs

- **Touch**: `fs_coil/commands.py` (`cmd_noise` reimplemented over the
  ledger; new `cmd_digest`; `cmd_prune` gains `--target notify|logs|all`;
  `cmd_status` prints the degraded flag), `fs_coil/cli.py` (dispatch +
  USAGE for `digest`, `noise` flags, `prune --target`),
  `fs_coil/dashboard.py` (mount the new pane).
- **Create**: `fs_coil/render_notify.py`,
  `~/Library/LaunchAgents/com.slav-it.llm-snitch-digest.plist` (install
  step, not a repo file — document the plist inline in the ticket).
- **Delete** (the T001 stopgap's remains): the
  `suppress_claude_self` key and its comment block from
  `~/.config/llm-snitch/config`'s `[notify]` section (replaced by the new
  `[notify]` schema above).
- **Docs**: update the vendored `fs_coil/AGENTS.md` and repo `README.md`
  (new commands, new config schema), add a pointer in repo `AGENTS.md` to
  this spec.
- **Done criteria**: `fs-coil noise` groups ledger rows; `fs-coil digest`
  writes the digest file and honors the banner threshold both ways;
  `fs-coil status` shows `degraded` when the flag is hand-set in the state
  file; dashboard renders the pane; `grep -rn "suppress_claude_self\|load_notify_suppress\|match_suppress\|_low_noise\|_should_emit" fs_coil bin`
  returns nothing; full test suite green.
- **Test strategy**: fixture ledgers for noise/digest; a `--date` override
  on `cmd_digest` for deterministic tests; render function returns strings —
  assert on content, not curses.

## Deferred: content-based digest (phase 2)

Full design, deferred implementation (D19) — ships only after ≥ 30 days of
ledger accrual exists to compute against.

**Goal**: the digest should surface *volume anomalies* — a known-benign
tuple suddenly chattering — which per-event novelty windows structurally
cannot see (they suppress repeats; they never notice "10× more repeats than
usual").

**Algorithm** (runs inside `fs-coil digest`, pure ledger read, no new
state):

1. For each novelty tuple seen yesterday, read up to the last 30 daily
   ledger files and compute the tuple's daily event counts.
2. Require ≥ 7 days with data for the tuple; otherwise skip (cold tuples
   can't have a baseline).
3. Compute mean μ and population stddev σ of the daily counts (yesterday
   excluded).
4. **Trigger**: yesterday's count fires an anomaly line iff
   `count > μ + 2σ` **and** `count ≥ 5`. The absolute floor stops σ≈0
   tuples (e.g. steady 1/day) from flapping on a single extra event.
5. Anomaly lines render in digest section ④ as:
   `⚠ <tuple>: <count> events yesterday vs baseline <μ>±<σ>/day — action:
   fs-coil noise --category <cat> --days 2`.

**Ledger fields it needs**: none beyond the v1 row schema — `ts`,
`category`, `actor_bucket` suffice. (This is why the schema ships complete
in T004 even though this section is deferred.)

**Non-goals**: no ML, no seasonality/weekday modeling, no per-path
granularity (tuples only), no real-time anomaly pages (digest only), no new
state files. If 2σ proves too twitchy, the knob is a single
`digest_anomaly_sigma` config value — not a new algorithm.

## Out of scope

Copied from the map — deliberately beyond this effort; return only via a
fresh wayfinder map:

- Multi-user / multi-host support — llmsnitch is a per-user tool.
- Any network delivery channel (Slack, email, webhook) — no network code,
  test-enforced.
- Any GUI dashboard beyond the existing `fs-coil dashboard` TUI.
- Telemetry / anonymized usage reporting — excluded by policy.
- Deep-mode Endpoint Security replacement (eslogger stays; watcher redesign
  is orthogonal).
- Rewriting the deny-list matcher or the fswatch integration.
- Cross-machine correlation of alerts.

## Open questions

Left open deliberately; neither blocks any migration ticket.

1. **Signing ids for codex / aider / copilot / cursor / windsurf / agy** —
   blocked on real observed values (guessing a signing id into a
   *suppression* path would be a security hole). The registry ships them
   empty; exe/path signals still attribute these agents. Fill in via
   `[agent.<name>] signing_ids = …` after running
   `codesign -dr - <app bundle>` on the installed app. Owner: user, as the
   agents get installed.
2. **Digest LaunchAgent hour** — spec says 09:00; purely a taste knob the
   user can edit in the plist. No config key for it in v1 (the plist IS the
   config, matching the existing session-shed/agent-flick cadence pattern).
