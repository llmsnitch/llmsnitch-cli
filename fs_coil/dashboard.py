"""tmux-backed dashboard. Spawns a 5-pane layout running fs-coil report
and fs-coil logs -f, plus proc-eye. Detach with Ctrl-b d."""

import os
import pwd
import resource
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from fs_coil.runtime import console_user, user_home
from fs_coil.theme import err


def _raise_fd_limit(target=4096):
    """Bump RLIMIT_NOFILE so `tmux split-window` can fork even when the
    parent has already opened many file descriptors (happens after repeated
    dashboard runs that leave old sessions around)."""
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        if soft < target:
            resource.setrlimit(
                resource.RLIMIT_NOFILE,
                (min(target, hard), hard),
            )
    except Exception:
        pass


def _kill_stale_sessions():
    """Kill any leftover fs-coil-* tmux sessions from prior runs.
    Each one holds a handful of PTY fds — they accumulate fast and
    eventually trip 'Too many open files' on the next split-window."""
    try:
        r = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True, text=True, timeout=2,
        )
    except Exception:
        return
    for line in (r.stdout or "").splitlines():
        name = line.strip()
        if name.startswith("fs-coil-"):
            subprocess.run(
                ["tmux", "kill-session", "-t", name], capture_output=True,
            )

# Width split: report pane = 50%, col_mid/col_right each = 25%.
_REPORT_WIDTH_PCT = 0.50
# Bottom strips auto-scale with terminal height, clamped per-strip.
# proc-eye wants to show ALL its lines — cap at 12 so it doesn't eat
# the dashboard on short terminals.
_STRIP_PCT  = 0.10
_LOGS_MIN,  _LOGS_MAX  = 3, 6
_LLM_MIN,   _LLM_MAX   = 4, 12


def cmd_dashboard():
    """5-pane layout:

        ┌──────────────┬──────────┬──────────┐
        │              │          │          │
        │    report    │  col_mid │ col_right│
        │    (50%)     │  (25%)   │  (25%)   │
        │              │          │          │
        ├──────────────┴──────────┴──────────┤
        │           live logs                │
        ├────────────────────────────────────┤
        │           proc-eye              │
        └────────────────────────────────────┘
    """
    if not shutil.which("tmux"):
        err("tmux not installed — install with: brew install tmux")
        sys.exit(1)

    if os.environ.get("TMUX"):
        err("already inside tmux — detach (Ctrl-b d) first, then rerun.")
        sys.exit(1)

    fs_bin  = shutil.which("fs-coil") or sys.argv[0]
    llm_bin = shutil.which("proc-eye") or os.path.join(
        os.path.dirname(os.path.realpath(fs_bin)), "proc-eye"
    )
    session = f"fs-coil-{os.getpid()}"

    user = console_user() or pwd.getpwuid(os.getuid()).pw_name
    home = user_home(user)
    log_dir  = Path(home) / "Library" / "Logs" / "llmsnitch" / "fs-coil"
    log_file = log_dir / f"fs-coil-{datetime.now():%Y-%m-%d}.log"

    def _report_loop(sec=None, interval=5):
        sec_arg = f"--section {sec} " if sec else ""
        return f"{fs_bin} report {sec_arg}--live --interval {interval}"

    logs_cmd = (
        f"mkdir -p {log_dir} && touch {log_file} && "
        f"{fs_bin} logs -f"
    )

    # Raise fd limit + kill stale fs-coil-* sessions BEFORE touching
    # tmux — that's what was causing the "fork failed: Too many open
    # files" error when split-window tried to create panes.
    _raise_fd_limit()
    _kill_stale_sessions()

    subprocess.run(["tmux", "kill-session", "-t", session], capture_output=True)

    def _run(args):
        return subprocess.run(args, capture_output=True, text=True)

    def _split(flag, target, cmd, *extra):
        args = ["tmux", "split-window", flag]
        if extra:
            args.extend(extra)
        args.extend(["-t", target, "-P", "-F", "#{pane_id}", cmd])
        s = _run(args)
        if s.returncode != 0:
            err(f"tmux split-window failed: {(s.stderr or s.stdout).strip()}")
            sys.exit(1)
        return s.stdout.strip()

    # Detect client terminal geometry so the session + splits use real size.
    try:
        term       = shutil.get_terminal_size((200, 60))
        total_cols = term.columns
        total_rows = term.lines
    except Exception:
        total_cols, total_rows = 200, 60

    # Create session sized exactly to client. -x/-y prevents the 80x24
    # default that causes tmux to re-scale panes on attach.
    r = _run(["tmux", "new-session", "-d",
              "-x", str(total_cols), "-y", str(total_rows),
              "-P", "-F", "#{pane_id}",
              "-s", session, _report_loop(interval=10)])
    if r.returncode != 0:
        err(f"tmux new-session failed: {(r.stderr or r.stdout).strip()}")
        sys.exit(1)
    p_left = r.stdout.strip()

    _run(["tmux", "set-option", "-t", session, "window-size", "manual"])
    _run(["tmux", "set-option", "-t", session, "aggressive-resize", "off"])
    _run(["tmux", "set-option", "-t", session, "status", "off"])

    # --- Bottom strips --------------------------------------------------
    pct = max(total_rows * _STRIP_PCT, 0)
    # proc-eye: always try to show all 12 lines, only shrink if the
    # terminal itself is tight (cap at one-third of total rows).
    llm_h  = int(min(_LLM_MAX,  max(_LLM_MIN, total_rows // 3)))
    logs_h = int(max(_LOGS_MIN, min(_LOGS_MAX, pct)))
    p_llm  = _split("-v", p_left, llm_bin,  "-l", str(llm_h))
    p_logs = _split("-v", p_left, logs_cmd, "-l", str(logs_h))

    # --- Top row: report | col_mid | col_right -------------------------
    # Split by COLUMN COUNT (not percent) so tmux does no scaling math.
    # After llm + logs have been carved out of the bottom, p_left still
    # spans the full window width. Width = total_cols.
    report_w = int(total_cols * _REPORT_WIDTH_PCT)     # e.g. 100 @ 200 cols
    mid_w    = (total_cols - report_w) // 2            # e.g. 50
    right_w  = total_cols - report_w - mid_w           # e.g. 50 (handles odd)

    # First split creates the right-hand block (col_mid starts here and
    # will be halved next). tmux `-l` is the NEW pane's width.
    p_mid   = _split("-h", p_left, _report_loop("col_mid"),
                     "-l", str(mid_w + right_w))
    # Halve the right block → col_right.
    p_right = _split("-h", p_mid,  _report_loop("col_right"),
                     "-l", str(right_w))

    # Lock in final dimensions. tmux's resize-pane -x/-y is authoritative.
    # Run AFTER all splits so each resize is applied to the final tree.
    _run(["tmux", "resize-pane", "-t", p_left,  "-x", str(report_w)])
    _run(["tmux", "resize-pane", "-t", p_mid,   "-x", str(mid_w)])
    _run(["tmux", "resize-pane", "-t", p_right, "-x", str(right_w)])
    _run(["tmux", "resize-pane", "-t", p_logs,  "-y", str(logs_h)])
    _run(["tmux", "resize-pane", "-t", p_llm,   "-y", str(llm_h)])

    subprocess.run(["tmux", "attach-session", "-t", session])
