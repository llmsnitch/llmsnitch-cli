"""Shared scaffolding for the tool-wrapper snakes (session-shed,
agent-flick): binary resolution, config-section load, secure state/log
writes, and the edge-triggered alert state machine.

Extracted once a second wrapper appeared (DRY threshold = two callers). Each
wrapper keeps thin module-level adapters over these so its own test surface
stays stable, while the logic lives here in one place.
"""

import configparser
import json
import os
from pathlib import Path

from fs_coil.runtime import console_user, user_home

# Normalized exit codes for a `check` gate: 0 pass / 1 breach / 2 operational.
# (Wrapped binaries may use other codes — the wrapper maps to these.)
EXIT_PASS, EXIT_BREACH, EXIT_OPERATIONAL = 0, 1, 2

_CONFIG_PATH = "~/.config/llm-snitch/config"


def resolve_bin(candidates):
    """First existing path in `candidates`, else None (= not installed)."""
    return next((p for p in candidates if p and os.path.exists(p)), None)


def state_dir(tool):
    """~/Library/Logs/llm-snitch/<tool>/, created 0700, owned by the console
    user's home. `tool` is the subdir name, e.g. 'session-shed'."""
    home = user_home(console_user() or "") if console_user() else os.path.expanduser("~")
    d = Path(home) / "Library" / "Logs" / "llm-snitch" / tool
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    return d


def secure_write(path, text, mode="w"):
    """Write `text` to `path` then chmod 0600. `mode='a'` appends (log files)."""
    with open(path, mode) as f:
        f.write(text)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_section(section, defaults, casters=None):
    """Read [section] from the llm-snitch INI config with per-key fallback.

    defaults: dict of key -> default value (defines which keys are read).
    casters:  dict of key -> callable (int/float/…); keys absent from casters
              are read as stripped strings. One malformed value never resets
              the others.
    """
    casters = casters or {}
    cfg = dict(defaults)
    path = os.path.expanduser(_CONFIG_PATH)
    if not os.path.exists(path):
        return cfg
    cp = configparser.ConfigParser(inline_comment_prefixes=("#",))
    try:
        cp.read(path)
    except configparser.Error:
        return cfg
    if cp.has_section(section):
        s = cp[section]
        for key in defaults:
            raw = s.get(key)
            if raw is None:
                continue
            caster = casters.get(key)
            try:
                cfg[key] = caster(raw) if caster else raw.strip()
            except (ValueError, TypeError):
                pass  # malformed -> keep default for THIS key only
    return cfg


def edge_alert(state_path, verdict, on_breach, on_recover):
    """Edge-triggered transition handler. Fires `on_breach()` on a
    healthy->breach transition and `on_recover()` on a real breach->pass
    (never on the first-ever healthy run, where prev is None). Persists the
    new verdict. Returns the previous verdict (or None)."""
    prev = None
    if state_path.exists():
        try:
            prev = json.loads(state_path.read_text()).get("verdict")
        except (OSError, json.JSONDecodeError):
            prev = None
    if verdict != prev:
        if verdict == "breach":
            on_breach()
        elif prev == "breach":
            on_recover()
        secure_write(state_path, json.dumps({"verdict": verdict}))
    return prev
