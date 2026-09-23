# T901 — Build the click action

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: —`
`blocks: T902`
`status: DONE (2026-09-22)`

## Question

Execution. Every decision is made (map D01–D06); build against them with
`tdd`, then run the two-axis `code-review` and `ponytail:ponytail-review`.

1. **Newest digest path** — one helper in `fs_coil/digest.py` (or next to
   `_notify_dir()` in `notify.py`, whichever keeps both files under 250
   lines): return the lexically greatest `digest-YYYY-MM-DD.txt` in the
   notify dir, or `None`. Filename regex-matched like
   `_install_ts_from_ledger` does for ledger files — never trust
   arbitrary names in that directory.
2. **`_deliver` passes the target** — `notify._deliver` resolves the path
   and hands `open_url="file://" + path` (or `None`) to
   `Notifier.notify`. The URL is a function of the directory listing
   only; no subject, actor, or title component may enter it (D03).
3. **`Notifier.notify` argv** — extract the argv construction into a
   pure function (e.g. `_argv(title, message, group, icon, open_url,
   as_root=(uid, user))`) that `notify()` calls; append `["-open",
   open_url]` when set; **delete `-sender com.apple.Terminal`** from the
   root branch (D04). Icon and `launchctl asuser … sudo -u` mechanics
   unchanged.
4. **Tests** (`tests/test_notify.py` or a new `tests/test_click.py`
   registered in `tests/all.py`; stdlib runner; `_seams.with_tmp`):
   - with two seeded digest files the argv carries `-open
     file://…/digest-<newest>.txt`;
   - with no digest file there is no `-open`;
   - `-sender` appears in neither the root nor the user argv;
   - a hostile subject (`"; open http://x"`, path separators, `file://`
     in the subject) never changes the URL;
   - `notify()` still returns True and ledgers normally when the notify
     dir is unreadable for listing (the click is best-effort; the
     banner is not).
5. **Docs** — `docs/notifier-spec.md` §"Delivery outlets" 1 gains one
   sentence (click opens the newest digest; `-sender` gone);
   `fs_coil/AGENTS.md` notifier line if it mentions `-sender`.

Done when: `python3 tests/all.py` green with the new tests; a manual
post from a plain terminal with a real digest present (`python3 -c
'from fs_coil.notify import notify; notify("config-audit",
"scan_finding", "click-test", record_only=False)'` under
`cold_start = 0`) shows the banner and `terminal-notifier -list ALL`
lists it; clicking it opens the digest in the default text editor.

## Delete

`-sender` and its comment in `fs_coil/notifier.py`.

## Answer

Built in two commits (`f0d221c`, then the review follow-up). Deviations
from the plan above, all from the two-axis `code-review` (7 findings) and
`ponytail-review` (4):

- **The click default lives in `Notifier.notify`**, not `_deliver`: with
  `open_url=None` every banner — including the direct `Notifier()` callers
  in `monitor.py` and `light_watcher.py` — gets `-open <newest digest>`.
  `_deliver` passes nothing, which is how D03 is enforced structurally
  (there is no row-derived input to the URL; the test asserts the kwarg is
  absent).
- **`ledger.digest_files(d)`** is the shared newest-digest lister (date
  regex `^digest-\d{4}-\d{2}-\d{2}\.txt$`, replacing digest.py's `?`-glob
  that let `digest-zzzz-zz-zz.txt` sort newest). `digest.py` and
  `notifier.py` both import it; the delivery path no longer imports
  `digest`.
- **URL via `Path(...).as_uri()`** — a space or `#` in the notify dir
  would otherwise make terminal-notifier reject the whole banner, not
  just the click.
- Kept the best-effort `try/except` in `_click_url` (monitor.py's read
  loop must never see an exception) but the test now covers it by making
  the lister raise, instead of a chmod-000 dir that `listdir` errors
  swallow anyway.
- Dropped the redundant end-to-end test the reviewer and ponytail both
  flagged; replaced with one that drives the REAL `_deliver` through
  `notify()` with a fake `Notifier`.

Tests: 5 in `tests/test_click.py`, suite 204 → 209, exit 0. `-sender`
gone from `fs_coil/`. Spec §"Delivery outlets" 1 amended. Live check on
this Mac: `_click_url()` → today's `digest-2026-09-22.txt`; one test
banner posted with that URL for the T902 click.

Deferred, recorded on the map: leading `[`/`(`/quote in a `-message`
value makes terminal-notifier fail to read it (its own help text); a
pre-existing banner-loss path, not a click concern.
