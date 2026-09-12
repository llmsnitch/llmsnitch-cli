"""llmsnitch scan — cold-path config audit over agent artifacts.

  llmsnitch scan [ROOT ...] [--format text|json]
                 [--fail-on critical|high|medium]
                 [--rebaseline] [--report] [--patrol]

--report renders the LATEST STORED scan — no re-scan, no baseline
mutation — so reviewing a drift finding never destroys the evidence it
points at. It is the action every scan_finding page names.

Design: docs/research/scanner-survey-mvp.md Part 2. Five scan types:
discovery walk, .claude/ compromise checks, skill-manifest checks,
secret-shape audit at rest, SHA-256 drift fingerprinting. Findings land as
NDJSON under <base>/scans/<scan-id>/ exactly like sessions; exit codes
reuse the gate contract (0 pass / 1 breach / 2 operational). Read-only
over the filesystem; never runs on the hook hot path.
"""

import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path

from . import hook, scanrules, store

_SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
_MAX_FILE = 1_000_000   # bytes; larger artifacts are inventoried, not read
_MAX_FILES = 4000       # walk cap; overflow reports a nonzero skipped
                        # count (truncation flag, not an exact miss tally)
_MAX_DEPTH = 6
_EVIDENCE_CAP = 180     # clawscan static_scanner.go:17 discipline
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
              "dist", "build", "target"}

_INSTRUCTION_NAMES = {"CLAUDE.md", "AGENTS.md", "GEMINI.md", ".cursorrules",
                      ".windsurfrules", "copilot-instructions.md"}
_SETTINGS_NAMES = {"settings.json", "settings.local.json",
                   "managed-settings.json"}
_SCRIPT_EXTS = {".py", ".js", ".ts", ".rb", ".ps1", ".sh"}

_HOME = str(Path.home())


def _display(path):
    p = str(path)
    return "~" + p[len(_HOME):] if p.startswith(_HOME) else p


def _agent_bucket(path):
    """Territory the artifact sits in (notifier-spec Actor-bucket, light-mode
    ceiling: territory, not actors). 'unknown' outside every territory."""
    p = str(path)
    for agent, prefixes in scanrules.TERRITORIES.items():
        for pref in prefixes:
            pref = os.path.expanduser(pref)
            if p == pref or p.startswith(pref + os.sep):
                return agent
    return "unknown"


def classify(path):
    """Artifact class for a path, or None if not an agent artifact."""
    name = path.name
    parts = path.parts
    if name == "SKILL.md":
        return "skill_manifest"
    if name in _SETTINGS_NAMES and ".claude" in parts:
        return "claude_settings"
    if name == ".claude.json" or name == "claude_desktop_config.json" \
            or name == ".mcp.json" or name == "mcp.json":
        return "mcp_config"
    if "hooks" in parts and ".claude" in parts:
        return "hook_script"
    if name in _INSTRUCTION_NAMES:
        return "instruction_file"
    if path.suffix in _SCRIPT_EXTS and (
            "skills" in parts or "commands" in parts):
        return "skill_script"
    return None


def _walk(root, budget):
    """Yield files under root, depth-capped, junk-skipped, budget-limited."""
    root = Path(root)
    base_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root):
        if len(Path(dirpath).parts) - base_depth >= _MAX_DEPTH:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in sorted(dirnames) if d not in _SKIP_DIRS
                       and not (d.startswith(".") and d not in
                                (".claude", ".cursor", ".codex", ".github",
                                 ".agents", ".windsurf", ".gemini"))]
        for fn in sorted(filenames):
            budget[0] -= 1        # decrement first: exhaustion must go
            if budget[0] < 0:     # negative so discover() can report it
                return
            yield Path(dirpath) / fn


