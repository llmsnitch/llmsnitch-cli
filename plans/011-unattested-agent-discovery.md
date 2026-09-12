# Plan 011 — Unattested-agent discovery (close the coverage gap)

- **Status:** TODO
- **Priority:** P2 (capability gap, not a live vuln)
- **Effort:** M
- **Written against commit:** `53b1ab4`
- **Depends on:** none. Independent of 001–003 (all DONE).
- **Grounding docs:** `docs/research/scanner-survey-mvp.md` §2.1 (scan-type-1
  "Discovery walk"), §2.2 (seed-table scope rule + snyk 36-row expansion
  path), §2.3 (finding schema), §2.5 (Notifications: categories, edge
  discipline, Decision/Actor/Novelty); `AGENTS.md` (actionability test);
  `docs/notifier-spec.md` (`scan_finding` surface, cold-start D23).

---

## Context — why this exists

An IT ticket reported a third-party AI tool ("Bari/Barri AI") on this Mac
dated 2026-08-13. `llmsnitch` revealed nothing, for a structural reason
confirmed in code: in patrol/no-roots mode `discover()`
(`llmsnitch/scan.py:125-146`) only walks the seven directories named in
`scanrules.TERRITORIES` (`scanrules.py:22-30`). A tool at `~/.bari/` is
**never visited** — invisible by construction. `_agent_bucket()`
(`scan.py:52-61`) already returns `"unknown"` for anything outside every
territory, but nothing *acts* on that.

