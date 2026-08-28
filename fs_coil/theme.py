"""ywizz-style theme (purple accent) — ANSI escapes, tree glyphs, plain
wordmark, tag printers. Mirrors lib/ywizz/theme.sh + info.sh so CLI output
looks the same as install.sh."""

import sys

# Plain text wordmark — no ASCII art.
BANNER = "llmSnitch"

TAGLINE = "    filesystem tripwire — guarding the path from Claude & Opencode"

# ---------------------------------------------------------------------------
# ywizz-style theme (purple accent).
# ---------------------------------------------------------------------------
_C7     = "\x1b[38;5;177m"   # purple accent
_PURPLE = _C7
_ORANGE = "\x1b[38;5;208m"   # xterm orange — severity ramp (purple → orange → red)
_GREEN  = "\x1b[32m"
_YELLOW = "\x1b[33m"
_RED    = "\x1b[31m"
_CYAN   = "\x1b[36m"
_DIM    = "\x1b[2m"
_BOLD   = "\x1b[1m"
_R      = "\x1b[0m"
_TREE_TOP = "┌ "
_TREE_MID = "│ "
_TREE_BOT = "└ "
_DIAMOND  = "◆ "


def _tty():
    return sys.stdout.isatty()


def _tag(color, label, msg, file=sys.stdout):
    if _tty():
        print(f"{_C7}{_TREE_MID}{_R}{color}[{label}]{_R} {color}{msg}{_R}", file=file)
    else:
        print(f"[{label}] {msg}", file=file)


def ok(msg):    _tag(_GREEN,  " OK ", msg)
def warn(msg):  _tag(_YELLOW, "WARN", msg, sys.stderr)
def err(msg):   _tag(_RED,    "FAIL", msg, sys.stderr)
def info(msg):  _tag(_CYAN,   "INFO", msg)
def skip(msg):  _tag(_DIM,    "SKIP", msg)


def item(msg):
    if _tty():
        print(f"{_C7}{_TREE_MID}{_R} {msg}")
    else:
        print(f"  {msg}")


def head(title):
    if _tty():
        print(f"{_C7}{_TREE_TOP}{_DIAMOND}{_BOLD}{_C7}{title}{_R}")
    else:
        print(f"== {title} ==")


def print_banner():
    if not sys.stdout.isatty():
        return
    reset = "\x1b[0m"
    print(f"{_C7}{_BOLD}{BANNER}{reset}")
    print(f"\x1b[38;2;255;105;180m{TAGLINE}{reset}\n")
