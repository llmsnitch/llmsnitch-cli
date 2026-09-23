# T901 — Build the click action

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: —`
`blocks: T902`
`status: OPEN`

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

<!-- filled at resolution: what was built, test count, review outcomes -->
