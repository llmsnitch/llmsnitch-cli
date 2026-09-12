# Bulletin contract v1

`schema_version: 1` — accepted 2026-09-11
(ticket `wayfinder/dep-audit/tickets/T503-bulletin-schema.md`)

The contract between the bulletin **provider** (out of scope for this repo —
`wayfinder/dep-audit/map.md`) and the llmsnitch CLI **consumer**. Vocabulary
(Bulletin, Intake, Waiver) is canon in `CONTEXT.md`. Grounding:
`docs/research/dep-audit-advisory-sources.md` (T501),
`docs/research/dep-audit-stdlib-matching.md` (T502),
`docs/adr/0001-bulletin-egress.md` (egress model).

## Artifact

A bulletin is **one JSON object**, served as a gzipped file over HTTPS, with
a sidecar hash file at `<bulletin-url>.sha256` holding the lowercase hex
SHA-256 of the raw served bytes (the gzipped file exactly as fetched).

- A bulletin file MAY carry entries from any mix of ecosystems; the client
  filters to ecosystems it knows. The MVP deployment is one PyPI-only file.
  URL layout is client fetch-config, not part of this contract.
- The provider SHOULD keep each file ≤ 10 MB gzipped per ecosystem
  (guidance; the client never enforces a size limit).
- Bulletins are always **full-ecosystem** distillations. Package-scoped
  (per-client-filtered) bulletins are outside this contract: the machine's
  intake list never leaves the machine.
- An empty `entries` array is a valid bulletin.

## Shape

```json
{
  "meta": {
    "schema_version": 1,
    "issued_at": "2026-09-11T06:00:00Z",
    "sources": {
      "osv": "2026-09-11",
      "kev": "2026.09.11",
      "epss": "2026-09-11T12:00:21Z"
    }
  },
  "entries": []
}
```

### meta

| field | type | required | meaning |
| --- | --- | --- | --- |
| `schema_version` | integer | yes | contract version of this file; this document is version `1` |
| `issued_at` | string | yes | ISO 8601 UTC build time of the distillation; the client stamps payload age from this field alone |
| `sources` | object | no | provenance stamps of the upstream snapshots (`osv` export date, `kev` catalog version, `epss` score date) — informational only, never gated on |

### entries[]

One entry per **(advisory-group × package)**: the provider collapses upstream
records that alias each other (e.g. a GHSA and its PYSEC twin) into a single
entry per affected package.

| field | type | required | meaning |
| --- | --- | --- | --- |
| `id` | string | yes | canonical advisory id: the CVE id when any group member has one, else the lexicographically-first source id (`MAL-*`, `GHSA-*`, `PYSEC-*`, …). Chosen for stability across weekly rebuilds — waiver keys depend on it |
| `aliases` | array of string | yes (may be empty) | every other known id for the group. Waiver matching uses `{id} ∪ aliases` (see Waiver joins) |
| `ecosystem` | string | yes | OSV ecosystem name: `PyPI` now; `npm`, `NuGet`, `Maven` later with no schema change. The client skips entries with ecosystems it doesn't handle |
| `name` | string | yes | package name, already PEP 503-normalized by the provider |
| `class` | string | yes | `vulnerability` \| `malicious`. MAL-derived entries (`malicious`) carry no severity, no fix, usually `all_versions: true` |
| `versions` | array of string | yes unless `all_versions` is true | affected versions, pre-enumerated by the provider, PEP 440 canonical form. The client does set membership only — never range math |
| `all_versions` | boolean | no (default `false`) | every version is affected (the introduced-0-no-fix shape). When `true`, `versions` MAY be absent |
| `severity` | object | no | `{label, vectors, source}` — `label` ∈ `low` \| `moderate` \| `high` \| `critical`; `vectors` an array of CVSS vector strings; `source` the assessing database. Display metadata only: severity never gates a page |
| `kev` | object | no | `{listed: bool, date_added: "YYYY-MM-DD", ransomware: bool}` from the CISA KEV catalog, joined via CVE alias. Absent means not listed. `kev.listed` is the field that satisfies the criticality gate's "actively exploited" clause |
| `epss` | object | no | `{score, percentile, date}` — a 30-day exploitation *forecast*, carried as digest context. EPSS is never evidence: it satisfies no gate and triggers no waiver re-raise |
| `fixed_in` | array of string | no | upgrade targets for display ("upgrade to ≥ X"). Display-only: the client never compares against it |
| `summary` | string | no | one-line human description, for digest/TUI rendering |
| `url` | string | no | canonical advisory link (e.g. `https://osv.dev/vulnerability/<id>`) |

Unknown fields at any level are ignored (tolerant reader).

## Client matching

The whole matcher, per T502 — zero version-comparison code:

1. Normalize the intake's package name: `re.sub(r"[-_.]+", "-", name).lower()`
   (PEP 503).
2. Canonicalize the installed version string (PEP 440 canonical form:
   lowercase, `-`/`_` → `.`, spelling map `alpha`→`a` `beta`→`b`
   `c|pre|preview`→`rc` `rev|r`→`post`, strip leading zeros in numeric parts,
   strip a leading `v`) and strip any `+local` suffix.
3. An entry matches an intake iff `ecosystem` matches, names are equal, and
   (`all_versions` is true, or the canonicalized version is a member of
   `versions`).

Known blind spot (documented, accepted): non-PyPI installs (VCS/editable/dev
builds) never appear in an enumeration; entries with a fix-less
`introduced > 0` shape ship their build-date enumeration, so a version
released after the build matches only after the next weekly rebuild (gap
≤ refresh interval).

## Fetch, verify, cache

1. Fetch the bulletin file and its `.sha256` sidecar (curl subprocess,
   ADR 0001).
2. Compare the SHA-256 of the raw fetched bytes to the sidecar. On mismatch:
   discard the download, keep the last good cache, record an operational
   condition. The sidecar provides **integrity** (truncation, corruption);
   authenticity rides on TLS. Signing is a v2 candidate — no field reserved.
3. Decompress, parse, check `meta.schema_version` against the client's
   supported set (a v1 client supports `{1}`). Unknown version: same fallback
   as a hash mismatch.
4. Atomically move the verified file into the cache under `~/.llmsnitch/`,
   recording the verified hash.
5. At scan time: re-verify the stored file against the recorded hash, run
   fully offline, stamp payload age from `meta.issued_at`. A missing or stale
   bulletin is an operational condition, never a crash.

## Contract versioning

- `meta.schema_version` is a bare integer; a client declares an explicit
  support set.
- Additive changes (new optional fields) do not bump the version — tolerant
  reading absorbs them. Breaking changes (field removed, retyped, or
  re-meant) bump it.
- The provider MAY publish consecutive versions at different URLs during a
  migration window.

## Waiver joins

- A waiver is keyed **(advisory id × PEP 503 package name)**.
- A waiver matches an entry when its advisory id is in
  `{entry.id} ∪ entry.aliases` and the names are equal — waivers written
  against any alias survive canonical-id changes across rebuilds. `aliases`
  MUST carry every known id for the group precisely to make this hold.
- A waived finding **re-raises** on exactly two field transitions, compared
  bulletin-to-bulletin: `severity.label` escalates to a higher band, or
  `kev.listed` flips false→true. EPSS movement never re-raises.

## Provider obligations (distillation rules)

- Collapse alias groups to one entry per (group × package); pick `id` by the
  CVE-first rule above.
- Drop withdrawn advisories entirely — the client recomputes findings from
  scratch each scan, so retracted entries simply vanish.
- Pre-enumerate affected versions (OSV's `affected[].versions` where
  populated — 77% of blocks — else the same enumeration against the package
  index); emit `all_versions: true` for the introduced-0-no-fix shape.
- Emit PEP 503-normalized names and PEP 440-canonical version strings.
- Join KEV and EPSS via CVE aliases.
- Publish the sidecar `.sha256` beside every bulletin file.

## Out of contract (v1)

Version ranges (the client never evaluates them), machine-checkable abuse
indicators (fog — no source ships them, T501), an `open_ended` marker (the
client can't order versions, so it could only manufacture unverifiable
findings), a `withdrawn` marker, an entry count (the hash already proves the
file is whole), signing/authenticity (v2 candidate), and package-scoped
bulletins (privacy).

## Example entries

```json
{
  "id": "CVE-2019-10906",
  "aliases": ["GHSA-462w-v97r-4m45", "PYSEC-2019-217"],
  "ecosystem": "PyPI",
  "name": "jinja2",
  "class": "vulnerability",
  "versions": ["2.10", "2.10.1"],
  "severity": {
    "label": "high",
    "vectors": ["CVSS:3.0/AV:L/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H"],
    "source": "GHSA"
  },
  "epss": {"score": 0.00284, "percentile": 0.69, "date": "2026-09-11"},
  "fixed_in": ["2.10.1"],
  "summary": "Sandbox escape via str.format_map in Jinja2 before 2.10.1",
  "url": "https://osv.dev/vulnerability/GHSA-462w-v97r-4m45"
}
```

```json
{
  "id": "MAL-2022-7421",
  "aliases": [],
  "ecosystem": "PyPI",
  "name": "ascii2text",
  "class": "malicious",
  "all_versions": true,
  "summary": "Malicious code in ascii2text (typosquat, CWE-506)",
  "url": "https://osv.dev/vulnerability/MAL-2022-7421"
}
```
