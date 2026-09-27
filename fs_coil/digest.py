"""Daily digest — the notify layer's pull outlet (docs/notifier-spec.md §3,
.wayfinder/digest-outlet). Renders the ledger's trailing 24h: ① health,
② new since last digest, ③ counts, ④ noisiest. Banners only when the
watchers themselves are unhealthy — findings never re-page from here.

fs_coil never imports llmsnitch: producers stamp state files under
~/.llmsnitch/ (scan meta.json, depaudit-state.json); this module reads them.
"""

import glob
import html
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from fs_coil import ledger, notify
from fs_coil.ledger import clean
from fs_coil.digest_agent import install_agent_run

PATROL_MAX_AGE = DEPAUDIT_MAX_AGE = 26 * 3600
BULLETIN_MAX_AGE_DAYS = 14
LOOKBACK = 7 * 86400
_CAP = 20                      # ② subjects on one screen; --full lifts it
_NO_DECISION = {c for c, (_, _, a) in notify.CATEGORIES.items() if a.startswith("none")}
_TIERS = ("critical", "high", "lesser")
_FIX = {"patrol": "launchctl kickstart gui/$(id -u)/com.slav-it.llmsnitch-patrol",
        "dep-audit": "llmsnitch depaudit",
        "bulletin": "refresh the bulletin cache (docs/bulletin-spec.md)",
        "notifier": "fs-coil status; NOTIFIER-ERROR lines in fs-coil logs"}

# ---------------------------------------------------------------- health

def _base_dir():
    return os.path.expanduser(os.environ.get("LLMSNITCH_DIR", "~/.llmsnitch"))


def _json(path):
    try:
        with open(path) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def health_report(now=None):
    """Watcher health from producer state files + the degraded flag. Never raises."""
    now = now if now is not None else time.time()
    patrol = None
    patrol_meta = None
    for p in glob.glob(os.path.join(_base_dir(), "scans", "*", "meta.json")):
        m = _json(p)
        if m.get("trigger") == "patrol" and _num(m.get("ended_at")) is not None:
            if patrol is None or m["ended_at"] > patrol:
                patrol, patrol_meta = m["ended_at"], m
    dep = _json(os.path.join(_base_dir(), "depaudit-state.json"))
    dep_ts, age = _num(dep.get("ts")), _num(dep.get("bulletin_age_days"))
    degraded = notify.get_degraded()

    def ago(ts):
        return f"{(now - ts) / 3600:.0f}h ago" if ts else "never"
    problems = []
    if patrol is None or now - patrol > PATROL_MAX_AGE:
        problems.append(f"patrol missed ({ago(patrol)})")
    if dep_ts is None or now - dep_ts > DEPAUDIT_MAX_AGE:
        problems.append(f"dep-audit missed ({ago(dep_ts)})")
    if age is None or age > BULLETIN_MAX_AGE_DAYS:
        problems.append(f"bulletin stale ({'unknown' if age is None else f'{age:.0f}d'})")
    if degraded:
        problems.append(f"notifier degraded: {clean(degraded)}")
    sev = (patrol_meta or {}).get("findings_by_severity")
    return {"now": now, "patrol_ts": patrol, "depaudit_ts": dep_ts,
            "bulletin_age_days": age, "degraded": degraded, "problems": problems,
            "scan_findings": sev if isinstance(sev, dict) else {},
            "scan_waived": _num((patrol_meta or {}).get("findings_waived")) or 0,
            "dep_findings": _num(dep.get("findings")) or 0,
            "dep_critical": _num(dep.get("findings_critical")) or 0}


# ---------------------------------------------------------------- render

def _key(r):
    return (r["category"], r.get("actor_bucket", "unknown"), r["subject"])


def _tier(r):
    """0 critical / 1 high / 2 lesser. record_only wins: dep-audit rows carry
    the category default severity ("critical") even when they are lesser."""
    if r.get("record_only") or r.get("severity") == "low":
        return 2
    if r.get("severity") == "critical" or r["subject"].startswith("critical "):
        return 0
    return 1