def discover(roots=None):
    """[(path, artifact_class, agent)] — the seed inventory (spec §2.2).
    Without roots: notifier-registry territories + cwd. With roots: generic
    classified walk. Returns (targets, skipped_count)."""
    budget = [_MAX_FILES]
    seen = {}

    def add(p):
        try:
            if not p.is_file() or p.is_symlink():
                return
        except OSError:
            return
        cls = classify(p)
        if cls and str(p) not in seen:
            seen[str(p)] = (p, cls, _agent_bucket(p))

    if roots:
        for r in roots:
            for p in _walk(os.path.expanduser(r), budget):
                add(p)
    else:
        home = Path(_HOME)
        for prefixes in scanrules.TERRITORIES.values():
            t = Path(os.path.expanduser(prefixes[0]))
            for single in (t / "settings.json", t / "settings.local.json",
                           t / "managed-settings.json", t / "mcp.json",
                           t / "CLAUDE.md"):
                add(single)
            for sub in ("hooks", "skills", "commands"):
                if (t / sub).is_dir():
                    for p in _walk(t / sub, budget):
                        add(p)
        add(home / ".claude.json")
        cwd = Path.cwd()
        for name in _INSTRUCTION_NAMES | {".mcp.json"}:
            add(cwd / name)
        add(cwd / ".github" / "copilot-instructions.md")
        for sub in (".claude", ".agents"):
            if (cwd / sub).is_dir():
                for p in _walk(cwd / sub, budget):
                    add(p)
    return list(seen.values()), max(0, -budget[0])


# hook._SECRET has no left boundary (fine for tool payloads, an FP factory
# over prose: "task-completed"/"risk-based" contain "sk-…"). At rest we
# require a non-alnum left edge.
_SECRET_ALL = re.compile(
    r"(?<![A-Za-z0-9])(?:" + hook._SECRET.pattern + "|"
    + scanrules.SECRET_EXTRA.pattern + ")")


def _read(path):
    try:
        if path.stat().st_size > _MAX_FILE:
            return None
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw[:512]:   # binary sniff (skill-detector discover.go)
        return None
    return raw.decode("utf-8", errors="replace")


def _evidence(line):
    return hook._clean(line.strip())[:_EVIDENCE_CAP]


def _fingerprint(rule_id, artifact, salt=""):
    """Novelty key. Deliberately coarser than the spec's draft
    (rule|artifact|line|evidence): line/evidence in the key means any edit
    to a flagged line re-pages a known finding, which the same spec's edge
    discipline forbids (skill-detector's delta.go uses soft keys for the
    same reason). Grain: one condition per (rule, artifact); drift salts
    with the content hash so each distinct state is one event."""
    return hashlib.sha256(
        f"{rule_id}|{artifact}|{salt}".encode()).hexdigest()


def _finding(scan_id, rule_id, category, severity, path, cls, agent,
             line_no, line, sha):
    art = _display(path)
    ev = _evidence(line)
    return {"v": 1, "ts": store.now(), "scan_id": scan_id,
            "rule_id": rule_id, "category": category, "severity": severity,
            "artifact": art, "artifact_class": cls, "agent": agent,
            "line": line_no, "evidence": ev, "sha256": sha,
            "fingerprint": _fingerprint(rule_id, art)}


def _frontmatter_allowed_tools(text):
    """Hand parser: 'allowed-tools:' value between the first two --- fences.
    Returns None when the key (or the opening fence) is absent. Bounded at
    400 lines / 32 KB of frontmatter — a resource cap, not an evasion
    window (plan 003)."""
    lines = text[:32768].splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:401]:
        if line.strip() == "---":
            return None
        if line.startswith("allowed-tools:"):
            return line.split(":", 1)[1].strip()
    return None


