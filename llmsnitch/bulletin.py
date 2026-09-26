"""Bulletin cache reader + fetch — docs/bulletin-spec.md "Fetch, verify, cache".

The fetch is a curl subprocess (ADR 0001: no network code in the package);
refresh() lands the pair in temps beside the cache, verifies them with the
same load() the audit uses, and swaps atomically. Re-verifies the cached gz against its .sha256 sidecar (integrity over the
raw bytes), gates on schema_version {1}, and stamps payload age from
meta.issued_at. The cache file is hostile input: load() never raises —
every failure is (None, "short reason") — and index() skips malformed
entries. Matching is set membership only (T502): no version ranges, no
ordering, ever.
"""

import gzip
import hashlib
import io
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import store

# Decompression bound: the spec's guidance is <= 10 MB gz per ecosystem; a
# hostile cache file must not be able to balloon memory (gzip packs ~1000:1).
_MAX_DECOMP = 200_000_000

# Rolling release published by the provider (developed independently at
# ~/Repos/llmsnitch-bulletin, docs/bulletin-spec.md is the shared contract);
# LLMSNITCH_BULLETIN_URL overrides — file:// URLs work, that is the test seam.
BULLETIN_URL = ("https://github.com/llmsnitch/bulletin/releases/download/"
                "bulletin/pypi.json.gz")
# ponytail: a constant, not a config key — the digest already says
# "bulletin stale" at 14 days; make this configurable when someone asks.
REFRESH_DAYS = 7


def default_path():
    """Lazy — base_dir() honors the LLMSNITCH_DIR seam at call time."""
    return store.base_dir() / "bulletins" / "pypi.json.gz"


def load(path=None):
    """(bulletin, None) or (None, reason). Never raises."""
    p = Path(path) if path is not None else default_path()
    try:
        raw = p.read_bytes()
    except OSError:
        return None, "bulletin missing"
    try:
        want = Path(str(p) + ".sha256").read_text().split()[0]
    except (OSError, IndexError):
        return None, "sidecar missing"
    if hashlib.sha256(raw).hexdigest() != want.lower():
        return None, "hash mismatch"
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as g:
            data = g.read(_MAX_DECOMP + 1)
        if len(data) > _MAX_DECOMP:
            return None, "unreadable bulletin"
        doc = json.loads(data)
    except Exception:   # noqa: BLE001 — truncated gz, bad zlib, non-JSON, …
        return None, "unreadable bulletin"
    if not isinstance(doc, dict) or not isinstance(doc.get("meta"), dict) \
            or not isinstance(doc.get("entries"), list):
        return None, "unreadable bulletin"
    sv = doc["meta"].get("schema_version")
    if sv is True or sv != 1:   # bool guard: JSON true == 1 in Python
        return None, f"unsupported schema_version {sv}"
    return doc, None


def needs_refresh():
    """Cache missing, unloadable, or payload older than REFRESH_DAYS."""
    doc, _ = load()
    if doc is None:
        return True
    age = age_days(doc["meta"])
    return age is None or age >= REFRESH_DAYS


def _curl(url, dest):
    try:
        rc = subprocess.run(
            ["curl", "-fsSL", "--retry", "3", "--max-time", "120",
             "-o", str(dest), url], capture_output=True).returncode
    except OSError:          # no curl on PATH
        return False
    store._chmod_private(dest)   # curl opens the file itself
    return rc == 0


def refresh(out):
    """Fetch bulletin + sidecar to temps, verify with load(), swap
    atomically. 0 ok / 2 failed (one [WARN] line); never raises — the
    caller keeps auditing on the old cache."""
    url = os.environ.get("LLMSNITCH_BULLETIN_URL", BULLETIN_URL)
    p = default_path()
    tmp = Path(str(p) + ".tmp")
    tmp_sc = Path(str(tmp) + ".sha256")   # load(tmp) finds it unchanged
    try:
        store._mkdir_private(p.parent)
        if not (_curl(url, tmp) and _curl(url + ".sha256", tmp_sc)):
            reason = "fetch failed"
        else:
            doc, reason = load(tmp)
        if reason is None:
            os.replace(tmp_sc, Path(str(p) + ".sha256"))
            os.replace(tmp, p)
            return 0
    except OSError as e:
        reason = type(e).__name__
    finally:
        for f in (tmp, tmp_sc):
            try:
                f.unlink()
            except OSError:
                pass
    out.write(f"[WARN] bulletin refresh failed: {reason}\n")
    return 2


def age_days(meta):
    """Days since meta.issued_at, or None. Naive stamps are UTC."""
    try:
        dt = datetime.fromisoformat(
            meta["issued_at"].replace("Z", "+00:00"))
    except (TypeError, KeyError, ValueError, AttributeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0


def normalize_name(name):
    return re.sub(r"[-_.]+", "-", name).lower()


# Pre/post spelling segment: an optional joining dot, the spelling, an
# optional dot before the number. Longest spellings first so "preview"
# never half-matches as "pre", "rev"/"rc" before bare "r"/"c".
_SPELLING = re.compile(
    r"(?<=\d)\.?(alpha|beta|preview|pre|rc|rev|c|r|a|b)\.?(\d*)")
_SPELL_MAP = {"alpha": "a", "beta": "b", "preview": "rc", "pre": "rc",
              "rc": "rc", "c": "rc", "rev": "post", "r": "post",
              "a": "a", "b": "b"}


def canonical_version(v):
    """PEP 440 canonical form of an INSTALLED version string (spec
    "Client matching" step 2) — bulletin entries arrive already canonical."""
    v = str(v).strip().lower()
    v = v.split("+", 1)[0]          # strip local segment
    if v.startswith("v"):
        v = v[1:]
    v = re.sub(r"[-_]", ".", v)
    v = _SPELLING.sub(lambda m: _SPELL_MAP[m.group(1)] + m.group(2), v)
    return re.sub(r"(?<!\d)0+(?=\d)", "", v)   # 1.01.007 -> 1.1.7


def index(bulletin):
    """name -> entries, PyPI only. Skips malformed entries — hostile
    garbage in the cache must degrade to a miss, never a crash."""
    out = {}
    entries = bulletin.get("entries") if isinstance(bulletin, dict) else None
    if not isinstance(entries, list):
        return out
    for e in entries:
        if not isinstance(e, dict) or e.get("ecosystem") != "PyPI":
            continue
        if not all(isinstance(e.get(k), str) for k in ("id", "name", "class")):
            continue
        if not e.get("all_versions") and not isinstance(e.get("versions"), list):
            continue
        # Optional fields are hostile too: wrong types degrade to absent, so
        # one poisoned entry can never crash the audit downstream.
        if not (isinstance(e.get("aliases"), list)
                and all(isinstance(a, str) for a in e["aliases"])):
            e["aliases"] = []
        for k in ("kev", "severity"):
            if k in e and not isinstance(e[k], dict):
                del e[k]
        for k in ("summary", "url"):
            if k in e and not isinstance(e[k], str):
                del e[k]
        out.setdefault(normalize_name(e["name"]), []).append(e)
    return out


def match(entries, installed_version):
    """Entries hitting installed_version: all_versions, or set membership
    of the canonicalized string in versions[]. Zero version-order logic."""
    cv = canonical_version(installed_version)
    return [e for e in entries
            if e.get("all_versions")
            or (isinstance(e.get("versions"), list) and cv in e["versions"])]
