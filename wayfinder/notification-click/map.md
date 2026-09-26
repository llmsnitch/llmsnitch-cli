# Notification Click — Wayfinder Map

`label: wayfinder:map`
`status: ACTIVATED (2026-09-26) — T901 done, T902 merged to main `3a02156` + pipx reinstalled + light agent restarted; installed-tree click confirmed 13:14; closes when the 09-27 10:00 digest writes its .html twin (check from main)`

## Destination

**Clicking a llmsnitch banner opens the newest daily digest in the
browser.** The digest is the one review artifact this project already
maintains for its users — health first, then what is new, then counts —
and its browser twin (`digest-YYYY-MM-DD.html`, the same text escaped
inside `<pre>`) opened by the OS default handler is the destination that
works for anyone: the `.html` handler is a browser on every OS, never an
IDE, and nothing is pinned or registered. macOS: `terminal-notifier -open
file:///…/notify/digest-YYYY-MM-DD.html`. Windows (future outlet): a toast
`launch="file:///…"` with `activationType="protocol"` opens the same file
— the artifact needs no change when that outlet exists. The map closes
when [T902](tickets/T902-activate-click.md)'s done criteria hold: a real
banner on this Mac, posted by the installed tree, clicked, opens the
current digest in the default browser.

## Notes

- **Tracker location**: `wayfinder/notification-click/` on branch
  `feature/notification-click-action` in the worktree
  `~/.supacode/repos/llmsnitch-cli/feature/notification-click-action`.
  Merging to `main` (canonical, `~/llmsnitch-cli`) is the user's call.
- **Origin**: 2026-09-22 evening — clicking a banner does nothing useful.
- **Machine facts (2026-09-22)**:
  - `terminal-notifier 3.1.0` (Homebrew). Click actions are `-open URL`,
    `-execute CMD`, `-activate BUNDLE_ID`; without one of them a click
    only dismisses. `-sender` is **removed since 3.0** — the root-mode
    branch in `fs_coil/notifier.py:151` still passes
    `-sender com.apple.Terminal`; 3.1.0 prints a warning (swallowed by
    `stderr=DEVNULL`) and ignores it. Pre-3.0 that flag made a click
    open Terminal.app with nothing in it; today it does nothing.
    `-open` is stored with the notification and runs **in the GUI
    session on click** — the root LaunchDaemon path (`launchctl asuser …
    sudo -u`) needs no extra plumbing. `-open` values need a scheme:
    `file:///path`, never a bare path.
  - `log show --predicate 'process == "terminal-notifier"' --last 6h`
    is empty — consistent with no click action ever having been set.
  - `-list ALL` shows ~100 undismissed `🐍 fs-coil (light) · W` banners
    from plugin-cache churn. Those come from the **stale installed
    tree**: the LaunchAgent `com.slav-it.fs-coil` runs
    `/usr/local/bin/fs-coil light-agent` (root-owned, 2026-08-26), not
    the pipx shim `~/.local/bin/fs-coil` (2026-09-19). The pipx
    `fs_coil/notifier.py` is byte-identical to this repo's. The flood
    itself is `wayfinder/quiet-light` (branch
    `feature/reduce-notification-noise`, T802 activate pending); that
    branch touches `light_watcher.py` only, so no conflict here.
  - Banners actually posted through `notify()` in the last 30 ledger
    days: 44, all `config-audit / scan_finding` (2,408 rows total).
  - Digest files: `~/Library/Logs/llmsnitch/notify/digest-YYYY-MM-DD.txt`,
    written 10:00 daily by `com.slav-it.llmsnitch-digest`, 0600, chown'd
    to the console user when euid is 0 (`fs_coil/digest.py`). The
    `watcher_health` banner is posted by the digest run itself, right
    after the file is written — its click lands on the digest that
    named the problem.
  - **Windows footprint: none.** `fcntl` in `llmsnitch/patrol.py`,
    `llmsnitch/intake.py`, and most of `fs_coil`; `~/Library` paths,
    `launchctl`, eslogger/fswatch throughout. Windows support is a
    **future effort** (user, 2026-09-22); this map only guarantees the
    click artifact carries over. Microsoft Learn (toast XML schema): the
    `<toast>` `launch` attribute is the string handed to the activated
    app; `activationType="protocol"` launches another app by protocol
    activation, so a `file:///` URI opens with the default handler. A
    desktop caller needs an AppUserModelID; PowerShell's own works from
    a script via `subprocess` — no Python dependency.
- **Doctrine**: a click is part of the notification — it must serve the
  **Decision** gate (AGENTS.md). Ledger subjects are hostile
  (`fs_coil/AGENTS.md`); nothing subject-derived may reach a shell or a
  URL. `fs_coil` files ≤ 250 lines.
- **Repo policy**: local-only git; `trash`, never `rm`; never run
  `install.sh`; stdlib only, Python 3.9+; no network imports
  (test-enforced); files 0600 / dirs 0700; `python3 tests/all.py` is the
  gate. Subprocess argv list-form only.
- **Skills**: `tdd` for the build ticket; `code-review` two-axis and
  `ponytail:ponytail-review` after it.

## Options considered (grilling round 1 input)

