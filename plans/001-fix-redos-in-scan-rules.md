# Plan 001: Make the scan ruleset immune to catastrophic backtracking (ReDoS)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat a7a83bb..HEAD -- llmsnitch/scanrules.py llmsnitch/scan.py tests/test_llmsnitch.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: security
- **Planned at**: commit `a7a83bb`, 2026-08-26

## Why this matters

`llmsnitch scan` runs regex rules line-by-line over agent config files —
content that is, by this tool's own threat model, potentially attacker
controlled (a hostile skill bundle). Two rules backtrack catastrophically on
crafted input: a single 200 KB line of repeated `curl ` takes **42 seconds**;
160 KB of repeated `nc ` takes **70 seconds** (measured, this machine).
Growth is ~O(n²), so one 1 MB line ≈ 15–25 minutes of pinned CPU. The
defensive audit tool can be hung by exactly the content it exists to
inspect.

## Current state

- `llmsnitch/scanrules.py` — the inline ruleset. Two rules are ambiguous:
  - `scanrules.py:42` (`hook_curl_pipe_shell`):
    `re.compile(r"\b(curl|wget)\s+[^|;]*\|\s*(sudo\s+)?(ba|z|da)?sh\b")`
    — `\s+` and the adjacent `[^|;]*` both match whitespace; on a long
    line with no `|`, the split point between them is retried
    quadratically.
  - `scanrules.py:47-49` (`hook_reverse_shell`) contains the alternation
    branch `nc\s+(-\w*e\w*\s|.*\s-e\s)` — the `.*\s-e\s` part backtracks
    the same way on long `nc `-repeated lines.
- `llmsnitch/scan.py:218-224` (`scan_file`) — runs every rule against
  every line via `rx.search(line)`; lines come from `body.splitlines()`
  of files up to `_MAX_FILE` (1 MB, `scan.py:31`), so a single crafted
  line reaches the vulnerable regexes at full length.
- Repo conventions: stdlib only (`dependencies = []` — hard, test-enforced;
  the `regex` PyPI module with possessive quantifiers is NOT an option).
  Python 3.9+ (no `re` atomic groups — those need 3.11; do not use them).
  Comments state constraints, not narration; deliberate ceilings get a
  `ponytail:` comment naming the upgrade path (see `scanrules.py:50-52`
  for the idiom).

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Scan tests | `python3 tests/test_llmsnitch.py` | `27/27 passed` (30/30 after this plan) |
| Notify-wiring tests | `python3 tests/test_scan_notify.py` | `8/8 passed` |
| Notify tests | `python3 tests/test_notify.py` | `18/18 passed` |

(No build/lint/typecheck steps exist in this repo — the test scripts are the
whole gate.)

## Scope

**In scope** (the only files you should modify):
- `llmsnitch/scanrules.py`
- `llmsnitch/scan.py` (only if adding a pre-match line-length cap)
- `tests/test_llmsnitch.py` (add tests)

**Out of scope** (do NOT touch, even though they look related):
- `llmsnitch/hook.py` — its `_SECRET` regex runs on the hot path with a
  2000-char input cap (`_MAX_STR`), which already bounds backtracking;
  changing hot-path code is a separate, riskier change.
- `fs_coil/` — vendored live-install baseline owned by migration tickets
  T005–T007.

## Git workflow

- Work on the current branch `research/scanner-survey-mvp` (this repo is
  local-only: NEVER add a remote or push).
- One commit; message style: `scan: <imperative summary>` + body, ending
  with `Co-Authored-By: Claude <noreply@anthropic.com>` (see `git log -3`).

## Steps

### Step 1: Add the failing performance tests first

In `tests/test_llmsnitch.py`, after `test_scan_skill_manifest_rules`, add:

```python
def test_scan_rules_resist_redos():
    """A crafted long line must not hang the ruleset (measured pre-fix:
    42s for 200KB of 'curl '; budget here is generous CI headroom)."""
    import time
    from llmsnitch import scanrules
    for payload in ("curl " * 40_000, "nc " * 55_000, "wget  x" * 25_000):
        t0 = time.monotonic()
        for _, _, _, _, rx in scanrules.RULES:
            rx.search(payload)
        assert time.monotonic() - t0 < 2.0, \
            f"ruleset took too long on {payload[:12]!r}..."
```

