# T401 — Clear the wrapper snakes

`label: wayfinder:ticket` · map: [rd-triage](../map.md) · status: CLOSED (2026-08-27)

## What was cleared

- `bin/agent-flick`, `bin/session-shed` — wrappers around upstream
  `agent-strace` / `agenttrace`, neither installed on this machine; nothing
  schedules them (no cron, no LaunchAgent).
- `fs_coil/bridge.py` — imported only by the two wrappers.
- `fs_coil/notify.py` `_SURFACE_SECTION` rows + glyph comment.
- `CONTEXT.md` Surface definition (dated retirement note).
- `docs/notifier-spec.md` — 7 targeted dated edits: surface table,
  event-sources para, decision-chain step 2, `threshold_breach` category row
  (reserved, not deleted), config table + example, T006 retirement note.
- `tests/test_notify.py` — surface label `session-shed` → `gate` (3 calls;
  the label is free-form, tests exercise category mechanics).

## Live-system note (inherited by track B)

`/usr/local/bin/{fs-coil,session-shed,agent-flick}` and
`/usr/local/share/llmsnitch/` remain installed and untouched — that tree is
track B's territory. The vendored T003 baseline survives in git history
(pre-`d69e02f` ancestors) if the migration ever needs the byte-identical
reference. The running `com.slav-it.fs-coil` light agent is unaffected.
