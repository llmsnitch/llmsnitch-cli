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

from fs_coil import ledger, notifier  # noqa: E402
from fs_coil import notify as nf  # noqa: E402
from tests._seams import with_tmp as _with_tmp, rows as _rows, run  # noqa: E402

_REAL_DELIVER = nf._deliver   # with_tmp stubs nf._deliver; keep the real one


def _seed_digests(d, *names):
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    for n in names:
        (d / n).write_text("digest\n")
    return d


def test_argv_carries_open_and_never_sender():
    url = "file:///x/digest-2026-09-22.txt"
    for root in ((501, "alice"), None):
        argv = notifier._argv("t", "[m", "g", "/tmp/i.png", url, root)
        assert argv[-4:] == ["-contentImage", "/tmp/i.png", "-open", url], argv
        assert "-sender" not in argv and argv.count("-title") == 1, argv
    assert argv[:6] == ["/bin/launchctl", "asuser", "501", "/usr/bin/sudo", "-u", "alice"] \
        or root is None
    assert "-open" not in notifier._argv("t", "m", "g", None, None, None)


def test_digest_files_are_date_shaped_only():
    def body(t, delivered, errors):
        d = _seed_digests(t / "notify", "digest-2026-09-22.txt", "digest-2026-09-20.txt",
                          "digest-YYYY-MM-DD.txt", "digest-zzzz-zz-zz.txt",
                          "digest-latest.txt", "events-2026-09-23.ndjson")
        got = [os.path.basename(p) for p in ledger.digest_files(str(d))]
        assert got == ["digest-2026-09-20.txt", "digest-2026-09-22.txt"], got
        assert ledger.digest_files(str(t / "missing")) == []
    _with_tmp(body)


def test_click_url_is_escaped_uri_or_none():
    def body(t, delivered, errors):
        assert notifier._click_url() is None              # first day: no digest
        d = _seed_digests(t / "My Logs" / "notify", "digest-2026-09-21.txt",
                          "digest-2026-09-22.txt")
        os.environ["LLMSNITCH_NOTIFY_DIR"] = str(d)        # with_tmp restores it
        url = notifier._click_url()
        assert url == (d / "digest-2026-09-22.txt").as_uri(), url
        assert url.startswith("file:///") and "%20" in url and " " not in url, url
    _with_tmp(body)


def test_click_url_is_best_effort():
    old = ledger.digest_files

    def boom(_):
        raise RuntimeError("listing failed")
    ledger.digest_files = boom
    try:
        assert notifier._click_url() is None
    finally:
        ledger.digest_files = old


def test_deliver_never_passes_a_row_derived_target():
    captured = []

    class _Fake:
        def notify(self, title, message, key, **kw):
            captured.append((message, kw))

    def body(t, delivered, errors):
        nf._deliver = _REAL_DELIVER                        # with_tmp restores the stub
        old, notifier.Notifier = notifier.Notifier, _Fake
        try:
            got = [nf.notify("config-audit", "scan_finding", subj, _now=1_755_600_000.0 + i)
                   for i, subj in enumerate(("; open http://x", "file:///tmp/evil.txt",
                                             "digest-2099-01-01.txt"))]
        finally:
            notifier.Notifier = old
        assert got == [True, False, False] and not errors, (got, errors)   # one page; repeats windowed
        assert len(captured) == 1
        message, kw = captured[0]
        assert "open_url" not in kw, kw                     # target is Notifier's default only
        assert "; open http://x" in message
        assert len(_rows(t)) == 3 and _rows(t)[0]["notified"] is True
    _with_tmp(body)


if __name__ == "__main__":
    sys.exit(run(globals()))
