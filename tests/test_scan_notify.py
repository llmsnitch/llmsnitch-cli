#!/usr/bin/env python3
"""Track-A guards: config-audit scan findings route through notify().

Run: python3 tests/test_scan_notify.py
"""

import io
import json
import os
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from fs_coil import notify as nf  # noqa: E402
from llmsnitch import scan        # noqa: E402


def _with_tmp(fn):
    """LLMSNITCH_DIR (scan store) + the notify seams from test_notify.py,
    cold_start=0 so first-seen findings may banner, _deliver stubbed."""
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        (t / "cache").mkdir()
        (t / "config.ini").write_text("[notify]\ncold_start = 0\n")
        env = {"LLMSNITCH_DIR": str(t / "store"),
               "LLMSNITCH_NOTIFY_DIR": str(t / "notify"),
               "LLMSNITCH_HOT_STATE": str(t / "cache" / "notify-state.json"),
               "LLMSNITCH_CONFIG": str(t / "config.ini")}
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        delivered, errors = [], []
        old_deliver, old_log = nf._deliver, nf._log_error
        nf._deliver = lambda *a, **k: delivered.append(a)
        nf._log_error = errors.append
        try:
            fn(t, delivered)
        finally:
            nf._deliver, nf._log_error = old_deliver, old_log
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


def _ledger(t):
    out = []
    for f in sorted((t / "notify").glob("events-*.ndjson")):
        out += [json.loads(line) for line in f.read_text().splitlines()]
    return out


def _seed(root):
    cdir = root / ".claude"
    cdir.mkdir(parents=True)
    (cdir / "settings.json").write_text(json.dumps({
        "permissions": {"allow": ["Bash(*)"],
                        "defaultMode": "bypassPermissions"}}))
    sk = cdir / "skills" / "helper"
    sk.mkdir(parents=True)
    (sk / "SKILL.md").write_text(
        "---\nname: helper\nallowed-tools: Read\n---\nrun things\n"
        "```bash\ncurl example.com\n```\n")


def test_scan_findings_become_ledger_rows_one_banner():
    """N findings → N scan_finding ledger rows; one actor bucket → ≤1
    banner; low-severity non-drift findings are record_only."""
    def body(t, delivered):
        root = t / "proj"
        _seed(root)
        assert scan.cmd_scan([str(root)], io.StringIO()) == 1
        scan_rows = [r for r in _ledger(t) if r["category"] == "scan_finding"]
        nd = next((t / "store" / "scans").iterdir()) / "findings.ndjson"
        findings = [json.loads(x) for x in nd.read_text().splitlines()
                    if not json.loads(x).get("resolved")]
        assert len(scan_rows) == len(findings) >= 3, (
            len(scan_rows), len(findings))
        assert len(delivered) == 1, [d[2] for d in delivered]
        assert all(r["surface"] == "config-audit" for r in scan_rows)
        low = [r for r in scan_rows
               if r["subject"].startswith("skill_undeclared_bash")]
        assert low and all(r.get("record_only") for r in low), low
        crit = [r for r in scan_rows
                if r["subject"].startswith("wildcard_bash_grant")]
        assert crit and not any(r.get("record_only") for r in crit)
        assert sum(1 for r in scan_rows if r["notified"]) == 1
    _with_tmp(body)


def test_drift_is_never_record_only():
    """A changed control file emits drift_changed through notify() without
    record_only — drift always names a decision (rebaseline or revert)."""
    def body(t, delivered):
        root = t / "proj"
        _seed(root)
        scan.cmd_scan([str(root)], io.StringIO())
        sj = root / ".claude" / "settings.json"
        sj.write_text(sj.read_text() + "\n")
        scan.cmd_scan([str(root)], io.StringIO())
        drift = [r for r in _ledger(t)
                 if r["category"] == "scan_finding"
                 and r["subject"].startswith("drift_changed")]
        assert drift, "drift_changed never reached the notify ledger"
        assert not any(r.get("record_only") for r in drift), drift
    _with_tmp(body)


def test_notifier_failure_never_breaks_scan():
    """notify() fails closed; the scan run and its own report survive a
    poisoned notify environment untouched."""
    def body(t, delivered):
        root = t / "proj"
        _seed(root)
        os.environ["LLMSNITCH_HOT_STATE"] = "/dev/null/not/a/dir/state.json"
        buf = io.StringIO()
        rc = scan.cmd_scan([str(root)], buf)
        assert rc == 1, "scan verdict changed by notifier failure"
        assert "wildcard_bash_grant" in buf.getvalue()
    _with_tmp(body)


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
