# T506 — Interim bulletin for this machine

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: T503`
`blocks: T507`
`status: DONE (2026-09-12)`

## Question

A working MVP needs a real bulletin to consume, and the provider is out of
scope. Produce one: a one-off distillation script (out-of-package tooling —
never shipped in the wheel, may use network/deps freely) that pulls
OSV + KEV for the packages in this machine's 9 envs and emits a
spec-conformant bulletin. Resolution records: script location, the
bulletin's cache path, how to re-run it until a provider exists (this is
the manual stand-in for the weekly refresh). AFK once T503's spec is
locked.

## Resolution

**Scope supersession**: this ticket predates T503 and asks for a bulletin
"for the packages in this machine's 9 envs" — T503 ruled bulletins are
always full-ecosystem (the intake list never leaves the machine), so a
**full-PyPI** bulletin was built instead.

**Script**: `tools/distill_bulletin.py` — out-of-package tooling, never in
the wheel (`pyproject.toml` lists `packages = ["llmsnitch", "fs_coil"]`
explicitly, so `tools/` can't be picked up). Curl subprocesses for all
network; PEP 723 inline metadata declares its one dep (`packaging`, for the
PEP 440 range math the *client* is forbidden to do).

**Re-run (the manual weekly-refresh stand-in until a provider exists)**:

```bash
uv run tools/distill_bulletin.py          # feeds cached in <tmp>/llmsnitch-bulletin-work
uv run tools/distill_bulletin.py --fresh  # force feed re-download
```

**Bulletin cache path** (spec left it open; this sets the precedent for
T507's reader): `~/.llmsnitch/bulletins/pypi.json.gz` + sidecar
`~/.llmsnitch/bulletins/pypi.json.gz.sha256` (bare lowercase hex + newline —
the spec's literal reading; a `sha256sum`-style reader should `split()[0]`).
Dir `0700`, files `0600` per house style.

**Build of 2026-09-12** (sources: OSV export 2026-09-12, KEV catalog
2026.09.11, EPSS score date 2026-09-11):

- 25,583 OSV records → 573 withdrawn dropped → **19,033 entries**
  (alias groups collapsed): 11,717 `malicious` / 7,316 `vulnerability`;
  6,379 `all_versions`; **21 KEV-listed**; 6,905 with EPSS.
- 1,156,698 bytes gzipped (12.99 MB raw) — well under the 10 MB soft
  budget; no display fields dropped.
- 108 packages enumerated live against the PyPI index (the ~500
  non-enumerated ranged blocks); 300 (group × package) pairs dropped as
  unenumerable (GIT-only ranges, 26 packages gone from the index with
  closed ranges, 13 rangeless non-MAL blocks) — the spec forbids an entry
  with neither `versions` nor `all_versions`.
- sha256 `9b738ae37975c42d1bf79db7aaa2fd2ac571a2189dc5c4cee4e832ed8b7b02c3`,
  sidecar verified.

**Spot-checks**: `CVE-2019-10906`/`jinja2` — aliases GHSA-462w-v97r-4m45 +
PYSEC-2019-217 collapsed, enumerated versions 2.0rc1…2.10, severity
high/GHSA, EPSS present, `fixed_in: ["2.10.1"]`. `MAL-2022-7421`/
`ascii2text` — `class: malicious`, `all_versions: true`, matches the spec
example (plus its GHSA alias). `CVE-2020-11978`/`apache-airflow` —
`kev.listed: true` with enumerated versions and severity. Schema sweep:
0 non-conformant entries.

**Distiller choices the spec left open** (recorded for T507/a future
provider): `id` with multiple CVEs in a group = lexicographically-first
CVE; `class: malicious` iff the alias group contains a `MAL-*` record;
`severity` emitted only when a label is derivable (GHSA
`database_specific.severity`, else a computed CVSS 3.x base-score band) —
vector-only records that can't be scored omit `severity` entirely; `url`
points at the lexicographically-first source record id (the spec example's
own pattern).
