"""Sidebar composer + the per-AI live network pane.

`_render_sidebar` is the dashboard's right-pane composer; `_render_stats`
is the live-stats stack the sidebar leads with."""

from fs_coil.network import _NET_SESSION, _sample_network
from fs_coil.parser import _fmt_size
from fs_coil.render_alerts import _render_alerts
from fs_coil.render_posture import _render_health
from fs_coil.render_resource import _render_net
from fs_coil.render_subprocs import _render_commands, _render_subprocs
from fs_coil.theme import (
    _BOLD, _C7, _DIM, _GREEN, _ORANGE, _R, _TREE_MID, _tty, head,
)


def _render_network_ai(d):
    """Sidebar-friendly per-AI network view: live MB counters + top hosts.
    Compact table format so the pane fits a narrow sidebar column."""
    cur = _sample_network()
    head("network · per AI")

    rows = [
        ("VSCode Claude", "vscode_claude"),
        ("Claude.app",    "claude_app"),
        ("OpenCode",      "opencode"),
    ]
    NAME_W, NUM_W = 14, 8

    if _tty():
        print(f"{_C7}{_TREE_MID}{_R} {_DIM}"
              f"{'actor / host':<{NAME_W}}"
              f"{'↓ total':>{NUM_W}}{'↑ total':>{NUM_W}}"
              f"{_R}")
        print(f"{_C7}{_TREE_MID}{_R} {_DIM}"
              + "─" * (NAME_W + NUM_W * 2) + f"{_R}")

    for label, key in rows:
        sess_b   = _NET_SESSION[key]
        tot_in   = _fmt_size(sess_b["bytes_in"])
        tot_out  = _fmt_size(sess_b["bytes_out"])
        top_hosts = sess_b["hosts"].most_common(3)
        if sess_b["bytes_in"] == 0 and sess_b["bytes_out"] == 0 and not top_hosts:
            if _tty():
                print(f"{_C7}{_TREE_MID}{_R} {_DIM}{label:<{NAME_W}}{_R}"
                      f"{_DIM}{'·':>{NUM_W}}{'·':>{NUM_W}}{_R}")
            else:
                print(f"  {label}: quiet")
            continue
        if _tty():
            print(f"{_C7}{_TREE_MID}{_R} {_BOLD}{_GREEN}{label:<{NAME_W}}{_R}"
                  f"{_BOLD}{_ORANGE}{tot_in:>{NUM_W}}{tot_out:>{NUM_W}}{_R}")
            for host, n in top_hosts:
                # Truncate host if it'd overflow the name column.
                display = host if len(host) <= NAME_W else host[:NAME_W-1] + "…"
                print(f"{_C7}{_TREE_MID}{_R}  {display:<{NAME_W-1}}"
                      f"{_DIM}{n:>{NUM_W-1}} hits{_R}")
        else:
            print(f"  {label}: ↓{tot_in} ↑{tot_out}")
            for host, n in top_hosts:
                print(f"    {n:>3}  {host}")
    print()


def _render_stats(d):
    """Combined live stats pane: alerts + subprocs (includes cpu+mem
    sparklines) + network (per AI) + commands."""
    _render_alerts(d)
    _render_subprocs(d)
    _render_network_ai(d)
    _render_commands(d)


def _render_sidebar(d):
    """Everything that lives in the dashboard's single right pane:
    live stats up top, health + watched reference below."""
    _render_stats(d)
    _render_health(d)


def _render_col_mid(d):
    """Middle dashboard column — live 'what is happening now' view:
    alerts · file alerts chart · subprocs (now with cpu+mem sparklines
    folded in, so the separate cpu+memory pane is gone)."""
    from fs_coil.render_alerts import _render_file_alerts
    _render_alerts(d)
    _render_file_alerts(d)
    _render_subprocs(d)


def _render_col_right(d):
    """Right dashboard column: network per AI (live MB + top hosts) →
    commands history → health/watched reference."""
    _render_network_ai(d)
    _render_commands(d)
    _render_health(d)
