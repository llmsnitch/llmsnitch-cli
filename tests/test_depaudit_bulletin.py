#!/usr/bin/env python3
"""Bulletin cache reader guards (docs/bulletin-spec.md). Stdlib only,
no network. The cache file is hostile input: load()/index() must never
raise, whatever is on disk.

Run: python3 tests/test_depaudit_bulletin.py
"""

import gzip
import hashlib
import io
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from llmsnitch import bulletin  # noqa: E402


def _with_tmp_store(fn):
    with tempfile.TemporaryDirectory() as t:
        old = os.environ.get("LLMSNITCH_DIR")
        os.environ["LLMSNITCH_DIR"] = t
        try:
            fn(Path(t))
        finally:
            os.environ.pop("LLMSNITCH_BULLETIN_URL", None)
            if old is None:
                os.environ.pop("LLMSNITCH_DIR", None)
            else:
                os.environ["LLMSNITCH_DIR"] = old


def _doc(entries=None, schema=1, issued="2026-09-11T06:00:00Z"):
    return {"meta": {"schema_version": schema, "issued_at": issued},
            "entries": entries if entries is not None else []}


def _write(t, obj=None, raw=None, sidecar=True, sidecar_text=None):
    """Drop a bulletin (+ sidecar) at the default cache path under t."""
    d = t / "bulletins"
    d.mkdir(parents=True, exist_ok=True)
    if raw is None:
        raw = gzip.compress(json.dumps(obj).encode())
    (d / "pypi.json.gz").write_bytes(raw)
    if sidecar:
        if sidecar_text is None:
            sidecar_text = hashlib.sha256(raw).hexdigest()
        (d / "pypi.json.gz.sha256").write_text(sidecar_text)
    return raw


def _remote(t, obj, sidecar_text=None, name="pypi.json.gz"):
    """A provider stand-in: bulletin + sidecar under t/remote, and point
    LLMSNITCH_BULLETIN_URL (the seam) at it as a file:// URL."""
    d = t / "remote"
    d.mkdir(exist_ok=True)
    raw = gzip.compress(json.dumps(obj).encode())
    (d / name).write_bytes(raw)
    (d / (name + ".sha256")).write_text(
        sidecar_text if sidecar_text is not None
        else hashlib.sha256(raw).hexdigest() + "\n")
    os.environ["LLMSNITCH_BULLETIN_URL"] = f"file://{d / name}"
    return raw


def _no_temps(t):
    return not list((t / "bulletins").glob("*.tmp*"))


_GOOD = {"id": "CVE-2019-10906", "aliases": ["GHSA-462w-v97r-4m45"],
         "ecosystem": "PyPI", "name": "jinja2", "class": "vulnerability",
         "versions": ["2.10", "2.10.1"]}
_MAL = {"id": "MAL-2022-7421", "aliases": [], "ecosystem": "PyPI",
        "name": "ascii2text", "class": "malicious", "all_versions": True}


def test_load_happy_path_default_resolution():
    def body(t):
        _write(t, _doc([_GOOD]))
        # lazy: default_path() follows LLMSNITCH_DIR at call time
        assert bulletin.default_path() == t / "bulletins" / "pypi.json.gz"
        b, note = bulletin.load()   # path=None -> default_path()
        assert note is None, note
        assert b["meta"]["schema_version"] == 1
        assert b["entries"][0]["name"] == "jinja2"
    _with_tmp_store(body)


def test_load_sidecar_trailing_newline_accepted():
    def body(t):
        raw = _write(t, _doc(), sidecar=False)
        (t / "bulletins" / "pypi.json.gz.sha256").write_text(
            hashlib.sha256(raw).hexdigest() + "\n")
        b, note = bulletin.load()
        assert note is None and b["entries"] == []
    _with_tmp_store(body)


def test_load_hash_mismatch():
    def body(t):
        _write(t, _doc(), sidecar_text="0" * 64)
        b, note = bulletin.load()
        assert b is None and note == "hash mismatch"
    _with_tmp_store(body)


def test_load_missing_bulletin():
    def body(t):
        b, note = bulletin.load()
        assert b is None and note == "bulletin missing"
    _with_tmp_store(body)


