"""Per-AI CPU+memory pane and live-TCP network pane for the daemon."""

import shutil
from datetime import datetime

from fs_coil.history import _ACTOR_LAST_SEEN, _hist, _sparkline
from fs_coil.parser import _fmt_size
from fs_coil.runtime import _running_actor_detail, _tcp_conn_counts
from fs_coil.theme import (
    _BOLD, _C7, _DIM, _GREEN, _ORANGE, _R, _TREE_MID, _YELLOW, _tty, head, item,
)


_CHART_W_MAX = 100   # hard cap — chart never exceeds this even in wide terms


def _chart_width():
    """Sparkline width = min(100, pane_cols - prefix). Capping at pane
    width prevents the bar wrapping onto the next row when the pane is
    narrower than 100 cols (was causing the 'graph overlaps log text' look)."""
    try:
        cols = shutil.get_terminal_size((60, 24)).columns
    except Exception:
        cols = 60
    return max(20, min(_CHART_W_MAX, cols - 22))


def _render_cpu_mem(d):
    """Per-AI CPU + memory — **one metric per row**, sparkline pinned at
    a fixed 100-column width regardless of pane size. Shorter history is
    left-padded with dim dots so the chart always takes the same space.

    Tracked actors: VSCode's Claude (vscode), Claude App (app), OpenCode.
    """
    agg = _running_actor_detail()
    now = datetime.now()
    for bucket, info in agg.items():
        if info["n"] > 0:
            _ACTOR_LAST_SEEN[bucket] = now

    head("cpu + memory · per AI")

    chart_w = _chart_width()

    def _pad(values):
        """Left-pad with None so the chart is always `chart_w` wide.
        None cells render as blank spaces — no more distracting dots."""
        v = list(values)[-chart_w:]
        if len(v) < chart_w:
            v = [None] * (chart_w - len(v)) + v
        return v

    labels = [
        ("vscode_claude", "vscode"),
        ("claude_app",    "app"),
        ("opencode",      "opencode"),
    ]
    rendered = 0
    for bucket, label in labels:
        info = agg.get(bucket, {"n": 0, "cpu": 0.0, "rss_kb": 0})
        last = _ACTOR_LAST_SEEN.get(bucket)
        if info["n"] == 0 and (not last or (now - last).total_seconds() > 3600):
            continue

        cpu_hist = _hist(f"cpu_{bucket}",    maxlen=40)
        mem_hist = _hist(f"mem_{bucket}_kb", maxlen=40)
        cpu_hist.append(info["cpu"])
        mem_hist.append(info["rss_kb"])

        cur_cpu = f"{info['cpu']:.1f}%" if info["n"] > 0 else "—"
        cur_mem = _fmt_size(info["rss_kb"] * 1024) if info["n"] > 0 else "—"
        dot     = f"{_GREEN}●{_R}" if info["n"] > 0 else f"{_DIM}○{_R}"
        n_badge = (f"{_DIM}x{info['n']:<2}{_R}" if info["n"] > 0
                   else f"{_DIM}idle{_R}")

        # Fixed 100-col sparkline, left-padded with None for empty cells.
        cpu_tail = _pad(cpu_hist)
        mem_tail = _pad(mem_hist)

        if _tty():
            cpu_nonempty = [v for v in cpu_tail if v is not None]
            cpu_spark = _sparkline(cpu_tail,
                                   max_val=max(max(cpu_nonempty, default=0), 5))
            mem_spark = _sparkline(mem_tail)
            # Row 1: label + status dot + current CPU + full-width sparkline.
            print(f"{_C7}{_TREE_MID}{_R} {_DIM}{label:<8}{_R} "
                  f"{dot} {n_badge} {_DIM}cpu{_R} "
                  f"{_BOLD}{_ORANGE}{cur_cpu:>6}{_R} {cpu_spark}")
            # Row 2: same alignment, mem on its own line.
            print(f"{_C7}{_TREE_MID}{_R} {' ':<8}       "
                  f"{_DIM}mem{_R} "
                  f"{_BOLD}{_ORANGE}{cur_mem:>6}{_R} {mem_spark}")
        else:
            print(f"  {label:<8}  cpu {cur_cpu}  mem {cur_mem}  (n={info['n']})")
        rendered += 1

    if rendered == 0:
        item(f"{_DIM}(no AI processes seen in the last hour){_R}" if _tty()
             else "(no AI processes seen in the last hour)")
    print()


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
