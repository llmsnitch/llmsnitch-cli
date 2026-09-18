"""llmsnitch depaudit — the dep-audit surface: intakes × bulletin.

  llmsnitch depaudit [--format text|json]
                     [--waive ID PACKAGE --reason TEXT]

Findings are recomputed from scratch each run: sweep intakes from stored
sessions (intake.sweep), read the verified bulletin cache (bulletin.load —
fetch wiring is T508's), join intake-attributed distributions against
bulletin entries, and gate criticality on machine-local evidence:

    critical = (malicious AND intake) OR (intake AND kev.listed AND exercised)

Everything else is a lesser finding: visible here and in the notify ledger
(record_only, for the future digest), never paging. Waivers — (advisory x
package) + required reason in <base>/waivers.json — silence findings; a
waived finding re-raises on severity-band escalation or kev.listed
false->true, never on EPSS movement. Missing/unverifiable bulletin is an
operational condition (exit 2), never a crash. Exit: 0 pass / 1 critical /
2 operational — the gate contract.
"""

import glob
import json
import os
import re
import stat
from importlib.metadata import distributions
from pathlib import Path

from . import bulletin, intake, store
from .scan import _Parser

_SEV_RANK = {None: 0, "low": 1, "moderate": 2, "high": 3, "critical": 4}
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
              "dist", "build", "target"}
_MAX_FILES = 4000
_MAX_DEPTH = 6
_MAX_SRC = 1_000_000   # bytes; a bigger "source file" is not project source
# Everything user-facing here quotes attacker-influenced strings (bulletin
# entries, dist-info metadata, command-derived paths): control chars would
# let a finding erase itself from a terminal (ANSI) — flatten them.
_CTRL = re.compile(r"[\x00-\x1f\x7f]")
# T505 evidence B: any python/pytest/`uv run` execution in the project's
# sessions after the intake ts. Head-token match per segment — a command
# merely *mentioning* python (`pip install python-dateutil`) is not a run.
_ENV_ASSIGN = re.compile(r"\w+=")
_PY_HEAD = re.compile(r"python3?(\.\d+)?")
_IMPORT_RE = re.compile(r"^\s*(?:import\s+([\w.,\s]+)|from\s+([\w.]+)\s+import)",
                        re.MULTILINE)


# -- env reading (the dist-info join: intake is the claim, disk is the fact) --

def _safe(v):
    return _CTRL.sub(" ", v) if isinstance(v, str) else v


def _site_packages(env):
    hits = glob.glob(os.path.join(glob.escape(env),
                                  "lib", "python3*", "site-packages"))
    return sorted(hits)


def _installed(env):
    """PEP 503 name -> (version, Distribution) for one env; {} if unreadable."""
    sps = _site_packages(env)
    if not sps:
        return {}
    out = {}
    try:
        for dist in distributions(path=sps):
            try:
                name = dist.metadata["Name"]
                if not name:
                    continue
                out[bulletin.normalize_name(name)] = (dist.version or "", dist)
            except Exception:  # noqa: BLE001 — one broken dist-info, not the env
                continue
    except Exception:  # noqa: BLE001
        return {}
    return out


def _import_names(dist, package):
    """Import names a dist provides: top_level.txt, fallback RECORD top
    segments (top_level.txt covers only ~45% of dists — the fallback is
    mandatory, T505)."""
    try:
        text = dist.read_text("top_level.txt")
    except Exception:  # noqa: BLE001
        text = None
    if text:
        names = {n.strip() for n in text.split() if n.strip()}
        if names:
            return names
    names = set()
    try:
        record = dist.read_text("RECORD") or ""
    except Exception:  # noqa: BLE001
        record = ""
    for line in record.splitlines():
        path = line.split(",", 1)[0]
        if not path or path.startswith("..") or ".dist-info" in path:
            continue
        top = path.split("/", 1)[0]
        if top.endswith(".py"):
            names.add(top[:-3])
        elif "/" in path:
            names.add(top)
    return names or {package.replace("-", "_")}


# -- exercised evidence (T505: A source-import OR B project-ran-after) --------

