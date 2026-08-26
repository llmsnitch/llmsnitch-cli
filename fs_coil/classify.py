"""Actor / source classification + signing-id shortener + actor counters.

These functions bucket events into 'VSCode Claude / Claude.app / OpenCode /
other' so dashboards and counters have a stable taxonomy.
"""

from datetime import datetime


def _classify_source(exe_path, signing_id):
    """Bucket a process by install origin so we can answer who/what/where at
    a glance. Ordered most-specific → most-generic."""
    p = (exe_path or "").lower()
    s = (signing_id or "").lower()
    if "/extensions/" in p and (".vscode" in p or "/code/" in p or "vscodium" in p):
        return "vscode-ext"
    if "/extensions/" in p and "/cursor" in p:
        return "cursor-ext"
    if "/applications/" in p and ".app/contents/macos/" in p:
        return "desktop"
    if "/cellar/" in p or p.startswith("/opt/homebrew/") or "/.linuxbrew/" in p:
        return "homebrew"
    if "/node_modules/" in p or "/.nvm/" in p or "/npm/" in p or "/pnpm/" in p:
        return "npm"
    if "/.local/bin/" in p or "/pipx/" in p:
        return "pipx"
    if s.startswith("com.anthropic."):
        return "anthropic-signed"
    return "other"


def _short_sign(signing_id):
    """Trim common `com.vendor.` prefix for display (keeps tables narrow)."""
    if not signing_id or signing_id == "-":
        return "-"
    if signing_id.startswith("com.anthropic."):
        return "anthropic/" + signing_id[len("com.anthropic."):]
    parts = signing_id.split(".")
    if len(parts) >= 3 and parts[0] == "com":
        return ".".join(parts[2:])
    return signing_id


def _ai_bucket_from_pinfo(pinfo):
    """Bucket a watched event into VSCode Claude / Claude.app / OpenCode
    based on the responsible process (rexe + rsign). Falls back to
    vscode_claude since the CLI is the most common runtime."""
    rexe  = (pinfo.get("rexe")  or "").lower()
    rsign = (pinfo.get("rsign") or "").lower()
    exe   = (pinfo.get("exe")   or "").lower()
    sign  = (pinfo.get("sign")  or "").lower()
    blob  = " ".join((rexe, rsign, exe, sign))
    if "opencode" in blob:
        return "opencode"
    # Signing_id is the only reliable identifier — survives any install path.
    # Path fallback anchors on `/claude.app/` anywhere (covers bundles under
    # non-default /Applications subfolders, e.g. `/Applications/-+[ Dev ]+-/`).
    if "com.anthropic.claudefordesktop" in rsign + " " + sign:
        return "claude_app"
    if "/claude.app/" in rexe + " " + exe:
        return "claude_app"
    # Disclaimer-spawned descendants: ancestry recovered via ppid walk in
    # events.process_info. Without this, `sqlite3 /Users/.../Zed/db.sqlite`
    # spawned by Claude.app looks like an orphan Apple-signed utility.
    if pinfo.get("disclaim_descendant"):
        return "claude_app"
    return "vscode_claude"


def _actor_bucket(m):
    """Classify a match dict into one of: 'vscode_claude', 'claude_app',
    'opencode', or 'other'. Used for per-actor alert counters."""
    src  = (m.get("src")  or "").lower()
    sign = (m.get("sign") or "").lower()
    proc = (m.get("proc") or "").lower()
    if "opencode" in proc or "opencode" in sign:
        return "opencode"
    if src == "vscode-ext" and "claude" in (proc + sign):
        return "vscode_claude"
    if src == "desktop" and "claude" in (proc + sign):
        return "claude_app"
    if "claude" in proc:
        # Unclassified claude (e.g. homebrew CLI, npm) — lump under vscode_claude
        # when we can't disambiguate; the most common case is the CLI running
        # under VSCodium's integrated terminal.
        return "vscode_claude"
    return "other"


def _actor_counts(matches, seconds):
    """Per-actor match counts over the last N seconds."""
    now = datetime.now()
    buckets = {"vscode_claude": 0, "claude_app": 0, "opencode": 0, "other": 0}
    for m in matches:
        if (now - m["dt"]).total_seconds() > seconds:
            continue
        buckets[_actor_bucket(m)] += 1
    return buckets
