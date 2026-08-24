# T101 — Union roster + popularity ranking

`labels: wayfinder:research`
`parent: ../map.md`
`blocked by: —`
`blocks: T106`
`status: DONE (2026-08-24)`

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

*(roster-researcher, 2026-08-24. All figures fetched 2026-08-24 unless noted.)*

### Union and dedupe

Ori's 8 ∪ cookbook's 8 = **12 unique harnesses**. Four appear on both lists
(Claude Code, Codex CLI, Hermes, OpenCode); Ori contributes four uniques (Grok
Build, Pi, Prime Agent, DeepSeek Harness) and the cookbook four (Claude
Desktop, Cursor, Junie, OpenClaw). The ticket's "~12–13" upper bound counted
Ori's `claude` and the cookbook's "Claude Code" as possibly distinct; they are
the same CLI (`ori claude` starts the real Claude Code binary on `PATH` —
`harness.mdx:54`), so the union is 12, not 13.

### Ranking method

Two metrics, because no single one covers all 12:

- **npm weekly downloads** (`api.npmjs.org/downloads/point/last-week/<pkg>`) —
  the best available proxy for *installs actually happening*, used as the
  primary metric for every npm-distributed CLI.
- **GitHub stars** (`api.github.com/repos/<owner>/<repo>`) — the primary metric
  for open-source harnesses that are not npm-distributed (Hermes, DeepSeek
  Harness, Prime Agent), and a cross-check elsewhere.

Four harnesses are closed-source with no public install metric (Cursor, Claude
Desktop, Junie's IDE surface, Grok Build's binary). Their ranks lean on vendor
claims and are marked **low confidence** — re-sort them freely if better
evidence appears.

### Ordered roster

