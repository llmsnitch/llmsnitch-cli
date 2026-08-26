"""Daily / hourly chart blocks + a small horizontal-bar helper.

Returns (lines, width) tuples ready to feed _render_columns. Pure-render —
no data collection happens here."""

from fs_coil.render_core import _vlen
from fs_coil.theme import (
    _BOLD, _C7, _DIAMOND, _DIM, _ORANGE, _R, _TREE_MID, _TREE_TOP,
)


def _bar(n, max_n, width=20):
    if max_n <= 0:
        return "░" * width
    filled = int(round((n / max_n) * width))
    return ("█" * filled) + ("░" * (width - filled))


def _timeline_block(d):
    """Return the hits-per-day timeline as a (lines, width) block."""
    rows = d["hits_per_day"]
    max_n = max((n for _, n in rows), default=0)
    lines = [f"{_C7}{_TREE_TOP}{_DIAMOND}{_BOLD}{_C7}hits per day (last 7){_R}"]
    for date, n in rows:
        bar = _bar(n, max_n, width=20)
        weekday = date.strftime("%a")
        cn = _ORANGE if n > 0 else _DIM
        lines.append(
            f"{_C7}{_TREE_MID}{_R} {_DIM}{date.strftime('%m-%d')} {weekday}{_R}  "
            f"{cn}{bar}{_R}  {_BOLD}{n}{_R}"
        )
    return (lines, max((_vlen(ln) for ln in lines), default=0))


def _hourly_block(d, cell_w=2):
    """Return the hits-per-hour chart as a (lines, width) block.

    `cell_w` controls chart width: 2 (default) = 48 chars = bar + space
    between each hour. 1 = 24 chars = bars packed edge-to-edge, ~50%
    narrower for compact panes (used by the file_alerts section)."""
    rows   = d["hits_per_hour"]          # 24 entries
    n_rows = 6                           # bar chart height in text rows
    max_n  = max((n for _, n in rows), default=0)
    total  = sum(n for _, n in rows)
    active = sum(1 for _, n in rows if n > 0)
    ramp   = "▁▂▃▄▅▆▇█"                  # 1/8 .. 8/8 vertical blocks

    # Height of each hour's bar, in eighths (0 .. n_rows * 8).
    heights = []
    for _dt, n in rows:
        if max_n <= 0 or n <= 0:
            heights.append(0)
        else:
            heights.append(max(1, int(round((n / max_n) * n_rows * 8))))

    # Trailing space is only emitted when cell_w=2, giving breathing room
    # between bars. For cell_w=1 the bars sit edge-to-edge — compact.
    gap = " " if cell_w > 1 else ""
    def _cell(h, row):
        remaining = h - row * 8
        if remaining >= 8:
            return f"{_ORANGE}█{_R}{gap}"
        if remaining > 0:
            return f"{_ORANGE}{ramp[remaining - 1]}{_R}{gap}"
        return f"{_DIM}·{_R}{gap}"

    # Y-axis: label top / middle / bottom rows with the value represented
    # by the TOP edge of that row, so the reader can eyeball magnitudes.
    label_w = max(len(str(max_n)), 1)
    def _y_label(row):
        if row == n_rows - 1:
            return f"{max_n:>{label_w}}"
        if row == 0:
            return f"{0:>{label_w}}"
        if row == n_rows // 2:
            return f"{max_n // 2:>{label_w}}"
        return " " * label_w

    bar_rows = []
    for row in range(n_rows - 1, -1, -1):   # top row down to bottom
        bars = "".join(_cell(h, row) for h in heights)
        bar_rows.append((row, bars))

    # Hour labels at 00 / 06 / 12 / 18 — placed at the corresponding bar col.
    axis_chars = [" "] * (24 * cell_w)
    for i in (0, 6, 12, 18):
        hr = rows[i][0].hour
        s  = f"{hr:02d}"
        axis_chars[i * cell_w]     = s[0]
        axis_chars[i * cell_w + 1] = s[1]
    axis = "".join(axis_chars)

    now_h = rows[-1][0].strftime("%H") if rows else "??"
    title = (f"hits per hour (last 24) · total {total} · "
             f"active {active}/24 · now {now_h}h")

    # Y-tick character: `┤` draws a faint gutter between label and bars.
    lines = [f"{_C7}{_TREE_TOP}{_DIAMOND}{_BOLD}{_C7}{title}{_R}"]
    for row, bars in bar_rows:
        y = _y_label(row)
        lines.append(f"{_C7}{_TREE_MID}{_R} {_DIM}{y} ┤{_R} {bars}")
    # Axis line aligns with bars: pad past the label + tick column.
    axis_pad = " " * (label_w + 2)
    lines.append(f"{_C7}{_TREE_MID}{_R} {_DIM}{axis_pad}{axis}{_R}")
    return (lines, max((_vlen(ln) for ln in lines), default=0))
