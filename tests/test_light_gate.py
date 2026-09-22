"""fs-coil light through the doctrine gate (wayfinder/quiet-light, T801).

Synthetic home and paths only — never the live store or a real subject.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fs_coil import light_watcher as lw  # noqa: E402
from tests import _seams  # noqa: E402
from tests._seams import rows, with_tmp  # noqa: E402

HOME = "/Users/probe"
T0 = 1_755_600_000.0
CACHE_HIT = f"{HOME}/.claude/plugins/cache/temp_git_1_ab/.git/hooks/x.sample"


def _c(p):
    return lw.classify_light(p, HOME)


def test_classify_territory_table():
    assert _c(CACHE_HIT) == ("agent_plugin_cache", "claude-code")
    assert _c(f"{HOME}/.claude/settings.json") == ("agent_self", "claude-code")
    assert _c(f"{HOME}/.claude.json") == ("agent_self", "claude-code")
    assert _c(f"{HOME}/.codex/config.toml") == ("agent_self", "codex")
    assert _c(f"{HOME}/.zprofile") == ("deny_write", "unknown")
    assert _c(f"{HOME}/.ssh/config") == ("deny_write", "unknown")
    # whole-segment prefix: ~/.claude-evil is not inside ~/.claude
    assert _c(f"{HOME}/.claude-evil/settings.json") == ("deny_write", "unknown")


def test_low_category_ledgers_never_banners():
    def body(t, delivered, errors):
        out = lw.route_hit(CACHE_HIT, "created", "/**/.git/hooks/**", HOME, now=T0)
        assert out == ("agent_plugin_cache", "claude-code", False)
        assert delivered == [] and errors == []
        (r,) = rows(t)
        assert r["surface"] == "fs-coil-light"
        assert r["record_only"] is True and r["notified"] is False
        assert r["novelty_reason"] == "first_seen"        # first ever, still silent
        assert r["subject"] == "~/.claude/plugins/cache/temp_git_1_ab/.git/hooks/x.sample"
        assert r["deny_pattern"] == "/**/.git/hooks/**"
        assert r["actor_bucket"] == "claude-code"
    with_tmp(body)


def test_deny_write_banners_once_per_window():
    def body(t, delivered, errors):
        a = lw.route_hit(f"{HOME}/.zprofile", "updated", "~/.zprofile", HOME, now=T0)
        b = lw.route_hit(f"{HOME}/.ssh/config", "updated", "~/.ssh/**", HOME, now=T0 + 60)
        assert a == ("deny_write", "unknown", True)
        assert b == ("deny_write", "unknown", False)     # same tuple, inside 1h
        assert len(delivered) == 1 and errors == []
        surface, category, subject, bucket, pattern, title, message = delivered[0][:7]
        assert (surface, category, subject, bucket) == \
            ("fs-coil-light", "deny_write", "~/.zprofile", "unknown")
        assert pattern == "~/.zprofile" and title is None
        assert "event: updated" in message and "action: investigate" in message
        assert [x["novelty_reason"] for x in rows(t)] == ["first_seen", "window_repeat"]
    with_tmp(body)


def test_stdout_only_ledgers_without_banner():
    def body(t, delivered, errors):
        out = lw.route_hit(f"{HOME}/.zprofile", "updated", "~/.zprofile", HOME,
                           stdout_only=True, now=T0)
        assert out == ("deny_write", "unknown", False)
        assert delivered == []
        assert rows(t)[0]["record_only"] is True
    with_tmp(body)


if __name__ == "__main__":
    sys.exit(_seams.run(globals()))
