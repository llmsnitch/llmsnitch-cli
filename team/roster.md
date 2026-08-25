# Harness Roster

Queue for team runs. Source: wayfinder ticket
[T101](../wayfinder/harness-team/tickets/T101-roster-ranking.md) (full
evidence and citations live there — this table is the working state, not
the argument). Status: `pending` | `in-run` | `done` | `deferred` |
`needs-probe` | `out-of-scope`.

| Rank | Harness | Tier | Status | Derived-of | Notes |
|---|---|---|---|---|---|
| — | claude-code | live+ledger | done (live); ledger adapter pending | — | rank-exempt; dossier exists; ledger adapter is a future run (contract C2 diff-check) |
| 1 | codex | ledger | done | — | **pilot** (T106) complete 2026-08-25; oracle-exact 84/84 vs state_5.sqlite; run journal `runs/codex/journal.md` |
| 2 | cursor | — | needs-probe | — | undocumented `state.vscdb` schema; probe before ticketing a run |
| 3 | openclaw | ledger | pending | — | `~/.openclaw/agents/<id>/sessions/` |
| 4 | opencode | ledger | pending | — | SQLite `~/.local/share/opencode/opencode*.db` |
| 5 | hermes | ledger | pending | — | SQLite SessionDB + sessions.json |
| 6 | deepseek-harness | deferred | deferred | — | `.jsonl.zstd`; waits for stdlib zstd (Python 3.14) — contract C3 |
| 7 | pi | ledger | pending | — | `~/.pi/agent/sessions/` |
| 8 | grok-build | — | needs-probe | — | closed binary; only `~/.grok/bin` inspectable |
| 9 | claude-desktop | — | out-of-scope (chat) | — | chat surface cloud-only; Code tab covered by claude-code (map Out of scope) |
| 10 | prime-agent | ledger | pending | pi | Pi-derived; delta-dossier + registry entry only |
| 11 | junie | — | needs-probe | — | closed binary, no documented session path |

`needs-probe` rows need a probe result (does it write local sessions, and
readably?) before they become `pending` or `out-of-scope`; a probe is a
dossier-researcher errand, not a full run.
