"""Live-TCP network pane for the daemon."""

from fs_coil.history import _hist, _sparkline
from fs_coil.runtime import _tcp_conn_counts
from fs_coil.theme import (
    _BOLD, _C7, _DIM, _GREEN, _ORANGE, _R, _TREE_MID, _YELLOW, _tty, head,
)


def _render_net(d):
    """Live TCP-connection sparkline for the fs-coil daemon."""
    rt = d["rt"]
    conn_hist = _hist("conns", maxlen=40)

    total, est, lst = _tcp_conn_counts(rt["pid"])
    conn_hist.append(total)

    head(f"network · pid {rt['pid'] or '—'}")
    if _tty():
        spark = _sparkline(conn_hist, max_val=max(conn_hist, default=1))
        print(f"{_C7}{_TREE_MID}{_R} {_DIM}tcp  {_R}"
              f"{_BOLD}{_ORANGE}{total:>4}{_R}  "
              f"{_GREEN}est {est}{_R}  {_YELLOW}lst {lst}{_R}")
        print(f"{_C7}{_TREE_MID}{_R} {_DIM}trend{_R} {spark}")
        print(f"{_C7}{_TREE_MID}{_R} {_DIM}(history "
              f"{len(conn_hist)}/{conn_hist.maxlen}){_R}")
    else:
        print(f"  tcp {total}  est {est}  lst {lst}")
    print()
