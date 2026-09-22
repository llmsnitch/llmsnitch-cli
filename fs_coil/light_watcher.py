"""Light-mode watcher — no Full Disk Access, no root, no eslogger.

Delegates directory watching to `fswatch` (Homebrew), which uses macOS
FSEvents under the hood. FSEvents is user-scope: any path the invoking
user can read, `fswatch` can watch — no TCC / FDA required.

Trade-off vs. the eslogger deep mode:
  - Catches CREATE / RENAME / DELETE / MODIFY / ATTRIB on watched dirs.
  - Does NOT catch READS. FSEvents cannot report reads; that requires
    Endpoint Security (which requires FDA). If read-detection is critical
    for your threat model, use `fs-coil daemon` (deep mode) instead.

Runs as the user via LaunchAgent. Reuses deep mode's deny-list matcher and
Logger; every hit goes through `fs_coil.notify` (the doctrine gate).
"""

import os
import signal
import subprocess
import sys
from datetime import datetime

from fs_coil.denylist import (
    _shrink, compile_deny, is_sensitive_basename, match_deny, path_in_noise,
)
from fs_coil.logger import Logger
from fs_coil.notify import CATEGORIES, notify
from fs_coil.runtime import console_user, user_home

# Territory table (CONTEXT.md). ponytail: mirrors llmsnitch/scanrules
# .TERRITORIES by hand — fs_coil never imports llmsnitch; add `[agent.*]`
# config merge only if a territory must change without a release.
_TERRITORIES = {
    "claude-code": ("~/.claude", "~/.claude.json"),
    "codex":       ("~/.codex",),
    "aider":       ("~/.aider",),
    "copilot":     ("~/.copilot",),
    "cursor":      ("~/.cursor",),
    "windsurf":    ("~/.windsurf",),
    "agy":         ("~/.agy",),
}
_CACHE_PATHS = {"claude-code": ("~/.claude/plugins/cache",)}


def _inside(path, roots, home):
    """Exact-segment prefix; single-file roots match by equality."""
    roots = [home + r[1:] if r.startswith("~") else r for r in roots]
    return any(path == r or path.startswith(r + "/") for r in roots)


def classify_light(path, home):
    """(category, actor_bucket) from the path alone — FSEvents carries no
    pid, so light attributes territory, not actor (spec's named ceiling)."""
    for agent, roots in _TERRITORIES.items():
        if _inside(path, roots, home):
            cache = _inside(path, _CACHE_PATHS.get(agent, ()), home)
            return ("agent_plugin_cache" if cache else "agent_self"), agent
    return "deny_write", "unknown"


def route_hit(path, kind, hit, home, *, stdout_only=False, now=None):
    """One deny hit → one notify() call → (category, actor, notified).
    Low severity names no decision → record_only (scan.py's precedent);
    foreground `fs-coil light` ledgers but never banners."""
    category, actor = classify_light(path, home)
    low = CATEGORIES[category][1] == "low"
    subject = _shrink(path, home)
    notified = notify(
        "fs-coil-light", category, subject,
        actor_bucket=actor, deny_pattern=hit,
        record_only=low or stdout_only,
        message=(f"{subject}\nevent: {kind}\nrule: {hit}\n"
                 f"action: {CATEGORIES[category][2]}\n"
                 "(light mode: writes only — no read-detection)"),
        _now=now)
    return category, actor, notified

# Default paths — sensitive credential / config dirs the invoking user
# owns and can read without any special TCC grant.
DEFAULT_WATCH_PATHS = [
    "~/.ssh", "~/.aws", "~/.gnupg", "~/.docker", "~/.config/gh",
    "~/.kube", "~/.claude",
    "~/Library/LaunchAgents",
    # Individual dotfiles a compromised agent might overwrite as a backdoor:
    "~/.bashrc", "~/.zshrc", "~/.zshenv", "~/.zprofile", "~/.profile",
    "~/.gitconfig", "~/.netrc", "~/.npmrc", "~/.pypirc",
]

# fswatch -x flag column list; the columns we care about map cleanly to
# our existing (mode, event_kind) shape used by the eslogger path.
_MUTATE_FLAGS = {"Created", "Updated", "Renamed", "Removed",
                 "OwnerModified", "AttributeModified",
                 "MovedFrom", "MovedTo"}


