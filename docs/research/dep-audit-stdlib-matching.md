# Dep-audit: stdlib-only matching of installed dists to bulletin entries (T502)

> Convention note: lives in `docs/research/` beside `scanner-survey-mvp.md`
> and `unicode-evasion-redaction.md` — cited primary-source dossiers.
> Ticket: `wayfinder/dep-audit/tickets/T502-stdlib-matching.md`.
> Corpus numbers were measured 2026-09-11 against the full OSV PyPI dump
> (`https://osv-vulnerabilities.storage.googleapis.com/PyPI/all.zip`,
> 25,570 advisories); scanner behavior read from source at HEAD.

## TL;DR

**Verdict for the bulletin schema: carry pre-chewed enumerated versions,
not ranges.** The client's whole matcher is then: PEP 503-normalize the
name (one regex), canonicalize the version string (~30 lines), strip any
`+local` suffix, and do set membership — zero PEP 440 *comparison* code.
This is not a compromise design; it is what the ecosystem already does:

- **OSV itself pre-chews.** osv.dev's importer enumerates exact affected
  versions server-side (fetching PyPI's `releases` keys, sorting with
  `packaging`, slicing between `introduced`/`fixed`) and publishes them in
  each record's `affected[].versions` array. 23,540 of 30,615 PyPI
  affected-blocks (77%) in the live corpus carry that array.
- **osv-scanner's offline matcher checks the enumerated `versions` array
  by plain string equality first**, and only falls back to range
  arithmetic. Membership-first is production practice, not a hack.
- **pip-audit does no client-side range math at all** — both its backends
  send `(canonical_name, version_string)` to a server (api.osv.dev or
  PyPI's JSON API) and trust the server's match.
- Enumeration is bounded: median 11 affected versions per block, p95 243,
  max 2,458 (`awscli`, GHSA-hqvf-45jj-mccq). A *distilled* bulletin (only
  actively-exploited advisories × packages actually intaken) is tiny.
- The one shape enumeration can't carry — "every version is affected, no
  fix" (typical of MAL/malicious-package records, which are most of the
  ranges-only blocks) — needs a single boolean, e.g. `all_versions: true`.

`importlib.metadata.distributions(path=[...])` is sufficient for foreign
envs: verified live against a Python 3.12 project venv, the non-standard
`.venv-dashboard`, and a Python 3.14 uv tool env, all read from one host
interpreter. The API exists in 3.9 stdlib.

---

## Q1 — How pip-audit / osv-scanner / grype match today

### pip-audit (pypa/pip-audit)