def scan_file(scan_id, path, cls, agent):
    text = _read(path)
    if text is None:
        return None, []
    sha = hashlib.sha256(text.encode()).hexdigest()
    findings = []
    body = text
    if text.startswith("﻿"):   # leading BOM is benign
        body = text[1:]
    for line_no, line in enumerate(body.splitlines(), 1):
        if len(line) > 4096:    # rules face attacker-sized lines; a real
            line = line[:4096]  # config line never approaches this
        canon = hook._canonical(line)
        for rid, cat, sev, classes, rx in scanrules.RULES:
            if cls in classes and (rx.search(line) or
                                   (canon is not line and rx.search(canon))):
                findings.append(_finding(scan_id, rid, cat, sev, path, cls,
                                         agent, line_no, line, sha))
        if _SECRET_ALL.search(canon if canon is not line else line):
            findings.append(_finding(scan_id, "secret_shape", "secret_at_rest",
                                     "high", path, cls, agent, line_no, line,
                                     sha))
    if cls == "skill_manifest":
        allowed = _frontmatter_allowed_tools(text)
        if allowed is not None and "Bash" not in allowed and \
                re.search(r"```(ba)?sh\b|subprocess|os\.system", text):
            findings.append(_finding(scan_id, "skill_undeclared_bash",
                                     "scan_hygiene", "low", path, cls, agent,
                                     0, "allowed-tools: " + allowed, sha))
    return sha, findings


# -- drift baseline ----------------------------------------------------------

def _baseline_path():
    return store.base_dir() / "baseline.json"


