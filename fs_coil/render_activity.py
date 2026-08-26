"""Activity-related render panes: the packed top-band (charts + top-lists),
plus the standalone two-col / recent / timeline / rules / offenders panes
exposed via the --section flag."""

from fs_coil.classify import _short_sign
from fs_coil.denylist import _shrink
from fs_coil.network import _NET_SESSION
from fs_coil.render_charts import _hourly_block, _timeline_block
from fs_coil.render_core import _render_columns, _top_block, _two_col
from fs_coil.theme import (
    _BOLD, _C7, _DIM, _ORANGE, _R, _RED, _TREE_MID, _YELLOW, _tty, head, item,
)


def _render_offenders(d):
    _two_col(
        "top offenders", d["actors"].most_common(5),   lambda k: _shrink(k, d["home"]),
        "top parents",   d["parents"].most_common(5),  lambda k: k or "?",
    )


def _render_rules(d):
    _two_col(
        "top rules", d["patterns"].most_common(5), lambda k: k,
        "top paths", d["paths"].most_common(5),    lambda k: _shrink(k, d["home"]),
    )


def _render_timeline(d):
    """Standalone timeline (used by the tmux dashboard section selector)."""
    lines, _ = _timeline_block(d)
    for ln in lines:
        print(ln)
    print()


def _render_activity(d):
    """Timeline + hourly sparkline + all top-lists, packed across the width."""
    blocks = [_timeline_block(d), _hourly_block(d)]
    if d["actors"]:
        blocks.append(_top_block("top offenders", d["actors"].most_common(5),
                                  lambda k: _shrink(k, d["home"])))
    if d["parents"]:
        blocks.append(_top_block("top parents",   d["parents"].most_common(5),
                                  lambda k: k or "?"))
    if d["sources"]:
        blocks.append(_top_block("top sources",   d["sources"].most_common(5),
                                  lambda k: k))
    if d["signs"]:
        blocks.append(_top_block("top signing ids", d["signs"].most_common(5),
                                  lambda k: k))
    if d["patterns"]:
        blocks.append(_top_block("top rules",     d["patterns"].most_common(5),
                                  lambda k: k))
    if d["paths"]:
        blocks.append(_top_block("top paths",     d["paths"].most_common(5),
                                  lambda k: _shrink(k, d["home"])))

    # Per-AI top commands (EXEC aggregation, 7-day window).
    execs_7d = d.get("execs_7d") or {}
    ai_labels = [
        ("VSCode Claude", "vscode_claude"),
        ("Claude.app",    "claude_app"),
        ("OpenCode",      "opencode"),
    ]
    for label, key in ai_labels:
        cnt = execs_7d.get(key)
        if cnt:
            blocks.append(_top_block(f"cmds · {label}", cnt.most_common(5),
                                      lambda k: k))

    # Per-AI top remote hosts (populated live via _sample_network — session
    # scope, since we don't persist NET lines yet).
    for label, key in ai_labels:
        hosts = _NET_SESSION.get(key, {}).get("hosts")
        if hosts:
            blocks.append(_top_block(f"hosts · {label}", hosts.most_common(5),
                                      lambda k: k))

    _render_columns(blocks)


def _render_recent(d, limit=8):
    matches = d["matches"]
    home = d["home"]
    head(f"recent (last {min(limit, len(matches))})")
    if not matches:
        item(f"{_DIM}no matches yet{_R}" if _tty() else "no matches yet")
        print()
        return
    for m in matches[-limit:]:
        ts     = m["dt"].strftime("%H:%M:%S")
        who    = m.get("via") or m["proc"]
        src    = m.get("src")  or "?"
        sign   = _short_sign(m.get("sign") or "")
        parent = m.get("parent") or "?"
        ppid   = m.get("ppid") or "0"
        daemon_badge = " [D]" if m.get("daemon") == "yes" else ""
        mc = _ORANGE if m["mode"] == "R" else _YELLOW
        if _tty():
            print(
                f"{_C7}{_TREE_MID}{_R} {_DIM}{ts}{_R} {mc}{m['mode']}{_R} "
                f"{who}[{m['pid']}]{_YELLOW}{daemon_badge}{_R}  "
                f"{_DIM}← {parent}[{ppid}]{_R}  "
                f"{_YELLOW}{src}{_R}{_DIM}/{_R}{_ORANGE}{sign}{_R}  "
                f"{_shrink(m['path'], home)}"
            )
        else:
            print(
                f"  {ts} {m['mode']} {who}[{m['pid']}]{daemon_badge} "
                f"← {parent}[{ppid}]  {src}/{sign}  {_shrink(m['path'], home)}"
            )
    print()
