"""CLI entry point — parses argv and dispatches to the per-command handlers
that live in fs_coil.commands / report / dashboard / monitor."""

import os
import sys

from fs_coil.commands import (
    cmd_logs, cmd_noise, cmd_prune, cmd_restart, cmd_start, cmd_status,
    cmd_stop, cmd_test,
)
from fs_coil.dashboard import cmd_dashboard
from fs_coil.monitor import run_monitor
from fs_coil.report import cmd_report
from fs_coil.theme import print_banner

USAGE = """🐍 fs-coil — filesystem tripwire for Claude Code / Opencode

Usage:
  fs-coil                status
  fs-coil report         dashboard: posture + 7-day activity (single page)
  fs-coil dashboard      live tmux dashboard (4 panes, 5s refresh)
  fs-coil light          run light-mode watcher foreground (no FDA, writes only)
  fs-coil light-agent    internal, invoked by user LaunchAgent (light mode)
  fs-coil start          load LaunchDaemon (sudo) — DEEP MODE (requires FDA)
  fs-coil stop           unload LaunchDaemon (sudo)
  fs-coil restart        stop + start
  fs-coil logs [-f]      show today's log (-f = tail follow)
  fs-coil noise [--category X] [--days N]
                         show writes that were logged but suppressed from
                         notifications ("actionable, not informational")
  fs-coil prune [--days N]  delete daily logs older than N days (default 30)
  fs-coil test           run foreground (deep mode), no notifications
  fs-coil daemon         internal, invoked by launchd (deep mode, root)
"""


def _light_paths_from_config():
    """Read `paths` from [light-watch] in ~/.config/llmsnitch/config.
    Falls back to the module default when absent/malformed."""
    from fs_coil.light_watcher import DEFAULT_WATCH_PATHS
    try:
        import configparser
        cp = configparser.ConfigParser(inline_comment_prefixes=("#",))
        cp.read(os.path.expanduser("~/.config/llmsnitch/config"))
        if cp.has_section("light-watch"):
            raw = cp["light-watch"].get("paths", "")
            parts = [p.strip() for p in raw.split(",") if p.strip()]
            if parts:
                return parts
    except Exception:
        pass
    return DEFAULT_WATCH_PATHS


def _opt(rest, flag, default=None, cast=str):
    """Value following `--flag` in rest, or `default` (also on bad cast)."""
    if flag in rest:
        i = rest.index(flag)
        if i + 1 < len(rest):
            try:
                return cast(rest[i + 1])
            except ValueError:
                pass
    return default


def main():
    argv = sys.argv[1:]
    first = argv[0] if argv else ""
    if first in ("", "status", "test", "-h", "--help", "help"):
        print_banner()
    if not argv or argv[0] in ("-h", "--help", "help"):
        if not argv:
            cmd_status()
        else:
            print(USAGE)
        return

    c = argv[0]
    rest = argv[1:]
    if c == "status":
        cmd_status()
    elif c == "report":
        cmd_report(section=_opt(rest, "--section"),
                   live=("--live" in rest),
                   interval=max(1, _opt(rest, "--interval", 5, int)),
                   banner=("--no-banner" not in rest))
    elif c == "dashboard":
        cmd_dashboard()
    elif c == "start":
        cmd_start()
    elif c == "stop":
        cmd_stop()
    elif c == "restart":
        cmd_restart()
    elif c == "logs":
        cmd_logs(follow=("-f" in argv[1:]))
    elif c == "noise":
        cmd_noise(category=_opt(rest, "--category"),
                  days=max(1, _opt(rest, "--days", 1, int)))
    elif c == "prune":
        cmd_prune(days=max(1, _opt(rest, "--days", 30, int)))
    elif c == "test":
        cmd_test()
    elif c == "daemon":
        # launchd entry point (deep mode) — must not exit cleanly on success
        if os.geteuid() != 0:
            print("daemon mode requires root", file=sys.stderr)
            sys.exit(1)
        run_monitor(stdout_only=False)
    elif c in ("light", "light-agent"):
        # `light` = foreground; `light-agent` = LaunchAgent entry point.
        # Both run as the user, no root, no FDA — uses fswatch under the hood.
        from fs_coil.light_watcher import run_light_monitor
        paths = _light_paths_from_config()
        run_light_monitor(paths=paths, stdout_only=(c == "light"))
    else:
        print(USAGE)
        sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
