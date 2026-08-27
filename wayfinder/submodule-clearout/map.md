# Submodule Clearout — Wayfinder Map

`label: wayfinder:map`
`status: CLOSED (2026-08-27) — destination reached: 0 gitlinks in the index,
\`git submodule status\` exits clean, tree trashed, active references
repointed to upstream pins; suites 34/34 + 18/18 + 8/8 green. Residual fog
(broader R&D-blend triage, CLAUDE.md drift) inherited by future efforts.`

## Destination

The `submodules/` tree **gone from the repo cleanly**: no gitlink entries in
the index, no empty directories in the working tree, `git submodule status`
exits clean, every evidence citation that pointed into `submodules/` repointed
to upstream URL + pinned commit, and the active team role file no longer
instructs agents to read local submodule paths. Suites stay green
(trivially — no code imports anything under `submodules/`).

## Why now (recon, 2026-08-27)

- HEAD (`c012b0e`) deleted `.gitmodules` but left **13 gitlink entries in the
  index** — the repo is in a broken half-removed state: `git submodule status`
  is fatal ("no submodule mapping found").
- All 13 working-tree dirs are **empty** — never initialized in this checkout;
  no `.git/modules/`, no `submodule.*` local config. Removal is
  `git rm --cached` + trashing empty dirs, nothing more.
- Both maps that consumed these sources are **CLOSED**:
  - harness-team (2026-08-25): D03/D04 — OpenRouterTeam artifacts are
    design-time reference only, mined into the roster (T101) and dossier
    format (T103); "no OpenRouter runtime integration" is an explicit
    out-of-scope decision.
  - scan-rollout (2026-08-26): snyk-agent-scan's well-known-path table was
    ported into `llmsnitch/scanrules.py` (T203, SD-020/SD-022) — the port is
    shipped and smoke-tested; the source tree is no longer needed.
- No `.py` file references `submodules/` — only docs do (see T302).

## Evidence pins (recorded before deletion — the index is the only copy)

These are the commits the R&D actually read. Dossier citations stay valid
only if these survive somewhere; after `git rm --cached` they exist only in
git history of this repo. Recorded here so no citation goes dangling.

| Submodule | Upstream | Pinned commit |
|---|---|---|
| OpenRouterTeam/docs | github.com/OpenRouterTeam/docs | `fbb9177` |
| OpenRouterTeam/SnitchScript | github.com/OpenRouterTeam/SnitchScript | `4469b1e` |
| OpenRouterTeam/ai-sdk-provider | github.com/OpenRouterTeam/ai-sdk-provider | `b96b207` |
| OpenRouterTeam/awesome-openrouter | github.com/OpenRouterTeam/awesome-openrouter | `771cc3e` |
| OpenRouterTeam/go-agent | github.com/OpenRouterTeam/go-agent | `93a9343` |
| OpenRouterTeam/go-sdk | github.com/OpenRouterTeam/go-sdk | `4756653` |
| OpenRouterTeam/python-agent | github.com/OpenRouterTeam/python-agent | `f060a49` |
| OpenRouterTeam/python-sdk | github.com/OpenRouterTeam/python-sdk | `a33b0ce` |
| OpenRouterTeam/skills | github.com/OpenRouterTeam/skills | `f8fdfb7` |
| OpenRouterTeam/typescript-agent | github.com/OpenRouterTeam/typescript-agent | `74ddfc3` |
| OpenRouterTeam/typescript-sdk | github.com/OpenRouterTeam/typescript-sdk | `00d51c7` |
| OpenRouterTeam/.github | github.com/OpenRouterTeam/.github | `fbacd42` |
| security-scanners/snyk-agent-scan | github.com/snyk/agent-scan (Apache-2.0) | `a59b55a` |

Only two pins carry evidentiary weight: **docs `fbb9177`** (roster T101,
cookbook config paths) and **snyk `a59b55a`** (scanrules port T203, codex
dossier discoverer citations). The SDK/agent repos were roster survey
material never cited by line.

## Decisions

- **D-SC1** Removal is `git rm --cached` on the gitlinks, never a
  working-tree-only delete — the index holds them, and HEAD already proved
  that deleting `.gitmodules` alone leaves git broken.
- **D-SC2** Closed maps and tickets are **decision records — never rewritten**.
  Their `submodules/...` citations become historical paths, resolvable via
  the pin table above. Only *active* documents (team role files, dossiers
  that future runs consume) get repointed.
- **D-SC3** Dossier evidence lines get upstream-URL + pin annotations, not
  deletion — a dossier with dangling evidence fails its own format
  (T103: evidence-dated facts).
- **D-SC4** Empty dirs go via `trash`, never `rm` (repo policy).

## Tickets

- [T301 — Remove gitlinks + trash the tree](tickets/T301-remove-gitlinks.md)
- [T302 — Repoint active references](tickets/T302-repoint-references.md)

## Not yet specified

- **Broader R&D-blend cleanup** — the user's larger goal. What else in main
  is dead R&D vs. live: `fs_coil/` *ships in the wheel* (notify layer,
  T204 — live, not clearable); `team/` + `dossiers/` feed future harness
  runs (harness-team map: "per-harness work lives with the team"); `plans/`
  are open fix plans. Needs its own triage before anything else is cleared —
  own map when scoped.
- **CLAUDE.md drift** — "seven files, ~640 LOC" and the
  `wayfinder/map.md` pointer are stale; fix belongs to the broader cleanup.

## Out of scope

- Re-cloning any submodule content locally — sources are mined; future
  research uses curl-only design-time network per team playbook (T104).
- Rewriting closed wayfinder maps/tickets (D-SC2).
- Any change under `llmsnitch/` or `fs_coil/` — no code references exist.
