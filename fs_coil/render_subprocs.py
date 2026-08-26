"""Subprocesses pane + per-AI commands pane (live ps + EXEC aggregation).

Subprocs now folds in the old cpu+memory pane: each running AI bucket gets
a cpu/mem sparkline row directly under its PID list, so you only need one
section to see both 'who is running' and 'what are they burning'."""

import shutil
from collections import Counter
from datetime import datetime

from fs_coil.history import _ACTOR_LAST_SEEN, _hist, _sparkline
from fs_coil.parser import _fmt_size
from fs_coil.runtime import _running_actor_detail
from fs_coil.theme import (
    _BOLD, _C7, _DIM, _GREEN, _ORANGE, _R, _RED, _TREE_MID, _tty, head, item,
)


_CHART_W_FIXED = 250   # sparkline width — fixed 250 cols


def _chart_width():
    """Sparkline width is a fixed 250 cols. If the pane is narrower than
    250, we clamp to (pane_cols - 20) so the bar doesn't wrap onto the
    next row and step on content below."""
    try:
        cols = shutil.get_terminal_size((60, 24)).columns
    except Exception:
        cols = 60
    return max(20, min(_CHART_W_FIXED, cols - 20))


_AI_LABELS = [
    ("VSCode Claude", "vscode_claude"),
    ("Claude.app",    "claude_app"),
    ("OpenCode",      "opencode"),
]


def _render_subprocs(d, top=5):
    """Per-AI subprocess tree with inline cpu/mem sparklines:
      • bucket summary row  (aggregate cpu/mem for the whole AI)
      • sparkline row × 2   (cpu history + mem history, fixed-width)
      • child PIDs          (top N by cpu%)"""
    agg = _running_actor_detail()
    now = datetime.now()
    for bucket, info in agg.items():
        if info["n"] > 0:
            _ACTOR_LAST_SEEN[bucket] = now

    head("subprocs · cpu+mem per AI")
    NAME_W, PID_W, CPU_W, MEM_W = 14, 6, 5, 6
    chart_w = _chart_width()

    if _tty():
        print(f"{_C7}{_TREE_MID}{_R} {_DIM}"
              f"{'actor':<{NAME_W}}"
              f"{'pid':>{PID_W}}{'cpu':>{CPU_W+1}}{'mem':>{MEM_W+1}}  cmd{_R}")
        print(f"{_C7}{_TREE_MID}{_R} {_DIM}"
              + "─" * (NAME_W + PID_W + CPU_W + MEM_W + 10) + f"{_R}")

    def _pad(values):
        v = list(values)[-chart_w:]
        if len(v) < chart_w:
            v = [None] * (chart_w - len(v)) + v
        return v

    for label, key in _AI_LABELS:
        info  = agg.get(key, {"n": 0, "cpu": 0.0, "rss_kb": 0, "procs": []})
        procs = sorted(info["procs"], key=lambda p: p["cpu"], reverse=True)[:top]
        n     = info["n"]

        # Grow per-bucket cpu/mem history so sparklines survive across ticks.
        cpu_hist = _hist(f"cpu_{key}",    maxlen=40)
        mem_hist = _hist(f"mem_{key}_kb", maxlen=40)
        if n > 0:
            cpu_hist.append(info["cpu"])
            mem_hist.append(info["rss_kb"])

        if not _tty():
            print(f"  {label}: n={n} cpu {info['cpu']:.1f}% "
                  f"mem {_fmt_size(info['rss_kb'] * 1024)}")
            for p in procs:
                print(f"    {p['pid']:>6}  {p['cpu']:>5.1f}%  "
                      f"{_fmt_size(p['rss_kb'] * 1024):>7}  {p['name']}")
            continue

        last = _ACTOR_LAST_SEEN.get(key)
        if n == 0 and (not last or (now - last).total_seconds() > 3600):
            # Haven't seen this bucket in over an hour — skip entirely.
            continue
        if n == 0:
            print(f"{_C7}{_TREE_MID}{_R} {_DIM}{label:<{NAME_W}}{_R}"
                  f" {_DIM}{'·':>{PID_W}}{'·':>{CPU_W+1}}{'·':>{MEM_W+1}}  "
                  f"○ idle{_R}")
            continue

        # Row 1: bucket summary (aggregate cpu / mem).
        print(f"{_C7}{_TREE_MID}{_R} {_BOLD}{_GREEN}{label:<{NAME_W}}{_R}"
              f"{_DIM}{n:>{PID_W}}{_R}"
              f"{_BOLD}{_ORANGE}{info['cpu']:>{CPU_W}.1f}%{_R}"
              f" {_DIM}{_fmt_size(info['rss_kb'] * 1024):>{MEM_W}}{_R}  "
              f"{_DIM}total{_R}")
        # Row 2: CPU sparkline.
        cpu_tail    = _pad(cpu_hist)
        cpu_nonempty = [v for v in cpu_tail if v is not None]
        cpu_spark   = _sparkline(cpu_tail,
                                 max_val=max(max(cpu_nonempty, default=0), 5))
        print(f"{_C7}{_TREE_MID}{_R} {' ':<{NAME_W}}"
              f"{_DIM}{'cpu':>{PID_W+CPU_W+MEM_W+3}}{_R}  {cpu_spark}")
        # Row 3: memory sparkline.
        mem_tail  = _pad(mem_hist)
        mem_spark = _sparkline(mem_tail)
        print(f"{_C7}{_TREE_MID}{_R} {' ':<{NAME_W}}"
              f"{_DIM}{'mem':>{PID_W+CPU_W+MEM_W+3}}{_R}  {mem_spark}")
        for p in procs:
            cpu_c = _ORANGE if p["cpu"] > 1.0 else _DIM
            print(f"{_C7}{_TREE_MID}{_R} {' ':<{NAME_W}}"
                  f"{_DIM}{p['pid']:>{PID_W}}{_R}"
                  f"{cpu_c}{p['cpu']:>{CPU_W}.1f}%{_R}"
                  f" {_DIM}{_fmt_size(p['rss_kb']*1024):>{MEM_W}}{_R}  "
                  f"{p['name']}")
        if info["n"] > top:
            print(f"{_C7}{_TREE_MID}{_R} {' ':<{NAME_W}}"
                  f"{_DIM}{'…':>{PID_W}}{'':>{CPU_W+1}}{'':>{MEM_W+1}}  "
                  f"+{info['n'] - top} more{_R}")
    print()


