"""Glob-to-regex compiler + path-noise/sensitive helpers. DENY_RULES (the
rule table) lives in deny_rules.py; compile_deny below turns it into regexes."""

import fnmatch
import re

from fs_coil.constants import NOISE_PATH_SUBSTRINGS, SENSITIVE_BASENAME_GLOBS
from fs_coil.deny_rules import DENY_RULES


def glob_to_regex(pat, home):
    """Convert our glob syntax to a full-path regex.

    Rules:
      ~      → $HOME
      /**/   → /(?:.*/)?    (zero or more path components)
      **     → .*
      *      → [^/]*
      ?      → [^/]
      other  → regex-escaped
    """
    if pat.startswith("~/"):
        pat = home + pat[1:]
    elif pat.startswith("~"):
        pat = home + pat[1:]

    out = ["^"]
    i = 0
    while i < len(pat):
        c = pat[i]
        if c == "*":
            if pat[i:i+4] == "/**/":
                out.append("/(?:.*/)?")
                i += 4
                continue
            if pat[i:i+2] == "**":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    out.append("$")
    return re.compile("".join(out))


def compile_deny(home):
    return [(mode, pat, glob_to_regex(pat, home)) for (mode, pat) in DENY_RULES]


def is_sensitive_basename(name):
    return any(fnmatch.fnmatchcase(name, g) for g in SENSITIVE_BASENAME_GLOBS)


def path_in_noise(path):
    return any(s in path for s in NOISE_PATH_SUBSTRINGS)


def match_deny(path, mode, deny_compiled):
    for (rule_mode, rule_pat, rx) in deny_compiled:
        if rule_mode != "RW" and rule_mode != mode:
            continue
        if rx.match(path):
            return rule_pat
    return None


def _shrink(p, home):
    """Tilde-shorten absolute paths so notifications fit."""
    if not p:
        return ""
    if home and p == home:
        return "~"
    if home and p.startswith(home + "/"):
        return "~" + p[len(home):]
    return p