The scanner survey already reserved this feature. §2.1 lists "Discovery
walk" as scan-type #1 ("enumerate agent-config artifacts … before checking
anything"), and §2.5's Actor gate states: *"A finding outside any territory
buckets to `unknown` — still an answer ('nobody registered owns this
file')."* This plan **activates that decided-but-unbuilt concept**: surface
an un-dossiered agent home as a first-class, Decision-bearing finding.

**Reconciliation with the ponytail-audit (commit `53b1ab4`).** That audit
removed `--inventory`, which the survey (§2.1:366) had positioned as
discovery's standalone output. This feature is its *actionable successor*:
instead of a passive inventory dump (which names no Decision and so fails
the AGENTS.md gate), discovery emits a finding that names one. The survey is
a research doc under `docs/research/`, not a normative spec, so its lingering
`--inventory`/`--out` references (§2.1:366, §2.4:511) dangle harmlessly; a
one-line "superseded by plan 011" footnote there is a nice-to-have, not a
blocker, and is out of scope for the executor.

---

## What "done" looks like

A scan (patrol or manual) that encounters a directory matching agent-home
heuristics whose path is **not** under a known `TERRITORIES` prefix emits an
`unattested_agent`-class finding, ledgered and routed through the existing
notify path, tiered by context. No new false positives on ordinary dot-dirs
(`~/.ssh`, `~/.docker`, `~/.config`, `~/.cargo`, `~/.aws`). All three test
suites green.

---

## Design decisions (these resolve real traps — do not "simplify" them away)

### D1 — Bucket is bare `unknown`, NOT `unknown:<dirname>`

`_route_to_notifier` (`scan.py:408-420`) routes **every** non-resolved
finding to `fs_notify.notify(...)` on **every** run; it does *not* gate on
`f["new"]`. De-duplication is delegated entirely to the notify-layer novelty
tuple `(category, actor_bucket)` + its window. A unique bucket per directory
would therefore share a tuple with nothing and **re-page every patrol,
forever** (an alert storm). Set `agent="unknown"` (survey §2.3/§2.5). Per-
tool grain still exists where it belongs — the **fingerprint**
(`_fingerprint(rule_id, artifact)`, `scan.py:173-181`) is keyed on the
artifact path, so each distinct home is a distinct ledger row; the shared
`unknown` bucket just means simultaneous discovery of N homes is "one banner
+ N rows in the ledger," which is the survey's intended §2.5 Novelty
behavior.

### D2 — Two rule_ids across two categories, severity fixed per category

`scanrules.py:9-10` is doctrine: *"Severity is fixed per category."* The
existing code splits `config_drift` (high) vs `scan_hygiene` (low) by
**changing category**, never by varying severity within one. Follow that:

| Context (all disk-observable) | rule_id | category | severity |
|---|---|---|---|
| Found during a **patrol** (unattended) **or** under a **system/OS root** (`SYSTEM_TERRITORIES`) | `unattested_agent_home` | `unattested_agent` (new, fixed **high**) | high |
| Found during a **manual** scan under a user-supplied working root, not system-scoped | `unattested_agent_worktree` | `scan_hygiene` (existing, low) | low |

Distinct rule_ids → distinct fingerprints → a later high patrol finding is
**never** suppressed by an earlier low manual finding on the same path
(closes the severity-escalation-invisibility trap: `_fingerprint` excludes
severity, so same-rule_id across tiers would silently dedupe).

- **Autonomy proxy** = `trigger` (already threaded through
  `run_scan(..., trigger)`, `scan.py:333`; `patrol` vs `manual`).
- **Blast-radius proxy** = whether the dir is under a `SYSTEM_TERRITORIES`
  prefix.
- The low tier becomes `record_only` **for free**: `_route_to_notifier`
  auto-sets `record_only` for `low`/`info` non-drift findings
  (`scan.py:419`). Do **not** set it manually — double-handling.

### D3 — Cold-start honesty (known limitation, not a bug to hide)

`scan_finding` is quiet-by-design: `docs/notifier-spec.md` pins it "capped
at high, never pierces cold start" (D23). So on the **first-ever scan**, a
high `unattested_agent_home` lands in the **ledger + daily digest + exit
code 1**, but **no Notification Center banner**. This still closes the gap
the ticket exposed (total invisibility → ledgered, reportable, gate-tripping
finding); the daily patrol banners it on the next run after cold start.
State this plainly in code comments and the notifier-spec category row.
Making first-run *banner* requires piercing cold start — see the optional
**Step 7**; it is a separate, bounded decision, not part of the core.

### D4 — Tight, depth-1 signals (false-positive control)

Signals are tested **directly inside** a candidate dir (one `os.scandir`, no
recursion, symlinks not followed). Recursion would trip `~/.config/*/
config.toml` and similar. Signal set — high-specificity only:

- a regular file named exactly one of: `SKILL.md`, `mcp.json`, `.mcp.json`,
  `mcp_config.json`, `claude_desktop_config.json`, `hooks.json`; **or**
- a subdirectory named `sessions` or `history` containing ≥1 regular file
  (one shallow `scandir`, bounded).

Deliberately **excluded** as too generic: `config.toml`, `AGENTS.md`
(`~/.cargo/config.toml`, countless `AGENTS.md`). `mcp_config.json` /
`claude_desktop_config.json` are **included** to match real agent homes in
the survey's snyk table (§1:184) that bare `mcp.json` would miss.

---

## Files in scope

- `llmsnitch/scanrules.py` — new constants + extend `ruleset_sha256()`.
- `llmsnitch/scan.py` — new `discover_unattested()` + `_dir_finding()` +
  `_discover_roots()`; one call site in `run_scan()`.
- `CONTEXT.md` — one vocabulary term.
- `docs/notifier-spec.md` — one category-table row.
- `README.md` — document `[scan] discover_roots`.
- `tests/test_llmsnitch.py` — new test cases (scan tests live here).

**Out of scope (do not touch):** `fs_coil/` (no notify-layer change in the
core; Step 7 only if selected), `llmsnitch/harness.py`/`ingest.py` (session
ledger, unrelated), the deleted `--inventory`/`--out` (do not re-add), the
survey doc.

---

## Steps

### Step 1 — Constants in `scanrules.py`

Add after `TERRITORIES` (`scanrules.py:30`):

```python
# Un-dossiered agent-home discovery (plan 011). Depth-1 markers that mean
# "a directory is an AI-agent home" — the admission test (CONTEXT.md) made
# concrete. High-specificity only: config.toml / AGENTS.md are deliberately
# excluded (too common: ~/.cargo, ~/.config).
DISCOVERY_FILE_SIGNALS = frozenset({
    "SKILL.md", "mcp.json", ".mcp.json", "mcp_config.json",
    "claude_desktop_config.json", "hooks.json",
})
DISCOVERY_DIR_SIGNALS = frozenset({"sessions", "history"})

# OS/system scopes: an unattested home here is high-blast-radius (→ high
# tier regardless of trigger). Prefixes, ~-expanded at use.
SYSTEM_TERRITORIES = ("~/Library", "/Library", "/etc", "/usr/local", "/opt")

UNATTESTED_CATEGORY = "unattested_agent"   # fixed severity: high
```

Extend `ruleset_sha256()` (`scanrules.py:118-123`) so the stamp reflects the
detector. **Every set/dict MUST be `sorted()`** — an unsorted `set` iterates
non-deterministically and would make the "reproducibility stamp" change
run-to-run:

```python
    blob += "|secret_extra:" + SECRET_EXTRA.pattern
    blob += "|territories:" + "|".join(
        sorted(f"{a}:{','.join(sorted(p))}" for a, p in TERRITORIES.items()))
    blob += "|discover_files:" + "|".join(sorted(DISCOVERY_FILE_SIGNALS))
    blob += "|discover_dirs:" + "|".join(sorted(DISCOVERY_DIR_SIGNALS))
    blob += "|system_terr:" + "|".join(sorted(SYSTEM_TERRITORIES))
    return hashlib.sha256(blob.encode()).hexdigest()
```

**Verify:** `python3 -c "from llmsnitch import scanrules as s;
print(s.ruleset_sha256()); print(s.ruleset_sha256())"` prints the **same**
hash twice (determinism), and it differs from the pre-change value.

### Step 2 — `_discover_roots()` config reader in `scan.py`

`[scan]` is net-new. Values are a **colon-separated** list (PATH
convention — pick this, do not invent another delimiter). Add near the other
helpers:

```python
def _discover_roots():
    """Roots whose top-level dirs are probed for un-dossiered agent homes.
    [scan] discover_roots = colon-separated paths; default = $HOME.
    Malformed config falls back to $HOME (never raises)."""
    import configparser
    home = os.path.expanduser("~")
    path = os.path.expanduser("~/.config/llmsnitch/config")
    cp = configparser.ConfigParser(inline_comment_prefixes=("#",))
    try:
        cp.read(path)
    except configparser.Error:
        return [home]
    raw = cp.get("scan", "discover_roots", fallback="~") \
        if cp.has_section("scan") else "~"
    roots = [os.path.expanduser(r.strip()) for r in raw.split(":") if r.strip()]
    return roots or [home]
```

### Step 3 — `_dir_finding()` in `scan.py`

`_finding()` (`scan.py:184-192`) is built for a file *line* (needs `cls`,
`line_no`, `sha`, an evidence line). A discovered home is a directory:
`classify()` returns `None` for it, there is no line or file hash. Add a
sibling constructor that produces the **same dict shape** (downstream — the
`new`-flag loop at `scan.py:360-362`, routing at `:417`, `to_text` — assumes
these keys exist):

```python
def _dir_finding(scan_id, rule_id, category, severity, dirpath, signal):
    art = _display(dirpath)
    return {"v": 1, "ts": store.now(), "scan_id": scan_id,
            "rule_id": rule_id, "category": category, "severity": severity,
            "artifact": art, "artifact_class": "agent_home",
            "agent": "unknown", "line": 0,
            "evidence": f"agent-home signal: {signal}", "sha256": "",
            "fingerprint": _fingerprint(rule_id, art)}
```

`agent="unknown"` per **D1**. `_fingerprint(rule_id, art)` reuses the shipped
coarse key (`scan.py:173`) — do **not** use the survey's older
`rule_id|artifact|line|evidence` formula; the code deviated from it on
purpose.

### Step 4 — `discover_unattested()` detector in `scan.py`

Resolve `$HOME` at **call time** (not the module-level `_HOME`, which is
bound at import and would ignore a test's `HOME` override):

```python
_DISCOVER_MAX = 500   # candidate-dir cap; the sweep is cheap but bounded

def discover_unattested(scan_id, trigger, roots=None):
    """Un-dossiered agent homes: top-level dirs under each discover-root
    that carry an agent-home signal (scanrules.DISCOVERY_*) and sit outside
    every known TERRITORY. Tier by context (plan 011 D2). Depth-1, symlinks
    skipped, bounded. Never raises — a bad root is skipped."""
    home = os.path.expanduser("~")
    roots = roots if roots is not None else _discover_roots()
    sys_prefixes = [os.path.expanduser(p) for p in scanrules.SYSTEM_TERRITORIES]
    out, seen, budget = [], set(), _DISCOVER_MAX
    for root in roots:
        is_home = os.path.realpath(root) == os.path.realpath(home)
        try:
            entries = list(os.scandir(root))
        except OSError:
            continue
        for e in entries:
            if budget <= 0:
                return out
            try:
                if not e.is_dir(follow_symlinks=False):
                    continue
            except OSError:
                continue
            name = e.name
            if is_home and not name.startswith("."):
                continue                      # $HOME: dot-dirs only
            p = e.path
            if p in seen:
                continue
            seen.add(p)
            budget -= 1
            if _agent_bucket(p) != "unknown":
                continue                      # a known territory — skip
            sig = _home_signal(p)
            if not sig:
                continue
            in_system = any(p == sp or p.startswith(sp + os.sep)
                            for sp in sys_prefixes)
            if trigger == "patrol" or in_system:
                out.append(_dir_finding(
                    scan_id, "unattested_agent_home",
                    scanrules.UNATTESTED_CATEGORY, "high", p, sig))
            else:
                out.append(_dir_finding(
                    scan_id, "unattested_agent_worktree",
                    "scan_hygiene", "low", p, sig))
    return out


def _home_signal(dirpath):
    """First agent-home signal directly inside dirpath, or None. Depth-1."""
    try:
        entries = list(os.scandir(dirpath))
    except OSError:
        return None
    for e in entries:
        try:
            if e.is_file(follow_symlinks=False) and \
                    e.name in scanrules.DISCOVERY_FILE_SIGNALS:
                return e.name
            if e.is_dir(follow_symlinks=False) and \
                    e.name in scanrules.DISCOVERY_DIR_SIGNALS:
                try:
                    if any(c.is_file(follow_symlinks=False)
                           for c in os.scandir(e.path)):
                        return e.name + "/"
                except OSError:
                    continue
        except OSError:
            continue
    return None
```

### Step 5 — Wire into `run_scan()`

Insert **one line** right after the target-scan loop (after `scan.py:353`,
`findings.extend(fnds)`'s loop ends) and **before** `_drift` (`:355`), so
discovery findings flow through the existing `new`-flag pass (`:360-362`) and
routing (`:384`):

```python
    findings.extend(discover_unattested(scan_id, trigger))
```

Note the parameter name: `discover_unattested` reads its own
`_discover_roots()`, independent of `run_scan`'s `roots` (which are the
user's target-scan `ROOT` args — do not pass them through; they mean
different things).

### Step 6 — Docs + vocabulary

- `CONTEXT.md`: add under the vocabulary list —
  **"Unattested agent"**: a directory matching agent-home heuristics
  (`scanrules.DISCOVERY_*`) that sits outside every registered `TERRITORIES`
  prefix — a tool present on disk with no dossier. Distinct from the
  `unknown` actor-bucket (which also covers an intruder inside *known*
  territory). Emitted by the scan as `unattested_agent_home` (high) /
  `unattested_agent_worktree` (low).
- `docs/notifier-spec.md`: add a category row mirroring the existing scan
  rows — `unattested_agent` | fires when the scan finds an un-dossiered
  agent home | high | 24h | *Decision:* "Attest or remove — add
  `dossiers/<name>.md` to bring it under coverage if you installed it;
  otherwise remove the directory and rotate any credential it could read."
  Note it routes through `scan_finding` and so is **quiet on cold start**
  (D3) until Step 7 lands.
- `README.md`: under the `[gate]` config block, document
  `[scan]\ndiscover_roots = ~:~/Library/Application Support` (colon-
  separated; default `~`). Explain that widening toward the survey's snyk
  36-row table (§2.2) is exactly this key.

### Step 7 — OPTIONAL, decision required: banner on cold start

**Only if the maintainer wants first-run discovery to push a Notification
Center banner** (the user's stated intent was "system/auto → page"). The
core (Steps 1-6) deliberately does not, honoring the survey's quiet-by-design
`scan_finding` and keeping `fs_coil` untouched.

The change: give the **high** tier its own notify category that pierces cold
start, instead of flattening to `scan_finding`. This also fixes a latent
survey-vs-code gap — §2.5's table says `config_compromise` (critical)
"pierces," but the shipped `_route_to_notifier` (`scan.py:414-418`) routes
*everything* as `scan_finding` and only varies the subject label, so no scan
finding pierces today.

Sketch (touches `fs_coil/notify.py` `CATEGORIES` + `_route_to_notifier`):
add a `CATEGORIES["unattested_agent"] = ("24h", "high-pierce-or-critical", …)`
per the spec's cold-start rules, and in `_route_to_notifier` pass the notify
category based on the finding's rule_id/severity rather than the constant
`"scan_finding"`. **Blast radius:** every `config_compromise` finding would
begin piercing cold start too (arguably a bugfix aligning code to survey
§2.5, but a behavior change worth a line in the commit). Ships with its own
`test_scan_notify.py` case asserting a cold-start banner. **Escape hatch:**
if wiring this cleanly requires more than ~15 lines in `_route_to_notifier`
or changing the `notify()` signature, STOP and report — it means the notify
category model needs its own plan, not a graft here.

---

## Test plan (`tests/test_llmsnitch.py`, follow the `_with_tmp_store` pattern)

Add cases (use a temp `LLMSNITCH_DIR` **and** a temp discover-root so the
sweep is hermetic; pass `roots=` explicitly to `discover_unattested` to avoid
depending on the real `~/.config`):

1. `test_unattested_home_high_on_patrol` — seed `<tmproot>/.faketool/
   sessions/s.jsonl`; call `discover_unattested(scan_id, "patrol",
   roots=[tmproot])`; assert one finding, `rule_id=="unattested_agent_home"`,
   `severity=="high"`, `category=="unattested_agent"`, `agent=="unknown"`.
2. `test_unattested_worktree_low_on_manual` — same seed, `trigger="manual"`,
   a non-system `tmproot`; assert `rule_id=="unattested_agent_worktree"`,
   `severity=="low"`.
3. `test_known_territory_not_flagged` — seed `<tmproot>/.claude/SKILL.md`
   after monkeypatching a `TERRITORIES` entry (or point a root at a real
   territory); assert **no** `unattested_*` finding.
4. `test_generic_dotdirs_no_false_positive` — seed `<tmproot>/.ssh/config`,
   `<tmproot>/.config/foo/config.toml`, `<tmproot>/.docker/config.json`;
   assert zero `unattested_*` findings (proves `config.toml` recursion and
   generic files don't trip it).
5. `test_signal_detection_shallow_only` — seed a `config.toml` **nested**
   under `<tmproot>/.tool/sub/config.toml` (no depth-1 signal); assert no
   finding (depth-1 discipline).
6. `test_ruleset_sha_deterministic_and_changed` — assert
   `ruleset_sha256()==ruleset_sha256()` and that it differs from the stored
   pre-change constant (paste the old hash into the test).
7. Routing (`tests/test_scan_notify.py`): assert a high home yields a
   `scan_finding` ledger row with `actor_bucket=="unknown"`, and a low one
   is `record_only` (no delivered banner).

## Done criteria (machine-checkable)

- `python3 tests/test_llmsnitch.py` → all pass (was 34/34; now 34+N).
- `python3 tests/test_notify.py` → 14/14.
- `python3 tests/test_scan_notify.py` → all pass (was 8/8; now 8+M).
- `python3 -m compileall -q llmsnitch` → clean.
- Live: with a temp `LLMSNITCH_DIR` and a temp discover-root containing
  `.faketool/sessions/x.jsonl`, `discover_unattested` returns one high
  finding; a real `llmsnitch scan --patrol` over the actual machine adds
  **no** `unattested_*` finding for `~/.ssh`/`~/.docker`/`~/.config`
  (grep the newest `~/.llmsnitch/scans/*/findings.ndjson`).
- `ruleset_sha256()` is stable across two processes.

## Maintenance notes

- **Exit-code side effect:** a patrol that discovers a new home emits a high
  finding → `--fail-on high` (default) → **exit 1**. This is the intended
  gate signal (a new unattested agent *should* fail the patrol), but any
  cron/LaunchAgent wrapper must treat exit 1 as "review," not "crash." Note
  it in the patrol docs.
- **Watch in review:** anyone adding a new agent to `TERRITORIES` must
  confirm it stops appearing as `unattested_*` (the `_agent_bucket !=
  "unknown"` skip handles this automatically — verify with a scan).
- **Interacts with:** the survey's snyk-table expansion (§2.2) is now just
  values in `[scan] discover_roots`; no code change to broaden coverage.
- **Do not** let the signal set grow toward generic filenames — every added
  signal widens the false-positive surface across every dot-dir on disk.

## Escape hatches

- If `_route_to_notifier`'s per-finding routing (Step 7) can't be done in
  ~15 lines without touching `notify()`'s signature — **STOP**, ship Steps
  1-6, and file the cold-start-pierce work as its own plan.
- If any generic dot-dir on the real machine trips `unattested_*` in the
  live check — **STOP**, tighten `DISCOVERY_FILE_SIGNALS`, and re-run test 4
  before proceeding. A false-positive-y discovery pass is worse than none.
