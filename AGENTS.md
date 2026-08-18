# AGENTS.md

Read `README.md` first — the design constraints there (no network code, stdlib
only, flat files, hot path never blocks) are non-negotiable and test-enforced.

## Notifications: actionable, or silent

Every user-facing alert this project ships (Notification Center, gate output,
any future watcher) must pass the **actionability test** before it fires:

1. **Decision** — the notification names what the user should do right now:
   allow, investigate, revoke, kill. If the honest answer is "nothing",
   stay silent.
2. **Actor** — name who did it (process, agent session), not just the path
   touched. A path without an actor is a question, not an answer.
3. **Novelty** — a recurring known-benign pattern gets suppressed or rolled
   into a daily digest, never paged one event at a time.

Grounding case (2026-08-18): the fs-coil watcher paged five times in one day
for Claude Code's own plugin installer writing
`~/.claude/plugins/cache/temp_git_*/.github/workflows/…` — zero action
possible, pure noise — while the day's only real signal (the `az` CLI reading
the Azure DevOps PAT from keychain and writing `~/.azure/msal_token_cache.json`)
produced no notification at all. Build for the second class; silence the first.

Corollary for deny-list design: a pattern match alone is not notification-worthy.
Match × unexpected-actor × first-time-seen is.
