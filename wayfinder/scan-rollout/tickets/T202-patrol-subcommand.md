# T202 — `llmsnitch patrol` subcommand + trigger stamp

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: —`
`blocks: T204`
`status: OPEN`

## Question

Nothing to decide (all decisions locked in grilling — see map Decisions so
far); execution ticket per the map's plan-vs-do override.

Build, on branch `research/scanner-survey-mvp`:

1. `llmsnitch scan --patrol` — identical to `scan`, plus
   `meta["trigger"] = "patrol"` (manual runs stamp `"manual"`). One field;
   ledger, report, notify behavior otherwise unchanged.
2. `llmsnitch patrol` subcommand mirroring `setup_cmd`'s trust posture:
   - default: PRINT the LaunchAgent plist
     (`com.slav-it.llmsnitch-patrol`) — daily `StartCalendarInterval`
     (pick a fixed morning time, e.g. 09:30), `ProgramArguments`
     `[~/.local/bin/llmsnitch, scan, --patrol]`, working dir `$HOME`,
     `StandardErrorPath ~/Library/Logs/llm-snitch/patrol.err`
     (+ StandardOutPath to `.out`), `RunAtLoad false`.
   - `--write`: write plist to `~/Library/LaunchAgents/` and
     `launchctl bootstrap gui/$UID` it (kickstart pattern:
     see `docs/notifier-spec.md` §Migration for the house launchctl idiom).
     No inside-Claude-Code refusal guard — the plist does not wire the
     monitored agent's own hook config (grilling Q7).
3. Tests in the house stdlib-runner style: trigger stamp lands in
   meta.json for `--patrol` and reads `"manual"` otherwise; `patrol`
   prints a plist that `plutil -lint` accepts (skip plutil assert if
   unavailable); `--write` refuses when the target plist path is
   unwritable (exit 2).

Constraints: stdlib only; no network; hot path untouched; `launchctl` runs
only under `--write` (a subprocess call is acceptable on this cold path —
note it in the module docstring since the no-network test greps imports,
not subprocess).

Done when: all suites green on the branch; `llmsnitch patrol | plutil -lint -`
passes locally; the review gates from the map Notes have run over the diff.
