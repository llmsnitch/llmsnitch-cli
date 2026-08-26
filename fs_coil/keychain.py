"""Classify exec events that touch Apple Keychain.

Apple ships /usr/bin/security as the only CLI entry point into Keychain
Services — every subcommand either reads, writes, or deletes a Keychain
item. ssh-add with --apple-use-keychain (or legacy -K) stores an SSH
passphrase. Classifying the subcommand gives us READ / WRITE / DELETE
signal from a single exec event, without needing auth-level ES hooks.
"""

import hashlib
import os


KEYCHAIN_BINARIES = {"security", "ssh-add"}


def _redact(value):
    """Fingerprint a sensitive value for logging: short SHA-256 + length.
    Preserves detection signal (same value → same hash) without leaking
    identifiers like emails/usernames/paths."""
    if not value:
        return ""
    h = hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:8]
    return f"<sha256:{h}:len{len(value)}>"

# security <verb> → operation. Anything not in this map is flagged as READ?
# (defensive default — don't miss verbs Apple might add).
SECURITY_VERBS = {
    # read
    "find-generic-password":                "READ",
    "find-internet-password":               "READ",
    "find-certificate":                     "READ",
    "find-identity":                        "READ",
    "find-key":                             "READ",
    "dump-keychain":                        "READ",
    "export":                               "READ",
    "list-keychains":                       "READ",
    "list-smartcards":                      "READ",
    "show-keychain-info":                   "READ",
    "default-keychain":                     "READ",
    "login-keychain":                       "READ",
    # mutate
    "add-generic-password":                 "WRITE",
    "add-internet-password":                "WRITE",
    "add-certificates":                     "WRITE",
    "add-trusted-cert":                     "WRITE",
    "import":                               "WRITE",
    "unlock-keychain":                      "WRITE",
    "lock-keychain":                        "WRITE",
    "lock":                                 "WRITE",
    "set-keychain-settings":                "WRITE",
    "set-keychain-password":                "WRITE",
    "set-generic-password-partition-list":  "WRITE",
    "set-internet-password-partition-list": "WRITE",
    "set-key-partition-list":               "WRITE",
    "change-password":                      "WRITE",
    "create-keychain":                      "WRITE",
    "create-keypair":                       "WRITE",
    # delete
    "delete-generic-password":              "DELETE",
    "delete-internet-password":             "DELETE",
    "delete-certificate":                   "DELETE",
    "delete-identity":                      "DELETE",
    "delete-keychain":                      "DELETE",
}


def classify_keychain_exec(exe_path, args):
    """Return (op, hint) if this exec touches Keychain, else None.

    - op is 'READ' / 'WRITE' / 'DELETE' / 'READ?' (unknown verb)
    - hint is a short string identifying the target: service/account for
      `security`, key path for `ssh-add`. Empty string if not detectable.
    """
    base = os.path.basename(exe_path or "")
    if base not in KEYCHAIN_BINARIES:
        return None

    if base == "security":
        if not args or len(args) < 2:
            return None
        verb = args[1]
        op = SECURITY_VERBS.get(verb, "READ?")
        hint = _extract_security_hint(args) or verb
        return (op, hint)

    if base == "ssh-add":
        # --apple-use-keychain / -K / -A touches Keychain to store or load
        # passphrases. Plain `ssh-add <file>` only talks to ssh-agent.
        has_kc_flag = any(a in ("--apple-use-keychain", "-K", "-A") for a in args)
        if not has_kc_flag:
            return None
        writes = any(a in ("--apple-use-keychain", "-K") for a in args)
        return ("WRITE" if writes else "READ", _extract_sshadd_hint(args))

    return None


def _extract_security_hint(args):
    """Pull -s <service> or -a <account> out of a `security` argv.
    Values are redacted — `account=` is often an email/username."""
    for i, a in enumerate(args):
        if a in ("-s", "--service") and i + 1 < len(args):
            return f"service={_redact(args[i + 1])}"
        if a in ("-a", "--account") and i + 1 < len(args):
            return f"account={_redact(args[i + 1])}"
    return ""


def _extract_sshadd_hint(args):
    """Last non-flag arg of `ssh-add` — usually the private key path.
    Redacted; a full user-home path is itself identifying."""
    for a in reversed(args or []):
        if a and not a.startswith("-"):
            return _redact(a)
    return ""
