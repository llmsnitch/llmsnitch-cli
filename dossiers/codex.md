# Dossier: codex

```
harness:    codex                  # canonical name = actor bucket
tier:       ledger                 # no pre-existing live capture (C3 normal state)
admission:  PASS                   # 84 local JSONL rollouts on disk (evidence §2)
dossier_date: 2026-08-25
observed_on:  this machine (macOS arm64, Codex CLI 0.149.1 via Homebrew cask)
status:     complete               # T101 rank 1; the T106 pilot target
```

One dossier per harness: the single fact sheet that feeds the **adapter**
(contract C1 entry + code hook), the **agent registry** (C9), and — later,
outside this map — the scan MVP's seed table. Every fact carries its
evidence; facts observed on a live machine are dated. Contract:
`docs/harness-adapter-contract.md`.

## 1. Identity & registry (C9)

| Field | Value | Evidence |
|---|---|---|
| Territory paths | `~/.codex/` (global; relocatable via `CODEX_HOME`), `<project>/.codex/` (per-repo) | observed 2026-08-25; `CODEX_HOME` per snyk-agent-scan `agents/codex.py:346` |
| Exe basenames | `codex` | `command -v codex` → `$HOME.local/bin/codex` (observed 2026-08-25) — **a user wrapper, not the real binary; see §7 trap 4** |
| Real binary | `/opt/homebrew/bin/codex` → `/opt/homebrew/Caskroom/codex/0.149.1/bin/codex` | observed 2026-08-25 |
| Signing identity | Identifier `codex`, TeamIdentifier `2DC432GLL2`, Mach-O thin arm64, hardened runtime (flags `0x10000`), signed 2026-08-23 | **OBSERVED** 2026-08-25: `codesign -dv /opt/homebrew/Caskroom/codex/0.149.1/bin/codex`. Note the identifier is the bare string `codex` — not a reverse-DNS bundle id like Claude Code's |
| Cache paths (benign-writer suppression) | `~/.codex/cache/`, `~/.codex/.tmp/`, `~/.codex/tmp/`, `~/.codex/shell_snapshots/`, `~/.codex/thread-writer-locks/`, `~/.codex/log/`, `~/.codex/*.sqlite-wal`, `~/.codex/*.sqlite-shm`, `~/.codex/models_cache.json`, `~/.codex/cloud-config-bundle-cache.json` | observed 2026-08-25 (`~/.codex` listing). The `-wal`/`-shm` sidecars and `models_cache.json` churn constantly — high notifier noise if unsuppressed |
| Self-run sentinel | none identified | no `CODEX*` env sentinel observed; `CODEX_HOME` was unset in this shell |
| Additional originators | `codex-tui` (86 metas), `codex_vscode` (4 metas) | observed — the VS Code extension writes into the **same** ledger, so one adapter covers both surfaces |

## 2. Ledger (C2) — where sessions live

| Fact | Value |
|---|---|
| Session files | `~/.codex/sessions/<YYYY>/<MM>/<DD>/rollout-<local-ts>-<uuid>.jsonl` |
| Glob | `~/.codex/sessions/*/*/*/rollout-*.jsonl` — matched exactly 84 files, and the tree contains **no** other files (84 total = 84 rollouts) |
| Format | JSONL, one object per line, append-only during a session |
| Row shape | every row is exactly `{"timestamp": str, "type": str, "payload": …}` — 325/325 rows in the oldest file, uniform across all 84 |
| Growth | new file per session; 84 sessions spanning 2026-04-02 → 2026-08-21, 32,197 rows total |
| Compression / rotation | none observed (plain UTF-8 JSONL, mode 0644) |
| Adjacent — NOT ingested | `~/.codex/history.jsonl` (195 rows, keys `{session_id, text, ts}` — prompt bodies, message-body class per C6) |
| Adjacent — corroboration only | `~/.codex/state_5.sqlite` (§3 cross-check), `~/.codex/thread_history_1.sqlite`, `session_index.jsonl` (2 rows only — stale, not an index of the 84) |

Admission evidence: files present and readable on this machine, newest
rollout 2026-08-21. Plain stdlib `json` per line; malformed lines skipped
(fail-soft rule) — zero malformed lines observed across 32,197.