def _render_commands(d):
    """Per-AI top commands invoked (exec events). Table-style, narrow.
    Three right-aligned count columns (1h / 24h / 7d) match ALERTS layout."""
    e1h = d.get("execs_1h")  or {}
    e24 = d.get("execs_24h") or {}
    e7d = d.get("execs_7d")  or {}
    total_1h = d.get("execs_total_1h") or 0

    head(f"commands  ·  {total_1h} (1h)")
    NAME_W, NUM_W = 14, 4

    if _tty():
        print(f"{_C7}{_TREE_MID}{_R} {_DIM}"
              f"{'actor / cmd':<{NAME_W}}"
              f"{'1h':>{NUM_W}}{'24h':>{NUM_W}}{'7d':>{NUM_W}}"
              f"{_R}")
        print(f"{_C7}{_TREE_MID}{_R} {_DIM}"
              + "─" * (NAME_W + NUM_W * 3) + f"{_R}")

    any_rendered = False
    for label, key in _AI_LABELS:
        c1  = e1h.get(key)  or Counter()
        c24 = e24.get(key)  or Counter()
        c7  = e7d.get(key)  or Counter()
        total_ai_1h = sum(c1.values())
        if total_ai_1h == 0 and not c24 and not c7:
            if _tty():
                print(f"{_C7}{_TREE_MID}{_R} {_DIM}{label:<{NAME_W}}{_R}"
                      f"{_DIM}{'·':>{NUM_W}}{'·':>{NUM_W}}{'·':>{NUM_W}}{_R}")
            else:
                print(f"  {label}: no commands")
            continue
        any_rendered = True
        if _tty():
            # Bucket row: bold name + aggregate counts.
            print(f"{_C7}{_TREE_MID}{_R} {_BOLD}{_GREEN}{label:<{NAME_W}}{_R}"
                  f"{_RED if total_ai_1h else _DIM}{_BOLD}"
                  f"{total_ai_1h:>{NUM_W}}{_R}"
                  f"{_ORANGE if sum(c24.values()) else _DIM}{_BOLD}"
                  f"{sum(c24.values()):>{NUM_W}}{_R}"
                  f"{_DIM}{_BOLD}{sum(c7.values()):>{NUM_W}}{_R}")
            # Per-command rows (top 6 to keep pane compact).
            for cmd, n in c1.most_common(6):
                n24 = c24[cmd]
                n7  = c7[cmd]
                color = _RED if n > 5 else _ORANGE if n > 0 else _DIM
                print(f"{_C7}{_TREE_MID}{_R}  {cmd[:NAME_W-2]:<{NAME_W-2}}"
                      f"{color}{_BOLD}{n:>{NUM_W}}{_R}"
                      f"{_DIM}{n24:>{NUM_W}}{n7:>{NUM_W}}{_R}")
        else:
            print(f"  {label}: {total_ai_1h} calls (1h)")
            for cmd, n in c1.most_common(6):
                print(f"    {n:>4} 1h  {c24[cmd]:>4} 24h  {c7[cmd]:>4} 7d  {cmd}")
    if not any_rendered and _tty():
        item(f"{_DIM}(no commands logged — restart daemon to arm exec events){_R}")
    print()
