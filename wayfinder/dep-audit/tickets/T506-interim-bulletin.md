# T506 — Interim bulletin for this machine

`labels: wayfinder:task`
`parent: ../map.md`
`blocked by: T503`
`blocks: T507`
`status: OPEN`

## Question

A working MVP needs a real bulletin to consume, and the provider is out of
scope. Produce one: a one-off distillation script (out-of-package tooling —
never shipped in the wheel, may use network/deps freely) that pulls
OSV + KEV for the packages in this machine's 9 envs and emits a
spec-conformant bulletin. Resolution records: script location, the
bulletin's cache path, how to re-run it until a provider exists (this is
the manual stand-in for the weekly refresh). AFK once T503's spec is
locked.
