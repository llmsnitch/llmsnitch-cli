"""Module-level constants: paths, process names, noise substrings, sensitive
basename globs. No side effects beyond a small filesystem probe to pick the
terminal-notifier path."""

import os
from pathlib import Path

PLIST_LABEL = "com.slav-it.llmsnitch"
PLIST_PATH = Path(f"/Library/LaunchDaemons/{PLIST_LABEL}.plist")
BIN_PATH = Path("/usr/local/bin/fs-coil")
LIGHT_AGENT_LABEL = "com.slav-it.fs-coil"   # user LaunchAgent (light mode):
                                             # ~/Library/LaunchAgents/<label>.plist
ESLOGGER = "/usr/bin/eslogger"
TERMINAL_NOTIFIER = next(
    (p for p in ("/opt/homebrew/bin/terminal-notifier",
                 "/usr/local/bin/terminal-notifier")
     if os.path.exists(p)),
    "/opt/homebrew/bin/terminal-notifier",  # fallback path for error messages
)

# Event classes we subscribe to. "write" fires on every write() syscall so it's
# noisy; we rely on "create" + "rename" + "unlink" for mutation signal and
# "open" for reads (flag-filtered below).
ES_EVENTS = ["open", "create", "rename", "unlink", "link", "exec"]

# ---------------------------------------------------------------------------
# Processes we watch. Matched against process.executable.path (basename) AND
# process.signing_id. Substring match, case-insensitive.
# ---------------------------------------------------------------------------
WATCHED_PROC = (
    "claude",
    "opencode",
    "com.anthropic",
)

# Shells / interpreters that become "interesting" only when their responsible
# ancestor is one of the watched agents. eslogger gives us responsible_audit_token
# which is the token of the process that "caused" this action (set via
# responsibility API). For Claude Code spawning bash -c ..., responsible == claude.
INTERPRETER_PROC = (
    "bash", "zsh", "sh", "dash", "fish",
    "python", "python3", "node", "ruby", "perl", "deno", "bun",
)

# ---------------------------------------------------------------------------
# Fast-reject: if the path contains any of these substrings, drop the event
# BEFORE running the deny matcher. Overridden for files matching
# SENSITIVE_BASENAME_GLOBS (those are ALWAYS examined).
# ---------------------------------------------------------------------------
NOISE_PATH_SUBSTRINGS = (
    "/node_modules/",
    "/.venv/", "/venv/", "/.virtualenv/",
    "/__pycache__/", "/.pytest_cache/", "/.mypy_cache/", "/.ruff_cache/",
    "/target/debug/", "/target/release/",  # Rust
    "/.cargo/registry/", "/.cargo/git/",
    "/dist/", "/build/", "/out/",
    "/.next/", "/.nuxt/", "/.svelte-kit/", "/.turbo/", "/.parcel-cache/",
    "/.cache/",
    "/DerivedData/", "/.build/",          # Xcode, SPM
    "/Pods/",
    "/.gradle/caches/", "/.gradle/wrapper/",
    "/.idea/", "/.vscode-server/",
    "/.terraform/",
    "/.pnpm-store/", "/.yarn/cache/", "/.bun/install/cache/",
    "/Library/Caches/", "/Library/Logs/",
    "/.git/objects/", "/.git/logs/", "/.git/refs/", "/.git/pack/",
    "/Library/Logs/llmsnitch/", "/Library/Caches/llmsnitch/",                       # avoid feedback loop
    "/.Trash/",                            # separate concern
)

# Globs for basenames that must ALWAYS be checked, even inside noise dirs
# (someone could hide a .env in node_modules).
SENSITIVE_BASENAME_GLOBS = (
    ".env", ".env.*",
    "id_rsa", "id_rsa.pub",
    "id_ed25519", "id_ed25519.pub",
    "id_ecdsa", "id_ecdsa.pub",
    "id_dsa", "id_dsa.pub",
    "*.p12", "*.pfx", "*.jks", "*.keystore",
    "secrets.json", "secrets.yml", "secrets.yaml",
    "credentials", "credentials.json", "credentials.toml",
    "service-account*.json",
    ".git-credentials",
    ".htpasswd", ".pgpass", ".netrc",
    ".claude.json",
)
