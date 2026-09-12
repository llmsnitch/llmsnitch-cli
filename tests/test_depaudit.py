#!/usr/bin/env python3
"""Dep-audit surface guards: the criticality predicate end-to-end.

    critical = (malicious AND intake) OR (intake AND kev.listed AND exercised)

Seeded fake bulletin + fake session events + fake envs under a tmp
LLMSNITCH_DIR; findings route through fs_coil.notify (seamed).

Run: python3 tests/test_depaudit.py
"""

import gzip
import hashlib
import io
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from llmsnitch import depaudit  # noqa: E402
from tests._seams import rows as _rows, run, with_tmp  # noqa: E402


def _with_tmp(fn):
    with_tmp(fn, store=True)


def _write_bulletin(t, entries, issued_at="2026-09-12T00:00:00Z",
                    bad_hash=False):
    bdir = t / "store" / "bulletins"
    bdir.mkdir(parents=True, exist_ok=True)
    raw = gzip.compress(json.dumps(
        {"meta": {"schema_version": 1, "issued_at": issued_at},
         "entries": entries}).encode())
    (bdir / "pypi.json.gz").write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    if bad_hash:
        digest = "0" * 64
    (bdir / "pypi.json.gz.sha256").write_text(digest + "\n")


def _seed_session(t, sid, cwd, cmds, ts0=1000.0):
    sdir = t / "store" / "sessions" / sid
    sdir.mkdir(parents=True)
    with open(sdir / "events.ndjson", "w") as f:
        for i, c in enumerate(cmds):
            f.write(json.dumps({"ts": ts0 + i, "event": "PreToolUse",
                                "tool": "Bash",
                                "input": {"command": c}}) + "\n")
    (sdir / "meta.json").write_text(json.dumps(
        {"cwd": cwd, "harness": "claude-code"}))