**Verify**: `python3 tests/test_llmsnitch.py` → `test_scan_rules_resist_redos` FAILS (times out the 2 s budget). If it passes pre-fix, STOP: the regexes have already been changed.

### Step 2: De-ambiguate the two regexes

In `llmsnitch/scanrules.py`:

- `hook_curl_pipe_shell`: change `\s+[^|;]*` so the two parts cannot both
  consume whitespace — target shape:
  `r"\b(curl|wget)\s[^|;]{0,400}\|\s*(sudo\s+)?(ba|z|da)?sh\b"`
  (single `\s`, bounded non-pipe run; the 400 cap bounds any residual
  scanning and no real hook command line exceeds it).
- `hook_reverse_shell`: replace the `.*\s-e\s` branch with a bounded form:
  `nc\s(-\w*e\w*\s|[^\n]{0,200}\s-e\s)` — same semantics on real
  command lines, linear on garbage.
- Add a comment on each naming the constraint (backtracking bound), e.g.:
  `# bounded runs: rules face attacker-sized lines; see plan 001 / test_scan_rules_resist_redos`

**Verify**: `python3 tests/test_llmsnitch.py` → `test_scan_rules_resist_redos` PASSES and `test_scan_flags_compromise_and_secrets` still PASSES (positive matches preserved).

### Step 3: Belt-and-braces line cap in scan_file

In `llmsnitch/scan.py` `scan_file`, cap the line length fed to the ruleset
(evidence is already capped later at 180 chars):

```python
    for line_no, line in enumerate(body.splitlines(), 1):
        if len(line) > 4096:   # rules face attacker-sized lines; a real
            line = line[:4096]  # config line never approaches this
```

Secret scanning must still see the capped line (a secret split at 4096 is
out of scope — note it in the comment if you must, don't fix it).

**Verify**: `python3 tests/test_llmsnitch.py` → all pass; `python3 tests/test_scan_notify.py` → `8/8 passed`.

### Step 4: Full-file pathological test

Add one end-to-end test: write a skill script containing a single 500 KB
`curl `-repeated line into a tmp root, run `scan.cmd_scan([root], buf)`,
assert it completes in under 5 s and exits cleanly (0 or 1, not 2). Model
the tmp-store setup on `_with_tmp_store` in the same file.

**Verify**: `python3 tests/test_llmsnitch.py` → `30/30 passed` (27 existing + 3 new: rules-resist, full-file, and whichever split you chose — adjust the count to what you actually added and record it in the commit body).

## Test plan

- `test_scan_rules_resist_redos` — every compiled rule under 2 s against
  three pathological payloads (the regression lock for this plan).
- End-to-end pathological file scan under 5 s.
- Existing positive-match tests (`test_scan_flags_compromise_and_secrets`,
  `test_scan_skill_manifest_rules`) are the semantic guard — they must
  pass unmodified. If a regex change breaks one, the regex is wrong, not
  the test.

## Done criteria

- [ ] `python3 tests/test_llmsnitch.py` exits 0, count increased by the new tests
- [ ] `python3 tests/test_scan_notify.py` exits 0 (8/8)
- [ ] `python3 tests/test_notify.py` exits 0 (18/18)
- [ ] `git status` shows only in-scope files modified
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The regexes at `scanrules.py:42` / `:47-49` don't match the excerpts
  above (drift).
- Step 1's test passes BEFORE any fix (someone fixed it already).
- Fixing the regex breaks a positive-match test twice in a row — report
  the exact payload that stopped matching instead of loosening the test.
- You find yourself wanting `regex` (PyPI) or `(?>...)` atomic groups —
  both are unavailable here (stdlib-only; Python 3.9 floor).

## Maintenance notes

- Every future rule added to `scanrules.RULES` faces attacker-sized input.
  The reviewer checklist for new rules: no `X*`/`X+` adjacent to a class
  that overlaps `X`; unbounded `.*` only when anchored. The
  `test_scan_rules_resist_redos` payloads should grow with new rule shapes.
- The 4096 line cap (step 3) is the backstop if a future rule regresses —
  do not remove it when tuning rules.
