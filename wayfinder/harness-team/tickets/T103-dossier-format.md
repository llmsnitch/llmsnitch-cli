# T103 — Dossier format (prototype: claude-code as the worked example)

`labels: wayfinder:prototype`
`parent: ../map.md`
`blocked by: T102`
`blocks: T104`
`status: DONE (2026-08-24) — format proven by ../../dossiers/claude-code.md`

## Question

Design the **dossier** — the single per-harness fact sheet (map D15) that
feeds the adapter, the agent-registry entry, and (later, outside this map)
the scan MVP's seed table. Prototype it by writing the claude-code dossier
for real from the shipped code, so the format is proven against the one
harness fully known.

Must capture at least: trace/session file locations + format, hook system
(or absence), config paths, cost/pricing source, exe basenames + observed
signing ids, territory paths for the registry, admission-test verdict with
evidence. Decide where dossiers live in the repo and how the
dossier-researcher role fills one.

## Resolution

Resolved 2026-08-24 (prototype, HITL — user approved the format as-is).
Asset: `dossiers/claude-code.md` — the format prototype AND the real
claude-code dossier, populated from observed facts.

Format decisions:
- **Location**: `dossiers/<harness>.md` at repo root — operational inputs,
  not research notes (`docs/`), and they outlive team runs (`team/`).
- **Shape**: fixed 9 sections — fenced summary header (harness / tier /
  admission / dates / status), Identity & registry (C9), Ledger (C2),
  Signal-set mapping (C4) with per-signal confidence `high|medium`,
  Pricing families (C7), Live capture context, Config paths (scan-seed
  context per map D15), Quirks & warnings, copy-paste C1 declarative entry
  draft, Sources. Every fact carries evidence; machine-observed facts are
  dated.
- **Dossier → adapter is transcription, not interpretation**: the closing
  C1 dict is copied by the adapter-implementer verbatim.

Findings from writing it for real:
- **Observed signing identity for claude-code**: `com.anthropic.claude-code`,
  TeamIdentifier `Q6L2SF6YDW` (codesign on the 2.1.231 Homebrew binary) —
  resolves the notifier spec's open question for this harness.
- **Error-signal trap**: `toolUseResult.interrupted` is a user-interruption
  flag, not an error; real errors are `is_error: true` on `tool_result`
  content blocks in user-type rows. Dossier §7 warns adapters off it.