## 3. Signal-set mapping (C4)

How each required signal is derived from the ledger format. Confidence:
**high** = observed in current transcripts; **medium** = observed but
shape may vary across versions.

| Signal | Where | Confidence |
|---|---|---|
| model ids | `payload.model` on `type:"turn_context"` rows. Observed live: `gpt-5.5` (221), `gpt-5.6-sol` (51), `gpt-5.4` (11), `gpt-5.4-mini` (2), `gpt-5.3-codex` (1), and one full `azureml://registries/azure-openai/models/gpt-5.3-codex/versions/2026-02-24` URI (§7 trap 7). 79/84 sessions carry exactly one model, 1 switches mid-session, 4 carry none — and those same 4 carry zero tokens, so no spend goes unattributed | high |
| tokens per model | **cumulative-delta** reading of `payload.info.total_token_usage.{input_tokens, cached_input_tokens, output_tokens, reasoning_output_tokens, total_tokens}` on `event_msg`/`token_count` rows (4,424 of 4,428 have `info` populated; 4 are null and must be skipped) — never sum `last_token_usage`, rows are restated (trap 1 as corrected). Attribute each delta to the most recent preceding `turn_context.payload.model` — verified safe: **zero** files emit a `token_count` before their first `turn_context` | high for session totals (oracle-exact 84/84); **medium** for the per-model split (the join is positional, and only 1/84 sessions exercised it) |
| session start/end | min/max top-level `timestamp` across rows — ISO-8601 UTC with milliseconds and a literal `Z` (all 90 metas). Present on **32,197 of 32,197** rows, zero missing | high |
| session cwd/project | `payload.cwd` on the **first** `session_meta` row (zero nulls across 84 files, 18 distinct cwds); `turn_context.payload.cwd` corroborates. Project identity further available from `session_meta.payload.git.{branch, commit_hash, repository_url}` | high |
| error count (suspicion proxy) | **PARTIAL — see §7 trap 5 and the visible-degradation note below.** In current versions only two markers exist: `patch_apply_end.success == false`, and `mcp_tool_call_end` where `payload.result` has an `Err` key or `result.Ok.isError == true`. Observed across the 81 files on cli 0.14x/0.15x: 10 `isError`, 1 `Err`, 0 patch failures | **low–medium** |

Native session id: `payload.id` on the **first** `session_meta` row
(= the filename UUID; a UUIDv7). Store id per C5: `codex-<uuid>`.

**C4 signal 5 must be reported visibly degraded.** The dominant tool-result
row — `function_call_output`, 5,318 of 32,197 rows — carries no error flag
at all: its `output` is a bare string (5,158 of 5,318 are not even JSON) with
no status, exit code, or success field. The one structured shell signal,
`exec_command_end.{exit_code, status}`, stopped being emitted after cli
0.125.0 (§7 trap 5). Suggested `check` line, following the contract's
honest-disablement precedent:

```
health: partial — codex records tool errors only for MCP calls and patch-apply;
        shell tool results carry no error flag
```

### Independent cross-check (not a second ledger)

`~/.codex/state_5.sqlite` carries a `threads` table with **exactly one row
per rollout file** (84/84, every `rollout_path` present on disk and inside
the sessions tree), columns including `model`, `model_provider`, `cwd`,
`tokens_used`, `created_at`, `updated_at`, `cli_version`, `thread_source`.
Its `tokens_used` matched the JSONL final `total_token_usage.total_tokens`
**exactly on all 84 threads** — which is what independently proves the
cumulative-token rule in §7 trap 1. Its `model` column is null on precisely
the same 4 sessions that lack `turn_context`, and `thread_source` splits
44 `user` / 37 `subagent` / 3 null.

Use it as a **verification oracle for the adapter's parse test, not as the
ingest source**: the filename is version-numbered (`state_5` → a future
`state_6`), so the path is unstable (§7 trap 11). `thread_history_1.sqlite`
is not viable at all — it projects only 9 of 84 threads, and its promising
`thread_turns.error_json` column is null on all 42 rows.

## 4. Pricing / provider families (C7)

