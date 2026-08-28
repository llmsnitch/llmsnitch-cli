"""Module-level mutable state shared across --live ticks.

_STATS_HISTORY  — per-metric deques feeding the live sparklines.
_ACTOR_LAST_SEEN — per-bucket datetime of last running observation, so a row
stays visible for ≤ 1 hour after the process disappears.
_sparkline — compact block-character renderer.
"""

from collections import deque

from fs_coil.theme import _DIM, _ORANGE, _R

_STATS_HISTORY = {}   # {metric_name: deque}
# Persistent "last seen" timestamps per AI bucket, so a row stays visible
# for ≤ 1 hour after the last time we saw the process run.
_ACTOR_LAST_SEEN = {}


def _hist(metric, maxlen=40):
    dq = _STATS_HISTORY.get(metric)
    if dq is None or dq.maxlen != maxlen:
        dq = _STATS_HISTORY[metric] = deque(maxlen=maxlen)
    return dq


def _sparkline(values, max_val=None):
    """Compact ramp-based sparkline. Empty cells render as BLANK spaces so
    the chart looks clean on dark backgrounds (no '·' dots noise)."""
    ramp = "▁▂▃▄▅▆▇█"
    if not values:
        return ""
    if max_val is None:
        # Filter None out of max() so left-padded deques don't crash.
        nonnull = [v for v in values if v is not None]
        max_val = max(nonnull, default=1)
    hi = max_val if max_val and max_val > 0 else 1
    out = []
    for v in values:
        if v is None:
            out.append(" ")
        elif v <= 0:
            # True-zero samples get a baseline tick so you can distinguish
            # "no data yet" (space) from "process was alive but idle" (dim ▁).
            out.append(f"{_DIM}▁{_R}")
        else:
            idx = min(7, max(0, int((v / hi) * 8) - 1))
            out.append(f"{_ORANGE}{ramp[idx]}{_R}")
    return "".join(out)


