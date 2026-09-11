# 0001 — Bulletin refresh is the product's only network egress

**Status**: accepted (2026-09-11)

## Context

llmsnitch is no-network by doctrine: `test_no_network_imports` greps the
package for network imports, and everything works offline from flat files.
The dep-audit surface needs current vulnerability intelligence, which is
inherently network-fed. Alternatives considered: wrapping an installed OSS
scanner (pip-audit, osv-scanner, grype — none present on this machine;
adds a binary dependency and their noise model contradicts the
evidence-gated criticality doctrine), or a fully offline snapshot with no
refresh (advisories go stale silently).

## Decision

The CLI consumes a **distilled bulletin** produced by an external provider
(out of scope here; contract in `docs/bulletin-spec.md`). Refresh is a
weekly `curl` **subprocess** — the package stays import-clean, so the
test-enforced constraint holds as written. The cache under `~/.llmsnitch/`
is hash-verified; scans always run offline against the cache and stamp its
age, never blocking on the network.

## Consequences

- First deliberate network egress in the product: one URL, weekly, pull-only.
- The no-network constraint's meaning is now precise: *no network code in
  the package*, not *the product never touches the network*.
- A missing/stale bulletin is an operational condition, never a crash —
  the hot path and gate semantics are unaffected.