def _project_imports(cwd):
    """Top-level module names imported anywhere in the project tree."""
    names, budget = set(), [_MAX_FILES]
    root = Path(cwd)
    base_depth = len(root.parts)
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            budget[0] -= 1   # count directories too: cwd near / must not
            if budget[0] < 0:   # walk a large slice of the disk
                break
            if len(Path(dirpath).parts) - base_depth >= _MAX_DEPTH:
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in sorted(dirnames)
                           if d not in _SKIP_DIRS and not d.startswith(".")]
            for fn in filenames:
                if not fn.endswith(".py"):
                    continue
                budget[0] -= 1
                if budget[0] < 0:
                    break
                p = Path(dirpath) / fn
                try:
                    st = os.lstat(p)
                    # Regular files only — a FIFO named *.py blocks open()
                    # forever; symlinks can point at devices.
                    if not stat.S_ISREG(st.st_mode) or st.st_size > _MAX_SRC:
                        continue
                    text = p.read_text(errors="replace")
                except OSError:
                    continue
                for m in _IMPORT_RE.finditer(text):
                    if m.group(2):
                        names.add(m.group(2).split(".", 1)[0])
                    else:
                        for part in m.group(1).split(","):
                            part = part.strip().split(" as ")[0]
                            if part:
                                names.add(part.split(".", 1)[0])
    except OSError:
        pass
    return names


def _is_run(cmd):
    """True when some segment actually EXECUTES python/pytest/uv-run."""
    for seg in re.split(r"&&|;|\|", cmd):
        toks = seg.split()
        while toks and _ENV_ASSIGN.match(toks[0]):
            toks.pop(0)
        if not toks:
            continue
        head = os.path.basename(toks[0])
        if _PY_HEAD.fullmatch(head) or head == "pytest":
            return True
        if head == "uv" and toks[1:2] == ["run"]:
            return True
    return False


def _run_timestamps(cwd):
    """Sorted ts of python/pytest/uv-run Bash events across the project's
    sessions (meta.cwd == cwd)."""
    ts_list = []
    try:
        for sid, _ in store.list_sessions():
            if store.read_meta(sid).get("cwd", "") != cwd:
                continue
            for ev in store.iter_events(sid):
                if ev.get("event") != "PreToolUse" or ev.get("tool") != "Bash":
                    continue
                inp = ev.get("input")
                cmd = inp.get("command") if isinstance(inp, dict) else None
                ts = ev.get("ts")
                if isinstance(cmd, str) and _is_run(cmd) \
                        and isinstance(ts, (int, float)):
                    ts_list.append(float(ts))
    except OSError:
        pass
    ts_list.sort()
    return ts_list


def _exercised(cwd, intake_ts, dist, package):
    if not cwd:
        return False
    if _project_imports(cwd) & _import_names(dist, package):
        return True
    runs = _run_timestamps(cwd)
    return bool(runs) and runs[-1] > (intake_ts or 0)


# -- waivers ------------------------------------------------------------------

def _waivers_path():
    return store.base_dir() / "waivers.json"


def _waivers_raw():
    """Every row in the shared file — config-audit rows included (D05,
    wayfinder/quiet-patrol). Writers append to this, never to the filtered
    view, or they silently drop the other surface's waivers."""
    try:
        raw = json.loads(_waivers_path().read_text())
    except (OSError, json.JSONDecodeError):
        return []
    return raw if isinstance(raw, list) else []


def load_waivers():
    """Well-formed dep-audit waivers only: str id, package, non-empty reason.
    The file is user-editable; malformed rows are ignored, never trusted to
    silence."""
    return [w for w in _waivers_raw()
            if isinstance(w, dict)
            and isinstance(w.get("id"), str)
            and isinstance(w.get("package"), str)
            and isinstance(w.get("reason"), str) and w["reason"].strip()]


def _waiver_for(waivers, entry, package):
    ids = {entry.get("id")} | set(entry.get("aliases") or [])
    for w in waivers:
        if w["id"] in ids and bulletin.normalize_name(w["package"]) == package:
            return w
    return None


def _reraised(waiver, entry):
    """Exactly two transitions re-raise (T503): severity-band escalation or
    kev.listed false->true. A hand-added waiver without snapshot fields has
    no baseline — it never re-raises (written eyes-open at current state)."""
    if "severity_label" not in waiver and "kev_listed" not in waiver:
        return False
    cur_sev = _SEV_RANK.get((entry.get("severity") or {}).get("label"), 0)
    if cur_sev > _SEV_RANK.get(waiver.get("severity_label"), 0):
        return True
    kev_now = bool((entry.get("kev") or {}).get("listed"))
    return kev_now and not waiver.get("kev_listed")


