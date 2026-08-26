"""Agent registry — who is allowed to look like an agent (notifier-spec D17).

Built-in table of known coding agents + `[agent.<name>]` config merge,
`attribute_actor()` (D14–D16) and `classify_event()` (D06, D07).

Stdlib only. Config path honors the LLMSNITCH_CONFIG test seam, defaulting
to the shared llm-snitch INI.
"""

import configparser
import os
import re
import subprocess

_CONFIG_PATH = "~/.config/llm-snitch/config"
_NAME_RE = re.compile(r"^[a-z0-9_-]+$")

# Built-in registry (D17). signing_ids ship empty for non-Claude agents —
# real values must be observed, not guessed (spec: Open questions).
AGENTS = {
    "claude-code": {
        "paths": ["~/.claude", "~/.claude.json"],
        "cache_paths": ["~/.claude/plugins/cache"],
        "exes": ["claude", "Claude"],
        "signing_ids": ["com.anthropic."],
    },
    "codex":    {"paths": ["~/.codex"],    "exes": ["codex"],    "signing_ids": []},
    "aider":    {"paths": ["~/.aider"],    "exes": ["aider"],    "signing_ids": []},
    "copilot":  {"paths": ["~/.copilot"],  "exes": ["copilot", "github-copilot"], "signing_ids": []},
    "cursor":   {"paths": ["~/.cursor"],   "exes": ["cursor", "Cursor"],     "signing_ids": []},
    "windsurf": {"paths": ["~/.windsurf"], "exes": ["windsurf", "Windsurf"], "signing_ids": []},
    "agy":      {"paths": ["~/.agy"],      "exes": ["agy"],      "signing_ids": []},
}

# Non-agent tool basenames normalized to their own buckets (D16).
_KNOWN_TOOLS = {"bash", "zsh", "sh", "git", "python", "security", "curl",
                "ssh", "node", "ruby", "perl"}
_LIST_KEYS = ("paths", "cache_paths", "exes", "signing_ids")


def _config_path():
    return os.environ.get("LLMSNITCH_CONFIG",
                          os.path.expanduser(_CONFIG_PATH))


def load_registry(log=None):
    """Built-ins merged with `[agent.<name>]` config sections.

    A listed key replaces that key's built-in list; unlisted keys keep the
    built-in. Unknown section name registers a new agent. Invalid agent
    names (must match [a-z0-9_-]+, D12's separator guarantee) are rejected
    with a NOTIFIER-ERROR line via `log` (callable, best-effort).
    """
    reg = {name: {k: list(spec.get(k, [])) for k in _LIST_KEYS}
           for name, spec in AGENTS.items()}
    path = _config_path()
    if not os.path.exists(path):
        return reg
    cp = configparser.ConfigParser(inline_comment_prefixes=("#",))
    try:
        cp.read(path)
    except configparser.Error:
        return reg
    for section in cp.sections():
        if not section.startswith("agent."):
            continue
        name = section[len("agent."):]
        if not _NAME_RE.match(name):
            if log:
                try:
                    log(f"NOTIFIER-ERROR: invalid agent name {name!r} rejected")
                except Exception:  # noqa: BLE001 — logging is best-effort
                    pass
            continue
        entry = reg.setdefault(name, {k: [] for k in _LIST_KEYS})
        for key in _LIST_KEYS:
            raw = cp[section].get(key)
            if raw is not None:
                entry[key] = [v.strip() for v in raw.split(",") if v.strip()]
    return reg


def _inside(path, roots):
    """Exact-segment prefix after ~ expansion; file entries match by equality."""
    for p in roots:
        p = os.path.expanduser(p)
        if path == p or path.startswith(p + "/"):
            return True
    return False


def _agent_for_path(path, registry):
    for name, spec in registry.items():
        if _inside(path, spec.get("paths", [])):
            return name
    return None


def _normalize_tool(base):
    b = base.lower()
    if b.startswith("python"):
        return "python"
    return b if b in _KNOWN_TOOLS else None


def _ps_comm(ppid):
    """Best-effort `ps -p <ppid> -o comm=` (D15). Races accepted."""
    try:
        out = subprocess.run(["/bin/ps", "-p", str(ppid), "-o", "comm="],
                             capture_output=True, text=True, timeout=2)
        return out.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def attribute_actor(path=None, pinfo=None, ppid=None, registry=None):
    """(actor_bucket, actor_raw) per D14–D16.

    Path is NEVER consulted when process signals exist — otherwise an
    unrecognized binary writing into ~/.claude would be attributed to
    Claude and suppressed, and D07's actor-mismatch could never fire.
    """
    registry = registry if registry is not None else load_registry()

    comm = None
    if pinfo is None and ppid is not None:
        comm = _ps_comm(ppid)

    if pinfo is not None or comm is not None:
        raw = None
        if pinfo is not None:
            raw = pinfo.get("rexe") or pinfo.get("exe")
            # 1. signing id — OS-verified, unspoofable, checked first
            for sig in (pinfo.get("rsign"), pinfo.get("sign")):
                if not sig:
                    continue
                for name, spec in registry.items():
                    if any(sig.startswith(s) for s in spec.get("signing_ids", []) if s):
                        return name, raw
        base = os.path.basename(raw or comm or "")
        # 2. exe basename
        for name, spec in registry.items():
            if base in spec.get("exes", []):
                return name, raw or comm
        # 3. known tool normalization
        tool = _normalize_tool(base)
        return (tool or "unknown"), (raw or comm)

    # No process signals (fs-coil light): territory attribution only.
    # ponytail: named ceiling — light mode cannot tell Claude writing
    # ~/.claude from an intruder doing the same; that is why deep mode exists.
    if path is not None:
        agent = _agent_for_path(os.path.expanduser(path), registry)
        if agent:
            return agent, None
    return "unknown", None


def classify_event(path, mode, actor_bucket, registry=None):
    """(category, actor_mismatch) — the D06/D07 territory table.

    Called on events that already matched the deny list, in both modes.
    """
    registry = registry if registry is not None else load_registry()
    path = os.path.expanduser(path)
    by_mode = "deny_read" if mode == "R" else "deny_write"
    owner = _agent_for_path(path, registry)
    if owner is None:
        return by_mode, None
    if actor_bucket == owner:
        if _inside(path, registry[owner].get("cache_paths", [])):
            return "agent_plugin_cache", None
        return "agent_self", None
    if actor_bucket in registry:      # registered agent X ≠ Y (D07)
        return "deny_write", owner
    return by_mode, None
