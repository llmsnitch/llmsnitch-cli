"""Posture / health / actors panes.

These are the slow-moving context blocks at the top of the static report.
Health is also reused as the bottom of the dashboard sidebar."""

from pathlib import Path

from fs_coil.constants import (
    BIN_PATH, ESLOGGER, INTERPRETER_PROC, PLIST_PATH, SENSITIVE_BASENAME_GLOBS,
    WATCHED_PROC,
)
from fs_coil.denylist import _shrink
from fs_coil.parser import _fmt_size
from fs_coil.render_core import _block, _render_columns
from fs_coil.theme import (
    _BOLD, _C7, _DIM, _GREEN, _ORANGE, _R, _TREE_MID, _YELLOW, _tty, head, item,
)


def _render_posture(d):
    """All posture blocks greedily packed into as many columns as fit."""
    rt = d["rt"]
    daemon_label = {
        "running":     "● running",
        "not running": "○ not running",
        "waiting":     "◐ waiting (launchd throttle)",
        "?":           "○ not loaded",
    }.get(rt["state"], f"● {rt['state']}")

    pid_s       = str(rt["pid"])      if rt["pid"]      else "—"
    runcount_s  = str(rt["run_count"]) if rt["run_count"] is not None else "—"
    lastexit_s  = rt["last_exit"]      or "—"
    uptime_s    = rt["etime"]          or "—"
    cpu_s       = f"{rt['pcpu']:.1f}%" if rt["pcpu"] is not None else "—"
    rss_s       = _fmt_size(rt["rss_kb"] * 1024) if rt["rss_kb"] is not None else "—"

    blocks = [
        _block("status", [
            ("daemon",   daemon_label,                           rt["state"] == "running"),
            ("user",     d["user"],                              bool(d["user"])),
            ("rules",    f"{d['total']}  (R:{d['r_cnt']} W:{d['w_cnt']} RW:{d['rw_cnt']})",
                                                                 d["total"] > 0),
            ("log span", d["log_span"],                          bool(d["log_files"])),
        ]),
        _block("daemon runtime", [
            ("pid",        pid_s,      rt["pid"] is not None),
            ("state",      rt["state"], rt["state"] == "running"),
            ("uptime",     uptime_s,   rt["etime"] is not None),
            ("cpu",        cpu_s,      rt["pcpu"] is not None),
            ("memory",     rss_s,      rt["rss_kb"] is not None),
            ("run count",  runcount_s, rt["run_count"] == 1),
            ("last exit",  lastexit_s, "never exited" in lastexit_s),
        ]),
        _block("paths", [
            ("plist",      str(PLIST_PATH),                               PLIST_PATH.exists()),
            ("binary",     str(BIN_PATH),                                 BIN_PATH.exists()),
            ("log dir",    _shrink(str(d["log_dir"]),  d["home"]),        d["log_dir"].is_dir()),
            ("icon cache", f"{_shrink(str(d['icon_dir']), d['home'])} ({d['icon_count']})",
                                                                          d["icon_dir"].is_dir()),
            ("config",     _shrink(f"{d['home']}/.config/llmsnitch/config", d["home"]),
                           Path(f"{d['home']}/.config/llmsnitch/config").exists()),
        ]),
        _block("activity (7d)", [
            ("matches", f"{d['h1']} (1h) · {d['d1']} (24h) · {d['d7']} (7d)",
                        d["h1"] == 0),
            ("sources", f"{d['interactive_n']} interactive · {d['daemon_n']} daemon",
                        d["daemon_n"] == 0),
        ]),
        _block("log volume", [
            ("files",       str(len(d["log_files"])),        bool(d["log_files"])),
            ("total size",  _fmt_size(d["log_bytes"]),       True),
            ("total lines", f"{d['log_lines']:,}",           True),
            ("deny hits",   f"{d['match_lines']:,}",         d["match_lines"] == 0),
        ]),
    ]
    _render_columns(blocks)


def _render_health(d):
    """Health + watched — compact indicators only (no verbose paths)."""
    head("health")
    # Just a green ✓ or yellow ✗ per check. Paths dropped — they were noise.
    checks = [
        ("eslogger",     d["eslogger_ok"]),
        ("notifier",     bool(d["notifier"])),
        ("FDA grant",    d["fda_inferred"]),
        ("log writable", d["log_writable"]),
        ("plist",        PLIST_PATH.exists()),
    ]
    for k, ok in checks:
        mark  = "✓" if ok else "✗"
        color = _GREEN if ok else _YELLOW
        if _tty():
            print(f"{_C7}{_TREE_MID}{_R} {_DIM}{k:<14}{_R}  "
                  f"{_BOLD}{color}{mark}{_R}")
        else:
            print(f"  {k:<14}  {mark}")
    print()

    head("watched")
    # One item per line — keeps the narrow sidebar pane from wrapping.
    # Interpreters are shown as a count, not the full list (it used to
    # blow past 60 cols and wrap).
    agents_line = " · ".join(WATCHED_PROC)
    interp_line = f"{len(INTERPRETER_PROC)} interpreters"
    sens_line   = f"{len(SENSITIVE_BASENAME_GLOBS)} sensitive globs"
    for k, v in (("agents", agents_line),
                 ("interpreters", interp_line),
                 ("sensitive", sens_line)):
        if _tty():
            print(f"{_C7}{_TREE_MID}{_R} {_DIM}{k:<14}{_R}  {v}")
        else:
            print(f"  {k:<14}  {v}")
    print()


def _render_actors(d):
    """Unique (name, source, signing id) actor triples — who/what/where."""
    ident = d.get("actor_identity")
    if not ident:
        return
    head("known actors (who · where · what)")
    # Column widths based on longest value.
    rows = ident.most_common(12)
    name_w = max(len(n) for (n, _s, _g), _ in rows) if rows else 0
    src_w  = max(len(s) for (_n, s, _g), _ in rows) if rows else 0
    for (name, src, sign), count in rows:
        if _tty():
            print(
                f"{_C7}{_TREE_MID}{_R} {_BOLD}{_C7}{count:>4}{_R}  "
                f"{_GREEN}{name:<{name_w}}{_R}  "
                f"{_DIM}·{_R}  {_YELLOW}{src:<{src_w}}{_R}  "
                f"{_DIM}·{_R}  {_ORANGE}{sign}{_R}"
            )
        else:
            print(f"  {count:>4}  {name:<{name_w}}  ·  {src:<{src_w}}  ·  {sign}")
    print()
