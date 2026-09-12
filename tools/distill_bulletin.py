#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["packaging"]
# ///
"""Interim bulletin distiller (T506) — out-of-package tooling, never shipped.

Stands in for the bulletin provider (out of scope, docs/bulletin-spec.md)
until one exists. Pulls the three upstream feeds with curl subprocesses,
distills them into one spec-conformant full-PyPI bulletin, and writes the
gzipped file + .sha256 sidecar into the local cache under ~/.llmsnitch/.

Unlike the llmsnitch package this script may use the network and deps
(`packaging` for PEP 440 ordering while enumerating ranges — the one thing
the client is forbidden to do, the provider must).

Run:  uv run tools/distill_bulletin.py            # weekly manual refresh
      uv run tools/distill_bulletin.py --fresh    # force re-download
Feeds land in a reusable workdir (default: <tmp>/llmsnitch-bulletin-work).
"""

import argparse
import datetime
import gzip
import hashlib
import json
import os
import re
import subprocess
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor

from packaging.version import InvalidVersion, Version

OSV_URL = "https://storage.googleapis.com/osv-vulnerabilities/PyPI/all.zip"
KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
EPSS_URL = "https://epss.empiricalsecurity.com/epss_scores-current.csv.gz"
PYPI_JSON = "https://pypi.org/pypi/{name}/json"

DEFAULT_OUT = os.path.expanduser("~/.llmsnitch/bulletins")
SIZE_BUDGET = 10 * 1024 * 1024  # spec's soft guidance, gzipped


# ---------------------------------------------------------------- fetch

def curl(url, dest):
    """Download url to dest, preserving the server's Last-Modified mtime."""
    subprocess.run(
        ["curl", "-fsSL", "--retry", "3", "-R", "-o", dest, url], check=True
    )


def fetch_feeds(workdir, fresh):
    os.makedirs(workdir, exist_ok=True)
    feeds = {
        "osv": (OSV_URL, os.path.join(workdir, "pypi-all.zip")),
        "kev": (KEV_URL, os.path.join(workdir, "kev.json")),
        "epss": (EPSS_URL, os.path.join(workdir, "epss.csv.gz")),
    }
    paths = {}
    for key, (url, dest) in feeds.items():
        if fresh or not os.path.exists(dest):
            print(f"fetching {url}")
            curl(url, dest)
        paths[key] = dest
    return paths


def fetch_pypi_releases(name):
    """Release version strings for one package, or None (deleted/404)."""
    p = subprocess.run(
        ["curl", "-fsSL", "--retry", "2", "--max-time", "30",
         PYPI_JSON.format(name=name)],
        capture_output=True,
    )
    if p.returncode:
        return None
    try:
        return list(json.loads(p.stdout).get("releases", {}))
    except (json.JSONDecodeError, AttributeError):
        return None


# ------------------------------------------------------------- normalize

