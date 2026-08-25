# Dossier: claude-code

```
harness:    claude-code            # canonical name = actor bucket
tier:       live+ledger            # only harness with pre-existing live capture
admission:  PASS                   # local JSONL transcripts on disk (evidence §2)
dossier_date: 2026-08-24
observed_on:  this machine (macOS, Claude Code 2.1.231 via Homebrew cask)
status:     prototype              # T103 format prototype; also the real claude-code dossier
```

One dossier per harness: the single fact sheet that feeds the **adapter**
(contract C1 entry + code hook), the **agent registry** (C9), and — later,
outside this map — the scan MVP's seed table. Every fact carries its
evidence; facts observed on a live machine are dated. Contract:
`docs/harness-adapter-contract.md`.

## 1. Identity & registry (C9)

| Field | Value | Evidence |
|---|---|---|
| Territory paths | `~/.claude/` (global), `<project>/.claude/` (per-repo) | notifier-spec §Agent registry; observed |
| Exe basenames | `claude` | `command -v claude` → `/opt/homebrew/bin/claude` (observed 2026-08-24) |
| Signing identity | Identifier `com.anthropic.claude-code`, TeamIdentifier `Q6L2SF6YDW`, Mach-O arm64, hardened runtime | **OBSERVED** 2026-08-24: `codesign -dv /opt/homebrew/Caskroom/claude-code/2.1.231/claude`. Resolves the notifier-spec open question for this harness |
| Cache paths (benign-writer suppression) | `~/.claude/plugins/cache/**` | notifier-spec built-in `cache_paths`; the grounding noise case in `AGENTS.md` |
| Self-run sentinel | env `CLAUDECODE=1` set inside sessions | `llmsnitch/setup_cmd.py:37-41` (context only — the contract has no installer seam) |

## 2. Ledger (C2) — where sessions live

| Fact | Value |
|---|---|
| Session files | `~/.claude/projects/<cwd-slug>/<session-uuid>.jsonl` |
| `<cwd-slug>` | absolute cwd with `/` → `-` (e.g. `-Users-llnsnitch-Documents`) |
| Format | JSONL, one object per line, append-only during a session |
| Growth | new file per session; observed 44 transcripts across 15 project slugs |
| Compression / rotation | none observed |
| Adjacent | `~/.claude/history.jsonl` (prompt history — NOT ingested; message-body class, contract C6) |

Admission evidence: files present and readable on this machine, newest
transcript same-day. Plain stdlib `json` per line; malformed lines skipped
(fail-soft rule).

## 3. Signal-set mapping (C4)

How each required signal is derived from the ledger format. Confidence:
**high** = observed in current transcripts; **medium** = observed but
shape may vary across versions.

| Signal | Where | Confidence |
|---|---|---|
| model ids | `message.model` on `type:"assistant"` rows | high |
| tokens per model | `message.usage.{input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens}` on assistant rows — same fields `llmsnitch/transcript.py:33-60` already sums | high |
| session start/end | min/max `timestamp` (ISO-8601) across rows | high |
| session cwd/project | `cwd` key on rows; corroborated by the directory slug | high |
| error count | count of `tool_result` content blocks with `is_error: true` inside `type:"user"` rows (37 observed in 6-transcript sample). `toolUseResult.interrupted` is a user-interruption marker, NOT an error — do not count it | medium |

Native session id: the transcript filename UUID (= `sessionId` key on
rows). Store id per C5: `claude-code-<uuid>`.

## 4. Pricing / provider families (C7)

| Model-id pattern | Provider family |
|---|---|
| `*opus*`, `*sonnet*`, `*haiku*` | `anthropic` (rates: existing table, `llmsnitch/transcript.py:14-22`) |
| anything else (e.g. `claude-fable-5`, observed live) | `anthropic` fallback tier + `unknown model` flag — first-class signal per contract |

Note: usage objects now carry fields beyond the four llmsnitch reads
(`cache_creation{}`, `service_tier`, `server_tool_use`, …) — ignored, not
errors.

## 5. Live capture (context — outside contract)

Hook path stays as shipped: `PreToolUse`/`PostToolUse`/`Stop` events via
`~/.claude/settings.json` hooks block (`llmsnitch/hook.py`,
`llmsnitch/setup_cmd.py`). Standing correctness check (contract C2): diff
this harness's ledger-adapter output against its hook output.

## 6. Config paths (scan-seed context, not ingested)

`~/.claude/settings.json`, `settings.local.json`, `~/.claude.json`,
`~/.claude/hooks/`, `~/.claude/agents/`, `~/.claude/skills/`,
`<project>/.claude/**`. Consumed later by the scan MVP's seed table; listed
here because the dossier is the single per-harness fact sheet (map D15).

## 7. Quirks & warnings

- Transcript rows are heterogeneous (`assistant`, `user`, `system`,
  `attachment`, `file-history-*`, `queue-operation`, …) — the adapter
  reads only assistant usage rows, user tool_result error blocks, and
  timestamps; everything else skipped unread (C6: message bodies never
  copied).
- Subagent transcripts (`isSidechain: true` rows) live in the same file —
  token counts include them; that is correct (they are real spend).
- One session file can exceed thousands of lines; the ingest cursor's byte
  offset (C8) applies cleanly since files are append-only.

## 8. Declarative entry draft (C1 — copy for the adapter)

```python
"claude-code": {
    "session_paths": ["~/.claude/projects/*/*.jsonl"],
    "session_format": "jsonl",
    "config_paths": ["~/.claude/settings.json", "~/.claude.json"],
    "registry": {
        "paths": ["~/.claude"],
        "exes": ["claude"],
        "signing_ids": ["com.anthropic.claude-code"],  # observed 2026-08-24, team Q6L2SF6YDW
        "cache_paths": ["~/.claude/plugins/cache"],
    },
    "provider_families": {"": "anthropic"},  # everything → anthropic
    "tier": "live+ledger",
}
```

## 9. Sources

1. Live filesystem + binary, this machine, 2026-08-24 (codesign, transcript
   structure probe over 6 recent files, ~/.claude listing).
2. `llmsnitch/hook.py`, `llmsnitch/transcript.py`, `llmsnitch/setup_cmd.py`
   — shipped Claude support (the seams the contract generalizes).
3. `docs/notifier-spec.md` §Agent registry — territory/cache-path
   built-ins.
4. snyk-agent-scan `src/agent_scan/agents/claude_code.py:51-104` —
   corroborates scope/skill paths (§6).
