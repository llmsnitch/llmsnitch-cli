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


def test_argv_carries_open_uri_and_never_sender():
    path = "/x/My Logs/digest-2026-09-22.html"
    for root in ((501, "alice"), None):
        argv = notifier._argv("t", "m", "g", "/tmp/i.png", path, root)
        assert argv[-4:] == ["-contentImage", "/tmp/i.png", "-open",
                             "file:///x/My%20Logs/digest-2026-09-22.html"], argv   # escaped, or the banner dies
        assert "-sender" not in argv and "-execute" not in argv and argv.count("-title") == 1, argv
    assert argv[:6] == ["/bin/launchctl", "asuser", "501", "/usr/bin/sudo", "-u", "alice"] \
        or root is None
    assert "-open" not in notifier._argv("t", "m", "g", None, None, None)


def test_argv_escapes_plist_looking_message_leads():
    for lead in '[({"-<':
        argv = notifier._argv("[title ok", f"{lead}rest", "g", None, None, None)
        assert argv[argv.index("-message") + 1] == f"\\{lead}rest", argv
        assert argv[argv.index("-title") + 1] == "[title ok", argv   # -title is not misread
    for lead in "'@a~/":
        argv = notifier._argv("t", f"{lead}rest", "g", None, None, None)
        assert argv[argv.index("-message") + 1] == f"{lead}rest", argv


def test_digest_files_are_date_shaped_only():
    def body(t, delivered, errors):
        d = _seed_digests(t / "notify", "digest-2026-09-22.txt", "digest-2026-09-20.txt",
                          "digest-2026-09-22.html", "digest-YYYY-MM-DD.txt",
                          "digest-zzzz-zz-zz.html", "digest-latest.txt",
                          "events-2026-09-23.ndjson")
        got = [os.path.basename(p) for p in ledger.digest_files(str(d))]
        assert got == ["digest-2026-09-20.txt", "digest-2026-09-22.txt"], got
        got = [os.path.basename(p) for p in ledger.digest_files(str(d), "html")]
        assert got == ["digest-2026-09-22.html"], got
        assert ledger.digest_files(str(t / "missing")) == []
    _with_tmp(body)


def test_click_path_is_newest_digest_or_none():
    def body(t, delivered, errors):
        assert notifier._click_path() is None              # first day: no digest
        d = _seed_digests(t / "My Logs" / "notify", "digest-2026-09-21.html",
                          "digest-2026-09-22.html", "digest-2026-09-23.txt")
        os.environ["LLMSNITCH_NOTIFY_DIR"] = str(d)        # with_tmp restores it
        assert notifier._click_path() == str(d / "digest-2026-09-22.html")   # twin, not txt
    _with_tmp(body)


def test_click_path_is_best_effort():
    old = ledger.digest_files

    def boom(_):
        raise RuntimeError("listing failed")
    ledger.digest_files = boom
    try:
        assert notifier._click_path() is None
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
        assert "click_path" not in kw, kw                   # target is Notifier's default only
        assert "; open http://x" in message
        assert len(_rows(t)) == 3 and _rows(t)[0]["notified"] is True
    _with_tmp(body)


if __name__ == "__main__":
    sys.exit(run(globals()))
