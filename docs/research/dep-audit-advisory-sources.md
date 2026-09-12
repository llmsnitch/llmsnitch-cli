# Advisory-source survey: what can a bulletin carry? (T501)

> Convention note: this lives in `docs/research/` beside
> `unicode-evasion-redaction.md` and `scanner-survey-mvp.md`, the established
> home for cited research notes. Every claim cites the primary source that
> owns it. All URLs fetched with `curl` on **2026-09-11**; "measured"
> claims come from that day's live data (OSV `PyPI/all.zip`, the KEV JSON
> feed, the EPSS daily CSV, and a tarball of `pypa/advisory-database@main`).
> Ticket: `wayfinder/dep-audit/tickets/T501-advisory-source-survey.md`.

## TL;DR — what constrains the bulletin schema

1. **Severity is unreliable as a field and absent as a norm.** Only GHSA
   consistently ships CVSS vectors plus a qualitative label; 38% of PYSEC
   records and 100% of malicious-package (`MAL-*`) records carry *no*
   severity at all. The bulletin must treat severity as optional metadata,
   never as the paging signal — which matches the map's evidence-centric
   doctrine.
2. **"Actively exploited" must be two separate fields.** KEV membership is
   a curated, evidence-backed boolean (CC0-licensed, trivially bulk-fetched);
   EPSS is a *forecast probability*, explicitly not evidence — by design it
   does not even move when exploitation is observed. Never merge them into
   one flag.
3. **Exact-version lists are workable but need an open-endedness marker.**
   73% of PyPI OSV records already ship enumerated version lists; the rest
   are ranges the distiller must enumerate against the PyPI index (PEP 440).
   ~8k records (nearly all `MAL-*`) have no `fixed` event — "all versions,
   forever" — where a frozen list silently misses versions published after
   the bulletin build. Carry `versions: [...]` **plus** an
   `open_ended: true|false` (or `introduced`-floor) marker.
4. **Machine-checkable abuse indicators: fog confirmed.** No source ships
   file hashes, paths, or behavioral IOCs. The one structured
   "affected code element" mechanism for Python
   (PyPA `ecosystem_specific.imports`) has **zero adoption** across all
   7,518 records in the live repo. "Exercised on this machine" evidence
   must come from local ledgers/fs-coil (T505), not bulletins.
5. **Malicious-package advisories are a distinct class, and they dominate.**
   46% of the PyPI OSV corpus (11,737 of 25,570) are `MAL-*` records — for
   an *agent-installed* population (typosquats!) these are the most
   page-worthy records and they have no severity, no fix, no CVE. The
   bulletin needs a `class: vulnerability | malicious` discriminator.
6. **One pipeline covers all target ecosystems.** OSV serves PyPI, npm,
   NuGet, Maven (and ~40 more) under one schema with per-ecosystem
   `all.zip` bulk files over plain HTTPS, no auth, no rate limit. The KEV
   and EPSS joins are CVE-alias-based and ecosystem-agnostic. Weekly
   `curl` refresh is comfortably feasible: `PyPI/all.zip` is 34 MB, KEV
   JSON 1.7 MB, EPSS CSV one gzip file.

---

## Source profiles

### OSV (schema + osv.dev distribution)

