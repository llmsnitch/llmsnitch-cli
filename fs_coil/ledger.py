"""Ledger reader for the notify layer (T601, Agent A).

Public API:
  ledger_dir() -> str
  iter_rows(start_ts, end_ts, *, dir_path=None) -> tuple[list[dict], int]
  cmd_noise(category=None, actor=None, days=1, all_rows=False, *, now=None) -> None

Stdlib only. No network. Never raises to the caller.
"""

import json
import os
import re
from collections import defaultdict
from datetime import date, datetime, timedelta

_FILE_RE = re.compile(r"^events-(\d{4}-\d{2}-\d{2})\.ndjson$")
_CTRL = re.compile(r"[\x00-\x1f\x7f]")


def clean(s):
    """Ledger subjects are hostile input (root-observed paths): never let
    a control sequence reach a terminal or the digest file."""
    return _CTRL.sub(" ", str(s))


# ---------------------------------------------------------------- public API

def ledger_dir() -> str:
    """Return the notify ledger directory (no mkdir)."""
    from fs_coil.notify import _notify_dir
    return _notify_dir()


def iter_rows(start_ts, end_ts, *, dir_path=None):
    """Return (rows, skipped_count).

    Rows where start_ts <= row["ts"] < end_ts, sorted ascending by ts.
    Only reads files named ^events-YYYY-MM-DD.ndjson$ whose date falls
    within [date(start_ts)-1d, date(end_ts)+1d].

    Hostile-input guarantees: never raises; invalid/undecodable lines are
    skipped and counted in the second return value.
    Missing dir or file -> ([], 0).
    """
    d = dir_path if dir_path is not None else ledger_dir()
    if not os.path.isdir(d):
        return ([], 0)

    start_date = datetime.fromtimestamp(start_ts).date() - timedelta(days=1)
    end_date   = datetime.fromtimestamp(end_ts).date()   + timedelta(days=1)

    out: list = []
    skipped = 0

    try:
        names = sorted(os.listdir(d))
    except OSError:
        return ([], 0)

    for name in names:
        m = _FILE_RE.match(name)
        if not m:
            continue
        try:
            file_date = date.fromisoformat(m.group(1))
        except ValueError:
            continue
        if not (start_date <= file_date <= end_date):
            continue

        path = os.path.join(d, name)
        try:
            with open(path, "rb") as fh:
                raw = fh.read()
        except OSError:
            continue

        for line_bytes in raw.splitlines():
            try:
                line = line_bytes.decode("utf-8")
            except Exception:               # noqa: BLE001
                skipped += 1
                continue
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            if not (isinstance(obj, dict)
                    and isinstance(obj.get("ts"), (int, float))
                    and isinstance(obj.get("category"), str)
                    and isinstance(obj.get("subject"), str)):
                skipped += 1
                continue
            if start_ts <= obj["ts"] < end_ts:
                out.append(obj)

    out.sort(key=lambda r: r["ts"])
    return (out, skipped)


def cmd_noise(category=None, actor=None, days=1, all_rows=False, *,
              now=None) -> None:
    """Print ledger rows grouped by category then actor_bucket (spec §2).

    Default shows only suppressed (notified==False) rows from today's and
    the (days-1) previous calendar-day files.  --all includes notified rows.
    --category and --actor compose as AND filters.
    """
    import time as _time
    from fs_coil.theme import _DIM, _R, _tty, head, item

    _now = now if now is not None else _time.time()

    # Calendar-day selection: start = local midnight of (today − (days−1) days)
    today = datetime.fromtimestamp(_now).date()
    start_date = today - timedelta(days=max(0, days - 1))
    start_ts = datetime.combine(start_date,
                                datetime.min.time()).timestamp()
    end_ts = _now + 1          # +1 so now itself is included

    result_rows, skipped = iter_rows(start_ts, end_ts)

    # Filter
    filtered = []
    for r in result_rows:
        if not all_rows and r.get("notified", False):
            continue
        if category and r.get("category") != category:
            continue
        if actor and r.get("actor_bucket") != actor:
            continue
        filtered.append(r)

    head(f"noise (last {days} day{'s' if days != 1 else ''})")

    if not filtered:
        item("nothing in this window — tune windows with [notify] "
             "window_<category> = 24h in ~/.config/llmsnitch/config")
        if skipped:
            item(f"{skipped} malformed line(s) skipped")
        return

    # Group by (category, actor_bucket)
    groups: dict = defaultdict(list)
    for r in filtered:
        key = (r.get("category", ""), r.get("actor_bucket", "unknown"))
        groups[key].append(r)

    for (cat, act) in sorted(groups):
        rows_in_group = groups[(cat, act)]
        item(f"{cat} · {act}: {len(rows_in_group)} row(s)")
        for r in rows_in_group[-10:]:
            ts_str = datetime.fromtimestamp(r["ts"]).strftime("%m-%d %H:%M:%S")
            subj = clean(r.get("subject", ""))
            act_b = r.get("actor_bucket", "unknown")
            nov = r.get("novelty_reason", "")
            if _tty():
                print(f"    {_DIM}{ts_str}{_R}  {subj}  {act_b}  {nov}")
            else:
                print(f"    {ts_str}  {subj}  {act_b}  {nov}")

    if skipped:
        item(f"{skipped} malformed line(s) skipped")
