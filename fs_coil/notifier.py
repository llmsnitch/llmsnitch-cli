"""Notifier — posts macOS notifications into the console user's GUI session.

Works both when fs-coil runs as root (LaunchDaemon) and as the user
(test mode). Icon helpers live in icons.py.
"""

import os
import pwd
import subprocess
import sys
import time
from pathlib import Path

from fs_coil.constants import PLIST_LABEL, TERMINAL_NOTIFIER
from fs_coil.icons import (
    _app_bundle_ancestor, _app_bundle_by_name,
    _bundle_icns, _icns_to_png,
)
from fs_coil.runtime import console_user, user_home


class Notifier:
    def __init__(self):
        self._last = {}   # dedupe (proc, kind, path) → timestamp
        self._cooldown = 60   # seconds
        self._user = console_user()
        self._uid = None
        self._gid = None
        if self._user:
            try:
                pw = pwd.getpwnam(self._user)
                self._uid = pw.pw_uid
                self._gid = pw.pw_gid
            except KeyError:
                pass

        home = user_home(self._user) if self._user else ""
        self._icon_dir = Path(home) / "Library" / "Caches" / "llm-snitch" / "fs-coil" / "icons" if home else None
        self._icon_override_dir = Path(home) / ".config" / "llm-snitch" / "icons" if home else None
        self._extra_app_roots = [str(Path(home) / "Applications")] if home else []
        self._icon_cache = {}   # key → str path or None
        if self._icon_dir is not None:
            try:
                self._icon_dir.mkdir(parents=True, exist_ok=True)
                self._chown_user(self._icon_dir)
            except OSError:
                pass

    def _chown_user(self, path):
        if os.geteuid() == 0 and self._uid is not None and self._gid is not None:
            try:
                # follow_symlinks=False: icon dir/cache live under a user-
                # writable path; a planted symlink must not redirect root's chown.
                os.chown(path, self._uid, self._gid, follow_symlinks=False)
            except OSError:
                pass

    def _resolve_icon(self, actor, exe_path=None, rexe_path=None):
        """Return a PNG path for `actor`'s app icon, or None. Caches results."""
        if not actor or self._icon_dir is None:
            return None
        key = actor.lower()
        if key in self._icon_cache:
            return self._icon_cache[key]

        # 1. User override (png or icns) in ~/.config/llm-snitch/icons/
        if self._icon_override_dir is not None:
            for ext in (".png", ".icns"):
                o = self._icon_override_dir / f"{key}{ext}"
                if o.exists():
                    if ext == ".png":
                        self._icon_cache[key] = str(o)
                        return str(o)
                    cached = self._icon_dir / f"{key}.png"
                    if _icns_to_png(o, cached):
                        self._chown_user(cached)
                        self._icon_cache[key] = str(cached)
                        return str(cached)

        # 2. Previously cached PNG
        cached = self._icon_dir / f"{key}.png"
        if cached.exists() and cached.stat().st_size > 0:
            self._icon_cache[key] = str(cached)
            return str(cached)

        # 3. Discover .app bundle — prefer the responsible exe, then exe,
        #    then a name match in /Applications.
        bundle = (_app_bundle_ancestor(rexe_path)
                  or _app_bundle_ancestor(exe_path)
                  or _app_bundle_by_name(actor, self._extra_app_roots))
        if rexe_path and bundle is None:
            bundle = _app_bundle_by_name(os.path.basename(rexe_path), self._extra_app_roots)
        if not bundle:
            self._icon_cache[key] = None
            return None

        icns = _bundle_icns(bundle)
        if icns and _icns_to_png(icns, cached):
            self._chown_user(cached)
            self._icon_cache[key] = str(cached)
            return str(cached)

        self._icon_cache[key] = None
        return None

    def _should_emit(self, key):
        now = time.time()
        last = self._last.get(key, 0)
        if now - last < self._cooldown:
            return False
        self._last[key] = now
        if len(self._last) > 512:
            # trim oldest
            for k, _ in sorted(self._last.items(), key=lambda kv: kv[1])[:256]:
                self._last.pop(k, None)
        return True

    def notify(self, title, message, key,
               icon_actor=None, exe_path=None, rexe_path=None):
        if not self._should_emit(key):
            return
        if not os.path.exists(TERMINAL_NOTIFIER):
            # Surface it — a missing notifier means the user gets NO alerts
            # and would otherwise assume silence == safe. Goes to the daemon's
            # StandardErrorPath (/var/log/fs-coil.err.log).
            print(f"[notifier] terminal-notifier not found at {TERMINAL_NOTIFIER}"
                  f" — desktop alerts disabled", file=sys.stderr, flush=True)
            return
        # Per-notification group suffix — without this, terminal-notifier's
        # -group flag makes macOS replace the previous banner of the same
        # group, so repeated matches only ever show one notification.
        group = f"{PLIST_LABEL}.{int(time.time() * 1000)}"
        icon = self._resolve_icon(icon_actor, exe_path, rexe_path) if icon_actor else None
        if os.geteuid() == 0 and self._uid is not None:
            # root → user session
            cmd = [
                "/bin/launchctl", "asuser", str(self._uid),
                "/usr/bin/sudo", "-u", self._user,
                TERMINAL_NOTIFIER,
                "-title", title,
                "-message", message,
                "-group", group,
                "-sender", "com.apple.Terminal",
            ]
        else:
            cmd = [
                TERMINAL_NOTIFIER,
                "-title", title,
                "-message", message,
                "-group", group,
            ]
        if icon:
            cmd += ["-contentImage", icon]
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            # Don't swallow silently — a broken notify path is a monitoring
            # blind spot, not a cosmetic hiccup.
            print(f"[notifier] failed to launch terminal-notifier: "
                  f"{type(e).__name__}: {e}", file=sys.stderr, flush=True)