def test_load_missing_or_empty_sidecar():
    def body(t):
        _write(t, _doc(), sidecar=False)
        b, note = bulletin.load()
        assert b is None and note == "sidecar missing"
        _write(t, _doc(), sidecar_text="  \n")   # whitespace-only sidecar
        b, note = bulletin.load()
        assert b is None and note
    _with_tmp_store(body)


def test_load_truncated_gz():
    def body(t):
        whole = gzip.compress(json.dumps(_doc()).encode())
        _write(t, raw=whole[:len(whole) // 2])   # sidecar matches the stump
        b, note = bulletin.load()
        assert b is None and note == "unreadable bulletin"
    _with_tmp_store(body)


def test_load_gz_of_non_json():
    def body(t):
        _write(t, raw=gzip.compress(b"not json {"))
        b, note = bulletin.load()
        assert b is None and note == "unreadable bulletin"
    _with_tmp_store(body)


def test_load_json_array_not_object():
    def body(t):
        _write(t, obj=[1, 2, 3])
        b, note = bulletin.load()
        assert b is None and note == "unreadable bulletin"
    _with_tmp_store(body)


def test_load_unsupported_schema_version():
    def body(t):
        _write(t, _doc(schema=2))
        b, note = bulletin.load()
        assert b is None and "schema_version" in note and "2" in note
    _with_tmp_store(body)


def test_load_explicit_path():
    def body(t):
        obj = _doc([_MAL])
        raw = gzip.compress(json.dumps(obj).encode())
        p = t / "elsewhere.json.gz"
        p.write_bytes(raw)
        Path(str(p) + ".sha256").write_text(hashlib.sha256(raw).hexdigest())
        b, note = bulletin.load(p)
        assert note is None and b["entries"][0]["id"] == "MAL-2022-7421"
    _with_tmp_store(body)


def test_refresh_happy_path_swaps_cache():
    def body(t):
        _write(t, _doc([_GOOD], issued="2026-01-01T00:00:00Z"))   # old cache
        _remote(t, _doc([_MAL], issued="2026-09-19T14:17:00Z"))
        out = io.StringIO()
        assert bulletin.refresh(out) == 0, out.getvalue()
        assert out.getvalue() == ""
        b, note = bulletin.load()
        assert note is None and b["entries"][0]["id"] == "MAL-2022-7421"
        assert _no_temps(t)
        assert oct(bulletin.default_path().stat().st_mode & 0o777) == "0o600"
    _with_tmp_store(body)


def test_refresh_into_empty_store_creates_dir():
    def body(t):
        _remote(t, _doc([_GOOD]))
        assert bulletin.refresh(io.StringIO()) == 0
        assert bulletin.load()[1] is None
        assert oct((t / "bulletins").stat().st_mode & 0o777) == "0o700"
    _with_tmp_store(body)


def test_refresh_sidecar_mismatch_keeps_old_cache():
    def body(t):
        old = _write(t, _doc([_GOOD]))
        _remote(t, _doc([_MAL]), sidecar_text="0" * 64)
        out = io.StringIO()
        assert bulletin.refresh(out) == 2
        assert "[WARN] bulletin refresh failed: hash mismatch" in out.getvalue()
        assert bulletin.default_path().read_bytes() == old
        assert _no_temps(t)
    _with_tmp_store(body)


def test_refresh_fetch_failure_is_2():
    def body(t):
        old = _write(t, _doc([_GOOD]))
        os.environ["LLMSNITCH_BULLETIN_URL"] = f"file://{t}/nope.gz"
        out = io.StringIO()
        assert bulletin.refresh(out) == 2
        assert "[WARN] bulletin refresh failed: fetch failed" in out.getvalue()
        assert bulletin.default_path().read_bytes() == old
        assert _no_temps(t)
    _with_tmp_store(body)


def test_refresh_rejects_schema_2_before_swap():
    def body(t):
        old = _write(t, _doc([_GOOD]))
        _remote(t, _doc([_MAL], schema=2))
        out = io.StringIO()
        assert bulletin.refresh(out) == 2
        assert "unsupported schema_version 2" in out.getvalue()
        assert bulletin.default_path().read_bytes() == old
        assert _no_temps(t)
    _with_tmp_store(body)


def test_needs_refresh():
    def body(t):
        assert bulletin.needs_refresh()                       # missing
        _write(t, _doc(), sidecar_text="0" * 64)
        assert bulletin.needs_refresh()                       # corrupt
        fresh = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _write(t, _doc(issued=fresh))
        assert not bulletin.needs_refresh()                   # fresh
        old = (datetime.now(timezone.utc) - timedelta(days=8)
               ).strftime("%Y-%m-%dT%H:%M:%SZ")
        _write(t, _doc(issued=old))
        assert bulletin.needs_refresh()                       # 8 days
        _write(t, _doc(issued="garbage"))
        assert bulletin.needs_refresh()                       # unstampable
    _with_tmp_store(body)


def test_age_days_z_suffix_and_naive_utc():
    stamp = "2026-09-01T00:00:00Z"
    a = bulletin.age_days({"issued_at": stamp})
    expected = (datetime.now(timezone.utc)
                - datetime(2026, 9, 1, tzinfo=timezone.utc)
                ).total_seconds() / 86400.0
    assert a is not None and a > 0 and abs(a - expected) < 0.01, a
    naive = bulletin.age_days({"issued_at": "2026-09-01T00:00:00"})
    assert naive is not None and abs(naive - a) < 0.001


def test_age_days_garbage_is_none():
    assert bulletin.age_days({"issued_at": "not-a-date"}) is None
    assert bulletin.age_days({"issued_at": 42}) is None
    assert bulletin.age_days({}) is None
    assert bulletin.age_days("nope") is None
    assert bulletin.age_days(None) is None


def test_normalize_name():
    assert bulletin.normalize_name("Foo.Bar_baz") == "foo-bar-baz"
    assert bulletin.normalize_name("requests") == "requests"
    assert bulletin.normalize_name("A--B__c") == "a-b-c"


def test_canonical_version():
    cases = [("V1.0.0-ALPHA1", "1.0.0a1"),
             ("1.2.3+local.build", "1.2.3"),
             ("1.0-preview2", "1.0rc2"),
             ("1.01.007", "1.1.7"),
             ("2.0rev3", "2.0post3"),
             ("1.0_beta.2", "1.0b2"),
             ("1.0C1", "1.0rc1"),
             ("2.10", "2.10")]
    for raw, want in cases:
        got = bulletin.canonical_version(raw)
        assert got == want, f"{raw!r} -> {got!r}, want {want!r}"


def test_index_filters_and_survives_hostile_entries():
    npm = dict(_GOOD, ecosystem="npm", name="lodash")
    hostile = ["just a string", 42, None, [],
               {"id": "X", "ecosystem": "PyPI", "class": "vulnerability",
                "versions": ["1"]},                       # no name
               {"name": "y", "ecosystem": "PyPI", "class": "vulnerability",
                "versions": ["1"]},                       # no id
               {"id": "Z", "name": "z", "ecosystem": "PyPI",
                "versions": ["1"]},                       # no class
               {"id": "W", "name": "w", "ecosystem": "PyPI",
                "class": "vulnerability", "versions": 42}]  # versions not list
    idx = bulletin.index(_doc([_GOOD, _MAL, npm] + hostile))
    assert set(idx) == {"jinja2", "ascii2text"}, set(idx)
    assert idx["jinja2"] == [_GOOD]
    assert idx["ascii2text"] == [_MAL]   # all_versions needs no versions list


def test_index_garbage_bulletin_is_empty():
    assert bulletin.index({"entries": "nope"}) == {}
    assert bulletin.index({}) == {}
    assert bulletin.index("garbage") == {}
    assert bulletin.index(None) == {}


def test_match_membership_only():
    assert bulletin.match([_GOOD], "2.10") == [_GOOD]
    assert bulletin.match([_GOOD], "V2.10") == [_GOOD]        # canonicalized
    assert bulletin.match([_GOOD], "2.10+cu118") == [_GOOD]   # local stripped
    assert bulletin.match([_GOOD], "2.11") == []
    assert bulletin.match([_GOOD, _MAL], "9.9") == [_MAL]


def test_match_mal_all_versions():
    assert bulletin.match([_MAL], "0.0.1") == [_MAL]
    assert bulletin.match([_MAL], "whatever") == [_MAL]


if __name__ == "__main__":
    from tests._seams import run
    sys.exit(run(globals()))
