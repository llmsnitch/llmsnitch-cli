"""App-bundle icon discovery helpers. Used by Notifier to decorate toasts
with the offending actor's .app icon."""

import os
import subprocess
from pathlib import Path

APP_SEARCH_ROOTS = ("/Applications", "/System/Applications")


def _app_bundle_ancestor(path):
    if not path:
        return None
    p = Path(path)
    for anc in [p] + list(p.parents):
        if anc.suffix == ".app" and anc.is_dir():
            return anc
    return None


def _app_bundle_by_name(name, extra_roots=()):
    if not name:
        return None
    nlow = name.lower()
    for root in list(APP_SEARCH_ROOTS) + list(extra_roots):
        if not os.path.isdir(root):
            continue
        try:
            entries = os.listdir(root)
        except OSError:
            continue
        for entry in entries:
            if not entry.endswith(".app"):
                continue
            stem = entry[:-4].lower()
            if stem == nlow or nlow in stem or stem in nlow:
                return Path(root) / entry
    return None


def _bundle_icns(bundle):
    rsrc = bundle / "Contents" / "Resources"
    plist = bundle / "Contents" / "Info.plist"
    for key in ("CFBundleIconFile", "CFBundleIconName"):
        try:
            out = subprocess.run(
                ["/usr/bin/defaults", "read", str(plist), key],
                capture_output=True, text=True, timeout=2,
            )
        except Exception:
            continue
        name = out.stdout.strip()
        if out.returncode == 0 and name:
            for ext in ("", ".icns"):
                c = rsrc / (name + ext)
                if c.exists():
                    return c
    if rsrc.is_dir():
        for f in rsrc.glob("*.icns"):
            return f
    return None


def _icns_to_png(icns, out):
    try:
        r = subprocess.run(
            ["/usr/bin/sips", "-s", "format", "png", str(icns), "--out", str(out)],
            capture_output=True, timeout=5,
        )
        return r.returncode == 0 and out.exists() and out.stat().st_size > 0
    except Exception:
        return False


def _find_notifier():
    for p in ("/opt/homebrew/bin/terminal-notifier",
              "/usr/local/bin/terminal-notifier"):
        if os.path.exists(p):
            return p
    return None