- **Name normalization**: every dependency exposes
  `canonical_name = packaging.utils.canonicalize_name(name)` — PEP 503
  normalization ("The `Dependency`'s PEP-503 canonicalized name",
  `pip_audit/_service/interface.py` L51–55,
  <https://github.com/pypa/pip-audit/blob/main/pip_audit/_service/interface.py>).
- **Version comparison: none client-side.** The OSV backend POSTs
  `{"package": {"name": canonical_name, "ecosystem": "PyPI"}, "version":
  str(version)}` to `https://api.osv.dev/v1/query` and treats the
  response as authoritative; the only version parsing it does is sorting
  the `fixed` events for display
  (`pip_audit/_service/osv.py`, `query()`,
  <https://github.com/pypa/pip-audit/blob/main/pip_audit/_service/osv.py>).
  The PyPI backend GETs
  `https://pypi.org/pypi/{canonical_name}/{version}/json` and reads the
  pre-matched `vulnerabilities` key
  (<https://github.com/pypa/pip-audit/blob/main/pip_audit/_service/pypi.py>).
  OSV's API docs describe the server-side semantics: "A fuzzy match is
  done against upstream versions"
  (<https://google.github.io/osv.dev/post-v1-query/>).
- **Environment enumeration**: shells out to `pip list` via `pip_api`
  (`pip_audit/_dependency_source/pip.py`), i.e. it audits *an
  interpreter's* environment, warning when `sys.executable` doesn't match
  `$VIRTUAL_ENV`. It does not scan foreign venvs by path — llmsnitch's
  requirement is different (see Q4).
- **Extras** play no role in matching: advisories key on distribution
  name + version only.

### osv-scanner (google/osv-scanner, matching in google/osv-scalibr)

- Offline matcher `IsAffected` (osv-scalibr
  `enricher/vulnmatch/osvlocal/internal/vulns/vulnerability.go`,
  <https://github.com/google/osv-scalibr/blob/main/enricher/vulnmatch/osvlocal/internal/vulns/vulnerability.go>):
  after ecosystem+name equality, it first calls
  `matchVersionOrTag(affected.GetVersions(), np.Version)` — **literal
  string equality** against the enumerated `versions` array (with only a
  leading-`v` tolerance) — and *then* falls back to
  `rangeAffectsVersion`, which walks sorted ECOSYSTEM events with real
  version comparison. A package with no version is assumed vulnerable
  ("false positives are better than false negatives here").
- Its PEP 440 comparison, used only for the range fallback, is a full Go
  reimplementation seeded from PEP 440's own Appendix B regex, with the
  spec's spelling normalizations (`alpha`→`a`, `c`/`pre`/`preview`→`rc`,
  `rev`/`r`→`post`) and even legacy-version handling — several hundred
  lines (`semantic/version-pypi.go`,
  <https://github.com/google/osv-scalibr/blob/main/semantic/version-pypi.go>).
  That is the cost the bulletin design avoids putting in the client.

### grype (anchore/grype)

- Parses PEP 440 via `github.com/aquasecurity/go-pep440-version` and
  **compares only the public portion of the version**: "for a version
  like `1.0.0+abc.1`, we only want to consider `1.0.0` for comparison
  purposes"; the local segment is consulted only when the *constraint*
  itself carries one (`grype/version/pep440_version.go`,
  <https://github.com/anchore/grype/blob/main/grype/version/pep440_version.go>).
  Precedent for the client stripping `+local` before matching.

## Q2 — PEP 440 corner cases vs their real-world frequency

What breaks naive tuple/string comparison, per the spec
(<https://peps.python.org/pep-0440/>):

- **Zero-padding**: "the shorter segment is padded out with additional
  zeros as necessary" — `1.0` and `1.0.0` are *equal versions* with
  different strings; `1.10 > 1.9` breaks lexicographic compare.
- **Epochs** (`1!1.0`): sort before/after everything by epoch first.
- **Pre-releases** (`2.0.0rc1 < 2.0.0`) with alternate spellings
  (`alpha`, `beta`, `c`, `pre`, `preview`) and optional separators.
- **Post/dev releases**: `1.0.post1 > 1.0 > 1.0.dev1`.
- **Local versions** (`2.6.0+cu124`): public part compared first; local
  segments compared piecewise numeric/lexicographic.

Measured frequency in the full OSV PyPI corpus (25,570 advisories,
30,615 PyPI affected-blocks, 1,309,199 enumerated version strings;
analysis script run 2026-09-11 against `PyPI/all.zip`):

| Corner case | In enumerated `versions` strings | In range events (`introduced`/`fixed`/`last_affected`) |
|---|---|---|
| epoch (`N!`) | **0** | **0** |
| pre-release | 187,596 (14.3%) | 2,120 |
| dev release | 42,523 (3.2%) | 128 |
| post release | 10,321 (0.8%) | 20 |
| local (`+`) | 39 (one advisory using timestamp versions, GHSA-6g88-vr3v-76mf) | **1** (PYSEC-2025-191, `last_affected=2.6.0+cu124` — torch) |

Reading: epochs are absent from the entire advisory corpus and local
versions vanishingly rare **in advisories** — but pre/post/dev bounds do
appear in thousands of range events, exactly where naive comparison gives
wrong answers (e.g. `fixed=5.3.0rc1`: a naive comparator calls `5.3.0`
fixed; PEP 440 says `5.3.0 > 5.3.0rc1`, so it *is* fixed — but
`introduced=0.5.0b3.dev85`-style bounds cut the other way). Local
versions **do** occur on the installed side (any torch from the CUDA
index: `2.6.0+cu118`), so the client must strip locals regardless of
schema. Conclusion: a client that evaluates ranges cannot skimp on
pre/post/dev ordering; a client that does membership never orders
anything — the oddities arrive as opaque strings that either equal the
installed string or don't.

## Q3 — Pre-chewing server-side (the load-bearing question): YES

Three independent primary-source facts make enumerated-versions the
right bulletin payload:

1. **OSV already enumerates.** osv.dev's importer resolves ECOSYSTEM
   ranges to concrete version lists by fetching
   `https://pypi.org/pypi/{package}/json`, taking `releases` keys,
   sorting with `packaging_legacy` (tolerating even non-PEP-440 legacy
   versions), and slicing between the range events
   (`osv/ecosystems/pypi.py`, `enumerate_versions()`,
   <https://github.com/google/osv.dev/blob/master/osv/ecosystems/pypi.py>).
   The result ships in `affected[].versions` of every API/dump record.
   Measured coverage: 23,540/30,615 blocks (77%) — GHSA 10,872/11,268,
   PYSEC 7,297/7,602, MAL 5,366/11,737. The distillation server mostly
   *copies* this field; where it's missing it can run the same
   enumeration itself (same PyPI JSON API), or emit `all_versions`.
2. **The ranges-only remainder is dominated by "everything is
   affected".** ~6,400 of the 7,054 ranges-only blocks are MAL
   (malicious-package) records — `introduced: 0`, no fix, versions often
   never on PyPI's index anymore. These need no enumeration, only a
   boolean: `all_versions: true`. The few hundred GHSA stragglers
   (OpenStack keystone/nova, opencv-python) enumerate fine from PyPI.
3. **Enumeration is bounded.** Per affected-block: median 11, p95 243,
   max 2,458 versions (`awscli`). Per package on PyPI (JSON API
   `releases` counts, 2026-09-11): botocore 2,514; django 442; openai
   424; anthropic 217; requests 163; numpy 151 — release counts sit in
   the hundreds, pathological cases low thousands. At ~10 bytes/string
   the worst single block is ~25 KB; a distilled bulletin (curated
   advisories × the machine's intake packages) is kilobytes.

**Residual client obligations under membership matching** (all stdlib,
no comparison logic):

- **PEP 503 name key**: `re.sub(r"[-_.]+", "-", name).lower()`
  (<https://peps.python.org/pep-0503/#normalized-names>), applied to both
  bulletin names and `dist.metadata["Name"]` (which preserves author
  case: observed `RapidFuzz`, `Jinja2`, `PyYAML` in live venvs).
- **Version canonicalization**: server emits versions in PEP 440
  canonical form; client applies the same ~30-line pure normalizer
  (lowercase; `-`/`_`→`.` separators; spelling map `alpha`→`a`,
  `beta`→`b`, `c|pre|preview`→`rc`, `rev|r`→`post`; strip leading zeros
  in numeric parts; strip a leading `v`). This is normalization of one
  string, not comparison of two.
- **Strip `+local`** from the installed version before lookup (grype
  precedent above; covers torch `+cuXXX` wheels). The zero-padding
  equality (`1.0` vs `1.0.0`) is the one theoretical string-membership
  miss; PyPI can't host two artifacts of equal PEP 440 version for the
  same filename, and the installed METADATA string equals the PyPI
  release string for anything actually installed from PyPI, so in
  practice the strings align. Non-PyPI installs (VCS/editable/dev builds)
  won't appear in any enumeration — a known, documentable blind spot that
  range-matching would *also* get wrong (their versions are often
  `0.1.dev12+g1234abc`).
- **Schema consequence**: bulletin `affected` entries carry
  `{ecosystem, name (normalized), versions: [canonical strings]}` plus
  `all_versions: true` for the introduced-0-no-fix shape. Ranges may ride
  along as provenance/display metadata but the client never evaluates
  them. This also keeps the multi-ecosystem promise: membership works
  identically for npm/Maven; only the server-side enumerator is
  per-ecosystem (osv.dev has one per ecosystem in `osv/ecosystems/`).

## Q4 — importlib.metadata across foreign envs: sufficient

- The API exists in Python 3.9's stdlib: `distributions(**kwargs)`
  forwards to `Distribution.discover()`, whose
  `DistributionFinder.Context` has a `path` attribute "that a
  distribution finder should search … defaults to `sys.path`"
  (CPython 3.9 `Lib/importlib/metadata.py` L383–411, L545,
  <https://github.com/python/cpython/blob/3.9/Lib/importlib/metadata.py>).
- **Verified live (2026-09-11, host Python 3.14.7)** —
  `distributions(path=[<site-packages>])` correctly enumerated three
  foreign envs from the census without invoking their interpreters:
  - `~/Repos/ms-foundry-transcribe/.venv-dashboard/lib/python3.14/site-packages`
    (the non-standard-name venv): 12 dists;
  - `~/Repos/tabfm-sierra/.venv/lib/python3.12/site-packages`
    (**different minor version than the host**): 42 dists;
  - `~/.local/share/uv/tools/graphifyy/lib/python3.14/site-packages`
    (uv tool env): 32 dists.
  It's pure filesystem parsing of `*.dist-info` — host/target Python
  version mismatch is irrelevant, and venv/pipx/uv-tool envs all share
  the same `lib/pythonX.Y/site-packages` layout (glob
  `lib/python*/site-packages` under each env root; census's env
  *discovery* is T-census territory, not this ticket's).
- Per dist, `dist.metadata["Name"]` + `dist.version` are the matching
  inputs; normalize the name per PEP 503 (dist-info directory names are
  not reliable — normalization rules changed across pip versions, and
  `metadata["Name"]` preserves original case).
- Caveats: editable installs surface with their project version but
  their code isn't the released artifact (mark, don't match-suppress);
  legacy `.egg-info` layouts are also handled by `importlib.metadata`'s
  `MetadataPathFinder`, so nothing extra is needed for old pips.

## Method note

Corpus analysis: downloaded `PyPI/all.zip` from the OSV public bucket and
scanned all 25,570 records with a stdlib Python script (regex classes for
epoch/pre/post/dev/local over both `affected[].versions` strings and
range-event bounds). Scanner behavior: read from pypa/pip-audit,
google/osv-scanner, google/osv-scalibr, anchore/grype, and google/osv.dev
sources on GitHub at HEAD, 2026-09-11. Live venv experiment run on this
machine against the census envs. All fetches via `curl`.
