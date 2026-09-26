# T902 — Activate the click action

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: T901`
`blocks: —`
`status: ACTIVATED (2026-09-26) — merged `3a02156`, pipx reinstalled, installed-tree banner posted; closes on its click + the 09-27 digest twin`

## Question

The user's ticket (merge and reinstall are theirs, not the orchestrator's).

1. Merge `feature/notification-click-action` to `main`; `pipx install
   --force ~/llmsnitch-cli`.
2. **One installed tree** (shared with quiet-light T802): the light
   LaunchAgent `com.slav-it.fs-coil` runs `/usr/local/bin/fs-coil
   light-agent` (root-owned tree, 2026-08-26). Either repoint its
   `ProgramArguments` at `~/.local/bin/fs-coil` and `launchctl kickstart
   -k gui/$(id -u)/com.slav-it.fs-coil`, or re-sync the `/usr/local`
   tree from the repo. Decide once with T802; record the policy in
   whichever map activates first.
3. Wait for a real banner (the next `scan_finding` page, or the digest's
   `watcher_health` if a health condition holds), click it.

Done when: a banner posted by the **installed** tree, clicked, opens the
current `digest-YYYY-MM-DD.html` in the default browser, and the next
10:00 digest run writes both the `.txt` and its `.html` twin. (The
system-log criterion is dropped — D08: a real click logged nothing.)
Then close the map.

Evidence so far (banners posted from the repo tree, not the install):
2026-09-23 — `.txt` target clicked, opened VS Code (led to D01-amended);
2026-09-26 — browser-twin banner clicked, opened `digest-2026-09-26.html`
in the default browser (user confirmed). Mechanism proven.

Activation (2026-09-26 13:12 EDT): main had moved (quiet-light closed,
digest-rollup T1002 — main itself made pipx the one installed tree, so
step 2 was already done); merged main into the branch (one conflict,
`tests/all.py` import list), suite 217 green, main fast-forwarded to
`3a02156`; `pipx install --force ~/llmsnitch-cli`; installed
`fs_coil/notifier.py` + `digest.py` byte-identical to main; light agent
`com.slav-it.fs-coil` kickstarted (pid 24990 → 89286, program
`~/.local/bin/fs-coil`). Banner "click test (T902, installed tree)"
posted from the pipx venv with `click_path` = today's `.html` twin —
clicked 13:14 EDT — opened the digest in the browser (user confirmed).
First closing criterion holds. Remaining: the 09-27 10:00 digest writing
both `digest-2026-09-27.txt` and `.html` (an observation from main;
this branch's worktree is disposable after this commit).

## Answer

<!-- filled at resolution -->
