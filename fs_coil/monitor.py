"""Core matching loop — reads eslogger JSON, filters watched procs, matches
against the deny list, writes log lines + notifies."""

import json
import os
import signal
import subprocess
import sys
from datetime import datetime

from fs_coil.classify import _ai_bucket_from_pinfo, _short_sign
from fs_coil.constants import ES_EVENTS, ESLOGGER
from fs_coil.denylist import (
    _shrink, compile_deny, is_sensitive_basename, match_deny, path_in_noise,
)
from fs_coil.events import (
    event_mode, extract_exec, extract_paths, is_read_open, is_watched,
    process_info, _pid_meta,
)
from fs_coil.keychain import classify_keychain_exec
from fs_coil.logger import Logger
from fs_coil.notifier import Notifier
from fs_coil.runtime import console_user, user_home


def _low_noise(pinfo, path):
    """True if this DENY-MATCH should be logged but NOT alerted.

    The canonical case: Claude reading its OWN credentials from the user's
    login keychain via `security find-generic-password`. At the file-access
    layer we can't tell which Keychain item was read (they all live in one
    .keychain-db file), so the heuristic is:

        responsible process is Claude / Anthropic-signed
        AND the touched file is inside ~/Library/Keychains/

    → log it (audit trail stays intact) but skip the macOS notification.
    """
    low_path = (path or "").lower()
    if "/library/keychains/" not in low_path:
        return False
    # This gate SUPPRESSES a notification, so it must fail safe: trust only
    # the OS-verified signing id (unspoofable). A bare "/claude.app/" path
    # substring is attacker-controllable — they can plant a binary under a
    # dir they named `claude.app` and silence their own keychain reads.
    rsign = (pinfo.get("rsign") or "").lower()
    sign  = (pinfo.get("sign")  or "").lower()
    if rsign.startswith("com.anthropic.") or sign.startswith("com.anthropic."):
        return True
    # Fallback for events where the signing id is stripped/empty: require the
    # genuine Claude.app bundle executable layout, not a bare /claude.app/ dir.
    rexe = (pinfo.get("rexe") or "").lower()
    exe  = (pinfo.get("exe")  or "").lower()
    return (
        "/claude.app/contents/macos/" in rexe
        or "/claude.app/contents/macos/" in exe
    )


