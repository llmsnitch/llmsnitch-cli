# Harness Team — Wayfinder Map

`label: wayfinder:map`

## Destination

A **committed, in-repo agentic implementation team** — folders/files under
`team/` on branch `feature/installation-mac` (worktree
`~/.supacode/repos/llmsnitch/feature/installation-mac`) — that can repeatedly
take one harness from the roster through
dossier → adapter → agent-registry entry → tests → doctrine audit → local
commit, delivering parity with today's Claude Code support (session tracing,
cost, health, redaction, notification, dashboards-as-defined). The map closes
when the team exists in the repo **and has proven itself** by taking the
top-roster harness end-to-end
([T106](tickets/T106-pilot-run.md)'s done criteria).

The team IS the destination — per-harness adapter work beyond the pilot lives
with the team, not on this map.

## Notes

- **Tracker location (standing rule for all initiatives)**: wayfinder maps
  and tickets live in `wayfinder/` inside the feature worktree
  (`~/.supacode/repos/llmsnitch/feature/installation-mac`) and are
  **committed to the feature branch**. Never use the main-branch checkout at
  `~/Repos/llmsnitch/` as a working space.
- **Skills to invoke when working this map**: `mattpocock-skills:grilling`,
  `mattpocock-skills:domain-modeling`, `mattpocock-skills:writing-for-agents`
  (agent definitions are agent-consumed writing),
  `mattpocock-skills:prototype`, `mattpocock-skills:research`.
- **Plan-vs-do override**: T105 (author the team) and T106 (pilot run) carry
  execution — the destination is a working artifact, not a spec.
- **Repo policy**: llmsnitch stays local-only. No remote, no push, no GitHub
  (memory `llmsnitch-git-local-only`). Never `rm` — always `trash`.
- **Grounding doctrine**: `AGENTS.md` three gates (Decision / Actor /
  Novelty); zero network code (test-enforced grep guard in
  `tests/test_llmsnitch.py`), stdlib-only Python 3.9+, flat files 0600/0700,
  hot path never blocks the agent, redact at capture.
- **Claude-specific seams to generalize** (from repo recon): hook payload
  schema (`llmsnitch/hook.py:55-85`), transcript parsing + pricing table
  (`llmsnitch/transcript.py:14-60`), gate (`llmsnitch/gate.py`), installer
  (`llmsnitch/setup_cmd.py`). No harness abstraction exists in shipped code.
- **Primary sources, all local**:
  - `submodules/OpenRouterTeam/docs` — `guides/ori/harness.mdx` (Ori's 8),
    `cookbook/coding-agents/*.mdx` (cookbook's 8, config-path hints).
  - snyk-agent-scan (vendored under the security-scanners submodules) —
    36-row per-OS `CandidateClient` well-known-path table + 9 per-agent
    discoverers (`well_known_clients.py`, `agents/`).
  - `~/Repos/agent-sh` — AgentSys patterns to borrow: `next-task/agents/*.md`
    file-based agent definitions, `audit-project/commands/` spawn logic.
  - `docs/notifier-spec.md` §Agent registry; `docs/research/scanner-survey-mvp.md`.
- **Dashboards are already defined**: terminal summaries + notifier
  digest/TUI pane — no HTML, no server
  (`docs/research/scanner-survey-mvp.md` §2.6).

## Decisions so far

*(15 decisions across 3 grilling rounds, 2026-08-24 — pre-map; closed
tickets append below as they resolve)*

### Scope + shape
- **D01** Destination = the team assembly itself, committed as repo files
  (R1 Q1=c).
- **D02** "Supported" = parity with today's Claude support — session tracing,
  cost, health, redaction, notification — plus dashboards as defined in the
  scan-survey verdict (R1 Q2; R2 Q11 context).
- **D06** Team lives in a standalone `team/` directory on
  `feature/installation-mac` (R1 Q6 + R2 Q13=b).
- **D07** AgentSys ship/PR phases replaced with local commits; everything
  stays local-only (R1).

### Roster
- **D03** OpenRouterTeam artifacts mined as roster + config-path hints, not
  ground truth; every harness gets its own local-trace research regardless
  (R1 Q3=b).
- **D04** Zero-network/zero-dep absolute. **Admission test**: a harness is
  adapter-eligible iff it writes local trace/session files on disk;
  cloud-only harnesses → companion browser extension (out of scope) (R1 Q4).
- **D05** Roster priority: popularity/market share first, then
  presence-on-this-machine (R1 Q5=b,a).
- **D08** Roster = union of Ori's 8 (claude, codex, grok, hermes, opencode,
  pi, prime-agent, dsh) and the docs cookbook's 8 (Claude Code, Claude
  Desktop, Codex CLI, Cursor, Hermes, Junie, OpenClaw, OpenCode), deduped,
  triaged by the admission test (R2 Q7=c).

### Team
- **D09** AgentSys borrowed, not installed: self-contained in-repo team
  modeled on next-task's file-based agent-definition patterns; no marketplace
  dependency (R2 Q8=b).
- **D10** Topology = purpose-built harness pipeline: roster-triage →
  dossier-researcher → adapter-implementer → test-verifier → doctrine-auditor
  → local-commit gate. One harness per run, phase-gated, resumable (R2 Q9=b).
- **D11** The harness-adapter contract is defined on this map, before team
  assembly — team prompts reference it (R2 Q10=a).

### Coupling
- **D14** Adapter and agent-registry entry are coupled: "supported" requires
  both, and one dossier feeds both (R3 Q14).
- **D15** The dossier is the single per-harness fact sheet; the scan MVP's
  seed table consumes it later without this map owning scan work (R3 Q15).

### Fog + scope markers
- **D12** Dashboards-per-harness = in-scope fog (R2 Q11=a).
- **D13** Browser extension = out of scope (R2 Q12).

### Closed tickets
- [T101 — Union roster + popularity ranking](tickets/T101-roster-ranking.md)
  — union = 12 (Ori's "claude" ≡ cookbook's "Claude Code"). Order: Codex CLI,
  Cursor, OpenClaw, OpenCode, Hermes, DeepSeek Harness, Pi, Grok Build,
  Claude Desktop, Prime Agent, Junie. **Pilot = Codex CLI** (top installs,
  only unsupported harness on this machine, plain JSONL sessions +
  `~/.codex/hooks.json`). 7 admission PASS, 3 needs-probe (Cursor, Grok
  Build, Junie), Claude Desktop split (see Out of scope). Feeds T102: zstd
  tier question; feeds T104: Pi/Prime Agent one-adapter collapse.

## Not yet specified

- **Per-harness dashboard parity** — extending the already-decided reporting
  surfaces (terminal summary, digest, TUI pane) to every supported harness.
  Sharpens after the adapter contract and first non-Claude adapters exist.
- **Support tiers for hook-less harnesses** — some union harnesses likely
  have no hook system; whether transcript-only ingestion counts as parity or
  a documented tier sharpens inside the adapter-contract grilling
  ([T102](tickets/T102-adapter-contract.md)).
- **Per-provider offline pricing** — non-Anthropic models need their own
  zero-network pricing tables and unknown-model fallbacks; shape emerges from
  T102/T103.
- **Signing-id observation procedure** — registry entries for new harnesses
  need observed (never guessed) signing ids per the notifier spec's open
  question; becomes per-harness work during team runs.

## Out of scope

- **Companion browser extension** for cloud-only harnesses — network by
  nature, its own effort (D13).
- **`llmsnitch scan` MVP** — own workstream per
  `docs/research/scanner-survey-mvp.md`; consumes dossiers, owns no map work
  (D15).
- **Any OpenRouter runtime integration** — OpenRouterTeam artifacts are
  design-time reference only; no network code ever ships (D03/D04).
- **Installing AgentSys marketplace plugins** — patterns are borrowed from
  the local clone instead (D09).
- **Cloud-only harnesses** failing the admission test — recorded per-harness
  in the roster ticket's resolution as they're identified (D04).
- **Claude Desktop's chat surface** — cloud-only (per T101, split verdict);
  its embedded Code tab writes locally but is already covered by the Claude
  Code adapter.
