"""eslogger JSON parsing + process-info helpers.

The schema is Apple's, not ours. Paths live in slightly different places per
event type. These accessors normalize."""

import os
import subprocess

from fs_coil.constants import INTERPRETER_PROC, WATCHED_PROC
from fs_coil.classify import _classify_source
from fs_coil.disclaim_tracker import is_claude_descendant


def extract_exec(event):
    """If this is an exec event, return (target_exe_path, args_list).
    Otherwise (None, None). Field names can vary between macOS releases
    so we try multiple shapes defensively."""
    ev = event.get("event") or {}
    if "exec" not in ev:
        return (None, None)
    ex = ev["exec"] or {}
    target = ex.get("target") or {}
    exe = ((target.get("executable") or {}).get("path")) or ""
    args = ex.get("args") or ex.get("argv") or target.get("args") or []
    if isinstance(args, str):
        args = args.split()
    return (exe, args)


def extract_paths(event):
    """Return list of (event_kind, path) tuples from one eslogger record."""
    ev = event.get("event") or {}
    out = []
    if "open" in ev:
        f = (ev["open"] or {}).get("file") or {}
        p = f.get("path")
        if p:
            out.append(("open", p))
    if "create" in ev:
        d = ev["create"] or {}
        dest = d.get("destination") or {}
        existing = dest.get("existing_file") or {}
        new_path = dest.get("new_path") or {}
        p = existing.get("path") or (
            (new_path.get("dir") or {}).get("path", "").rstrip("/")
            + "/" + new_path.get("filename", "")
        )
        if p and p != "/":
            out.append(("create", p))
    if "rename" in ev:
        r = ev["rename"] or {}
        src = (r.get("source") or {}).get("path")
        if src:
            out.append(("rename", src))
        dest = r.get("destination") or {}
        if "existing_file" in dest:
            p = (dest["existing_file"] or {}).get("path")
            if p:
                out.append(("rename", p))
        elif "new_path" in dest:
            np = dest["new_path"] or {}
            d = (np.get("dir") or {}).get("path", "").rstrip("/")
            fn = np.get("filename", "")
            if d and fn:
                out.append(("rename", f"{d}/{fn}"))
    if "unlink" in ev:
        t = (ev["unlink"] or {}).get("target") or {}
        p = t.get("path")
        if p:
            out.append(("unlink", p))
    if "link" in ev:
        l = ev["link"] or {}
        src = (l.get("source") or {}).get("path")
        if src:
            out.append(("link", src))
    return out


def event_mode(kind):
    """R (read) or W (mutation)."""
    return "R" if kind == "open" else "W"


def is_read_open(event):
    """Distinguish read-only open from write-open by fflag bits.

    FREAD=1, FWRITE=2. Pure read has bit 1 set, bit 2 clear.
    """
    try:
        flag = (event.get("event") or {}).get("open", {}).get("fflag", 0)
        return bool(flag & 1) and not bool(flag & 2)
    except Exception:
        return True  # safer to treat as read


def process_info(event):
    proc = event.get("process") or {}
    exe = ((proc.get("executable") or {}).get("path") or "")
    sign = proc.get("signing_id") or ""
    pid = ((proc.get("audit_token") or {}).get("pid")) or 0
    ppid = ((proc.get("parent_audit_token") or {}).get("pid")) or 0
    # responsible_audit_token points to the session-responsible process
    # (e.g. 'claude' when a child bash touches the FS).
    rproc = event.get("responsible_process") or {}
    rexe = ((rproc.get("executable") or {}).get("path") or "")
    rsign = rproc.get("signing_id") or ""
    # Classify by the responsible actor (real offender) if present, else
    # fall back to the direct exe.
    src_exe  = rexe  or exe
    src_sign = rsign or sign
    # Recover Claude.app origin for processes spawned via `disclaimer`
    # (Apple's responsibility-disclaim API hides the real rexe/rsign).
    # Only queried when the direct blob-match below will fail, so the
    # steady-state hot path for known-Claude events pays nothing.
    blob = " ".join((exe, sign, rexe, rsign)).lower()
    disclaim_descendant = (
        not any(s in blob for s in WATCHED_PROC)
        and is_claude_descendant(pid)
    )
    return {
        "exe": exe, "sign": sign, "pid": pid, "ppid": ppid,
        "rexe": rexe, "rsign": rsign,
        "source":     _classify_source(src_exe, src_sign),
        "blame_sign": src_sign or "",
        "disclaim_descendant": disclaim_descendant,
    }


def _pid_meta(pid):
    """Best-effort (parent_name, tty, is_daemon) for pid via /bin/ps.

    Daemon heuristic: no controlling tty AND parent pid is 1 (launchd). This
    catches LaunchDaemons/LaunchAgents; foreground processes under a terminal
    get tty=ttysN and are classified interactive.
    """
    try:
        out = subprocess.run(
            ["/bin/ps", "-p", str(pid), "-o", "ppid=,tty="],
            capture_output=True, text=True, timeout=0.3,
        )
        parts = out.stdout.split()
        if len(parts) < 1:
            return ("", "?", False)
        ppid = int(parts[0])
        tty = parts[1] if len(parts) > 1 else "?"
        parent_name = ""
        if ppid:
            p = subprocess.run(
                ["/bin/ps", "-p", str(ppid), "-o", "comm="],
                capture_output=True, text=True, timeout=0.3,
            )
            parent_name = os.path.basename(p.stdout.strip())
        is_daemon = tty in ("?", "??") and ppid == 1
        return (parent_name, tty, is_daemon)
    except Exception:
        return ("", "?", False)


def is_watched(pinfo):
    """True if this event came from (or via) claude / opencode."""
    blob = " ".join((pinfo["exe"], pinfo["sign"], pinfo["rexe"], pinfo["rsign"])).lower()
    if any(s in blob for s in WATCHED_PROC):
        return True
    # Claude.app uses `disclaimer` (responsibility_spawnattrs_setdisclaim)
    # to hide its parentage from Endpoint Security — recover it by walking
    # the ppid chain. Cached verdict, computed once in process_info.
    if pinfo.get("disclaim_descendant"):
        return True
    # Allow shell/interpreter events ONLY when responsible process is watched.
    exe_base = os.path.basename(pinfo["exe"]).lower()
    if exe_base in INTERPRETER_PROC:
        rblob = (pinfo["rexe"] + " " + pinfo["rsign"]).lower()
        return any(s in rblob for s in WATCHED_PROC)
    return False
