# T101 — Union roster + popularity ranking

`labels: wayfinder:research`
`parent: ../map.md`
`blocked by: —`
`blocks: T106`
`status: CLAIMED (roster-researcher, 2026-08-24)`

## Question

Produce the ordered harness roster the team will work through: the union of
Ori's 8 (claude, codex, grok, hermes, opencode, pi, prime-agent, dsh) and the
docs cookbook's 8 (Claude Code, Claude Desktop, Codex CLI, Cursor, Hermes,
Junie, OpenClaw, OpenCode), deduped (~12–13 unique), ranked by popularity /
market share with **cited evidence** (GitHub stars/downloads, surveys, vendor
claims — name your sources), then presence-on-this-machine as tiebreaker
(map D05).

For each harness also record a provisional admission-test verdict where
cheaply knowable: does it write local trace/session files on disk (map D04)?
Known-cloud-only candidates are flagged for the map's Out of scope, not
silently dropped. Claude Code is rank-exempt (already supported); the
top-ranked *unsupported* harness becomes the pilot target for
[T106](T106-pilot-run.md).

Research agents MAY use the network (curl only, no WebFetch/WebSearch tools);
shipped code may not.

## Sources

- `submodules/OpenRouterTeam/docs/guides/ori/harness.mdx` and
  `cookbook/coding-agents/*.mdx` (in the feature worktree).
- snyk-agent-scan's discoverers + 36-row `CandidateClient` table (vendored,
  see map Notes) for local-trace hints.
- This machine: which harnesses are actually installed.

## Resolution

*(append here: ordered roster table — name, rank, evidence, admission
verdict, on-machine? — then mark status DONE)*
