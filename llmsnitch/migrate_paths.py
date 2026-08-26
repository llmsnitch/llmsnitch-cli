"""Idempotent user-domain path migration: llm-snitch → llmsnitch.

Moves legacy hyphenated user-domain artifacts (config, logs, caches) to the
canonical dashless paths and leaves a symlink at the old location for one
release as a compat breadcrumb. Config files are merged section-wise —
[gate] lives on llmsnitch, [notify]/[notify.*]/[agent.*] live on fs_coil,
so a union is safe (sections don't overlap).

Root-domain paths (/usr/local/share/, LaunchDaemon plist) are out of scope —
they need sudo and are handled by the install wizard, not this command.

Usage:  llmsnitch migrate-paths
"""

import configparser
import os
from pathlib import Path


def _migrate_dir(old, new, out):
    if old.is_symlink() or not old.exists():
        return
    if new.exists():
        out.write(f"skip  {old} → {new}: destination exists\n")
        return
    new.parent.mkdir(parents=True, exist_ok=True)
    os.rename(old, new)
    os.symlink(new, old)   # compat breadcrumb
    out.write(f"moved {old} → {new} (symlink left behind)\n")


def _merge_config(old, new, out):
    if old.is_symlink() or not old.exists():
        return
    new.parent.mkdir(parents=True, exist_ok=True)
    if not new.exists():
        os.rename(old, new)
        os.symlink(new, old)
        out.write(f"moved {old} → {new}\n")
        return
    # Union sections — [gate] on new, [notify*]/[agent.*] on old, no overlap.
    cp = configparser.ConfigParser(inline_comment_prefixes=("#",))
    cp.read([new, old])   # last read wins; overlap would prefer `old` (the
                          # more actively edited notify config)
    with open(new, "w") as f:
        cp.write(f)
    os.chmod(new, 0o600)
    bak = old.with_suffix(old.suffix + ".merged")
    os.rename(old, bak)
    os.symlink(new, old)
    out.write(f"merged {old} → {new} (old kept as {bak})\n")


def run(out, home=None):
    """Idempotent. Second run is a no-op."""
    home = Path(home) if home else Path(os.path.expanduser("~"))
    _migrate_dir(home / "Library/Logs/llm-snitch",
                 home / "Library/Logs/llmsnitch", out)
    _migrate_dir(home / "Library/Caches/llm-snitch",
                 home / "Library/Caches/llmsnitch", out)
    _merge_config(home / ".config/llm-snitch/config",
                  home / ".config/llmsnitch/config", out)
    return 0
