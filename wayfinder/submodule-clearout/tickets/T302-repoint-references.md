# T302 — Repoint active references

`label: wayfinder:ticket` · map: [submodule-clearout](../map.md) · status: CLOSED (2026-08-27) — both files repointed to upstream URL + pin; grep criterion holds

## Scope (from recon — the only non-historical references)

| File | Line(s) | Treatment |
|---|---|---|
| `team/roles/dossier-researcher.md` | 16–17 | Active role file: replace local `submodules/...` source paths with upstream URLs + pins (docs `fbb9177`, snyk `a59b55a`); researcher already has curl-only design-time network per T104. |
| `dossiers/codex.md` | 308, 311 | Evidence citations: annotate with upstream URL + pin, keep line refs (D-SC3). |

**Not touched** (D-SC2, historical decision records):
`wayfinder/harness-team/map.md`, `wayfinder/harness-team/tickets/T101-roster-ranking.md`.

## Done criteria

- `grep -rn "submodules/" --include="*.md" . ` hits only `wayfinder/harness-team/`
  (closed records) and this effort's own files.
- A fresh dossier-researcher run needs no local `submodules/` tree.
