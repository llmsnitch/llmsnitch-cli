"""Logger + colorized log-line renderer.

Logger writes plain-text log files per day into
~/Library/Logs/llm-snitch/fs-coil/fs-coil-YYYY-MM-DD.log, chowns
them to the console user when running as root, and TTY-colorizes the
stdout echo. `_colorize_log_line` is reused by cmd_logs to paint the
severity ramp onto the tail output.
"""

import os
import pwd
import re
import sys
from datetime import datetime
from pathlib import Path

from fs_coil.runtime import user_home
from fs_coil.theme import (
    _BOLD, _C7, _DIM, _GREEN, _ORANGE, _PURPLE, _R, _RED,
)

_LOG_COLOR_MODE = {"R": _RED, "W": _ORANGE, "RW": _ORANGE}


def _colorize_log_line(line):
    """Apply ywizz purple-orange-red palette to a log line.

    Severity ramp: purple (structure) → orange (actor/path) → red (hit).
    Keys stay purple, values take severity color. Daemon=yes is red, =no dim.
    Noop when stdout isn't a TTY so log files / pipes stay plain-text.
    """
    if not sys.stdout.isatty():
        return line
    # Service lifecycle lines — dim purple, no further coloring.
    if "starting" in line or "stopping" in line or "eslogger exited" in line:
        return f"{_PURPLE}{_DIM}{line}{_R}"
    # Timestamp prefix → dim.
    line = re.sub(r"^(\[[^\]]+\])", f"{_DIM}\\1{_R}", line)
    # DENY-MATCH keyword → bold red; EXEC keyword → orange (less severe).
    line = line.replace("DENY-MATCH", f"{_BOLD}{_RED}DENY-MATCH{_R}")
    line = re.sub(r"\bEXEC\b", f"{_BOLD}{_ORANGE}EXEC{_R}", line)
    # ai=<bucket>, by=<name>[pid], cmd=<name>, args=... for EXEC lines.
    line = re.sub(r"\bai=(\S+)",   f"{_PURPLE}ai={_R}{_GREEN}\\1{_R}",  line)
    line = re.sub(r"\bby=(\S+?)\[(\d+)\]",
                  lambda m: f"{_PURPLE}by={_R}{_ORANGE}{m.group(1)}{_R}"
                            f"{_DIM}[{m.group(2)}]{_R}", line)
    line = re.sub(r"\bcmd=(\S+)",  f"{_PURPLE}cmd={_R}{_ORANGE}\\1{_R}", line)
    line = re.sub(r"\bargs=(.*)$", f"{_PURPLE}args={_R}{_DIM}\\1{_R}",   line)
    # proc=name[pid] / parent=name[pid] — label purple, name orange, pid dim.
    line = re.sub(
        r"\b(proc|parent)=(\S*?)\[(\d+)\]",
        lambda m: (
            f"{_PURPLE}{m.group(1)}={_R}"
            f"{_ORANGE}{m.group(2) or '?'}{_R}"
            f"{_DIM}[{m.group(3)}]{_R}"
        ),
        line,
    )
    # daemon=yes (bold red) / daemon=no (dim).
    line = re.sub(
        r"\bdaemon=(yes|no)\b",
        lambda m: (
            f"{_PURPLE}daemon={_R}"
            + (f"{_BOLD}{_RED}yes{_R}" if m.group(1) == "yes"
               else f"{_DIM}no{_R}")
        ),
        line,
    )
    # mode=R/W/RW — R is read (red), W/RW are writes (orange).
    line = re.sub(
        r"\bmode=(R|W|RW)\b",
        lambda m: f"{_PURPLE}mode={_R}{_LOG_COLOR_MODE[m.group(1)]}{m.group(1)}{_R}",
        line,
    )
    # event / path / pattern — label purple, value orange.
    line = re.sub(r"\bevent=(\S+)",   f"{_PURPLE}event={_R}{_ORANGE}\\1{_R}",   line)
    line = re.sub(r"\bpath=(\S+)",    f"{_PURPLE}path={_R}{_ORANGE}\\1{_R}",    line)
    line = re.sub(r"\bpattern=(\S+)", f"{_PURPLE}pattern={_R}{_ORANGE}\\1{_R}", line)
    return line


class Logger:
    def __init__(self, user):
        home = user_home(user) if user else "/var/root"
        self.dir = Path(home) / "Library" / "Logs" / "llm-snitch" / "fs-coil"
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            for p in (self.dir, self.dir.parent):
                try:
                    os.chmod(p, 0o700)
                except OSError:
                    pass
            if user and os.geteuid() == 0:
                pw = pwd.getpwnam(user)
                for p in (self.dir, self.dir.parent):
                    try:
                        # follow_symlinks=False: an attacker-planted symlink in
                        # the user-writable parent must not redirect root's chown.
                        os.chown(p, pw.pw_uid, pw.pw_gid, follow_symlinks=False)
                    except OSError:
                        pass
        except OSError:
            pass
        self._user = user
        self._fp = None
        self._day = None

    def _open_today(self):
        day = datetime.now().strftime("%Y-%m-%d")
        if day != self._day:
            if self._fp:
                self._fp.close()
            logfile = self.dir / f"fs-coil-{day}.log"
            self._fp = open(logfile, "a", buffering=1)
            try:
                os.chmod(logfile, 0o600)
            except OSError:
                pass
            if self._user and os.geteuid() == 0:
                try:
                    pw = pwd.getpwnam(self._user)
                    os.chown(logfile, pw.pw_uid, pw.pw_gid, follow_symlinks=False)
                except (OSError, KeyError):
                    pass
            self._day = day
        return self._fp

    def write(self, line):
        fp = self._open_today()
        fp.write(line + "\n")
        try:
            # Log file stays plain text (grep-friendly). TTY gets color:
            # DENY-MATCH in red, starting/stopping in dim purple.
            out = line
            if sys.stdout.isatty():
                if "DENY-MATCH" in line:
                    out = f"{_RED}{line}{_R}"
                elif "starting" in line or "stopping" in line:
                    out = f"{_C7}{_DIM}{line}{_R}"
            print(out, flush=True)
        except BrokenPipeError:
            pass
