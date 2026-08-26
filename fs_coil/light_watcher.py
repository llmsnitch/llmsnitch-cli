"""Light-mode watcher — no Full Disk Access, no root, no eslogger.

Delegates directory watching to `fswatch` (Homebrew), which uses macOS
FSEvents under the hood. FSEvents is user-scope: any path the invoking
user can read, `fswatch` can watch — no TCC / FDA required.

Trade-off vs. the eslogger deep mode:
  - Catches CREATE / RENAME / DELETE / MODIFY / ATTRIB on watched dirs.
  - Does NOT catch READS. FSEvents cannot report reads; that requires
    Endpoint Security (which requires FDA). If read-detection is critical
    for your threat model, use `fs-coil daemon` (deep mode) instead.

Runs as the user via LaunchAgent. Reuses the same deny-list matcher,
Logger, and Notifier as deep mode so log lines and alerts stay uniform.
"""

import configparser
import fnmatch
import os
import re
import signal
import subprocess
import sys
from datetime import datetime

from fs_coil.denylist import (
    _shrink, compile_deny, is_sensitive_basename, match_deny, path_in_noise,
)
from fs_coil.logger import Logger
from fs_coil.notifier import Notifier
from fs_coil.runtime import console_user, user_home


def load_notify_suppress(config_path="~/.config/llm-snitch/config"):
    """Read [notify] suppress_* rules from user config.

    Each `suppress_<name>` key defines a category whose comma-separated
    fnmatch globs match against the full path. A matching write is logged
    with a `suppressed=<name>` tag and never notifies. Malformed config
    returns [] — the notifier stays fail-safe.
    """
    rules = []
    try:
        cp = configparser.ConfigParser(inline_comment_prefixes=("#",))
        cp.read(os.path.expanduser(config_path))
        if not cp.has_section("notify"):
            return rules
        for key, raw in cp["notify"].items():
            if not key.startswith("suppress_"):
                continue
            category = key[len("suppress_"):]
            globs = [os.path.expanduser(g.strip())
                     for g in raw.split(",") if g.strip()]
            if globs:
                rules.append((category, globs))
    except Exception:
        pass
    return rules


def match_suppress(path, rules):
    """Return category name if `path` matches any suppress glob, else None."""
    for category, globs in rules:
        for g in globs:
            if fnmatch.fnmatch(path, g):
                return category
    return None

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
    notifier = Notifier()
    suppress_rules = load_notify_suppress()

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
    if not stdout_only:
        notifier.notify(
            "🐍 fs-coil (light) armed",
            f"watching {len(watched)} paths — writes only, no reads",
            "startup",
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
            suppressed = match_suppress(path, suppress_rules)
            line = (
                f"[{datetime.now():%Y-%m-%d %H:%M:%S}] DENY-MATCH "
                f"proc=?[0] src=light sign=- severity=high "
                f"parent=?[0] daemon=no "
                f"event={kind} mode={mode} path={path} pattern={hit}"
                + (f" suppressed={suppressed}" if suppressed else "")
            )
            logger.write(line)

            # Suppressed events are logged (recall via `fs-coil noise`) but
            # never notify — the AGENTS.md actionability rule: no page
            # without a decision the user can act on.
            if not stdout_only and not suppressed:
                title = "🐍 fs-coil (light) · W"
                message = (
                    f"{_shrink(path, home)}\n"
                    f"event: {kind}\n"
                    f"rule: {hit}\n"
                    f"(light mode: writes only — no read-detection)"
                )
                notifier.notify(
                    title=title,
                    message=message,
                    key=("light", mode, path),
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
