"""DENY_RULES — table of (mode, pattern) tuples.

Split out of denylist.py to keep each file ≤ 200 lines. Derived from Claude-Code
permission syntax in CLAUDE.md / .claude/settings.json. Each entry is
(mode, pattern) where:
  mode   = "R"  → match on read events only (open without write flag)
           "W"  → match on write/create/rename/unlink/link only
           "RW" → any event
  pattern is a path glob; ** matches zero-or-more path components,
  ~ expands to the console-user's home.
"""

DENY_RULES = [
    # 1a — tool credentials & tokens
    ("R",  "~/.ssh/**"),
    ("R",  "~/.aws/**"),
    ("R",  "~/.gnupg/**"),
    ("R",  "~/.netrc"),
    ("R",  "~/.docker/config.json"),
    ("R",  "~/.config/gh/**"),
    ("R",  "~/.kube/config*"),
    ("R",  "~/.npmrc"),
    ("R",  "~/.pypirc"),
    ("RW", "~/.claude.json"),
    ("RW", "~/.cargo/credentials.toml"),
    ("RW", "~/.gem/credentials"),
    ("RW", "~/.composer/auth.json"),
    ("RW", "~/.gradle/gradle.properties"),
    ("RW", "~/.android/debug.keystore"),
    ("RW", "~/.android/adbkey"),
    ("RW", "~/.emulator_console_auth_token"),

    # 1b — shell & command histories
    ("R",  "~/.bash_history"),
    ("R",  "~/.zsh_history"),
    ("R",  "~/.sh_history"),
    ("R",  "~/.history"),
    ("R",  "~/.mysql_history"),
    ("R",  "~/.psql_history"),
    ("R",  "~/.python_history"),
    ("R",  "~/.node_repl_history"),
    ("R",  "~/.lesshst"),
    ("R",  "~/.viminfo"),

    # 1c — shell / terminal config (write = backdoor risk)
    ("RW", "~/.gitconfig"),
    ("RW", "~/.bashrc"),
    ("RW", "~/.bash_profile"),
    ("RW", "~/.profile"),
    ("RW", "~/.zshrc"),
    ("RW", "~/.zshenv"),
    ("RW", "~/.zprofile"),
    ("RW", "~/.tcshrc"),
    ("RW", "~/.p10k.zsh"),
    ("RW", "~/.tmux.conf"),

    # 1d — app data & generic config
    ("RW", "~/.config/**"),
    ("RW", "~/.mutt/**"),
    ("RW", "~/.w3m/**"),

    # 1e — Keychain, Cookies, browsers, TCC, iCloud
    ("R",  "~/Library/Keychains/**"),
    # Keychain is monitored but matches by Claude on its OWN credentials
    # get downgraded to severity=low by _low_noise() in monitor.py — they
    # get logged (for audit) but don't fire a notification.
    ("R",  "~/Library/Cookies/**"),
    ("R",  "~/Library/Application Support/Google/Chrome/**"),
    ("R",  "~/Library/Application Support/Firefox/**"),
    ("R",  "~/Library/Application Support/com.apple.TCC/**"),
    ("RW", "~/Library/Mobile Documents/com~apple~CloudDocs/**"),

    # 1e-extra — other dev/productivity tools' state. Claude.app was
    # observed harvesting Zed's workspace SQLite DB via a disclaimer-
    # spawned sqlite3 subprocess (bypassing the usual Claude.app signing-id
    # match, recovered via disclaim_tracker). Flag any AI actor reading
    # these — Claude's OWN Application Support/Claude/** is untouched.
    ("R",  "~/Library/Application Support/Zed/**"),
    ("R",  "~/Library/Application Support/Cursor/**"),
    ("R",  "~/Library/Application Support/Code/**"),
    ("R",  "~/Library/Application Support/Code - Insiders/**"),
    ("R",  "~/Library/Application Support/VSCodium/**"),
    ("R",  "~/Library/Application Support/JetBrains/**"),
    ("R",  "~/Library/Application Support/Sublime Text/**"),
    ("R",  "~/Library/Application Support/Obsidian/**"),
    ("R",  "~/Library/Application Support/Notion/**"),
    ("R",  "~/Library/Application Support/Slack/**"),
    ("R",  "~/Library/Application Support/Discord/**"),
    ("R",  "~/Library/Application Support/Signal/**"),
    ("R",  "~/Library/Application Support/Telegram Desktop/**"),

    # 1f — system absolute paths
    ("R",  "/etc/passwd"),
    ("R",  "/etc/shadow"),
    ("R",  "/etc/gshadow"),
    ("R",  "/etc/master.passwd"),
    ("R",  "/etc/sudoers"),
    ("R",  "/etc/sudoers.d/**"),
    ("R",  "/etc/ssh/**"),
    ("R",  "/etc/ssl/private/**"),
    ("R",  "/etc/krb5.keytab"),
    ("R",  "/private/etc/passwd"),
    ("R",  "/private/etc/master.passwd"),
    ("R",  "/private/etc/sudoers"),
    ("R",  "/private/etc/sudoers.d/**"),
    ("R",  "/private/etc/ssh/**"),
    ("R",  "/private/etc/ssl/private/**"),
    ("R",  "/var/root/**"),
    ("R",  "/var/log/**"),

    # 1g — EXTERNAL / REMOVABLE / NETWORK volumes. On macOS every mounted
    # volume — DMGs, sparsebundles, USB / Thunderbolt drives, SMB / AFP /
    # NFS shares, iCloud Drive, disk images — appears under /Volumes/<name>.
    # Auto-mounted network paths also appear under /Network/<host>. Treat
    # *any* AI access to these paths as suspect (user didn't ask the AI
    # to wander off the boot volume).
    ("RW", "/Volumes/**"),        # external / removable / mounted image
    ("RW", "/Network/**"),        # auto-mounted network shares
    # AppTranslocation: macOS runs un-notarized apps from a shadow
    # directory under /private/var/folders/.../T/AppTranslocation/. AI
    # poking around there is highly suspicious.
    ("R",  "/private/var/folders/**/AppTranslocation/**"),

    # 1h — project-local sensitive files (basename match via /**/ prefix)
    ("RW", "/**/.env"),
    ("RW", "/**/.env.local"),
    ("RW", "/**/.env.*.local"),
    ("RW", "/**/.env.production"),
    ("RW", "/**/.env.prod"),
    ("RW", "/**/.env.staging"),
    ("RW", "/**/.env.stage"),
    ("RW", "/**/.env.development"),
    ("RW", "/**/.env.dev"),
    ("RW", "/**/.env.test"),
    ("RW", "/**/.env.secret"),
    ("RW", "/**/.env.secrets"),
    ("RW", "/**/id_rsa"),
    ("RW", "/**/id_ed25519"),
    ("RW", "/**/id_ecdsa"),
    ("RW", "/**/id_dsa"),
    ("RW", "/**/*.p12"),
    ("RW", "/**/*.pfx"),
    ("RW", "/**/*.jks"),
    ("RW", "/**/*.keystore"),
    ("RW", "/**/secrets.json"),
    ("RW", "/**/secrets.yml"),
    ("RW", "/**/secrets.yaml"),
    ("RW", "/**/credentials"),
    ("RW", "/**/credentials.json"),
    ("RW", "/**/service-account*.json"),
    ("RW", "/**/.git-credentials"),
    ("RW", "/**/.htpasswd"),
    ("RW", "/**/.pgpass"),

    # 1j — config self-unlock protection
    ("W",  "/**/.claude/settings.json"),
    ("W",  "/**/.claude/settings.local.json"),
    ("W",  "/**/.claude/hooks.json"),
    ("W",  "/**/.claude/managed-settings.json"),
    ("W",  "/**/.git/hooks/**"),
    ("W",  "/**/.git/config"),
    ("W",  "/**/.github/workflows/**"),
    ("W",  "/**/.vscode/tasks.json"),
]