def run_monitor(stdout_only=False):
    user = console_user()
    home = user_home(user) if user else os.path.expanduser("~")
    deny = compile_deny(home)
    logger = Logger(user)
    notifier = Notifier()

    logger.write(
        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] fs-coil starting "
        f"(user={user or 'none'}, home={home}, events={','.join(ES_EVENTS)}, "
        f"rules={len(deny)})"
    )

    # Startup notification so the user has visible proof the daemon is alive.
    # Skipped in test/foreground mode (stdout_only=True) since the banner + logs
    # already make it obvious there.
    if not stdout_only:
        notifier.notify(
            "🦍 fs-coil armed",
            f"watching {len(deny)} rules for claude/opencode",
            "startup",
        )

    cmd = [ESLOGGER, "--format", "json"] + ES_EVENTS
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        bufsize=1, text=True,
    )

    def shutdown(*_):
        logger.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] fs-coil stopping")
        try:
            proc.terminate()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    assert proc.stdout is not None
    for raw in proc.stdout:
        raw = raw.strip()
        if not raw:
            continue
        # Cap line size before parsing — a hostile agent can't force a
        # multi-GB json.loads allocation to DoS the daemon.
        if len(raw) > 262144:
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue

        # One malformed/adversarial event must not kill the loop. Without
        # this, an uncaught exception exits the daemon; launchd respawns it
        # after ThrottleInterval (10s) — a repeatable blind-the-monitor
        # window. Log and move on instead.
        try:
            pinfo = process_info(event)
            if not is_watched(pinfo):
                continue

            # exec events — track what commands the AI is spawning.
            exec_exe, exec_args = extract_exec(event)
            if exec_exe:
                ai_bucket = _ai_bucket_from_pinfo(pinfo)
                by_name   = os.path.basename(pinfo.get("rexe") or pinfo.get("exe") or "?")
                cmd_base  = os.path.basename(exec_exe) or "?"
                # Drop argv[0] — we already have it in `cmd`. Cap args length so
                # a pathological invocation can't blow up the log line.
                arg_tail  = " ".join(a for a in exec_args[1:] if a) if exec_args else ""
                if len(arg_tail) > 200:
                    arg_tail = arg_tail[:197] + "..."
                arg_tag = f" args={arg_tail}" if arg_tail else ""
                logger.write(
                    f"[{datetime.now():%Y-%m-%d %H:%M:%S}] EXEC "
                    f"ai={ai_bucket} by={by_name}[{pinfo['pid']}] "
                    f"cmd={cmd_base}{arg_tag}"
                )

                # Keychain-sensitive exec → dedicated log line + notification.
                kc = classify_keychain_exec(exec_exe, exec_args or [])
                if kc:
                    op, hint = kc
                    hint_tag = f" item={hint}" if hint else ""
                    logger.write(
                        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] KEYCHAIN-{op} "
                        f"ai={ai_bucket} by={by_name}[{pinfo['pid']}] "
                        f"cmd={cmd_base}{hint_tag}{arg_tag}"
                    )
                    if not stdout_only:
                        title = f"🦍 KEYCHAIN {op} · {by_name}[{pinfo['pid']}]"
                        msg_lines = [f"{cmd_base} {arg_tail}".strip()]
                        if hint:
                            msg_lines.append(hint)
                        notifier.notify(
                            title=title,
                            message="\n".join(msg_lines),
                            key=("keychain", op, cmd_base, hint),
                            icon_actor=by_name,
                            exe_path=pinfo.get("exe"),
                            rexe_path=pinfo.get("rexe"),
                        )
                continue

            for (kind, path) in extract_paths(event):
                if not path:
                    continue
                mode = event_mode(kind)
                if mode == "R" and kind == "open" and not is_read_open(event):
                    mode = "W"

                basename = os.path.basename(path)
                sensitive = is_sensitive_basename(basename)
                if path_in_noise(path) and not sensitive:
                    continue

                hit = match_deny(path, mode, deny)
                if not hit:
                    continue

                actor = os.path.basename(pinfo["exe"]) or "?"
                via = ""
                if pinfo["rexe"] and pinfo["rexe"] != pinfo["exe"]:
                    via = f" via {os.path.basename(pinfo['rexe'])}"

                # Enrich with parent/daemon context — best-effort /bin/ps lookup.
                # Falls back to "" / False silently if the process already died.
                parent_name, tty, is_daemon = _pid_meta(pinfo["pid"])
                parent_tag = (
                    f"parent={parent_name}[{pinfo['ppid']}]"
                    if parent_name else f"parent=?[{pinfo['ppid']}]"
                )

                src = pinfo.get("source") or "other"
                sign_field = pinfo.get("blame_sign") or "-"
                severity = "low" if _low_noise(pinfo, path) else "high"
                line = (
                    f"[{datetime.now():%Y-%m-%d %H:%M:%S}] DENY-MATCH "
                    f"proc={actor}[{pinfo['pid']}]{via} "
                    f"src={src} sign={sign_field} severity={severity} "
                    f"{parent_tag} daemon={'yes' if is_daemon else 'no'} "
                    f"event={kind} mode={mode} path={path} pattern={hit}"
                )
                logger.write(line)

                # Notifications fire on high-severity only. Low-severity hits
                # (Claude reading its own keychain entry, etc.) are still in
                # the log for audit but don't spam the screen.
                if not stdout_only and severity != "low":
                    rexe_base = os.path.basename(pinfo.get("rexe") or "") or ""
                    icon_actor = rexe_base or actor
                    via = f"  (via {rexe_base})" if rexe_base and rexe_base != actor else ""
                    title = f"🦍 {actor}[{pinfo['pid']}] · {mode}"
                    short_sign = _short_sign(pinfo.get("blame_sign") or "")
                    src_line = f"src: {src}" + (f" · {short_sign}" if short_sign != "-" else "")
                    message = (
                        f"{_shrink(path, home)}\n"
                        f"↳ {_shrink(pinfo['exe'], home)}{via}\n"
                        f"{src_line}\n"
                        f"rule: {hit}"
                    )
                    notifier.notify(
                        title=title,
                        message=message,
                        key=(actor, mode, path),
                        icon_actor=icon_actor,
                        exe_path=pinfo.get("exe"),
                        rexe_path=pinfo.get("rexe"),
                    )
        except Exception as e:
            logger.write(
                f"[{datetime.now():%Y-%m-%d %H:%M:%S}] EVENT-ERROR "
                f"{type(e).__name__}: {str(e)[:200]}"
            )
            continue

    rc = proc.wait()
    logger.write(
        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] eslogger exited rc={rc}"
        + (f" stderr={proc.stderr.read().strip()}" if proc.stderr else "")
    )
    sys.exit(rc or 1)
