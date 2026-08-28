"""Core rendering primitives used by every render_* module.

Terminal-width helpers, ANSI-aware visible-length, the section/top-list
line builders, and the multi-column packer that flows blocks across the
available terminal width."""

import re
import shutil

from fs_coil.theme import (
    _BOLD, _C7, _DIAMOND, _DIM, _GREEN, _R, _TREE_MID, _TREE_TOP,
    _YELLOW, _tty,
)

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


def _build_section_lines(title, rows):
    """Pre-format a status-style section (title + k/v rows) as lines."""
    out = [f"{_C7}{_TREE_TOP}{_DIAMOND}{_BOLD}{_C7}{title}{_R}"]
    maxw = max((len(r[0]) for r in rows), default=0)
    for (k, v, good) in rows:
        c = _GREEN if good else _YELLOW
        out.append(f"{_C7}{_TREE_MID}{_R} {_DIM}{k:<{maxw}}{_R}  {c}{v}{_R}")
    return out


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
    # Read raw terminal width (uncapped) so the packer can pack 3+ columns
    # on wide terminals.
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