| # | Click does | Mac mechanism | Windows analogue | Verdict |
|---|---|---|---|---|
| A | Bring a terminal to the front | `-activate app.supabit.supacode` (or Ghostty / Terminal) | protocol `wt:` (none registered) | Shows nothing; barely better than today. |
| **B** | **Open the newest digest file** | **`-open file://…/notify/digest-YYYY-MM-DD.html`** | `launch="file:///…"` | **Chosen (user, 2026-09-22): most sound for the project's users.** The digest is already the review home. Viewer settled in round 2 (below): the `.txt` default handler opened VS Code on the first live click, so the click target is a browser twin. Limitation: the digest is the 10:00 trailing view, so the clicked banner's own finding appears in tomorrow's ② — fog item below. |
| C | Open a terminal running the category's recall command | `-open file://…/click/<category>.command` (static scripts) | `launch="file:///…/<category>.cmd"` | Runner-up. Assumes a terminal user; adds generated executables. Returns only via the freshness fog item. |
| D | Same as C in the user's terminal of choice | `-execute '/usr/bin/open -na Ghostty …'` + config key | n/a | Mac-only, new config axis. Rejected. |
| E | Open a Supacode tab running the command | `supacode://worktree/<id>/tab/new?input=` | n/a | Needs a worktree id the daemon lacks; confirmation prompts; app coupling. Rejected. |
| F | Action buttons (Report / Waive) | `-action` — blocks waiting for the response | toast `<action>` | A daemon cannot block per banner; a state change from a click is a hostile-input path. Rejected. |
| G | Open a per-banner rendered page | write `pages/<ts>.txt`, `-open` it | `launch="file:///…"` | More files to prune and chown; copies hostile subjects into another artifact. Rejected. |

## Decisions so far

<!-- one line per closed ticket: gist + link -->

- Grilling round 1 (charting, accepted 2026-09-22): **D01 destination** =
  option B — the click opens the newest `digest-*.txt` via the OS default
  handler. **D02 target resolution at post time** — `_deliver` resolves
  the newest digest file in the notify dir when the banner is posted and
  passes `file://<path>` as `-open`; no digest yet (first day after
  install) → no `-open`, the click dismisses as today. No symlink, no
  `latest` file, no regeneration. **D03 nothing subject-derived reaches
  the URL** — the path is a function of the notify dir and the file
  listing only. **D04 delete `-sender`** in the same change (dead since
  3.0; its warning is silently dropped). **D05 Windows is a future
  effort** — the artifact (a text file opened by default handler) is
  chosen so a Windows outlet reuses it unchanged; no spike ticket, the
  toast mechanics are recorded in Notes for that day. **D06 argv is
  built by a pure function** so the test asserts on the list (`-open`
  present with a digest, absent without, `-sender` absent in both
  branches) without posting a banner.
- [T901 — Build the click action](tickets/T901-build-click-action.md) —
  `Notifier.notify` defaults `open_url` to the newest digest as a
  `file://` URI (`Path.as_uri`, so odd paths cannot sink the banner);
  every caller gets it, `_deliver` passes nothing (D03 structural);
  `ledger.digest_files` is the shared date-regex lister, fixing digest's
  `?`-glob newest pick too; `-sender` deleted; argv is a pure function.
  Two-axis review 7 findings → 6 fixed, 1 deferred (below). +5 tests,
  suite 209. **D02 amended**: resolution happens in `Notifier`, not
  `_deliver`.
- Grilling round 2 (2026-09-23/26, after the first live click opened VS
  Code): viewer options laid out with their Windows twin — OS default
  `.txt` handler (an IDE for most developers on both OSes), pinned
  TextEdit (`-execute open -a`; Windows would need an HKCU `llmsnitch:`
  scheme to reach Notepad), **browser twin**, terminal script, notify
  folder in Finder/Explorer, `-activate`, custom scheme, Quick Look.
  **D01 amended (user)**: the click target is `digest-YYYY-MM-DD.html`,
  written by every digest run beside the `.txt` (`html.escape`d in
  `<pre>`, 0600, chown'd, pruned together) — the only option where the
  click is a plain `file://` URI on both platforms and the viewer is never
  an IDE. **D07 message escape**: a `-message` whose first character is
  one of `[({"-<` is prefixed `\` in `_argv` — verified against 3.1.0
  (each rejects with exit 2 unescaped, `-title` is unaffected, the
  backslash is stripped from the shown text). **D08 T902 criterion**: the
  "system log records the open" criterion is dropped — a real click
  logged nothing under `process == "terminal-notifier"`; the observed
  open is the evidence. Suite 209 → 211.
- [T902 — Activate](tickets/T902-activate-click.md) — user: merge,
  reinstall, one real click from the installed tree; shares the
  one-installed-tree step with quiet-light T802. Live so far (repo tree,
  not installed): 2026-09-23 `.txt` click opened VS Code; 2026-09-26
  browser-twin click opened the digest in the browser (user confirmed) —
  mechanism proven, install pending.

## Not yet specified

- **Digest freshness** — a `scan_finding` clicked at 15:00 opens the
  10:00 digest, which does not yet list that finding; tomorrow's ② will.
  If that is felt in practice, the candidates are a `digest-latest.txt`
  rendered at delivery time (cost: a digest render inside the notify
  chain) or option C for the finding categories only. Fog until clicked
  for real.
- **One installed tree** — the light LaunchAgent runs the 2026-08-26
  `/usr/local` tree; repoint at the pipx shim or re-sync is a T902 step
  here and a T802 step on quiet-light. The *policy* is shared fog; decide
  once, in whichever activates first.
- **Windows outlet proper** — `notifier_win.py`, AUMID choice,
  `hook.handle` without `fcntl`, digest path on Windows. A fresh map when
  llmsnitch runs on Windows at all; this map's only Windows deliverable
  is that the click target survives the port.

## Out of scope

- Any network delivery channel (Slack, email, webhook) — no network
  code, test-enforced.
- Interactive banners (`-action` / `-reply`) — option F.
- Generated per-category or per-banner scripts (options C, G) — return
  only via the freshness fog item.
- Supacode / Ghostty coupling (options D, E).
- The plugin-cache banner flood — `wayfinder/quiet-light`.
- A Windows port of any producer or of the notify layer — future effort.
