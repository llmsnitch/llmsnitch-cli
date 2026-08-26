"""ALERTS pane — the dashboard's headline view.

Per-actor 1h/24h/7d counts + live process counts + 24h sparkline + last hit."""

import shutil

from fs_coil.classify import _actor_counts
from fs_coil.denylist import _shrink
from fs_coil.render_charts import _hourly_block
from fs_coil.runtime import _running_actor_procs
from fs_coil.theme import (
    _BOLD, _C7, _DIAMOND, _DIM, _GREEN, _ORANGE, _R, _RED, _TREE_MID, _TREE_TOP,
    _YELLOW, _tty,
)


def _mid_trunc(s, width):
    """Middle-truncate a string to `width` chars using '…' so the start and
    end stay readable (e.g. '/Users/yaro/…ude.json')."""
    if width <= 3 or len(s) <= width:
        return s
    keep = width - 1                      # reserve 1 char for '…'
    front = (keep + 1) // 2               # bias one char to front
    back  = keep - front
    return s[:front] + "…" + (s[-back:] if back else "")


def _pane_w():
    try:
        return max(24, shutil.get_terminal_size((60, 24)).columns)
    except Exception:
        return 60


def _render_file_alerts(d):
    """Dedicated 'file alerts' hourly chart — same machinery as the
    posture's hits-per-hour block, retitled to make it clear that the
    bars represent DENY-MATCH (file-access) alerts.

    Rendered with cell_w=1 (bars packed edge-to-edge) so the chart is
    ~20-50% narrower than the default — fits the compact sidebar column
    without wasted whitespace between bars."""
    lines, _ = _hourly_block(d, cell_w=1)
    hrs   = d.get("hits_per_hour") or []
    total = sum(n for _, n in hrs)
    lines[0] = (f"{_C7}{_TREE_TOP}{_DIAMOND}{_BOLD}{_C7}"
                f"file alerts (24h) · total {total}{_R}")
    for ln in lines:
        print(ln)
    print()


def _render_alerts(d):
    """ALERTS panel — the dashboard's headline view. Table-style per-actor
    breakdown with 1h / 24h / 7d counts, live process counts, an hourly
    sparkline, and the last hit. Purple accent + severity colors."""
    matches = d["matches"]
    h1, d1, d7 = d["h1"], d["d1"], d["d7"]

    # Per-actor counters for each window.
    by_1h  = _actor_counts(matches, 3600)
    by_24h = _actor_counts(matches, 86400)
    by_7d  = _actor_counts(matches, 7 * 86400)

    # Live process counts.
    vsc_total, vsc_claude, claude_app, opencode = _running_actor_procs()

    if _tty():
        # Headline: bold purple ALERTS · total. (24h sparkline moved out to
        # its own dedicated `file alerts` chart below.)
        total_c = _RED if d7 > 0 else _GREEN
        hdr = (f"{_C7}{_TREE_TOP}{_DIAMOND}{_BOLD}{_C7}ALERTS{_R}"
               f"{_DIM}  ·  total {_R}{_BOLD}{total_c}{d7}{_R}")
        print(hdr)

        # Column widths (visible chars, not ANSI). Row = 14 + 3×4 + 5 = 31.
        NAME_W = 14
        NUM_W  = 4    # rendered with right-align and a space gutter

        def _n(v, hot=False):
            """Format a count cell: orange-bold when hot, red when very
            hot, dim · for zero."""
            if v <= 0:
                return f"{_DIM}{'·':>{NUM_W}}{_R}"
            color = _RED if hot else _ORANGE
            return f"{color}{_BOLD}{v:>{NUM_W}}{_R}"

        # Header row.
        print(f"{_C7}{_TREE_MID}{_R} {_DIM}"
              f"{'actor':<{NAME_W}}"
              f"{'1h':>{NUM_W}}{'24h':>{NUM_W}}"
              f"{'7d':>{NUM_W}}{'live':>{NUM_W+1}}"
              f"{_R}")
        # Divider.
        print(f"{_C7}{_TREE_MID}{_R} {_DIM}"
              + "─" * (NAME_W + NUM_W * 4 + 1)
              + f"{_R}")

        rows = [
            ("VSCode Claude", "vscode_claude", vsc_claude),
            ("Claude.app",    "claude_app",    claude_app),
            ("OpenCode",      "opencode",      opencode),
        ]
        for label, key, live in rows:
            v1, v24, v7 = by_1h[key], by_24h[key], by_7d[key]
            live_c = _GREEN if live > 0 else _DIM
            # Name color: bold-white if any activity now, otherwise dim.
            name_c = f"{_BOLD}{_GREEN}" if live > 0 else _DIM
            if v1 > 0:
                name_c = f"{_BOLD}{_RED}"
            print(f"{_C7}{_TREE_MID}{_R} "
                  f"{name_c}{label:<{NAME_W}}{_R}"
                  f"{_n(v1, hot=True)}"
                  f"{_n(v24)}"
                  f"{_n(v7)}"
                  f" {live_c}{_BOLD}{(str(live) if live else '·'):>{NUM_W}}{_R}")

        # Subtle divider before the footer rows.
        print(f"{_C7}{_TREE_MID}{_R} {_DIM}"
              + "─" * (NAME_W + NUM_W * 4 + 1)
              + f"{_R}")

        # Footer 1: vscode subproc total.
        print(f"{_C7}{_TREE_MID}{_R} {_DIM}vscode subprocesses{_R}  "
              f"{_BOLD}{_ORANGE}{vsc_total}{_R}")

        # Footer 2: audit (low-severity) counter. These are self-keychain
        # reads by Claude and similar benign events — logged for audit
        # but excluded from the primary alert totals above.
        a_h1 = d.get("audit_h1", 0)
        a_d7 = d.get("audit_d7", 0)
        if a_h1 or a_d7:
            print(f"{_C7}{_TREE_MID}{_R} {_DIM}audit (low-severity)  "
                  f"{a_h1} (1h) · {a_d7} (7d){_R}")

        # Footer 2: last hit. Timestamp + mode + proc on row 1; path on
        # its OWN row (row 2), middle-truncated to pane width so it never
        # wraps — e.g. '/Users/yaro/…ude.json'.
        if matches:
            m = matches[-1]
            mc = _RED if m["mode"] == "R" else _YELLOW
            print(f"{_C7}{_TREE_MID}{_R} {_DIM}last{_R}  "
                  f"{_DIM}{m['dt'].strftime('%H:%M:%S')}{_R} "
                  f"{mc}{_BOLD}{m['mode']}{_R} "
                  f"{_BOLD}{m.get('via') or m['proc']}{_R}"
                  f"{_DIM}[{m['pid']}]{_R}")
            # Path row — budget = pane width minus the 4-char "│    " prefix.
            path   = _shrink(m["path"], d["home"])
            budget = _pane_w() - 6
            print(f"{_C7}{_TREE_MID}{_R}    {_mid_trunc(path, budget)}")
        else:
            print(f"{_C7}{_TREE_MID}{_R} {_DIM}last  (no matches yet){_R}")
    else:
        # Plain-text fallback for pipes.
        print("ALERTS · last 24h")
        print(f"  actor            1h  24h   7d  live")
        for label, key, live in [
            ("VSCode Claude", "vscode_claude", vsc_claude),
            ("Claude.app",    "claude_app",    claude_app),
            ("OpenCode",      "opencode",      opencode),
        ]:
            print(f"  {label:<14}  {by_1h[key]:>3}  {by_24h[key]:>3}  "
                  f"{by_7d[key]:>3}  {live:>4}")
        print(f"  vscode subprocesses  {vsc_total}")
    print()