The **authoritative** provider for a codex session is read from the ledger,
not inferred: `session_meta.payload.model_provider` — observed `openai` on
90/90 metas. Prefer it; fall back to model-id patterns only when absent.

| Model-id pattern | Provider family |
|---|---|
| `gpt-*`, `o1*`/`o3*`/`o4*`, `codex-*` | `openai` |
| `azureml://…/gpt-*`, any `azureml://` URI | `openai` (Azure OpenAI deployment — same family, different endpoint) |
| anything else | `openai` fallback tier **+ `unknown model` flag** — first-class detection signal per contract |

**Do not hardcode codex → openai.** Two independent routes put non-OpenAI
model ids in this ledger: the vendored cookbook documents pointing
`config.toml` at OpenRouter with slugs such as
`~anthropic/claude-sonnet-latest` (`codex-cli.mdx:167`), and this machine
already shows one Azure-hosted `azureml://` id. The `model_provider` field
is what keeps that honest.

Models currently offered to this install, from `~/.codex/models_cache.json`
(local file, `fetched_at` 2026-08-25T04:14:04Z, client 0.149.0): `gpt-5.6-sol`,
`gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini`,
`codex-auto-review`. That cache carries **no** rate fields — per-token prices
for the shared C7 table must be sourced separately by a human/agent with
real network access (see §9 note on network).

## 5. Live capture (context — outside contract)

None, and none is to be added: C2 forbids adapters wiring hooks into a
harness. For the record, Codex *does* support Claude-Code-shaped hooks —
`~/.codex/hooks.json` on this machine declares `SessionStart`, `Stop`, and
`UserPromptSubmit` entries, each `{type, command, timeout}` (observed
2026-08-25, already user-populated). llmsnitch must leave that file alone.
Codex is `ledger` tier; the ledger is the only ingest path.

## 6. Config paths (scan-seed context, not ingested)

`~/.codex/config.toml` (user), `~/.codex/<name>.config.toml` (profile
overlays selected with `--profile`), `/etc/codex/config.toml` (system),
`<project>/.codex/config.toml`, `~/.codex/AGENTS.md`, `~/.codex/skills/`,
`~/.agents/skills/`, `<project>/.agents/skills/`, `~/.codex/plugins/` with
`.codex-plugin/plugin.json` (Claude-compat `.claude-plugin` fallback),
`~/.codex/rules/`, `~/.codex/hooks.json`. Consumed later by the scan MVP's
seed table; listed here because the dossier is the single per-harness fact
sheet (map D15).

**`~/.codex/auth.json` and `config.toml` are credential-bearing** — mode
0600 on this machine. Seed them as *paths to notice writes to*; never read
their contents into any tool output or store. (This dossier was written
without reading either: an attempt to print `config.toml` was correctly
refused, and nothing was lost — only the path is needed.)

## 7. Quirks & warnings

1. **`total_token_usage` is cumulative, and it is the ONLY correct reading**
   *(corrected 2026-08-25 by the T106 verifier)*. Each `token_count` row
   restates the session running total (monotonic in all 84 files). Codex
   also **restates whole rows**: `last_token_usage` repeats under an
   unchanged cumulative — sometimes with a *different* `last` value — so
   summing `last_token_usage` double-counts (wrong on 15/84 real sessions,
   overstating up to +72.9%). Correct reading: track the cumulative
   `total_token_usage` (per-model attribution via deltas at each row);
   oracle-exact 84/84 against `state_5.sqlite`. Never sum
   `total_token_usage` either — that overcounts by roughly the turn count.
2. **Filename timestamps are local time; row timestamps are UTC.** E.g.
   `rollout-2026-04-02T14-38-40-…` whose first row is `2026-04-02T18:40:02.919Z`
   — a 4-hour EDT skew, consistent across samples. Derive session start from
   row `timestamp`, never from the filename, and never sort files by name
   across a DST boundary.
3. **The second `session_meta` is the *parent's* id, not this session's.**
   6 of 84 files carry two `session_meta` rows; in 4 of them the second row's
   `payload.id` is a different UUID — the spawning thread's. The first
   `session_meta.payload.id` always equals the filename UUID. **Take the
   first, never the last.**
