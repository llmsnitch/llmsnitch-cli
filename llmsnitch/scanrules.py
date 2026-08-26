"""Inline scan ruleset. Rules are CODE, not data files.

Ramparts loads rules from a runtime-resolved directory, ships none in its
crate, and documents the resulting silent fail-open-with-zero-rules
(ramparts src/scanner.rs:73-78). skill-detector compiles rules into the
binary and stamps a ruleset checksum into every result. We follow
skill-detector: see docs/research/scanner-survey-mvp.md §2.1.

Severity is fixed per category (spec §2.5): config_compromise=critical,
secret_at_rest=high, config_drift=high (control surfaces), scan_hygiene=low.
"""

import hashlib
import re

# Artifact classes that are control surfaces — where a compromise rule hit
# or a drift means an agent's behavior can be rewritten.
CONTROL_CLASSES = frozenset({"claude_settings", "hook_script", "mcp_config"})

# Agent territories from docs/notifier-spec.md §Agent registry (paths only —
# a batch scan attributes territory, not actors: the spec's light-mode ceiling).
TERRITORIES = {
    "claude-code": ["~/.claude", "~/.claude.json"],
    "codex":       ["~/.codex"],
    "aider":       ["~/.aider"],
    "copilot":     ["~/.copilot"],
    "cursor":      ["~/.cursor"],
    "windsurf":    ["~/.windsurf"],
    "agy":         ["~/.agy"],
}

# (rule_id, category, severity, classes, compiled regex) — line-matched.
# Shapes grounded in MIT/Apache sources only (survey Part 1); MEDUSA (AGPL)
# corroborates the class but contributed no pattern text.
_C = "config_compromise"
_H = "scan_hygiene"

RULES = [
    # -- compromise: control surfaces + skill/hook scripts ------------------
    # Bounded runs throughout: these rules face attacker-sized lines, and an
    # unbounded quantifier next to an overlapping class backtracks
    # quadratically (plan 001; regression lock: test_scan_rules_resist_redos).
    ("hook_curl_pipe_shell", _C, "critical",
     ("claude_settings", "hook_script", "mcp_config", "skill_script"),
     re.compile(r"\b(curl|wget)\s[^|;]{0,400}\|\s*(sudo\s+)?(ba|z|da)?sh\b")),
    ("hook_base64_decode_shell", _C, "critical",
     ("claude_settings", "hook_script", "mcp_config", "skill_script"),
     re.compile(r"base64\s+(-d|-D|--decode)\S*[^|]{0,400}\|\s*(sudo\s+)?(ba|z)?sh\b")),
    ("hook_reverse_shell", _C, "critical",
     ("claude_settings", "hook_script", "mcp_config", "skill_script",
      "skill_manifest"),
     re.compile(r"(bash\s+-i\s+>&\s*/dev/tcp/|/dev/tcp/\d"
                r"|nc\s(-\w*e\w*\s|[^\n]{0,200}\s-e\s)"
                r"|mkfifo\s+/tmp/\S+\s*;[^\n|]{0,200}\|\s*(ba|z)?sh)")),
    # ponytail: exact "Bash" / "Bash(*)" only (skill-detector's core shapes);
    # scoped wildcards like Bash(*terraform*) and hook '"matcher": "Bash"'
    # lines are deliberate non-matches. Widen only with a JSON-aware check.
    ("wildcard_bash_grant", _C, "critical",
     ("claude_settings",),
     re.compile(r'"Bash\(\*\)"|(?<!matcher": )(?<!matcher":)"Bash"')),
    ("bypass_permissions", _C, "critical",
     ("claude_settings",),
     re.compile(r"bypassPermissions")),
    # -- skill / instruction-file injection ---------------------------------
    ("skill_instruction_override", _C, "critical",
     ("skill_manifest", "instruction_file"),
     re.compile(r"(ignore|disregard|forget)\s+(all\s+|any\s+)?(previous|above|prior|earlier|system)\s+(instructions?|prompts?|rules?)", re.I)),
    ("skill_concealment", _C, "critical",
     ("skill_manifest", "instruction_file", "skill_script"),
     re.compile(r"do\s+not\s+(tell|inform|mention|reveal|show)\s+(this\s+)?(to\s+)?(the\s+)?user", re.I)),
    # bidi overrides / zero-width / Tags block on config or skills — Trojan
    # Source class. Deliberately narrower than hook._INV_RE: no variation
    # selectors, no BOM (benign in prose/first byte).
    ("invisible_unicode", _C, "critical",
     ("claude_settings", "hook_script", "mcp_config", "skill_manifest"),
     re.compile("[​-‏‪-‮⁦-⁩\U000e0020-\U000e007f]")),
    # -- hygiene (never pages; digest only) ----------------------------------
    ("skill_base64_blob", _H, "low",
     ("skill_manifest", "instruction_file"),
     re.compile(r"[A-Za-z0-9+/]{120,}={0,2}")),
]

# Secret shapes at rest: hook._SECRET (single source of truth) + issuer
# extensions grounded in Cisco hardcoded_secrets.yaml / skill-detector
# misconfiguration.go. High-specificity prefixes only (hook.py rationale).
SECRET_EXTRA = re.compile(
    r"(AIza[0-9A-Za-z_-]{35}"            # Google API key
    r"|(sk|rk)_live_[0-9a-zA-Z]{24,}"    # Stripe live/restricted
    r"|glpat-[0-9a-zA-Z_-]{20,}"         # GitLab PAT
    r"|npm_[A-Za-z0-9]{36}"              # npm token
    r"|hf_[A-Za-z0-9]{34}"               # Hugging Face
    r")"
)


def ruleset_sha256():
    """Reproducibility stamp (skill-detector pkg/rules/registry.go:37-51):
    every scan records which ruleset produced it."""
    blob = "|".join(sorted(f"{rid}:{rx.pattern}" for rid, _, _, _, rx in RULES))
    blob += "|secret_extra:" + SECRET_EXTRA.pattern
    return hashlib.sha256(blob.encode()).hexdigest()