def _fmt(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def render(window, lookback, prior, health, *, start_ts, end_ts,
           full=False, skipped=0):
    """Plain text, four sections. window = [start, end); lookback = the 7
    days before start (new vs known); prior = the equal-length window just
    before start (resolved). Subject-level, from row presence — novelty_reason
    is tuple-level and not used."""
    seen = {_key(r) for r in lookback}
    prev = {_key(r) for r in prior}
    first = {}
    for r in window:
        first.setdefault(_key(r), r)
    new = {k for k in first if k not in seen}
    resolved = prev - set(first)
    now, probs = health["now"], health["problems"]

    def ran(ts):
        return f"ran {_fmt(ts)} ({(now - ts) / 3600:.0f}h ago)" if ts else "never"

    def missed(prefix):
        return "MISSED — last " if any(p.startswith(prefix) for p in probs) else ""
    age = health["bulletin_age_days"]
    L = [f"llmsnitch digest — {_fmt(end_ts)}  (window {_fmt(start_ts)} → "
         f"{_fmt(end_ts)}, {len(window)} rows, {skipped} skipped)", "",
         "① health",
         f"  patrol      {missed('patrol')}{ran(health['patrol_ts'])}",
         f"  dep-audit   {missed('dep-audit')}{ran(health['depaudit_ts'])} · bulletin "
         f"{'unknown' if age is None else f'{age:.1f}d'}{' STALE' if missed('bulletin') else ''}",
         f"  degraded    {health['degraded'] or 'none'}"]
    L += [f"  → action: {p} — {_FIX[p.split(' ')[0]]}" for p in probs] or \
         ["  → all watchers healthy"]

    sev = health.get("scan_findings", {})
    sc, sh, sl = sev.get("critical", 0), sev.get("high", 0), sev.get("low", 0)
    dc, dtot = health.get("dep_critical", 0), health.get("dep_findings", 0)
    waived = f" · {health['scan_waived']} waived" if health.get("scan_waived") else ""
    if sc or sh or sl or dtot:
        parts = []
        if sc or sh or sl:
            parts.append(f"scan {sc}c/{sh}h/{sl}l (llmsnitch scan --report)")
        if dtot:
            parts.append(f"dep-audit {dc}c/{dtot} (llmsnitch depaudit)")
        L += ["", "open findings (last patrol): " + " · ".join(parts) + waived]
    else:
        L += ["", "open findings: none" + waived]

    items = sorted((_tier(first[k]), k) for k in new if k[0] not in _NO_DECISION)
    m = len(new) - len(items)                 # D01/D02: no-decision categories live in ③
    L += ["", f"② new since last digest ({len(items)}"
          + (f" · {m} digest-only, see ③)" if m else ")")]
    last = None
    for i, (t, (cat, act, sub)) in enumerate(items):
        if i >= _CAP and not full:
            L.append(f"  … {len(items) - i} more (fs-coil digest --full)")
            break
        if (t, cat) != last:               # decision line once per category group
            last = (t, cat)
            L += [f"  [{_TIERS[t].upper()}] {cat}",
                  f"    → action: {notify.CATEGORIES.get(cat, ('', '', '-'))[2]}"]
        L.append(f"    {act} · {clean(sub)}")
    if not items:
        L.append("  nothing new")

    L += ["", "③ counts (category · actor: rows  new/known/resolved)"]
    by_tuple = Counter(k[:2] for k in (_key(r) for r in window))
    for tup in sorted(set(by_tuple) | {k[:2] for k in resolved},
                      key=lambda t: (-by_tuple[t], t)):
        ks = {k for k in first if k[:2] == tup}
        L.append(f"  {tup[0]} · {tup[1]}  {by_tuple[tup]}  "
                 f"{len(ks & new)}/{len(ks & seen)}/"
                 f"{len({k for k in resolved if k[:2] == tup})}")

    L += ["", "④ noisiest subjects"]
    L += [f"  {n}  {clean(s)}" for s, n in
          Counter(r["subject"] for r in window).most_common(5)] or ["  (no rows)"]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- command

def _write_private(path, data):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600),
                   "w") as f:
        f.write(data)
    os.chmod(path, 0o600)
    notify._chown_user(path)


def cmd_digest(*, full=False, show=False, prune=False, install_agent=False,
               write=False, now=None, out=None):
    out = out or sys.stdout
    if install_agent:
        return install_agent_run(write, out)
    d = ledger.ledger_dir()
    files = ledger.digest_files(d)
    if show:
        out.write(Path(files[-1]).read_text() if files else
                  "no digest yet — run `fs-coil digest` to write one "
                  "(--install-agent --write installs the daily 10:00 LaunchAgent)\n")
        return 0
    end = now if now is not None else time.time()
    today = datetime.fromtimestamp(end).strftime("%Y-%m-%d")
    prior = [f for f in files if not f.endswith(f"digest-{today}.txt")]
    start = os.path.getmtime(prior[-1]) if prior else end - 86400
    if not end - LOOKBACK <= start < end:     # missed days widen, capped;
        start = max(end - LOOKBACK, min(start, end - 86400))   # future mtime → 24h
    window, skipped = ledger.iter_rows(start, end)
    lookback, _ = ledger.iter_rows(start - LOOKBACK, start)
    prior = [r for r in lookback if r["ts"] >= start - (end - start)]
    health = health_report(end)
    text = render(window, lookback, prior, health, start_ts=start,
                  end_ts=end, full=full, skipped=skipped)

    notify._mkdir_owned(d, 0o700)
    path = os.path.join(d, f"digest-{today}.txt")
    _write_private(path, text)
    # Browser twin — what a banner click opens (.wayfinder/notification-click
    # D01): the .html default handler is a browser on every OS, never an IDE.
    _write_private(path[:-4] + ".html",
                   f"<!doctype html><meta charset=utf-8><title>llmsnitch digest "
                   f"{today}</title><pre>{html.escape(text)}</pre>\n")
    out.write(f"digest written: {path}\n")

    if health["problems"] and notify._bool(
            notify._read_ini().get("notify", {}).get("outlet_digest"), True):
        joined = "; ".join(health["problems"])
        if notify.notify("digest", "watcher_health", joined,
                         actor_bucket="llmsnitch",
                         title="🐍 llmsnitch · watchers unhealthy",
                         message=f"{joined}\naction: fs-coil digest --show",
                         _now=end):
            out.write(f"banner: {joined}\n")
    if prune:
        from fs_coil.commands import cmd_prune
        cmd_prune(target="notify")
    return 0
