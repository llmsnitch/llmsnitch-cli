"""Shared test scaffolding: notify-layer env seams + the stdlib runner.

Not a test file — imported by test_notify.py / test_scan_notify.py /
test_llmsnitch.py (each inserts the repo root on sys.path first).
"""

import json
import os
import tempfile
from pathlib import Path

from fs_coil import notify as nf


def with_tmp(fn, config="", store=False):
    """Tmp dirs + env seams + no-banner _deliver stub + captured
    NOTIFIER-ERROR. store=True also points LLMSNITCH_DIR at the tmp dir."""
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        (t / "cache").mkdir()
        (t / "config.ini").write_text(config or "[notify]\ncold_start = 0\n")
        env = {"LLMSNITCH_NOTIFY_DIR": str(t / "notify"),
               "LLMSNITCH_HOT_STATE": str(t / "cache" / "notify-state.json"),
               "LLMSNITCH_CONFIG": str(t / "config.ini")}
        if store:
            env["LLMSNITCH_DIR"] = str(t / "store")
        old_env = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        delivered, errors = [], []
        old_deliver, old_log = nf._deliver, nf._log_error
        nf._deliver = lambda *a, **k: delivered.append(a)
        nf._log_error = errors.append
        try:
            fn(t, delivered, errors)
        finally:
            nf._deliver, nf._log_error = old_deliver, old_log
            for k, v in old_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


def rows(t):
    out = []
    for f in sorted((t / "notify").glob("events-*.ndjson")):
        out += [json.loads(line) for line in f.read_text().splitlines()]
    return out


def state(t):
    return json.loads((t / "cache" / "notify-state.json").read_text())


def run(globs):
    """Run every test_* in globs; print PASS/FAIL lines; return exit code."""
    tests = sorted((v for k, v in globs.items()
                    if k.startswith("test_") and callable(v)),
                   key=lambda f: f.__name__)
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0