def add_waiver(adv_id, package, reason, out):
    """Append a waiver, snapshotting the entry's current severity/kev so the
    re-raise triggers have a baseline (T503 judgment call)."""
    package = bulletin.normalize_name(package)
    w = {"id": adv_id, "package": package, "reason": reason,
         "added_ts": store.now()}
    bl, _ = bulletin.load()
    if bl:
        for entry in bulletin.index(bl).get(package, []):
            if adv_id in {entry.get("id")} | set(entry.get("aliases") or []):
                w["severity_label"] = (entry.get("severity") or {}).get("label")
                w["kev_listed"] = bool((entry.get("kev") or {}).get("listed"))
                break
    waivers = _waivers_raw()
    waivers.append(w)
    store._mkdir_private(store.base_dir())
    p = _waivers_path()
    p.write_text(json.dumps(waivers, indent=2))
    store._chmod_private(p)
    out.write(f"waived {adv_id} x {package}\n")
    return 0


def _stamp_state(meta, findings, note):
    """Health stamp the digest reads (fs_coil never imports us). A failed
    stamp never changes the exit code."""
    try:
        store._mkdir_private(store.base_dir())
        p = store.base_dir() / "depaudit-state.json"
        with os.fdopen(store._open_private(p, os.O_WRONLY | os.O_TRUNC), "w") as fh:
            fh.write(json.dumps({
                "ts": store.now(), "bulletin_age_days": meta.get("bulletin_age_days"),
                "intakes": meta.get("intakes"), "envs": meta.get("envs"),
                "findings": len(findings),
                "findings_critical": sum(1 for f in findings
                                         if f.get("critical") and not f.get("waived")),
                "note": note}))
        store._chmod_private(p)
    except OSError:
        pass


# -- the audit ----------------------------------------------------------------

def run_audit():
    """(meta, findings, note). note is the operational reason when the
    bulletin is unusable — findings are then [] and the caller exits 2."""
    intake.sweep()
    intakes = intake.read_intakes()
    for it in intakes:   # hand-edited rows: a str ts must not poison compares
        if not isinstance(it.get("ts"), (int, float)):
            it["ts"] = 0.0
    bl, note = bulletin.load()
    meta = {"intakes": len(intakes), "envs": 0, "bulletin_age_days": None}
    if bl is None:
        return meta, [], note
    meta["bulletin_age_days"] = bulletin.age_days(bl.get("meta") or {})
    idx = bulletin.index(bl)
    waivers = load_waivers()

    # Attribute packages per env: specific intakes name one package; bulk
    # intakes attribute every dist in the env. Earliest ts wins (most
    # generous "ran after install" baseline — recall over precision, T505).
    by_env = {}
    for it in intakes:
        env = it.get("env_hint") or "unresolved"
        if env != "unresolved":
            by_env.setdefault(env, []).append(it)

    findings = []
    for env, its in sorted(by_env.items()):
        installed = _installed(env)
        if not installed:
            continue   # env gone or unreadable — the claim found no fact
        meta["envs"] += 1
        attributed = {}   # package -> intake (earliest)
        for it in its:
            pkgs = installed if it.get("bulk") else (
                [it["package"]] if it.get("package") in installed else [])
            for p in pkgs:
                cur = attributed.get(p)
                if cur is None or (it.get("ts") or 0) < (cur.get("ts") or 0):
                    attributed[p] = it
        for package, it in sorted(attributed.items()):
            version, dist = installed[package]
            for entry in bulletin.match(idx.get(package, []), version):
                findings.append(_finding(entry, package, version, env, it,
                                         dist, waivers))
    findings.sort(key=lambda f: (not f["critical"], f["package"], f["id"]))
    return meta, findings, None


def _finding(entry, package, version, env, it, dist, waivers):
    kev = bool((entry.get("kev") or {}).get("listed"))
    malicious = entry.get("class") == "malicious"
    # Exercised only gates the KEV clause — malicious pages on install alone
    # (T505: the install IS the abuse), so don't pay the scan for the rest.
    exercised = (kev and not malicious
                 and _exercised(it.get("cwd", ""), it.get("ts"), dist, package))
    critical = malicious or (kev and exercised)
    w = _waiver_for(waivers, entry, package)
    reraised = bool(w and _reraised(w, entry))
    return {"v": 1, "ts": store.now(), "id": _safe(entry.get("id")),
            "aliases": [_safe(a) for a in entry.get("aliases") or []],
            "package": _safe(package), "ecosystem": "PyPI",
            "class": _safe(entry.get("class")),
            "installed_version": _safe(version), "env": _safe(env),
            "critical": critical, "kev_listed": kev, "exercised": exercised,
            "severity_label": _safe((entry.get("severity") or {}).get("label")),
            "waived": bool(w) and not reraised, "reraised": reraised,
            "summary": _safe(entry.get("summary")),
            "url": _safe(entry.get("url")),
            "intake_ts": it.get("ts"), "session_id": _safe(it.get("session_id")),
            "harness": _safe(it.get("harness", "claude-code"))}