def _load_baseline():
    try:
        b = json.loads(_baseline_path().read_text())
        return b if isinstance(b, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_baseline(baseline):
    store._mkdir_private(store.base_dir())
    p = _baseline_path()
    p.write_text(json.dumps(baseline, indent=2))
    store._chmod_private(p)


def _drift(scan_id, baseline, current, rebaseline):
    """config_drift findings vs baseline; mutates baseline to current.
    First scan (empty baseline) and --rebaseline seed silently."""
    findings = []
    seeded = not baseline
    now = store.now()
    for key, (sha, cls, agent) in current.items():
        prev = baseline.get(key)
        art = key.split("\x1f", 1)[1]
        if prev is None:
            baseline[key] = {"sha256": sha, "first_seen_ts": now}
            if not seeded and not rebaseline:
                findings.append(_drift_finding(scan_id, art, cls, agent,
                                               "added", sha))
        elif prev.get("sha256") != sha:
            baseline[key] = {"sha256": sha,
                             "first_seen_ts": prev.get("first_seen_ts", now)}
            if not rebaseline:
                findings.append(_drift_finding(scan_id, art, cls, agent,
                                               "changed", sha))
    for key in list(baseline):
        if key not in current:
            cls = key.split("\x1f", 1)[0]
            art = key.split("\x1f", 1)[1]
            if not Path(os.path.expanduser(art)).exists():
                del baseline[key]
                if not rebaseline:
                    findings.append(_drift_finding(scan_id, art, cls,
                                                   "unknown", "removed", ""))
    return findings


def _drift_finding(scan_id, art, cls, agent, change, sha):
    control = cls in scanrules.CONTROL_CLASSES
    cat = "config_drift" if control else "scan_hygiene"
    sev = "high" if control else "low"
    return {"v": 1, "ts": store.now(), "scan_id": scan_id,
            "rule_id": f"drift_{change}", "category": cat, "severity": sev,
            "artifact": art, "artifact_class": cls, "agent": agent,
            "line": 0, "evidence": change, "sha256": sha,
            "fingerprint": _fingerprint(f"drift_{change}", art, sha)}


# -- novelty diff vs previous scan (spec §2.5 edge discipline) ---------------

def _previous_fingerprints():
    scans = store.base_dir() / "scans"
    try:
        dirs = sorted(d for d in scans.iterdir() if d.is_dir())
    except OSError:
        return None
    if not dirs:
        return None
    fps = set()
    try:
        for line in (dirs[-1] / "findings.ndjson").read_text().splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and not row.get("resolved"):
                fps.add(row.get("fingerprint"))
    except OSError:
        return None
    return fps


# -- the scan ----------------------------------------------------------------

def run_scan(roots=None, rebaseline=False, trigger="manual"):
    scan_id = "scan-" + time.strftime("%Y%m%d-%H%M%S")
    d = store.base_dir() / "scans" / scan_id
    n = 1
    while d.exists():   # two scans in one second must not overwrite
        n += 1
        d = d.with_name(f"{scan_id}-{n}")
    scan_id = d.name
    started = store.now()
    targets, skipped = discover(roots)
    prev_fps = _previous_fingerprints()

    findings, current, files_scanned = [], {}, 0
    for path, cls, agent in targets:
        sha, fnds = scan_file(scan_id, path, cls, agent)
        if sha is None:
            skipped += 1
            continue
        files_scanned += 1
        current[f"{cls}\x1f{_display(path)}"] = (sha, cls, agent)
        findings.extend(fnds)

    baseline = _load_baseline()
    findings.extend(_drift(scan_id, baseline, current, rebaseline))
    _save_baseline(baseline)

    cur_fps = set()
    for f in findings:
        f["new"] = prev_fps is None or f["fingerprint"] not in prev_fps
        cur_fps.add(f["fingerprint"])
    if prev_fps:
        for fp in sorted(prev_fps - cur_fps):
            findings.append({"v": 1, "ts": store.now(), "scan_id": scan_id,
                             "fingerprint": fp, "resolved": True})

    by_sev = {}
    for f in findings:
        if not f.get("resolved"):
            by_sev[f["severity"]] = by_sev.get(f["severity"], 0) + 1
    meta = {"scan_id": scan_id, "started_at": started, "ended_at": store.now(),
            "roots": [str(r) for r in (roots or [])] or ["<territories+cwd>"],
            "files_scanned": files_scanned, "files_skipped": skipped,
            "findings_by_severity": by_sev, "trigger": trigger,
            "ruleset_sha256": scanrules.ruleset_sha256()}

    store._mkdir_private(d)
    nd = d / "findings.ndjson"
    with open(nd, "w") as fh:
        for f in findings:
            fh.write(json.dumps(f, separators=(",", ":")) + "\n")
    store._chmod_private(nd)
    meta["notify_routed"] = _route_to_notifier(findings)
    mp = d / "meta.json"
    mp.write_text(json.dumps(meta, indent=2))
    store._chmod_private(mp)
    return meta, findings


def _route_to_notifier(findings):
    """Route findings into the notify layer — config-audit is a second
    alert-producing surface, not a replacement for the scan report. Every
    finding becomes a notify ledger row; the (scan_finding, actor_bucket)
    novelty tuple means at most one banner per agent per window regardless
    of finding count — per-finding detail lives here and in `scan --report`.
    The notify tier is capped at the category default (quiet by design; a
    finding's own severity travels in the subject and the scan ledger).
    info/low findings carry no decision and are record_only (AGENTS.md
    doctrine) — except drift, which always names one (rebaseline or revert).
    Resolved tombstone rows are bookkeeping, not findings — no rule_id, not
    routed. Returns False when the notify layer is unavailable, and the
    caller records that in meta so silence stays discoverable."""
    try:
        from fs_coil import notify as fs_notify
    except Exception:   # noqa: BLE001 — no vendored tree, or a broken one;
        return False    # the scan must survive either
    for f in findings:
        if f.get("resolved"):
            continue
        sev = f["severity"]
        # Only `critical` is load-bearing in the subject — `high` equals the
        # derived alert tier and would be redundant next to it.
        label = "critical " if sev == "critical" else ""
        fs_notify.notify(   # never raises (fail-closed by contract)
            "config-audit", "scan_finding",
            f"{label}{f['rule_id']}: {f['artifact']}",
            actor_bucket=f["agent"],
            record_only=(sev in ("info", "low")
                         and not f["rule_id"].startswith("drift_")))
    return True


# -- emitters ----------------------------------------------------------------

def to_text(meta, findings):
    real = [f for f in findings if not f.get("resolved")]
    lines = [f"scan {meta['scan_id']}: {meta['files_scanned']} files, "
             f"{meta['files_skipped']} skipped"]
    if meta.get("notify_routed") is False:
        lines.append("note: notify layer unavailable — "
                     "findings ledgered here only")
    sev = meta["findings_by_severity"]
    if not real:
        lines.append("[OK] no findings")
    else:
        # Criticals first, then highs/mediums; counts close the block.
        for f in sorted(real, key=lambda f:
                        -_SEVERITY_RANK.get(f["severity"], 0)):
            if _SEVERITY_RANK.get(f["severity"], 0) >= 2:
                mark = "NEW" if f.get("new") else "known"
                lines.append(f"[{f['severity'].upper()}] {mark} {f['rule_id']} "
                             f"{f['artifact']}:{f['line']}  {f['evidence']}")
        lines.append("findings: " + ", ".join(
            f"{k}={sev[k]}" for k in
            sorted(sev, key=lambda s: -_SEVERITY_RANK.get(s, 0))))
    resolved = sum(1 for f in findings if f.get("resolved"))
    if resolved:
        lines.append(f"resolved since last scan: {resolved}")
    return "\n".join(lines) + "\n"


def to_json(meta, findings):
    return json.dumps({"meta": meta, "findings": findings}, indent=2) + "\n"


# -- CLI ---------------------------------------------------------------------

def _load_latest_scan():
    """(meta, findings) of the newest readable stored scan, or None.
    Read-only — tolerates a truncated findings tail like every other
    reader, and falls back past a corrupt/partial newest dir rather than
    claiming no scans exist."""
    scans = store.base_dir() / "scans"
    try:
        dirs = sorted((p for p in scans.iterdir() if p.is_dir()),
                      reverse=True)
    except OSError:
        return None
    for d in dirs:
        try:
            meta = json.loads((d / "meta.json").read_text())
            raw = (d / "findings.ndjson").read_text()
        except (OSError, json.JSONDecodeError):
            continue
        findings = []
        for line in raw.splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                findings.append(row)
        return meta, findings
    return None


class _Parser(argparse.ArgumentParser):
    """Bad arguments must return the operational exit code (2), never
    SystemExit, and complain on `out` rather than stderr."""
    def error(self, message):
        raise ValueError(message)


def cmd_scan(argv, out):
    p = _Parser(prog="llmsnitch scan", add_help=False)
    p.add_argument("roots", nargs="*")
    p.add_argument("--format", dest="fmt", default="text",
                   choices=("text", "json"))
    p.add_argument("--fail-on", dest="fail_on", default="high",
                   choices=tuple(_SEVERITY_RANK))
    p.add_argument("--rebaseline", action="store_true")
    p.add_argument("--report", action="store_true")
    p.add_argument("--patrol", dest="patrol_run", action="store_true")
    try:
        a = p.parse_args(argv)
    except ValueError as e:
        out.write(f"[ERROR] {e}\n")
        return 2
    for r in a.roots:
        if not Path(os.path.expanduser(r)).exists():
            out.write(f"[ERROR] no such root: {r}\n")
            return 2

    if a.report:
        if a.roots or a.rebaseline:
            out.write("[ERROR] --report reads the stored scan — "
                      "drop ROOT/--rebaseline\n")
            return 2
        loaded = _load_latest_scan()
        if loaded is None:
            out.write("[ERROR] no stored scans — run `llmsnitch scan` first\n")
            return 2
        meta, findings = loaded
    else:
        meta, findings = run_scan(a.roots or None, a.rebaseline,
                                  "patrol" if a.patrol_run else "manual")
    out.write({"text": to_text, "json": to_json}[a.fmt](meta, findings))

    threshold = _SEVERITY_RANK[a.fail_on]
    breach = any(not f.get("resolved")
                 and _SEVERITY_RANK.get(f["severity"], 0) >= threshold
                 for f in findings)
    rc = 1 if breach else 0
    if a.patrol_run:
        # The daily patrol carries both surfaces in one process (T508).
        # Worst verdict wins; a breach (1) in either surface is never
        # masked by an operational failure (2) in the other.
        from . import depaudit
        dep_rc = depaudit.cmd_depaudit(["--format", a.fmt], out)
        rc = 1 if 1 in (rc, dep_rc) else max(rc, dep_rc)
    return rc
