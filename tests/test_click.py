#!/usr/bin/env python3
"""T901 guards: a banner click opens the newest digest (wayfinder/
notification-click D01–D06). Stdlib only, no root, no banners posted.

Run: python3 tests/test_click.py
"""

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from fs_coil import notify as nf  # noqa: E402
from fs_coil import notifier  # noqa: E402
from tests._seams import with_tmp as _with_tmp, run  # noqa: E402

_REAL_DELIVER = nf._deliver   # with_tmp stubs nf._deliver; keep the real one


def _seed_digests(t, *stamps):
    d = t / "notify"
    d.mkdir(mode=0o700, exist_ok=True)
    for s in stamps:
        (d / f"digest-{s}.txt").write_text("digest\n")
    return d


def test_argv_carries_open_and_never_sender():
    for root in ((501, "alice"), None):
        argv = notifier._argv("t", "m", "g", None, "file:///x/digest-2026-09-22.txt", root)
        assert argv[-2:] == ["-open", "file:///x/digest-2026-09-22.txt"], argv
        assert "-sender" not in argv, argv
        assert argv.count("-title") == 1 and "-group" in argv, argv
    argv = notifier._argv("t", "m", "g", None, None, (501, "alice"))
    assert "-open" not in argv and "-sender" not in argv, argv
    assert argv[:6] == ["/bin/launchctl", "asuser", "501", "/usr/bin/sudo", "-u", "alice"], argv
    argv = notifier._argv("t", "m", "g", "/tmp/i.png", None, None)
    assert argv[-2:] == ["-contentImage", "/tmp/i.png"], argv


def test_click_url_is_newest_digest_or_none():
    def body(t, delivered, errors):
        assert nf._click_url() is None                 # no dir yet
        d = _seed_digests(t, "2026-09-20", "2026-09-22", "2026-09-21")
        (d / "digest-latest.txt").write_text("x")        # wrong shape: ignored
        (d / "events-2026-09-23.ndjson").write_text("")   # ledger, not digest
        assert nf._click_url() == "file://" + str(d / "digest-2026-09-22.txt")
    _with_tmp(body)


def test_click_url_unreadable_dir_is_best_effort():
    def body(t, delivered, errors):
        d = _seed_digests(t, "2026-09-22")
        os.chmod(d, 0o000)
        try:
            assert nf._click_url() is None
        finally:
            os.chmod(d, 0o700)
    if os.geteuid() != 0:
        _with_tmp(body)


def test_deliver_passes_url_untouched_by_hostile_subject():
    captured = []

    class _Fake:
        def notify(self, title, message, key, **kw):
            captured.append(kw)

    def body(t, delivered, errors):
        d = _seed_digests(t, "2026-09-22")
        old_cls, notifier.Notifier = notifier.Notifier, _Fake
        try:
            for subj in ("; open http://x", "../../etc/passwd",
                         "file:///tmp/evil.txt", "digest-2099-01-01.txt"):
                _REAL_DELIVER("config-audit", "scan_finding", subj, "unknown",
                              None, None, None, None, None, None)
        finally:
            notifier.Notifier = old_cls
        assert len(captured) == 4
        want = "file://" + str(d / "digest-2026-09-22.txt")
        assert all(c["open_url"] == want for c in captured), captured
    _with_tmp(body)


def test_notify_still_pages_and_ledgers_without_a_digest():
    def body(t, delivered, errors):
        assert nf.notify("config-audit", "scan_finding", "s1", _now=1_755_600_000.0)
        assert delivered and not errors
    _with_tmp(body)


if __name__ == "__main__":
    sys.exit(run(globals()))