| Harness | Rank | Popularity evidence (source, 2026-08-24) | Admission verdict (map D04) — evidence | On this machine? |
|---|---|---|---|---|
| **Claude Code** | — (exempt) | 22,614,173 npm/wk (`@anthropic-ai/claude-code`); 142,874 stars (`anthropics/claude-code`) | **PASS** — `~/.claude/projects/<slug>/<uuid>.jsonl`, verified on disk here; already the supported harness | **Yes** — `/opt/homebrew/bin/claude`, `~/.claude` |
| **Codex CLI** | **1** | 16,110,271 npm/wk (`@openai/codex`); 116,970 stars, Apache-2.0 (`openai/codex`) | **PASS (verified)** — `~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl` plus `~/.codex/session_index.jsonl` and `~/.codex/history.jsonl`, all confirmed present on this machine. Plain JSONL, no compression. | **Yes** — `~/.local/bin/codex`, `~/.codex` populated |
| **Cursor** | 2 *(low conf.)* | No public download metric. Vendor: "Trusted by over half of the Fortune 500" (cursor.com homepage). `cursor/cursor` (33,168 stars) is an issue tracker only, last push 2026-05-12 — not the product. | **PROBABLE PASS — needs probe.** VSCode-fork layout: snyk's `vscode/base.py:559-585` walks `<userdata>/User/workspaceStorage/<hash>/`, and Cursor is one of only two forks snyk marks "verified on disk" (`base.py:269`). Chat transcripts live in `state.vscdb` (SQLite) with an undocumented proprietary schema — readable via stdlib `sqlite3`, but the schema must be observed, never guessed. | No |
| **OpenClaw** | 3 | 2,558,339 npm/wk (`openclaw`); **387,408 stars** — the highest of any harness on the roster (`openclaw/openclaw`) | **PASS** — `src/config/sessions/paths.ts` resolves `<stateDir>/agents/<id>/sessions/`; docs show `~/.openclaw/agents/main/sessions/sessions.json` and `~/.openclaw/agents/main/agent/openclaw-agent.sqlite` (`docs/cli/sessions.md:71,268`). JSONL transcripts too (`src/transcripts/store-export-jsonl.ts`). Snyk lists `~/.clawdbot` as the legacy dir. | No |
| **OpenCode** | 4 | 2,499,036 npm/wk (`opencode-ai`); 201,008 stars, MIT (`anomalyco/opencode`) | **PASS** — projects and sessions in SQLite under `~/.local/share/opencode/opencode*.db` (Drizzle `project` table, `worktree` column); filename varies by install channel and `$OPENCODE_DB` can relocate it (snyk `agents/opencode.py:99-130`). Config `~/.config/opencode` or `~/.opencode`. | No |
| **Hermes** | 5 | 235,732 stars, MIT (`NousResearch/hermes-agent`). Not on npm — installed by curl/PowerShell one-liner, so no download metric exists. | **PASS** — `docs/session-lifecycle.md:144-203`: `SessionStore` persists to `sessions.json` with **SQLite (`SessionDB`) as the canonical transcript store**; JSONL is an explicit degradation fallback. Config at `~/.hermes` (`~/.hermes/.env`, `config.yaml` per cookbook `hermes-integration.mdx:65-77`); `%LOCALAPPDATA%\hermes` on native Windows. | No |
| **DeepSeek Harness (dsh)** | 6 | 191,792 stars, MIT (`deepseek-ai/deepseek-harness`). Not npm-distributed. | **PASS — with a real caveat.** Sessions are JSONL, but **zstd-compressed by default**: `.jsonl.zstd`, concatenated independent frames, `compression` omitted resolves to `'zstd'` (`.agents/notes/implemented/architecture/2026-07-19-zstandard-jsonl-session-logs.md:17-33`). Python 3.9's stdlib has **no zstd decoder** (`compression.zstd` only arrives in 3.14), so this collides with the map's stdlib-only, zero-dep rule. Raw `.jsonl` exists only when a deployment sets `compression: 'none'`. **Flag for T102.** | No |
| **Pi** | 7 | 96,581 stars, MIT (`earendil-works/pi` — `badlogic/pi-mono` now redirects here). CLI `@mariozechner/pi` is only 621 npm/wk; the 817,426/wk on `@mariozechner/pi-ai` is the SDK library, not the harness, and should not be read as harness adoption. | **PASS** — "Sessions auto-save to `~/.pi/agent/sessions/`, organized by working directory. Each session is a JSONL file with a tree structure" (`packages/coding-agent/docs/sessions.md:7`). Tree-shaped: entries carry `id`/`parentId` and branch, so it is not a flat append log. | No |
| **Grok Build** | 8 *(low conf.)* | 54,335 npm/wk (`@xai-official/grok`, "Bring Grok into your terminal"). Closed source — no repo, no stars. | **PROBABLE PASS — needs probe.** The npm package is a 4-file launcher whose postinstall drops a native binary into `~/.grok/bin` and completions into `~/.grok/completions`; nothing else is inspectable from the tarball. Third-party corroboration that local sessions exist: `RongleCat/grok-app` (1,079 stars) advertises "CLI session import" and "non-destructive shared mode (protects existing `~/.grok` configurations)". Path and format still unverified — **probe a live install before committing to an adapter.** | No |
| **Claude Desktop** | 9 *(low conf.)* | No public metric (closed-source first-party app). Rank is a placeholder; see verdict — position barely matters. | **SPLIT VERDICT.** Its *chat* surface is **cloud-only → out of scope (D04/D13)**: snyk's `claude_desktop.py:31-45` documents that Skills are stored per-account in the cloud with no local path, Connectors are OAuth/cloud with secrets in Keychain, and the extension dir is undocumented. Only `claude_desktop_config.json` is on disk, and that is config, not trace. **But** its embedded Code tab does write locally — `~/Library/Application Support/Claude/claude-code-sessions/` exists on this machine with one session dir. That local half is Claude-Code-shaped, i.e. already-covered territory rather than a new adapter. | **Partly** — `/Applications/Claude.app`, `~/Library/Application Support/Claude` |
| **Prime Agent** | 10 | 18,139 stars, MIT (`PrimeIntellect-ai/prime-agent`). Not npm-distributed. | **PASS** — "Sessions auto-save to `~/.prime/agent/sessions/`. Each session is a JSONL file with a tree structure" (`packages/coding-agent/docs/sessions.md:7`). **Note:** Prime Agent is Pi-derived — identical `packages/coding-agent/` tree and byte-identical session docs modulo the name and dir. One adapter should cover both; do Pi first and Prime Agent nearly falls out. | No |
| **Junie** | 11 *(low conf.)* | 1,628 npm/wk (`@jetbrains/junie`) + 215 (`@jetbrains/junie-cli`) — the lowest measured install volume on the roster. `JetBrains/junie` (398 stars) is a docs/issues repo, not source. Caveat: the IDE-plugin surface ships inside JetBrains IDEs and is invisible to npm, so true reach is understated. | **UNKNOWN — needs probe.** Closed source; installed by `curl https://junie.jetbrains.com/install.sh | bash` or `brew install junie` (cookbook `junie.mdx:41-55`). Neither the cookbook nor the JetBrains repo documents a session path. No evidence it is cloud-only, so do not out-scope it — probe a live install. | No |

