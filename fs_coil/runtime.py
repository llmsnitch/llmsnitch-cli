"""Process / daemon runtime helpers.

_daemon_runtime  → launchctl print parser + /bin/ps enrichment.
_running_actor_procs / _running_actor_detail → live AI process counts + detail.
_tcp_conn_counts → lsof-backed TCP connection counts for a pid.
console_user / user_home → GUI user helpers.
"""

import os
import pwd
import re
import subprocess

from fs_coil.constants import PLIST_LABEL


def console_user():
    """Current GUI user (the one who sees notifications). '' if no session."""
    try:
        out = subprocess.run(
            ["stat", "-f", "%Su", "/dev/console"],
            capture_output=True, text=True, check=True,
        )
        u = out.stdout.strip()
        return "" if u in ("", "root") else u
    except Exception:
        return ""


def user_home(user):
    try:
        return pwd.getpwnam(user).pw_dir
    except KeyError:
        return f"/Users/{user}"


_LCTL_PID_RE       = re.compile(r"^\s*pid\s*=\s*(\d+)",      re.M)
_LCTL_STATE_RE     = re.compile(r"^\s*state\s*=\s*(\w+)",    re.M)
_LCTL_RUNCOUNT_RE  = re.compile(r"^\s*run count\s*=\s*(\d+)", re.M)
_LCTL_LASTEXIT_RE  = re.compile(r"^\s*last exit code\s*=\s*(.+)$", re.M)
_LCTL_PROGRAM_RE   = re.compile(r"^\s*program\s*=\s*(.+)$",   re.M)


def _daemon_runtime():
    """Return a dict of launchd/process details for the fs-coil daemon."""
    out = {"loaded": False, "state": "?", "pid": None, "run_count": None,
           "last_exit": None, "program": None,
           "etime": None, "rss_kb": None, "pcpu": None}
    try:
        r = subprocess.run(
            ["/bin/launchctl", "print", f"system/{PLIST_LABEL}"],
            capture_output=True, text=True, timeout=3,
        )
    except Exception:
        return out
    if r.returncode != 0:
        return out
    out["loaded"] = True
    text = r.stdout
    m = _LCTL_STATE_RE.search(text);    out["state"]     = m.group(1) if m else "?"
    m = _LCTL_PID_RE.search(text);      out["pid"]       = int(m.group(1)) if m else None
    m = _LCTL_RUNCOUNT_RE.search(text); out["run_count"] = int(m.group(1)) if m else None
    m = _LCTL_LASTEXIT_RE.search(text); out["last_exit"] = m.group(1).strip() if m else None
    m = _LCTL_PROGRAM_RE.search(text);  out["program"]   = m.group(1).strip() if m else None
    if out["pid"]:
        try:
            ps = subprocess.run(
                ["/bin/ps", "-p", str(out["pid"]), "-o", "etime=,rss=,pcpu="],
                capture_output=True, text=True, timeout=2,
            )
            parts = ps.stdout.strip().split()
            if len(parts) >= 3:
                out["etime"]  = parts[0]
                out["rss_kb"] = int(parts[1])
                out["pcpu"]   = float(parts[2])
        except Exception:
            pass
    return out


def _running_actor_procs():
    """Count currently-running processes we care about. Returns
    (vscode_count, claude_in_vscode_count, claude_app_count, opencode_count)."""
    try:
        r = subprocess.run(
            ["/bin/ps", "-axo", "pid=,command="],
            capture_output=True, text=True, timeout=1,
        )
        if r.returncode != 0:
            return (0, 0, 0, 0)
    except Exception:
        return (0, 0, 0, 0)

    vscode = claude_vsc = claude_app = opencode = 0
    for ln in r.stdout.splitlines():
        low = ln.lower()
        if "vscodium" in low or "visual studio code" in low or "/code helper" in low:
            vscode += 1
            if "claude" in low:
                claude_vsc += 1
        elif "/claude.app/" in low:
            # Path-anchor on `/claude.app/` anywhere — the bundle may live
            # under a non-default /Applications subfolder.
            claude_app += 1
        elif "opencode" in low:
            opencode += 1
        elif "claude" in low and ("/code helper" not in low):
            # Bare claude CLI not under VSCode — treat as its own bucket
            # folded into claude_vsc so the user sees a non-zero count when
            # running `claude` from their shell.
            claude_vsc += 1
    return (vscode, claude_vsc, claude_app, opencode)


def _running_actor_detail():
    """Per-bucket process detail with aggregate CPU/RSS + per-PID rows.
    Returns a dict keyed by bucket → {'n', 'cpu', 'rss_kb', 'procs': [...]}
    where each proc entry is {'pid', 'cpu', 'rss_kb', 'name'}."""
    try:
        r = subprocess.run(
            ["/bin/ps", "-axo", "pid=,pcpu=,rss=,command="],
            capture_output=True, text=True, timeout=1,
        )
        if r.returncode != 0:
            return {}
    except Exception:
        return {}

    agg = {"vscode_claude": {"n": 0, "cpu": 0.0, "rss_kb": 0, "procs": []},
           "claude_app":    {"n": 0, "cpu": 0.0, "rss_kb": 0, "procs": []},
           "opencode":      {"n": 0, "cpu": 0.0, "rss_kb": 0, "procs": []}}
    for ln in r.stdout.splitlines():
        # Split only first 3 whitespace-separated fields; the rest is cmd.
        parts = ln.strip().split(None, 3)
        if len(parts) < 4:
            continue
        try:
            pid    = int(parts[0])
            cpu    = float(parts[1])
            rss_kb = int(parts[2])
        except ValueError:
            continue
        cmd = parts[3]
        low = cmd.lower()
        bucket = None
        if "opencode" in low:
            bucket = "opencode"
        elif "/claude.app/" in low:
            bucket = "claude_app"
        elif "claude" in low and (
            "vscodium" in low or "visual studio code" in low
            or "/code helper" in low or "/extensions/" in low
        ):
            bucket = "vscode_claude"
        elif "claude" in low:
            # Bare `claude` CLI (shell / homebrew) — attribute to vscode_claude
            # bucket since that's the most common host for the CLI.
            bucket = "vscode_claude"
        if bucket:
            # Friendly name: first-token basename, stripped of extension.
            first = cmd.split(None, 1)[0]
            name  = os.path.basename(first) or first
            # Some macOS Electron bundles have names like "Code Helper (Renderer)"
            # where the executable name itself carries the role suffix.
            agg[bucket]["n"]      += 1
            agg[bucket]["cpu"]    += cpu
            agg[bucket]["rss_kb"] += rss_kb
            agg[bucket]["procs"].append({
                "pid": pid, "cpu": cpu, "rss_kb": rss_kb, "name": name,
            })
    return agg


def _tcp_conn_counts(pid):
    """Best-effort (total, established, listen) via lsof. 1s timeout."""
    if not pid:
        return (0, 0, 0)
    try:
        r = subprocess.run(
            ["/usr/sbin/lsof", "-nP", "-iTCP", "-a", "-p", str(pid)],
            capture_output=True, text=True, timeout=1,
        )
        if r.returncode != 0:
            return (0, 0, 0)
        est = lst = total = 0
        for line in r.stdout.splitlines()[1:]:
            total += 1
            if "ESTABLISHED" in line:
                est += 1
            elif "LISTEN" in line:
                lst += 1
        return (total, est, lst)
    except Exception:
        return (0, 0, 0)