def pep503(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def canon_version(v):
    try:
        return str(Version(v))
    except InvalidVersion:
        return v.lower().lstrip("v")


def parse_version(v):
    try:
        return Version(v)
    except InvalidVersion:
        return None


def version_sort_key(v):
    parsed = parse_version(v)
    return (0, parsed, "") if parsed is not None else (1, Version("0"), v)


# ---------------------------------------------------------------- CVSS 3

_C3 = {
    "AV": {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2},
    "AC": {"L": 0.77, "H": 0.44},
    "PR": {"N": 0.85, "L": 0.62, "H": 0.27},
    "PR_C": {"N": 0.85, "L": 0.68, "H": 0.5},
    "UI": {"N": 0.85, "R": 0.62},
    "CIA": {"H": 0.56, "L": 0.22, "N": 0.0},
}


def _roundup(x):  # CVSS 3.1 spec Appendix A "Roundup"
    i = int(round(x * 100000))
    return i / 100000.0 if i % 10000 == 0 else (i // 10000 + 1) / 10.0


def cvss3_score(vector):
    """Base score from a CVSS:3.x vector, or None if not scoreable."""
    try:
        parts = dict(p.split(":", 1) for p in vector.split("/")[1:])
        changed = parts["S"] == "C"
        iss = 1 - (
            (1 - _C3["CIA"][parts["C"]])
            * (1 - _C3["CIA"][parts["I"]])
            * (1 - _C3["CIA"][parts["A"]])
        )
        impact = (
            7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15
            if changed else 6.42 * iss
        )
        pr = (_C3["PR_C"] if changed else _C3["PR"])[parts["PR"]]
        expl = (
            8.22 * _C3["AV"][parts["AV"]] * _C3["AC"][parts["AC"]]
            * pr * _C3["UI"][parts["UI"]]
        )
        if impact <= 0:
            return 0.0
        return _roundup(min(1.08 * (impact + expl), 10.0) if changed
                        else min(impact + expl, 10.0))
    except (KeyError, ValueError):
        return None


def score_to_label(score):
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "moderate"
    if score > 0.0:
        return "low"
    return None


_LABEL_MAP = {"LOW": "low", "MODERATE": "moderate", "MEDIUM": "moderate",
              "HIGH": "high", "CRITICAL": "critical"}


# ----------------------------------------------------------- OSV parsing

def load_osv(zip_path, stats):
    records = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if not info.filename.endswith(".json"):
                continue
            rec = json.loads(zf.read(info))
            stats["osv_records"] += 1
            if rec.get("withdrawn"):
                stats["withdrawn_dropped"] += 1
                continue
            records.append(rec)
    return records


class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        self.parent[self.find(a)] = self.find(b)


def group_records(records):
    """Collapse alias groups: {root -> [records]}."""
    uf = UnionFind()
    for rec in records:
        uf.find(rec["id"])
        for alias in rec.get("aliases", []):
            uf.union(rec["id"], alias)
    groups = {}
    for rec in records:
        groups.setdefault(uf.find(rec["id"]), []).append(rec)
    return groups


def ranges_to_spans(events):
    """OSV event list -> [(introduced, closer, closer_kind)] spans."""
    spans = []
    intro = None
    for ev in events:
        if "introduced" in ev:
            if intro is not None:
                spans.append((intro, None, None))
            intro = ev["introduced"]
        for kind in ("fixed", "last_affected", "limit"):
            if kind in ev:
                spans.append((intro if intro is not None else "0", ev[kind], kind))
                intro = None
    if intro is not None:
        spans.append((intro, None, None))
    return spans


def span_matches(spans, ver):
    for intro, closer, kind in spans:
        if intro != "0":
            intro_v = parse_version(intro)
            if intro_v is None or ver < intro_v:
                continue
        if closer is None:
            return True
        closer_v = parse_version(closer)
        if closer_v is None:
            continue
        if kind == "last_affected":
            if ver <= closer_v:
                return True
        elif ver < closer_v:
            return True
    return False


# ---------------------------------------------------------- distillation

def collect_packages(group, stats):
    """Per-package affected data across all records in one alias group.

    Returns {pep503_name: {"versions": set, "all_versions": bool,
                           "pending_spans": [spans], "fixed_in": set}}
    """
    pkgs = {}
    for rec in group:
        for block in rec.get("affected", []):
            pkg = block.get("package", {})
            if pkg.get("ecosystem") != "PyPI":
                continue
            name = pep503(pkg.get("name", ""))
            if not name:
                continue
            d = pkgs.setdefault(name, {"versions": set(), "all_versions": False,
                                       "pending_spans": [], "fixed_in": set()})
            eco_ranges = [r for r in block.get("ranges", [])
                          if r.get("type") in ("ECOSYSTEM", "SEMVER")]
            for r in eco_ranges:
                for ev in r.get("events", []):
                    if "fixed" in ev:
                        d["fixed_in"].add(canon_version(ev["fixed"]))
            if block.get("versions"):
                d["versions"].update(canon_version(v) for v in block["versions"])
                continue
            if not eco_ranges:
                # GIT-only or rangeless block: MAL rangeless means "the
                # package itself", everything else is unenumerable.
                if rec["id"].startswith("MAL-"):
                    d["all_versions"] = True
                else:
                    stats["blocks_unenumerable"] += 1
                continue
            for r in eco_ranges:
                spans = ranges_to_spans(r.get("events", []))
                if any(intro == "0" and closer is None for intro, closer, _ in spans):
                    d["all_versions"] = True
                else:
                    d["pending_spans"].append(spans)
    return pkgs


def enumerate_pending(groups_pkgs, stats):
    """Resolve pending_spans against the live PyPI index (provider duty:
    the client never does range math, so the distiller must)."""
    need = sorted({name for pkgs in groups_pkgs for name, d in pkgs.items()
                   if d["pending_spans"] and not d["all_versions"]})
    print(f"enumerating {len(need)} packages against the PyPI index")
    releases = {}
    with ThreadPoolExecutor(max_workers=12) as pool:
        for name, rels in zip(need, pool.map(fetch_pypi_releases, need)):
            releases[name] = rels
    for pkgs in groups_pkgs:
        for name, d in pkgs.items():
            if not d["pending_spans"] or d["all_versions"]:
                continue
            rels = releases.get(name)
            if rels is None:
                # package gone from the index: an open-ended span means
                # "every version that ever existed", a closed one is lost
                if any(closer is None for spans in d["pending_spans"]
                       for _, closer, _ in spans):
                    d["all_versions"] = True
                else:
                    stats["blocks_index_missing"] += 1
                continue
            stats["pkgs_enumerated"] += 1
            for rel in rels:
                ver = parse_version(rel)
                if ver is None:
                    continue
                if any(span_matches(spans, ver) for spans in d["pending_spans"]):
                    d["versions"].add(str(ver))


def build_severity(group):
    vectors = sorted({s["score"] for rec in group for s in rec.get("severity", [])
                      if s.get("score")})
    label = source = None
    for rec in sorted(group, key=lambda r: r["id"]):
        raw = (rec.get("database_specific") or {}).get("severity")
        if isinstance(raw, str) and raw.upper() in _LABEL_MAP:
            label = _LABEL_MAP[raw.upper()]
            source = rec["id"].split("-")[0]
            break
    if label is None:
        best = None
        for rec in sorted(group, key=lambda r: r["id"]):
            for s in rec.get("severity", []):
                if s.get("score", "").startswith("CVSS:3"):
                    sc = cvss3_score(s["score"])
                    if sc is not None and (best is None or sc > best[0]):
                        best = (sc, rec["id"].split("-")[0])
        if best:
            label = score_to_label(best[0])
            source = best[1]
    if label is None:
        return None  # vectors without a scoreable label: severity omitted
    return {"label": label, "vectors": vectors, "source": source}


def build_summary(group):
    for rec in sorted(group, key=lambda r: r["id"]):
        if rec.get("summary"):
            return rec["summary"]
    for rec in sorted(group, key=lambda r: r["id"]):
        details = rec.get("details", "").strip()
        if details:
            line = details.splitlines()[0].strip()
            return line[:200]
    return None


def build_entries(groups, kev_map, epss_map, stats):
    groups_list = list(groups.values())
    groups_pkgs = [collect_packages(g, stats) for g in groups_list]
    enumerate_pending(groups_pkgs, stats)

    entries = []
    for group, pkgs in zip(groups_list, groups_pkgs):
        record_ids = sorted(rec["id"] for rec in group)
        all_ids = sorted(set(record_ids) | {a for rec in group
                                            for a in rec.get("aliases", [])})
        cves = sorted(i for i in all_ids if i.startswith("CVE-"))
        canon_id = cves[0] if cves else record_ids[0]
        aliases = [i for i in all_ids if i != canon_id]
        is_mal = any(i.startswith("MAL-") for i in record_ids)

        severity = build_severity(group)
        summary = build_summary(group)
        url = "https://osv.dev/vulnerability/" + record_ids[0]

        kev = None
        for cve in cves:
            row = kev_map.get(cve)
            if row:
                kev = {
                    "listed": True,
                    "date_added": min(row["dateAdded"],
                                      kev["date_added"] if kev else row["dateAdded"]),
                    "ransomware": (kev["ransomware"] if kev else False)
                    or row.get("knownRansomwareCampaignUse") == "Known",
                }
        epss = None
        for cve in cves:
            row = epss_map.get(cve)
            if row and (epss is None or row[0] > epss["score"]):
                epss = {"score": row[0], "percentile": row[1], "date": epss_map["_date"]}

        for name, d in sorted(pkgs.items()):
            if not d["all_versions"] and not d["versions"]:
                stats["entries_dropped_empty"] += 1
                continue
            entry = {
                "id": canon_id,
                "aliases": aliases,
                "ecosystem": "PyPI",
                "name": name,
                "class": "malicious" if is_mal else "vulnerability",
            }
            if d["all_versions"]:
                entry["all_versions"] = True
            else:
                entry["versions"] = sorted(d["versions"], key=version_sort_key)
            if severity:
                entry["severity"] = severity
            if kev:
                entry["kev"] = kev
                stats["entries_kev"] += 1
            if epss:
                entry["epss"] = epss
                stats["entries_epss"] += 1
            if d["fixed_in"]:
                entry["fixed_in"] = sorted(d["fixed_in"], key=version_sort_key)
            if summary:
                entry["summary"] = summary
            entry["url"] = url
            if entry["class"] == "malicious":
                stats["entries_malicious"] += 1
            entries.append(entry)

    entries.sort(key=lambda e: (e["name"], e["id"]))
    return entries


# ---------------------------------------------------------------- inputs

def load_kev(path):
    with open(path, encoding="utf-8") as f:
        cat = json.load(f)
    return ({row["cveID"]: row for row in cat.get("vulnerabilities", [])},
            cat.get("catalogVersion", ""))


def load_epss(path):
    scores = {}
    date = ""
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#"):
                m = re.search(r"score_date:([^,\s]+)", line)
                if m:
                    date = m.group(1)
                continue
            if line.startswith("cve,") or not line:
                continue
            cve, epss, pct = line.split(",")
            scores[cve] = (float(epss), float(pct))
    scores["_date"] = date[:10]  # per-entry epss.date is date-only (spec example)
    return scores, date


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workdir",
                    default=os.path.join(tempfile.gettempdir(),
                                         "llmsnitch-bulletin-work"),
                    help="feed download dir, reused across runs")
    ap.add_argument("--out", default=DEFAULT_OUT,
                    help="bulletin cache dir (default: %(default)s)")
    ap.add_argument("--fresh", action="store_true",
                    help="re-download feeds even if cached in workdir")
    args = ap.parse_args()

    stats = {k: 0 for k in (
        "osv_records", "withdrawn_dropped", "blocks_unenumerable",
        "blocks_index_missing", "pkgs_enumerated", "entries_dropped_empty",
        "entries_malicious", "entries_kev", "entries_epss")}

    paths = fetch_feeds(args.workdir, args.fresh)
    osv_date = datetime.datetime.fromtimestamp(
        os.path.getmtime(paths["osv"]),
        datetime.timezone.utc).strftime("%Y-%m-%d")

    records = load_osv(paths["osv"], stats)
    groups = group_records(records)
    kev_map, kev_version = load_kev(paths["kev"])
    epss_map, epss_date = load_epss(paths["epss"])

    entries = build_entries(groups, kev_map, epss_map, stats)

    bulletin = {
        "meta": {
            "schema_version": 1,
            "issued_at": datetime.datetime.now(datetime.timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sources": {"osv": osv_date, "kev": kev_version, "epss": epss_date},
        },
        "entries": entries,
    }

    raw = json.dumps(bulletin, separators=(",", ":")).encode("utf-8")
    gz = gzip.compress(raw, mtime=0)
    if len(gz) > SIZE_BUDGET:
        # soft-budget fallback, display-only fields first (spec guidance)
        for field in ("summary", "severity", "fixed_in", "url"):
            for e in entries:
                e.pop(field, None)
            raw = json.dumps(bulletin, separators=(",", ":")).encode("utf-8")
            gz = gzip.compress(raw, mtime=0)
            print(f"over 10MB budget: dropped {field} -> {len(gz)} bytes gzipped")
            if len(gz) <= SIZE_BUDGET:
                break

    os.makedirs(args.out, exist_ok=True)
    os.chmod(args.out, 0o700)
    bulletin_path = os.path.join(args.out, "pypi.json.gz")
    sidecar_path = bulletin_path + ".sha256"
    digest = hashlib.sha256(gz).hexdigest()
    with open(bulletin_path, "wb") as f:
        f.write(gz)
    with open(sidecar_path, "w", encoding="utf-8") as f:
        f.write(digest + "\n")
    os.chmod(bulletin_path, 0o600)
    os.chmod(sidecar_path, 0o600)

    print(f"\nwrote {bulletin_path}")
    print(f"  raw {len(raw):,} bytes, gzipped {len(gz):,} bytes "
          f"(budget {SIZE_BUDGET:,})")
    print(f"  sha256 {digest}")
    print(f"  entries {len(entries):,} "
          f"(malicious {stats['entries_malicious']:,}, "
          f"kev {stats['entries_kev']:,}, epss {stats['entries_epss']:,})")
    print("  stats:", {k: v for k, v in stats.items() if v})


if __name__ == "__main__":
    main()