**Schema** (https://ossf.github.io/osv-schema/ — fetched from
https://raw.githubusercontent.com/ossf/osv-schema/main/docs/schema.md):

- `severity[]` is an array of `{type, score, source}`; `type` is one of
  `CVSS_V2`, `CVSS_V3`, `CVSS_V4`, `Ubuntu`; `score` is a **vector string**,
  not a number; optional `source` attributes the assessment to `NVD`, `CNA`,
  or `SELF` — the source field exists precisely because assessments of the
  same vulnerability differ by assessor
  (https://ossf.github.io/osv-schema/#severityscore-field).
- `affected[].ranges[]` has `type` `SEMVER` | `ECOSYSTEM` | `GIT` with
  `events` of `introduced` / `fixed` / `last_affected` / `limit`;
  `introduced: "0"` sorts before everything; `last_affected` is a
  publication-time ceiling that "opens up the possibility for false
  negatives" (https://ossf.github.io/osv-schema/#affectedrangesevents-fields).
- For `ECOSYSTEM` ranges the schema *recommends* an explicitly enumerated
  `affected[].versions` list, and notes that osv.dev "provides automation
  for auto-populating the `versions` list based on supported ECOSYSTEM
  ranges" (https://ossf.github.io/osv-schema/#affectedranges-field).
- Defined ecosystems include `PyPI`, `npm`, `NuGet`, `Maven`, `crates.io`,
  `Packagist`, `Pub`, `RubyGems`, `Go`, `Hex`, plus Linux distros
  (https://ossf.github.io/osv-schema/#defined-ecosystems).

**Bulk distribution** (https://google.github.io/osv.dev/data/):

- Continuously exported GCS bucket `gs://osv-vulnerabilities`, HTTP-reachable
  at `https://storage.googleapis.com/osv-vulnerabilities/…` — per-ecosystem
  `<ECOSYSTEM>/all.zip`, per-record JSON, `ecosystems.txt`, and
  `modified_id.csv` (global and per-ecosystem) for incremental sync.
- Measured 2026-09-11: `PyPI/all.zip` = 34,271,055 bytes (Last-Modified
  that same day); whole-DB `all.zip` = 2.42 GB — per-ecosystem zips are the
  right fetch unit.
- API (https://google.github.io/osv.dev/api/): `POST /v1/query`,
  `/v1/querybatch`; FAQ states "Currently there are no limits on the API"
  (response size 32 MiB on HTTP/1.1).

**Measured PyPI corpus** (from `PyPI/all.zip`, 2026-09-11 — 25,570 records):

| id prefix | records | with any `severity` | notes |
| --- | --- | --- | --- |
| `GHSA-*` | 6,225 | 5,925 (95%) | CVSS vectors + GitHub label in `database_specific.severity` |
| `PYSEC-*` | 7,600 | 4,722 (62%) | severity entirely absent in the rest |
| `MAL-*` | 11,737 | 0 | malicious packages, from github.com/ossf/malicious-packages |
| `OSV-*` | 8 | 0 | OSS-Fuzz-originated |

- Range/event counts: 25,162 `ECOSYSTEM` ranges, 1,583 `GIT`; 30,457
  `introduced`, 22,395 `fixed`, 1,678 `last_affected` events; 568 records
  withdrawn.
- 18,661 records (73%) carry enumerated `versions`; 6,888 have ranges but
  no enumeration (GHSA 229, PYSEC 285, MAL 6,371, OSV 2). Of the
  non-enumerated GHSA/PYSEC records, ~200 each *do* have a `fixed` event —
  i.e. the closed set exists in principle, osv.dev just didn't enumerate it;
  the `MAL` ones are open-ended by nature (`introduced: "0"`, no fix).
- Sample `MAL` record (`MAL-2022-7421`, ascii2text): one `ECOSYSTEM` range
  `{introduced: "0"}`, CWE-506 "Embedded Malicious Code", source pointer to
  github.com/ossf/malicious-packages, no severity, no CVE.

### GHSA (GitHub Advisory Database)

- Bulk form: github.com/github/advisory-database — all advisories as OSV
  JSON files, license **CC-BY 4.0**
  (https://github.com/github/advisory-database#license). Clone/tarball is
  the bulk path; but note GHSA records are *already re-exported inside
  OSV's per-ecosystem zips*, so a distiller pulling OSV bulk doesn't need
  this repo separately.
- Supported ecosystems: Composer, Erlang (hex), GitHub Actions, Go, Maven,
  npm, NuGet, **pip**, Pub, RubyGems, Rust (crates.io), Swift
  (https://github.com/github/advisory-database#supported-ecosystems) —
  covers PyPI now and npm/NuGet/Maven later.
- Severity: CVSS 3.x/4.0 vector plus a qualitative label drawn from the four
  CVSS Section 5 bands — Low, Medium/Moderate, High, Critical
  (https://docs.github.com/en/code-security/security-advisories/working-with-global-security-advisories-from-the-github-advisory-database/about-the-github-advisory-database).
  In the OSV files the label lives in `database_specific.severity`, which
  GitHub explicitly marks as internal-use, subject to change
  (https://github.com/github/advisory-database#database_specific-values).
- GitHub also *redistributes EPSS scores* on advisories with CVEs (same
  docs page) — a precedent for shipping EPSS alongside advisory data.
- REST API `GET /advisories` (verified live): unauthenticated
  `X-RateLimit-Limit: 60`/hour; response carries
  `vulnerable_version_range` strings in comma-comparator syntax
  (observed: `">= 0.8.0, < 0.11.1"` on GHSA-wvm9-9g5j-623f), a
  `first_patched_version`, and a `vulnerable_functions` array (empty in the
  sampled record). Rate limit makes REST unsuitable for bulk; fine since
  bulk goes through OSV zips.
- Ranges not representable in OSV land in
  `database_specific.last_known_affected_version_range`
  (https://github.com/github/advisory-database#database_specific-values) —
  a distiller reading only spec-level OSV fields loses those bounds; the
  enumerated `versions` list (when present) already reflects them.

### PyPA advisory-database (PYSEC)

- github.com/pypa/advisory-database — community-owned YAML-encoded OSV
  records for PyPI, license **CC-BY 4.0** (LICENSE file in repo). Largely
  triaged from the NVD CVE feed
  (https://github.com/pypa/advisory-database#triage-process); consumed by
  pip-audit and re-exported by osv.dev.
- The README specifies an `ecosystem_specific.imports` mechanism — affected
  `modules`/`attribute` lists "to help with reducing false positive
  matches"
  (https://github.com/pypa/advisory-database#marking-specific-attributes-as-vulnerable).
  **Measured adoption: zero.** In the 2026-09-11 tarball of `main`, 0 of
  7,518 `vulns/**/*.yaml` records populate `imports` (601 records have an
  `ecosystem_specific:` key at all, none with `imports`); the OSV-served
  PyPI corpus likewise contains 0 records with it. The spec exists; the
  data does not.
- PYSEC severity, when present, is CVSS vectors in OSV `severity[]`
  (62% measured, table above); there is no PYSEC qualitative label.

### CISA KEV

- What it asserts: a CVE is in the catalog only when (1) it has a CVE ID,
  (2) there is "reliable evidence that the vulnerability has been actively
  exploited in the wild", and (3) there is a clear remediation action.
  Active exploitation includes *attempted* exploitation (honeypot hits
  count) but excludes scanning and mere PoC publication
  (https://www.cisa.gov/known-exploited-vulnerabilities). BOD 26-04
  (issued 2026-06-10) carries the criteria forward from BOD 22-01.
- Formats: JSON, CSV, and a JSON Schema at stable URLs
  (https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json,
  `…_schema.json`); plain HTTPS, no auth, no documented rate limit; the
  JSON was 1.7 MB. Fields per schema: `cveID`, `vendorProject`, `product`,
  `vulnerabilityName`, `dateAdded`, `shortDescription`, `requiredAction`,
  `dueDate`, `knownRansomwareCampaignUse` ("Known"/"Unknown"), `notes`,
  `cwes`. The live feed additionally carries a `forensicTriage` field not
  yet in the published schema (observed on the 2026-09-11 entries) — parse
  tolerantly.
- License: **CC0 1.0** — "You may use this data in any legal manner"
  (https://www.cisa.gov/sites/default/files/licenses/kev/license.txt).
- Cadence: event-driven, not scheduled; each release stamps
  `catalogVersion` (date-formatted) and `dateReleased`. Measured
  2026-09-11: version `2026.09.11`, 1,708 entries, 360 with
  `knownRansomwareCampaignUse: "Known"`.
- **No severity, no version ranges, no package coordinates** — entries are
  free-text vendor/product keyed by CVE. Open-source *library* coverage is
  a sliver: 0 of 1,708 entries mention "python" in vendor/product; the OSS
  package hits are things like Apache Log4j2 (CVE-2021-44228/45046) and one
  npm library (CVE-2021-21315, "Npm package / System Information Library
  for Node.JS"). The KEV→package join must go through CVE `aliases[]` in
  the OSV records — and a KEV bit will fire rarely for pip packages, which
  is exactly the selectivity the criticality model wants.

### EPSS (FIRST.org)

- What it asserts: "an estimate of the likelihood that any one of our data
  partners (and their sensors) will detect, record and share evidence of
  exploitation activity associated with a vulnerability … in the next 30
  days" (https://www.first.org/epss/faq). A score of 0.05 is a calibrated
  5% probability of *observed exploitation activity* in 30 days
  (https://www.first.org/epss/how-it-works). It is a **forecast, not
  evidence**: "Exploitation activity observed today does not directly
  change tomorrow's score … Exploitation data informs model training, not
  daily scoring" (FAQ, same URL). EPSS deliberately defines no
  critical/high/medium bands (FAQ).
- Access (https://www.first.org/epss/data): scores published **daily**
  (FAQ: "typically within a minute or two after 13:30 UTC"), free, **no
  registration; attribution requested** (FAQ: "Is EPSS free to use?").
  Three channels:
  - Daily CSV at the stable URL
    `https://epss.empiricalsecurity.com/epss_scores-current.csv.gz` —
    verified live: header comment
    `#model_version:v2026.06.15,score_date:2026-09-11T12:00:21Z`, columns
    `cve,epss,percentile`, 371,626 scored CVEs. This is the bulk channel.
  - API at api.first.org — "designed for lookup, not bulk access" (data
    page); supports date-pinned and 30-day-history queries.
  - Historical archive github.com/empiricalsec/epss_scores back to
    2021-04-14; model-version boundaries (v2 2022-02-04, v3 2023-03-07,
    v4 2025-03-17, v5 2026-06-15) each produced a score shift — historical
    comparisons across a boundary reflect methodology change (data page).
- **CVE-keyed only**: a PyPI advisory with no CVE alias (all `MAL-*`, some
  PYSEC) can never have an EPSS score.

---

## The ticket's five questions, answered

### 1. Severity conventions and disagreements

Four different conventions coexist: OSV carries zero-or-more raw CVSS
*vector strings* (v2/v3/v4) with optional per-assessor `source`; GHSA adds a
qualitative four-band label in the non-contractual `database_specific`
area; PYSEC carries vectors or nothing (38% nothing); KEV and MAL records
carry nothing. Records for the *same* bug differ by database: measured live,
GHSA-462w-v97r-4m45 (jinja2, CVE-2019-10906) ships CVSS v3.0 + v4.0 vectors
and label HIGH, while its alias PYSEC-2019-217 ships no severity at all.
The OSV `severity[].source` field (`NVD`/`CNA`/`SELF`) exists because NVD
and CNA scores for one CVE routinely differ
(https://ossf.github.io/osv-schema/#severityscore-field).
**Bulletin consequence:** severity = optional `{label, vectors[], source}`
normalized by the provider; the client must render "unknown severity"
gracefully and must never gate a page on it.

### 2. Exploited-in-the-wild evidence

KEV asserts curated *past/ongoing exploitation evidence* (attempted counts,
scanning doesn't); event-driven updates; JSON/CSV/schema at stable
CISA URLs; CC0 1.0; no auth or rate limits; 1.7 MB. EPSS asserts a *daily
recalibrated 30-day forecast probability* (plus percentile); daily CSV at a
stable URL, free with attribution requested; API for lookups only; scores
exist only for CVEs. They are epistemically different objects — KEV can
satisfy the map's "bulletin says actively-exploited" clause; EPSS cannot
(it is explicitly not evidence), but is cheap to carry as advisory context
for the digest. **Bulletin consequence:** two fields, e.g.
`kev: {listed, date_added, ransomware}` and
`epss: {score, percentile, date}`, never one merged flag.

### 3. Version-range encodings and lossiness of exact-version lists

Encodings: OSV `ranges[]` (`ECOSYSTEM`/`SEMVER`/`GIT` + event timeline) and
optional enumerated `versions[]`; GHSA REST/GraphQL uses comparator strings
(`">= 0.8.0, < 0.11.1"`) plus a `database_specific` escape hatch for
unrepresentable ranges. Measured on the live PyPI corpus: 73% of records
already enumerate exact versions (osv.dev auto-populates ECOSYSTEM ranges);
27% would need distiller-side enumeration against the PyPI index using
PEP 440 ordering; 1,678 `last_affected` events and ~8k no-`fixed` records
(mostly `MAL-*`) are *open-ended* — an exact-version list for those is
frozen at build time and silently misses versions released afterwards
(bounded by the weekly refresh window). The schema also warns range/version
strings "are not guaranteed to exactly match versions of the package found
in the upstream package repository" (may be normalized)
(https://ossf.github.io/osv-schema/#affectedrangesevents-fields), so the
client should PEP 440-normalize the intake version before matching.
**Verdict:** exact-version lists are an acceptable distillation for the
closed (fixed-exists) majority; pair them with an `open_ended` marker (or
`introduced` floor) so the client can flag "affected, no fix exists" intakes
even when the exact installed version postdates the bulletin build.

### 4. Machine-checkable local abuse indicators — fog confirmed

No surveyed source ships file hashes, filesystem paths, process behaviors,
or any other host-side IOC. KEV is catalog metadata only (schema). The
only structured "affected code element" mechanisms found: PyPA's
`ecosystem_specific.imports` spec — **0 of 7,518 records use it**; GitHub's
REST `vulnerable_functions` array — empty in the sampled record; and the Go
ecosystem's affected-symbol convention noted in the OSV schema
(https://ossf.github.io/osv-schema/#affectedecosystem_specific-field),
which does not exist for PyPI. Even `MAL-*` records describe *that* a
package is malicious, never *what artifacts it drops*. **Consequence:** the
map's "indicator forensics is fog" call is confirmed by the data; the
"exercised" leg of the criticality test must be built from machine-local
evidence (T505), and the bulletin schema should not reserve indicator
fields it can never populate.

### 5. Multi-ecosystem coverage

OSV is the aggregation point: the live `ecosystems.txt` includes PyPI, npm,
NuGet, Maven (plus crates.io, Packagist, Pub, RubyGems, Go, Hex, …), each
with its own `all.zip` and `modified_id.csv` under one schema
(https://storage.googleapis.com/osv-vulnerabilities/ecosystems.txt,
https://google.github.io/osv.dev/data/). GHSA curates all four target
ecosystems (README list). KEV and EPSS are CVE-keyed and thus
ecosystem-agnostic; the join is identical everywhere. Per-ecosystem gaps:
KEV's OSS-library coverage is minimal in every ecosystem (a feature for
selectivity, not a bug); `MAL-*` malicious-package records exist for PyPI
and npm in ossf/malicious-packages (the PyPI corpus's MAL records all point
there). **Consequence:** the day-one `ecosystem` field is sufficient; no
per-ecosystem schema variation is needed — only per-ecosystem intake
grammar and version-normalization rules on the client side, as the map
already plans.

---

## License / access summary

| Source | License | Bulk access | Auth / rate limits | Cadence |
| --- | --- | --- | --- | --- |
| OSV (osv.dev) | per-source records; distribution is public GCS | `storage.googleapis.com/osv-vulnerabilities/<eco>/all.zip` (PyPI: 34 MB) | none; API "no limits" | continuous export |
| GHSA | CC-BY 4.0 | git/tarball of github/advisory-database (also inside OSV zips) | REST: 60/hr unauth | continuous |
| PyPA (PYSEC) | CC-BY 4.0 | git/tarball of pypa/advisory-database (also inside OSV zips) | none | continuous |
| CISA KEV | CC0 1.0 | single JSON/CSV file (1.7 MB) | none | event-driven, versioned per release |
| EPSS | free; attribution requested | daily CSV, stable URL (gzip) | none for CSV; API lookup-only | daily ~13:30 UTC |

All of it is compatible with the planned weekly `curl` subprocess +
hash-verified cache under `~/.llmsnitch/` (ADR 0001): every bulk endpoint
is a plain unauthenticated HTTPS file.