def find_fswatch():
    """Locate fswatch; None if absent (install.sh should have brew-installed it)."""
    for p in ("/opt/homebrew/bin/fswatch", "/usr/local/bin/fswatch",
              "/opt/local/bin/fswatch"):
        if os.path.exists(p):
            return p
    return None


def _expand_paths(raw):
    """Expand ~ and drop paths that don't exist (fswatch errors on missing)."""
    out = []
    for p in raw:
        p = os.path.expanduser(p.strip())
        if p and os.path.exists(p):
            out.append(p)
    return out


def _parse_event(line):
    """Parse one `fswatch -x` line: 'PATH FLAG1 FLAG2 IsFile'.

    fswatch quotes paths with spaces; we handle the common case where the
    last N tokens are flag names from a known set. Anything before that is
    the path.
    """
    if not line or not line.strip():
        return None, []
    parts = line.rstrip("\n").split(" ")
    # Walk from the right; flags are all known symbols.
    known = _MUTATE_FLAGS | {"IsFile", "IsDir", "IsSymLink",
                             "Link", "PlatformSpecific", "OverflowError"}
    flags = []
    while parts and parts[-1] in known:
        flags.append(parts.pop())
    path = " ".join(parts)
    return path or None, list(reversed(flags))


def run_light_monitor(paths=None, stdout_only=False):
    """Watch `paths` (list of str) via fswatch; alert on deny-list hits."""
    user = console_user() or os.getenv("USER") or ""
    home = user_home(user) if user else os.path.expanduser("~")
    deny = compile_deny(home)
    logger = Logger(user)

    fswatch = find_fswatch()
    if fswatch is None:
        msg = ("[fs-coil light] fswatch not found — "
               "install with: brew install fswatch")
        logger.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}")
        print(msg, file=sys.stderr, flush=True)
        sys.exit(2)

    watched = _expand_paths(paths or DEFAULT_WATCH_PATHS)
    if not watched:
        msg = "[fs-coil light] no watched paths exist — nothing to do"
        logger.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}")
        print(msg, file=sys.stderr, flush=True)
        sys.exit(2)

    logger.write(
        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] fs-coil light starting "
        f"(user={user or 'none'}, paths={len(watched)}, rules={len(deny)}, "
        f"reads=UNAVAILABLE)"
    )

    # fswatch -x: include event flag column(s). -r: recursive.
    # --event-flags plus one-event-per-line is the default; -x prepends flags.
    argv = [fswatch, "-x", "-r"] + watched
    proc = subprocess.Popen(
        argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        bufsize=1, text=True,
    )

    def shutdown(*_):
        logger.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] fs-coil light stopping")
        try:
            proc.terminate()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    assert proc.stdout is not None
    for raw in proc.stdout:
        try:
            path, flags = _parse_event(raw)
            if not path or not flags:
                continue
            # Reads are simply not reported by FSEvents; every event is a
            # mutation, so mode = "W" for the deny matcher.
            if not (_MUTATE_FLAGS & set(flags)):
                continue
            mode = "W"

            basename = os.path.basename(path)
            sensitive = is_sensitive_basename(basename)
            if path_in_noise(path) and not sensitive:
                continue

            hit = match_deny(path, mode, deny)
            if not hit:
                continue

            kind = flags[0].lower() if flags else "modified"
            # Every hit is ledgered; the gate decides whether it banners.
            category, actor, notified = route_hit(
                path, kind, hit, home, stdout_only=stdout_only)
            logger.write(
                f"[{datetime.now():%Y-%m-%d %H:%M:%S}] DENY-MATCH "
                f"proc=?[0] src=light sign=- "
                f"severity={CATEGORIES[category][1]} "
                f"parent=?[0] daemon=no "
                f"event={kind} mode={mode} path={path} pattern={hit} "
                f"category={category} actor={actor} "
                f"notified={'yes' if notified else 'no'}"
            )
        except Exception as e:
            logger.write(
                f"[{datetime.now():%Y-%m-%d %H:%M:%S}] EVENT-ERROR "
                f"{type(e).__name__}: {str(e)[:200]}"
            )
            continue

    rc = proc.wait()
    logger.write(
        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] fswatch exited rc={rc}"
        + (f" stderr={proc.stderr.read().strip()}" if proc.stderr else "")
    )
    sys.exit(rc or 1)
