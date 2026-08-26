# Plan 003: Parse skill frontmatter to its closing fence, not a 60-line window

> **Executor instructions**: Follow this plan step by step, run every
> verification, honor STOP conditions, update `plans/README.md` when done.
>
> **Drift check (run first)**: `git diff --stat a7a83bb..HEAD -- llmsnitch/scan.py tests/test_llmsnitch.py`
> Mismatch with "Current state" excerpts = STOP.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `a7a83bb`, 2026-08-26

## Why this matters

`skill_undeclared_bash` (a hygiene rule: SKILL.md whose scripts run bash
while `allowed-tools:` doesn't declare it) reads frontmatter through
`_frontmatter_allowed_tools`, which scans only `lines[1:60]`. A skill with
frontmatter longer than 60 lines — or an adversary padding it — silently
evades the check. Low severity (the rule never pages), but the gap is
evadable by construction, which defeats the rule's purpose.

## Current state

- `llmsnitch/scan.py:199-210` (`_frontmatter_allowed_tools`):

  ```python
  lines = text.splitlines()
  if not lines or lines[0].strip() != "---":
      return None
  for line in lines[1:60]:
      if line.strip() == "---":
          return None
      if line.startswith("allowed-tools:"):
          return line.split(":", 1)[1].strip()
  return None
  ```

  Two behaviors to preserve: returns `None` when there is no frontmatter
  fence at line 0, and returns `None` when the key is absent (caller at
  `scan.py:230-235` treats `None` as "no check possible" and skips the
  rule — that stays).
- Convention: hand parser on purpose — do NOT introduce a YAML library
  (stdlib-only is test-enforced; and `yaml` isn't stdlib).

## Commands you will need

| Purpose | Command | Expected |
|---------|---------|----------|
| Tests | `python3 tests/test_llmsnitch.py` | all pass, +1 new |

## Scope

**In scope**: `llmsnitch/scan.py` (`_frontmatter_allowed_tools` only),
`tests/test_llmsnitch.py` (one test).
**Out of scope**: parsing any other frontmatter key; multi-line YAML
values (a list-form `allowed-tools:` block is a known ceiling — keep it).

## Git workflow

Current branch `research/scanner-survey-mvp`; local-only (no remote/push).
One commit, `scan: <summary>`, `Co-Authored-By: Claude <noreply@anthropic.com>`.

## Steps

### Step 1: Failing test

Add to `tests/test_llmsnitch.py` (near `test_scan_skill_manifest_rules`):
a SKILL.md whose frontmatter has ~70 filler lines (`x{i}: y`) before
`allowed-tools: Read`, then the closing `---`, then a ```` ```bash ````
fence in the body. Scan it; assert `skill_undeclared_bash` IS in the
finding rules.

**Verify**: test FAILS (rule missing) before the fix.

### Step 2: Parse to the fence with a byte cap

Replace the `lines[1:60]` window: iterate until the closing `---` fence,
bounded by a generous cap that is about resource use, not evasion — e.g.
stop after 400 lines or 32 KB of frontmatter, whichever first, and update
the docstring to name the cap. Preserve both `None` behaviors above.

**Verify**: `python3 tests/test_llmsnitch.py` → all pass including the new
test and the existing `test_scan_skill_manifest_rules`.

## Test plan

- New: long-frontmatter skill still gets the undeclared-bash finding.
- Existing `test_scan_skill_manifest_rules` (short frontmatter) unchanged.

## Done criteria

- [ ] `python3 tests/test_llmsnitch.py` exits 0, +1 test
- [ ] `git status` — only in-scope files
- [ ] `plans/README.md` row updated

## STOP conditions

- Excerpt drift at `scan.py:199-210`.
- The fix seems to need YAML parsing — it doesn't; report instead.

## Maintenance notes

- If `allowed-tools:` ever appears as a YAML list block in the wild, the
  single-line parse misses it — that upgrade needs its own plan, not a
  quick patch here.