4. **`command -v codex` resolves to a user wrapper, not the binary.**
   `~/.local/bin/codex` is a Bourne-Again shell script that execs
   `/opt/homebrew/bin/codex` and shells out to a notifier on non-zero exit.
   `codesign` on the PATH entry yields nothing useful; registry exe
   resolution must follow the wrapper (and tolerate that an arbitrary user
   script can sit in front of any harness binary).
5. **The structured shell-error signal decayed across versions.**
   `exec_command_end` (with `exit_code` and `status`) appears 23 times total,
   all of them in files from cli 0.118.0 (19) and 0.125.0 (4) — and **zero
   times** in all 81 files on 0.140.0 through 0.149.0. Where it does appear,
   `status == "failed"` aligns exactly with `exit_code != 0` (5 of 23), so
   prefer `status` when present. Shell results in current versions arrive as
   flag-less `function_call_output`. Any error-count comparison across
   versions is apples-to-oranges.
6. **`function_call_output.output` is type-unstable**: a string in 5,245
   rows, a **list** in 73. Type-check before touching it (the adapter should
   not be reading its contents anyway — see quirk 12).
7. **A model id can be a full URI.** One observed id is
   `azureml://registries/azure-openai/models/gpt-5.3-codex/versions/2026-02-24`.
   Naive `startswith("gpt-")` matching misses it and mislabels the provider;
   pattern matching must be substring/suffix-aware, and `model_provider`
   preferred over patterns entirely (§4).
8. **Subagent sessions are separate files, unlike Claude Code's inline
   sidechains.** 37 of 84 threads are `thread_source = "subagent"`, each with
   its own rollout file and its own token accounting. Consequences: (a) no
   double-counting risk, but (b) a parent session's reported spend
   *excludes* its children, so per-session totals understate the real cost of
   a delegating run. Parent linkage is available from
   `session_meta.payload.source.subagent.thread_spawn.parent_thread_id`
   (a polymorphic field — a plain string `"cli"`/`"vscode"`, or a dict
   `{"subagent": "review"}`, or a nested `{"subagent": {"thread_spawn": {…}}}`;
   type-check it) and corroborated by `state_5.sqlite`'s
   `thread_spawn_edges` table (15 rows).
9. **`CODEX_HOME` relocates the entire territory.** `~/.codex` is a default,
   not a guarantee. Session globs and registry paths should honour the env
   var when set (it was unset on this machine).
10. **`patch_apply_end.changes` is a dict keyed by absolute file path** —
    arbitrary, machine-specific, user-identifying keys, each holding a
    `.content` blob. Never enumerate those keys into the store; the whole
    row is body-class (quirk 12).
11. **`state_5.sqlite`'s filename encodes a schema generation.** Sibling
    stores follow the same convention (`logs_2`, `goals_1`, `memories_1`,
    `queue_1`, `thread_history_1`). Never hardcode `state_5` — glob
    `state_*.sqlite` and pick the highest, or treat it as absent.
12. **Body-class fields, never copied (C6).** `session_meta.payload.base_instructions.text`;
    `event_msg`/`agent_message`, `event_msg`/`user_message`; `response_item`/`message`,
    `response_item`/`reasoning`; `exec_command_end.{stdout, stderr, aggregated_output, formatted_output}`;
    `patch_apply_end.changes.*.content`; `mcp_tool_call_end.invocation.arguments`;
    `history.jsonl.text`; and in the state DB `threads.{first_user_message, preview, title}`.
    The adapter reads only `session_meta` scalars, `turn_context.model`,
    `token_count.info`, timestamps, and the three error markers — everything
    else is skipped unread.
13. `turn_aborted` with `reason: "interrupted"` (14 rows) is a **user
    interruption, not an error** — do not count it. Exactly the precedent
    already set for Claude Code's `toolUseResult.interrupted`.
14. Row `type`/`payload.type` pairs are heterogeneous — 33 distinct
    combinations observed. The set is stable across cli 0.118.0 → 0.149.0
    (identical `session_meta`, `turn_context`, and `token_count.info` key
    sets in the oldest and newest files), so format drift is low risk for
    the fields the adapter actually reads.