def _route_to_notifier(findings):
    """Every finding becomes a notify ledger row (digest fodder); only
    unwaived criticals may banner — lesser and waived rows are record_only.
    Returns False when the notify layer is unavailable (recorded in meta so
    silence stays discoverable — scan.py discipline)."""
    try:
        from fs_coil import notify as fs_notify
    except Exception:  # noqa: BLE001
        return False
    for f in findings:
        quiet = not f["critical"] or f["waived"]
        # Row severity is the category default — the finding's own tier
        # travels in the subject (scan.py discipline, digest reads it).
        fs_notify.notify(
            "dep-audit", "depaudit_finding",
            f"{'' if quiet else 'critical '}{f['class']}: {f['package']} "
            f"{f['installed_version']} ({f['id']})",
            actor_bucket=f.get("harness", "unknown"),
            record_only=quiet)
    return True


# -- emitters -----------------------------------------------------------------

def to_text(meta, findings):
    age = meta.get("bulletin_age_days")
    age_s = f"{age:.1f}d" if age is not None else "unknown"
    lines = [f"dep-audit: {meta['intakes']} intakes, {meta['envs']} envs, "
             f"bulletin age {age_s}"]
    if meta.get("notify_routed") is False:
        lines.append("note: notify layer unavailable — findings shown here only")
    if not findings:
        lines.append("[OK] no findings")
    else:
        for f in findings:
            tag = "CRITICAL" if f["critical"] else (f["severity_label"]
                                                    or f["class"] or "?")
            flags = []
            if f["kev_listed"]:
                flags.append("kev")
            if f["exercised"]:
                flags.append("exercised")
            if f["waived"]:
                flags.append("waived")
            if f["reraised"]:
                flags.append("RERAISED")
            lines.append(f"[{tag.upper()}] {f['package']} "
                         f"{f['installed_version']} {f['id']} "
                         f"({f['class']}{', ' + ', '.join(flags) if flags else ''})"
                         f"  {f['env']}")
        crit = sum(1 for f in findings if f["critical"] and not f["waived"])
        waived = sum(1 for f in findings if f["waived"])
        lines.append(f"findings: critical={crit}, "
                     f"lesser={len(findings) - crit - waived}, waived={waived}")
    return "\n".join(lines) + "\n"


def to_json(meta, findings):
    return json.dumps({"meta": meta, "findings": findings}, indent=2) + "\n"


# -- CLI ----------------------------------------------------------------------

def cmd_depaudit(argv, out):
    p = _Parser(prog="llmsnitch depaudit", add_help=False)
    p.add_argument("--format", dest="fmt", default="text",
                   choices=("text", "json"))
    p.add_argument("--waive", nargs=2, metavar=("ID", "PACKAGE"))
    p.add_argument("--reason", default="")
    try:
        a = p.parse_args(argv)
    except ValueError as e:
        out.write(f"[ERROR] {e}\n")
        return 2

    if a.waive:
        if not a.reason.strip():
            out.write("[ERROR] --waive requires --reason\n")
            return 2
        return add_waiver(a.waive[0], a.waive[1], a.reason.strip(), out)

    try:
        meta, findings, note = run_audit()
    except Exception as e:  # noqa: BLE001 — hostile inputs may still find a
        # path the shape-normalizers missed; a crash must read as
        # operational, never as a breach, and never as a clean pass.
        out.write(f"[ERROR] audit failed: {type(e).__name__}\n")
        return 2
    _stamp_state(meta, findings, note)
    if note:
        out.write(f"[ERROR] {note} — run the weekly refresh (T508) or check "
                  f"{bulletin.default_path()}\n")
        return 2
    meta["notify_routed"] = _route_to_notifier(findings)
    out.write({"text": to_text, "json": to_json}[a.fmt](meta, findings))
    return 1 if any(f["critical"] and not f["waived"] for f in findings) else 0
