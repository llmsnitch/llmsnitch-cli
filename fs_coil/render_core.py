"""Core rendering primitives used by every render_* module.

Terminal-width helpers, ANSI-aware visible-length, the section/top-list
line builders, and the multi-column packer that flows blocks across the
available terminal width."""

import re
import shutil

from fs_coil.theme import (
    _BOLD, _C7, _DIAMOND, _DIM, _GREEN, _R, _TREE_MID, _TREE_TOP,
    _YELLOW, _tty, head, item,
)


def _term_cols():
    try:
        return max(40, min(shutil.get_terminal_size((80, 24)).columns, 120))
    except Exception:
        return 80


def _term_rows():
    try:
        return max(8, shutil.get_terminal_size((80, 24)).lines)
    except Exception:
        return 24


def _section(title, rows):
    head(title)
    maxw = max((len(r[0]) for r in rows), default=0)
    for (k, v, good) in rows:
        if _tty():
            c = _GREEN if good else _YELLOW
            print(f"{_C7}{_TREE_MID}{_R} {_DIM}{k:<{maxw}}{_R}  {c}{v}{_R}")
        else:
            print(f"  {k:<{maxw}}  {v}")


def _top_list(title, items, fmt):
    if not items:
        return
    head(title)
    for (key, count) in items:
        if _tty():
            print(f"{_C7}{_TREE_MID}{_R} {_BOLD}{_C7}{count:>4}{_R}  {fmt(key)}")
        else:
            print(f"  {count:>4}  {fmt(key)}")


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _vlen(s):
    """Visible (printable) length — strips ANSI color escapes."""
    return len(_ANSI_RE.sub("", s))


def _vpad(s, w):
    gap = w - _vlen(s)
    return s + (" " * gap) if gap > 0 else s


def _build_top_lines(title, items, fmt):
    """Return list of pre-formatted lines (header + rows) for a top-list block."""
    lines = [f"{_C7}{_TREE_TOP}{_DIAMOND}{_BOLD}{_C7}{title}{_R}"]
    for (key, count) in items:
        lines.append(
            f"{_C7}{_TREE_MID}{_R} {_BOLD}{_C7}{count:>4}{_R}  {fmt(key)}"
        )
    return lines


def _two_col(title_a, items_a, fmt_a, title_b, items_b, fmt_b):
    """Render two top-lists side-by-side when terminal ≥ 88 cols; otherwise
    fall back to stacked."""
    cols = _term_cols()
    if cols < 88 or not _tty() or not (items_a or items_b):
        if items_a:
            _top_list(title_a, items_a, fmt_a)
            print()
        if items_b:
            _top_list(title_b, items_b, fmt_b)
            print()
        return
    left  = _build_top_lines(title_a, items_a, fmt_a)
    right = _build_top_lines(title_b, items_b, fmt_b)
    width = cols // 2
    rows  = max(len(left), len(right))
    for i in range(rows):
        l = left[i]  if i < len(left)  else ""
        r = right[i] if i < len(right) else ""
        print(f"{_vpad(l, width)}{r}")
    print()


def _build_section_lines(title, rows):
    """Pre-format a status-style section (title + k/v rows) as lines."""
    out = [f"{_C7}{_TREE_TOP}{_DIAMOND}{_BOLD}{_C7}{title}{_R}"]
    maxw = max((len(r[0]) for r in rows), default=0)
    for (k, v, good) in rows:
        c = _GREEN if good else _YELLOW
        out.append(f"{_C7}{_TREE_MID}{_R} {_DIM}{k:<{maxw}}{_R}  {c}{v}{_R}")
    return out


def _two_blocks(left_lines, right_lines):
    """Print two pre-built line lists side-by-side or stacked (narrow term)."""
    cols = _term_cols()
    if cols < 88 or not _tty():
        for ln in left_lines:  print(ln)
        print()
        for ln in right_lines: print(ln)
        print()
        return
    width = cols // 2
    rows  = max(len(left_lines), len(right_lines))
    for i in range(rows):
        l = left_lines[i]  if i < len(left_lines)  else ""
        r = right_lines[i] if i < len(right_lines) else ""
        print(f"{_vpad(l, width)}{r}")
    print()


def _block(title, rows):
    """Prep a section as (lines, max_visible_width) — ready for _render_columns."""
    lines = _build_section_lines(title, rows)
    width = max((_vlen(ln) for ln in lines), default=0)
    return (lines, width)


def _top_block(title, items, fmt):
    """Wrap a top-list section as a (lines, width) block for _render_columns."""
    lines = _build_top_lines(title, items, fmt)
    width = max((_vlen(ln) for ln in lines), default=0)
    return (lines, width)


def _render_columns(blocks, gutter=2):
    """Greedy multi-column packer. Flows `blocks` into as many side-by-side
    columns as the terminal width allows, preserving input order. Falls back
    to one block per row on narrow terminals or non-TTY output."""
    if not blocks:
        return
    # Read raw terminal width (uncapped) so the packer can pack 3+ columns on
    # wide terminals. `_term_cols()` caps at 120 for legacy two-column callers.
    try:
        cols = max(40, shutil.get_terminal_size((120, 24)).columns)
    except Exception:
        cols = 120
    if not _tty():
        for lines, _ in blocks:
            for ln in lines:
                print(ln)
            print()
        return

    rows = []
    current = []
    current_w = 0
    for b in blocks:
        lines, w = b
        cost = w if not current else (current_w + gutter + w)
        if current and cost > cols:
            rows.append(current)
            current = [b]
            current_w = w
        else:
            current.append(b)
            current_w = cost
    if current:
        rows.append(current)

    sep = " " * gutter
    for row in rows:
        height = max(len(lines) for lines, _ in row)
        for i in range(height):
            parts = []
            for lines, w in row:
                ln = lines[i] if i < len(lines) else ""
                parts.append(_vpad(ln, w))
            print(sep.join(parts).rstrip())
        print()