15. Files are mode 0644 and append-only, so C8's byte-offset cursor applies
    cleanly. One observed file reaches 212 KB / thousands of rows.

## 8. Declarative entry draft (C1 — copy for the adapter)

```python
"codex": {
    "session_paths": ["~/.codex/sessions/*/*/*/rollout-*.jsonl"],  # honour $CODEX_HOME
    "session_format": "jsonl",
    "config_paths": [
        "~/.codex/config.toml",
        "~/.codex/hooks.json",
        "/etc/codex/config.toml",
    ],
    "registry": {
        "paths": ["~/.codex"],
        "exes": ["codex"],
        "signing_ids": ["codex"],  # observed 2026-08-25, team 2DC432GLL2
        "cache_paths": [
            "~/.codex/cache",
            "~/.codex/.tmp",
            "~/.codex/tmp",
            "~/.codex/log",
            "~/.codex/shell_snapshots",
            "~/.codex/thread-writer-locks",
            "~/.codex/models_cache.json",
            "~/.codex/cloud-config-bundle-cache.json",
        ],
    },
    "provider_families": {
        "gpt-": "openai",
        "o1": "openai",
        "o3": "openai",
        "o4": "openai",
        "codex-": "openai",
        "azureml://": "openai",
        "": "openai",  # fallback tier + `unknown model` flag
    },
    "tier": "ledger",
}
```

Code hook required (the JSONL shape genuinely diverges from Claude Code's):

- take the **first** `session_meta` for id / cwd / git / provider (trap 3);
- track the running `turn_context.payload.model` to attribute usage, and
  register every declared model even if no token row follows it — a
  superseded `azureml://` turn is a detection signal (trap 7);
- attribute **cumulative-delta** tokens from
  `token_count.info.total_token_usage` — never sum `last_token_usage`
  (restated rows double-count; trap 1 as corrected);
- count errors from `patch_apply_end.success == false` plus
  `mcp_tool_call_end` `Err`/`isError`, plus `exec_command_end.status ==
  "failed"` on pre-0.140 files, and report the signal as partial (§3);
- skip every body-class field in trap 12 unread.

Parse-test oracle: assert the adapter's per-session token total equals
`state_5.sqlite`'s `threads.tokens_used` for the same `rollout_path` — a
relationship that held on all 84 sessions here.

## 9. Sources

1. Live filesystem + binary, this machine, 2026-08-25: `codesign -dv` on the
   resolved cask binary; structural probe (JSON key names and types only,
   never message content) over **all 84** rollouts / 32,197 rows;
   `~/.codex` listing; read-only `sqlite3` schema + aggregate queries against
   `state_5`, `thread_history_1`, `logs_2`, `goals_1`, `memories_1`, `queue_1`;
   `models_cache.json`, `hooks.json`, `history.jsonl`, `version.json`,
   `session_index.jsonl` key dumps.
2. `wayfinder/harness-team/tickets/T101-roster-ranking.md:72,105,115-127` —
   roster rank 1, admission PASS, T106 pilot target, prior path confirmation.
3. `submodules/security-scanners/snyk-agent-scan/src/agent_scan/agents/codex.py:45-87,346-347`
   and `well_known_clients.py:97-100,187-190` — config/skill/plugin path
   tables, `CODEX_HOME`, `/etc/codex`, `~/.agents/skills`.
4. `submodules/OpenRouterTeam/docs/cookbook/coding-agents/codex-cli.mdx:37,155,167`
   — `~/.codex/config.toml` as the model-routing seam; OpenRouter slugs as
   legal codex model ids (the §4 warning).
5. `dossiers/claude-code.md` — exemplar format and the interrupted-is-not-an-error
   precedent (trap 13).

**Network note:** no external source is cited because this machine's egress
is proxy-intercepted — `https://api.openai.com/v1/models` returned `302`
where an unauthenticated call must return `401`, so any fetched body would
be the proxy's, not the vendor's. Every fact above is therefore local and
observed. The C7 rate table still needs vendor-cited prices gathered from an
un-intercepted network before the shared pricing module ships; this dossier
contributes only the `provider_families` mapping, which is all C7 asks of an
adapter.