def _seed_env(proj, dists):
    """proj/.venv with pyvenv.cfg + fake dist-infos. dists: [(name, ver)]."""
    env = proj / ".venv"
    sp = env / "lib" / "python3.11" / "site-packages"
    sp.mkdir(parents=True)
    (env / "pyvenv.cfg").write_text("home = /usr\n")
    for name, ver in dists:
        d = sp / f"{name}-{ver}.dist-info"
        d.mkdir()
        (d / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {ver}\n")
        (d / "top_level.txt").write_text(name.replace("-", "_") + "\n")
    return env


def _mal(name, mid="MAL-2026-0001"):
    return {"id": mid, "aliases": [], "ecosystem": "PyPI", "name": name,
            "class": "malicious", "all_versions": True,
            "summary": f"Malicious code in {name}"}


def _vuln(name, versions, kev=False, label="high", vid="CVE-2026-0001",
          aliases=()):
    e = {"id": vid, "aliases": list(aliases), "ecosystem": "PyPI",
         "name": name, "class": "vulnerability", "versions": versions,
         "severity": {"label": label, "vectors": [], "source": "GHSA"}}
    if kev:
        e["kev"] = {"listed": True, "date_added": "2026-01-01",
                    "ransomware": False}
    return e


def _audit(t, fmt="text"):
    out = io.StringIO()
    rc = depaudit.cmd_depaudit(["--format", fmt], out)
    return rc, out.getvalue()


def test_malicious_intake_pages_critical_bypassing_gate():
    """malicious AND intake = critical immediately — no KEV, no exercised
    (T505 d3); routes one banner through notify."""
    def body(t, delivered, errors):
        proj = t / "proj"
        _seed_env(proj, [("evilpkg", "1.0")])
        _seed_session(t, "s1", str(proj), ["pip install evilpkg"])
        _write_bulletin(t, [_mal("evilpkg")])
        rc, text = _audit(t)
        assert rc == 1, (rc, text)
        assert "[CRITICAL] evilpkg" in text, text
        crit_rows = [r for r in _rows(t) if r["category"] == "depaudit_finding"]
        assert len(crit_rows) == 1 and not crit_rows[0].get("record_only")
        assert crit_rows[0]["severity"] == "critical"
        assert len(delivered) == 1, [d[2] for d in delivered]
    _with_tmp(body)


def test_kev_exercised_is_critical():
    """intake AND kev.listed AND exercised (source imports it) = critical."""
    def body(t, delivered, errors):
        proj = t / "proj"
        _seed_env(proj, [("kevpkg", "2.0")])
        (proj / "app.py").write_text("import kevpkg\n")
        _seed_session(t, "s1", str(proj), ["pip install kevpkg"])
        _write_bulletin(t, [_vuln("kevpkg", ["2.0"], kev=True)])
        rc, text = _audit(t)
        assert rc == 1, (rc, text)
        assert "[CRITICAL] kevpkg" in text, text
    _with_tmp(body)


def test_kev_ran_after_install_is_exercised():
    """Evidence B: a python run in the project's sessions after intake ts."""
    def body(t, delivered, errors):
        proj = t / "proj"
        _seed_env(proj, [("kevpkg", "2.0")])
        _seed_session(t, "s1", str(proj),
                      ["pip install kevpkg", "python app.py"])
        _write_bulletin(t, [_vuln("kevpkg", ["2.0"], kev=True)])
        rc, text = _audit(t)
        assert rc == 1, (rc, text)
    _with_tmp(body)


def test_mention_of_python_is_not_a_run():
    """Evidence B must be an EXECUTION — a later install merely mentioning
    python (`pip install python-dateutil`) is not exercise."""
    def body(t, delivered, errors):
        proj = t / "proj"
        _seed_env(proj, [("kevpkg", "2.0")])
        _seed_session(t, "s1", str(proj),
                      ["pip install kevpkg",
                       "pip install python-dateutil",
                       "ls python && echo pytest-later"])
        _write_bulletin(t, [_vuln("kevpkg", ["2.0"], kev=True)])
        rc, text = _audit(t)
        assert rc == 0, (rc, text)   # lesser — never a critical
    _with_tmp(body)


def test_kev_unexercised_is_lesser_and_quiet():
    """intake AND kev but no exercise evidence: lesser — visible, record_only,
    exit 0 (the binary no-middle-tier decision, T505 d2)."""
    def body(t, delivered, errors):
        proj = t / "proj"
        _seed_env(proj, [("kevpkg", "2.0")])
        _seed_session(t, "s1", str(proj), ["pip install kevpkg"])
        _write_bulletin(t, [_vuln("kevpkg", ["2.0"], kev=True)])
        rc, text = _audit(t)
        assert rc == 0, (rc, text)
        assert "kevpkg" in text and "CRITICAL" not in text, text
        r = [r for r in _rows(t) if r["category"] == "depaudit_finding"]
        assert len(r) == 1 and r[0].get("record_only")
        assert not delivered
    _with_tmp(body)


def test_non_kev_vuln_is_lesser_even_exercised():
    def body(t, delivered, errors):
        proj = t / "proj"
        _seed_env(proj, [("vulnpkg", "1.5")])
        (proj / "app.py").write_text("import vulnpkg\n")
        _seed_session(t, "s1", str(proj), ["pip install vulnpkg"])
        _write_bulletin(t, [_vuln("vulnpkg", ["1.5"])])
        rc, text = _audit(t)
        assert rc == 0, (rc, text)
        assert "vulnpkg" in text and "CRITICAL" not in text, text
    _with_tmp(body)


def test_version_mismatch_no_finding():
    """The dist-info join is the oracle: installed 2.0 vs bulletin's 1.0."""
    def body(t, delivered, errors):
        proj = t / "proj"
        _seed_env(proj, [("vulnpkg", "2.0")])
        _seed_session(t, "s1", str(proj), ["pip install vulnpkg"])
        _write_bulletin(t, [_vuln("vulnpkg", ["1.0"])])
        rc, text = _audit(t)
        assert rc == 0 and "[OK] no findings" in text, (rc, text)
    _with_tmp(body)


def test_bulk_intake_attributes_whole_env():
    """`pip install -r requirements.txt` -> every dist in the env counts."""
    def body(t, delivered, errors):
        proj = t / "proj"
        _seed_env(proj, [("evilpkg", "1.0"), ("cleanpkg", "3.0")])
        _seed_session(t, "s1", str(proj), ["pip install -r requirements.txt"])
        _write_bulletin(t, [_mal("evilpkg")])
        rc, text = _audit(t)
        assert rc == 1 and "[CRITICAL] evilpkg" in text, (rc, text)
    _with_tmp(body)


def test_unresolved_intake_stays_quiet():
    """No env resolvable -> intake recorded, matches nothing, no finding."""
    def body(t, delivered, errors):
        proj = t / "proj"           # no venv seeded
        proj.mkdir()
        _seed_session(t, "s1", str(proj), ["pip install evilpkg"])
        _write_bulletin(t, [_mal("evilpkg")])
        rc, text = _audit(t)
        assert rc == 0 and "[OK] no findings" in text, (rc, text)
    _with_tmp(body)


def test_waiver_silences_critical():
    """Waived MAL finding: visible as waived, record_only, exit 0. The
    round-trip uses the CLI --waive path (required reason enforced)."""
    def body(t, delivered, errors):
        proj = t / "proj"
        _seed_env(proj, [("evilpkg", "1.0")])
        _seed_session(t, "s1", str(proj), ["pip install evilpkg"])
        _write_bulletin(t, [_mal("evilpkg")])
        assert depaudit.cmd_depaudit(
            ["--waive", "MAL-2026-0001", "evilpkg"], io.StringIO()) == 2
        assert depaudit.cmd_depaudit(
            ["--waive", "MAL-2026-0001", "evilpkg", "--reason",
             "known test fixture"], io.StringIO()) == 0
        rc, text = _audit(t)
        assert rc == 0, (rc, text)
        assert "waived" in text, text
        r = [r for r in _rows(t) if r["category"] == "depaudit_finding"]
        assert r and all(x.get("record_only") for x in r)
        assert not delivered
    _with_tmp(body)


def test_waiver_matches_alias():
    """Waiver written against any alias survives canonical-id churn."""
    def body(t, delivered, errors):
        proj = t / "proj"
        _seed_env(proj, [("kevpkg", "2.0")])
        (proj / "app.py").write_text("import kevpkg\n")
        _seed_session(t, "s1", str(proj), ["pip install kevpkg"])
        _write_bulletin(t, [_vuln("kevpkg", ["2.0"], kev=True,
                                  aliases=["GHSA-xxxx-yyyy-zzzz"])])
        assert depaudit.cmd_depaudit(
            ["--waive", "GHSA-xxxx-yyyy-zzzz", "kevpkg", "--reason", "ok"],
            io.StringIO()) == 0
        rc, text = _audit(t)
        assert rc == 0 and "waived" in text, (rc, text)
    _with_tmp(body)


def test_waiver_reraises_on_kev_flip():
    """kev.listed false->true after waiving re-raises (T503 d10)."""
    def body(t, delivered, errors):
        proj = t / "proj"
        _seed_env(proj, [("kevpkg", "2.0")])
        (proj / "app.py").write_text("import kevpkg\n")
        _seed_session(t, "s1", str(proj), ["pip install kevpkg"])
        _write_bulletin(t, [_vuln("kevpkg", ["2.0"], kev=False)])
        assert depaudit.cmd_depaudit(
            ["--waive", "CVE-2026-0001", "kevpkg", "--reason", "accepted"],
            io.StringIO()) == 0
        _write_bulletin(t, [_vuln("kevpkg", ["2.0"], kev=True)])
        rc, text = _audit(t)
        assert rc == 1, (rc, text)   # re-raised + exercised -> critical again
        assert "RERAISED" in text, text
    _with_tmp(body)


def test_waiver_reraises_on_severity_escalation():
    def body(t, delivered, errors):
        proj = t / "proj"
        _seed_env(proj, [("vulnpkg", "1.5")])
        _seed_session(t, "s1", str(proj), ["pip install vulnpkg"])
        _write_bulletin(t, [_vuln("vulnpkg", ["1.5"], label="low")])
        assert depaudit.cmd_depaudit(
            ["--waive", "CVE-2026-0001", "vulnpkg", "--reason", "low risk"],
            io.StringIO()) == 0
        _write_bulletin(t, [_vuln("vulnpkg", ["1.5"], label="critical")])
        rc, text = _audit(t)
        assert rc == 0, (rc, text)   # still lesser (no kev) — but unwaived
        assert "RERAISED" in text, text
    _with_tmp(body)


def test_hostile_entry_shapes_never_crash_or_evade():
    """Poisoned optional fields (kev as str, severity as str, unhashable
    aliases) degrade to absent — and must not suppress the legit MAL
    critical alongside them (crash-as-evasion)."""
    def body(t, delivered, errors):
        proj = t / "proj"
        _seed_env(proj, [("evilpkg", "1.0"), ("kevpkg", "2.0")])
        _seed_session(t, "s1", str(proj), ["pip install -r reqs.txt"])
        poisoned = _vuln("kevpkg", ["2.0"])
        poisoned["kev"] = "yes"
        poisoned["severity"] = "high"
        poisoned["aliases"] = [["nested"]]
        _write_bulletin(t, [poisoned, _mal("evilpkg")])
        rc, text = _audit(t)
        assert rc == 1, (rc, text)
        assert "[CRITICAL] evilpkg" in text, text
        assert depaudit.cmd_depaudit(   # --waive path crashed too (F1)
            ["--waive", "CVE-2026-0001", "kevpkg", "--reason", "x"],
            io.StringIO()) == 0
    _with_tmp(body)


def test_fifo_named_py_does_not_hang_import_scan():
    """A FIFO (or any non-regular file) named *.py must be skipped, not
    opened — open() on a FIFO blocks forever (F2)."""
    def body(t, delivered, errors):
        proj = t / "proj"
        _seed_env(proj, [("kevpkg", "2.0")])
        os.mkfifo(proj / "evil.py")
        _seed_session(t, "s1", str(proj), ["pip install kevpkg"])
        _write_bulletin(t, [_vuln("kevpkg", ["2.0"], kev=True)])
        rc, text = _audit(t)   # completing at all is the assertion
        assert rc == 0, (rc, text)
    _with_tmp(body)


def test_control_chars_flattened_in_output():
    """ANSI in bulletin ids must not reach the terminal or notify subjects —
    an entry could erase its own CRITICAL line (F5)."""
    def body(t, delivered, errors):
        proj = t / "proj"
        _seed_env(proj, [("evilpkg", "1.0")])
        _seed_session(t, "s1", str(proj), ["pip install evilpkg"])
        _write_bulletin(t, [_mal("evilpkg", mid="MAL-1\x1b[2K\x1b[1Aok")])
        rc, text = _audit(t)
        assert rc == 1 and "\x1b" not in text, (rc, repr(text))
        r = [r for r in _rows(t) if r["category"] == "depaudit_finding"]
        assert r and "\x1b" not in r[0]["subject"], r
    _with_tmp(body)


def test_string_ts_rows_tolerated():
    """Hand-edited intakes.ndjson / hostile event ts must not poison
    numeric compares (F4)."""
    def body(t, delivered, errors):
        proj = t / "proj"
        _seed_env(proj, [("kevpkg", "2.0")])
        sdir = t / "store" / "sessions" / "s1"
        sdir.mkdir(parents=True)
        with open(sdir / "events.ndjson", "w") as f:
            f.write(json.dumps({"ts": "yesterday", "event": "PreToolUse",
                                "tool": "Bash",
                                "input": {"command": "pip install kevpkg"}})
                    + "\n")
            f.write(json.dumps({"ts": "later", "event": "PreToolUse",
                                "tool": "Bash",
                                "input": {"command": "python app.py"}}) + "\n")
        (sdir / "meta.json").write_text(json.dumps(
            {"cwd": str(proj), "harness": "claude-code"}))
        _write_bulletin(t, [_vuln("kevpkg", ["2.0"], kev=True)])
        rc, text = _audit(t)
        assert rc in (0, 1), (rc, text)   # any verdict, never a traceback
    _with_tmp(body)


def test_missing_bulletin_is_operational():
    def body(t, delivered, errors):
        _seed_session(t, "s1", str(t / "proj"), ["pip install x"])
        rc, text = _audit(t)
        assert rc == 2 and "[ERROR]" in text, (rc, text)
    _with_tmp(body)


def test_hash_mismatch_is_operational():
    def body(t, delivered, errors):
        proj = t / "proj"
        _seed_env(proj, [("evilpkg", "1.0")])
        _seed_session(t, "s1", str(proj), ["pip install evilpkg"])
        _write_bulletin(t, [_mal("evilpkg")], bad_hash=True)
        rc, text = _audit(t)
        assert rc == 2 and "[ERROR]" in text, (rc, text)
    _with_tmp(body)


def test_bulletin_age_stamped():
    def body(t, delivered, errors):
        proj = t / "proj"
        _seed_env(proj, [("cleanpkg", "1.0")])
        _seed_session(t, "s1", str(proj), ["pip install cleanpkg"])
        _write_bulletin(t, [], issued_at="2026-09-01T00:00:00Z")
        rc, text = _audit(t)
        assert rc == 0 and "bulletin age" in text, (rc, text)
        assert "unknown" not in text.splitlines()[0], text
    _with_tmp(body)


if __name__ == "__main__":
    sys.exit(run(globals()))
