"""Report orchestration: _render_report_once routes --section, cmd_report
adds the --live loop with SIGWINCH redraws and tmux-pane housekeeping."""

import os
import signal
import subprocess
import sys
import time

from fs_coil.render_activity import (
    _render_activity, _render_offenders, _render_recent, _render_rules,
    _render_timeline,
)
from fs_coil.render_alerts import _render_alerts, _render_file_alerts
from fs_coil.render_posture import _render_actors, _render_health, _render_posture
from fs_coil.render_resource import _render_net
from fs_coil.render_sidebar import (
    _render_col_mid, _render_col_right, _render_network_ai, _render_sidebar,
    _render_stats,
)
from fs_coil.render_subprocs import _render_commands, _render_subprocs
from fs_coil.report_data import _report_data
from fs_coil.theme import _DIM, _R, _tty, err, head, item, print_banner


def _render_report_once(section=None, banner=True):
    """One-pass render: either a single section or the full stacked report."""
    d = _report_data()
    if section:
        renderers = {
            "posture":   _render_posture,
            "timeline":  _render_timeline,
            "offenders": _render_offenders,
            "rules":     _render_rules,
            "actors":    _render_actors,
            "recent":    _render_recent,
            "health":    _render_health,
            "net":       _render_net,
            "alerts":    _render_alerts,
            "file_alerts": _render_file_alerts,
            "subprocs":  _render_subprocs,
            "commands":  _render_commands,
            "network":   _render_network_ai,
            "stats":     _render_stats,
            "sidebar":   _render_sidebar,
            "col_mid":   _render_col_mid,
            "col_right": _render_col_right,
        }
        fn = renderers.get(section)
        if not fn:
            err(f"unknown section: {section} (use: {', '.join(renderers)})")
            sys.exit(2)
        fn(d)
        return

    if banner:
        print_banner(show_head=False)

    # Lead with the packed graphs + top-lists row (timeline · hourly ·
    # offenders · parents · rules · paths). This is the "dashboard" band
    # people want to glance at first. Charts always render (zeroed buckets
    # when nothing has fired); top-lists self-skip when their source is empty.
    _render_activity(d)
    if not d["matches"]:
        head("quiet")
        item(f"{_DIM}tripwire has not fired in the last 7 days{_R}" if _tty()
             else "tripwire has not fired in the last 7 days")
        print()

    # Posture (status, runtime, paths, activity counters, log volume) —
    # slower-changing context below the top band.
    _render_posture(d)

    if d["matches"]:
        # Known-actor table: unique (name · source · signing-id) triples so
        # you can eyeball "who/where/what" across all hits, not just counts.
        _render_actors(d)
        # Full recent-hits list at the bottom — finer detail after the summary.
        _render_recent(d)


def cmd_report(section=None, live=False, interval=5, banner=True):
    """Static print by default; --live loops with SIGWINCH-triggered redraws
    so panes/windows re-layout correctly when the terminal is resized. The
    tmux dashboard uses --live under the hood."""
    if not live:
        _render_report_once(section, banner=banner)
        return

    # Live mode: redraw on timer OR on terminal resize (SIGWINCH). Also
    # cover SIGCONT in case the pane was backgrounded/foregrounded.
    winch = [True]  # start True so we render immediately
    def _on_signal(signum, frame):
        winch[0] = True
    try:
        signal.signal(signal.SIGWINCH, _on_signal)
        signal.signal(signal.SIGCONT,  _on_signal)
    except (ValueError, AttributeError):
        # Not running on a platform that supports these signals (e.g. Windows).
        pass

    # Redraw strategy: render full content (no clip) so the user can scroll
    # within the current tick. Between ticks we (a) exit tmux copy mode so
    # viewport snaps live, (b) clear tmux's pane history so nothing remains
    # to scroll back to, (c) clear the terminal and reset cursor to home.
    tmux_pane = os.environ.get("TMUX_PANE")
    def _redraw(sec):
        # Exit tmux copy mode if the user scrolled up; always clear pane
        # scroll history BEFORE the render so old ticks can't accumulate.
        if tmux_pane:
            try:
                subprocess.run(
                    ["tmux", "send-keys", "-t", tmux_pane, "-X", "cancel"],
                    capture_output=True, timeout=0.5,
                )
                subprocess.run(
                    ["tmux", "clear-history", "-t", tmux_pane],
                    capture_output=True, timeout=0.5,
                )
            except Exception:
                pass
        # Clear the visible screen and park the cursor at home.
        sys.stdout.write("\x1b[H\x1b[2J\x1b[3J\x1b[H")
        sys.stdout.flush()
        _render_report_once(sec, banner=banner)
        sys.stdout.flush()
        # Scroll the pane to the TOP of the freshly rendered content. If
        # the report is taller than the pane, tmux's default is to leave
        # viewport at the bottom (where the cursor finished) — but the
        # interesting stuff (banner, charts, top-lists) is at the top.
        # copy-mode + history-top snaps viewport to row 0 of the buffer.
        # User stays in copy mode; the next tick's `send-keys -X cancel`
        # snaps them back out before the redraw begins.
        if tmux_pane:
            try:
                subprocess.run(
                    ["tmux", "copy-mode", "-t", tmux_pane],
                    capture_output=True, timeout=0.5,
                )
                subprocess.run(
                    ["tmux", "send-keys", "-t", tmux_pane, "-X", "history-top"],
                    capture_output=True, timeout=0.5,
                )
            except Exception:
                pass

    try:
        last = 0.0
        while True:
            now = time.time()
            if winch[0] or (now - last) >= interval:
                try:
                    _redraw(section)
                except Exception as e:
                    print(f"render error: {e}", file=sys.stderr)
                winch[0] = False
                last = time.time()
            # Poll at 100ms — snappy resize response without busy-looping.
            time.sleep(0.1)
    except KeyboardInterrupt:
        return