### Cloud-only / out-of-scope flags

Only one harness trips the D04 exclusion, and only partially: **Claude Desktop's
chat surface** (cloud-stored Skills, OAuth Connectors, Keychain secrets, no
documented local transcript path). Its Code-tab sessions *are* local, so the
right map entry is "chat surface out of scope, Code tab already covered by
Claude Code" — not a blanket exclusion. The other 11 are local-first CLIs or
desktop apps that keep state under a home directory.

Three verdicts are **needs-probe**, not fails: Cursor (undocumented SQLite
schema), Grok Build (closed binary), Junie (closed binary). None should be
out-scoped on today's evidence.

One finding deserves T102's attention independent of the ranking: **DeepSeek
Harness defaults to zstd-compressed session logs**, which no stdlib Python 3.9
can read. That is an adapter-contract problem (a "can this harness be ingested
at all under zero-dep?" tier question), not a popularity problem.

### Presence on this machine (tiebreaker, map D05)

Only **three** roster harnesses are installed: Claude Code
(`/opt/homebrew/bin/claude`), Codex CLI (`~/.local/bin/codex`, with a populated
`~/.codex/sessions/` tree), and Claude Desktop (`/Applications/Claude.app`).
Also present but off-roster: Gemini CLI (`~/.gemini`), VS Code, Warp. Absent:
`~/.cursor`, `~/.opencode`, `~/.config/opencode`, `~/.local/share/opencode`,
`~/.openclaw`, `~/.hermes`, `~/.pi`, `~/.prime`, `~/.grok`, `~/.junie`. The
tiebreaker never had to fire — the popularity ranking and the on-machine
evidence point at the same harness.

### Pilot recommendation

**Codex CLI is the pilot target for [T106](T106-pilot-run.md)**, and it is not a
close call. It is the top-ranked unsupported harness by the strongest metric
available (16.1M npm installs/week, second only to Claude Code itself), it is
the only unsupported harness actually installed on this machine — so the pilot
can be verified against real session data today instead of a synthetic fixture
— and its trace format is the closest possible analogue to the one llmsnitch
already parses: plain append-only JSONL, one file per session, no compression,
under a stable `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` layout with a
`session_index.jsonl` companion. That similarity is the point: the pilot's job
is to prove the *team* works and to force the Claude-specific seams
(`transcript.py`, `hook.py`, `gate.py`) into a real harness abstraction, so the
first run should stress the team's process rather than an exotic file format.
Codex also has documented hook support (`~/.codex/hooks.json` exists on this
machine), which gives the adapter a plausible route to hot-path parity rather
than transcript-only ingestion — the exact question T102 has open. The harder
formats (OpenCode's channel-varying SQLite, DeepSeek's zstd frames, Cursor's
undocumented `state.vscdb`) are better second and third runs, once the pipeline
has proven itself.

### Sources

All fetched 2026-08-24 via `curl`/`gh api` (no WebFetch/WebSearch).

**Local primary sources**
1. `submodules/OpenRouterTeam/docs/guides/ori/harness.mdx` — Ori's 8, lines 41-54, 141.
2. `submodules/OpenRouterTeam/docs/cookbook/coding-agents/{claude-desktop,codex-cli,cursor,hermes,junie,openclaw,opencode}-integration.mdx` — cookbook's 8 and config paths.
3. snyk-agent-scan, at `submodule/security-scanners/snyk-agent-scan/` in the **main checkout** (not vendored in this worktree): `src/agent_scan/well_known_clients.py` (per-OS `CandidateClient` rows) and `src/agent_scan/agents/{claude_code,claude_desktop,codex,opencode}.py` + `agents/vscode/base.py`.
4. This machine: `~/.claude`, `~/.codex`, `~/Library/Application Support/Claude`, `command -v` sweep, `/Applications`.

**Network primary sources**
5. GitHub REST `api.github.com/repos/{...}` — star/fork/license/pushed_at for `anthropics/claude-code`, `openai/codex`, `anomalyco/opencode`, `NousResearch/hermes-agent`, `openclaw/openclaw`, `deepseek-ai/deepseek-harness`, `earendil-works/pi`, `PrimeIntellect-ai/prime-agent`, `cursor/cursor`, `JetBrains/junie`.
6. npm registry `api.npmjs.org/downloads/point/last-week/{...}` — `@anthropic-ai/claude-code`, `@openai/codex`, `opencode-ai`, `openclaw`, `@xai-official/grok`, `@jetbrains/junie`, `@jetbrains/junie-cli`, `@mariozechner/pi`, `@mariozechner/pi-ai`.
7. GitHub Contents API — `earendil-works/pi:packages/coding-agent/docs/sessions.md`, `PrimeIntellect-ai/prime-agent:packages/coding-agent/docs/sessions.md`, `openclaw/openclaw:{docs/cli/sessions.md,src/config/sessions/paths.ts}`, `NousResearch/hermes-agent:docs/session-lifecycle.md`, `deepseek-ai/deepseek-harness:.agents/notes/implemented/architecture/2026-07-19-zstandard-jsonl-session-logs.md`.
8. npm tarball `@xai-official/grok@1.0.5` — unpacked and grepped for on-disk paths (yielded only `~/.grok/bin`, `~/.grok/completions`).
9. `cursor.com` homepage — "Trusted by over half of the Fortune 500".
10. npm registry search API — resolved "Grok Build" to `@xai-official/grok` and "Junie" to `@jetbrains/junie`, neither of which is named in the cookbook.

### Caveats for whoever reads this next

- **Ticket path in the T101 handoff was wrong.** It pointed at
  `~/Repos/llmsnitch/wayfinder/harness-team/`, which does not exist; the
  harness-team wayfinder lives in the **worktree** at
  `~/.supacode/repos/llmsnitch/feature/installation-mac/wayfinder/harness-team/`.
  The main checkout's `wayfinder/` is the older notifier map (T001/T002). Both
  the claim and this resolution were written to the worktree copy; the main
  checkout was not modified.
- **Rank confidence is uneven.** Ranks 1, 3-8, 10-11 rest on measured numbers.
  Ranks 2 and 9 (Cursor, Claude Desktop) rest on vendor claims because no
  install metric is public for either — treat them as placed, not measured.
- **Stars and downloads measure different things** and the roster shows it
  starkly: OpenClaw leads on stars (387k) while Codex leads on installs by
  6.3x. Downloads were weighted higher deliberately; a star-weighted ranking
  would promote OpenClaw, Hermes, and DeepSeek Harness above Cursor.
- Every path above is **cited, not guessed**. Grok Build, Junie, and Cursor
  have no citable session path yet — that is why they are marked needs-probe
  rather than assigned one.
