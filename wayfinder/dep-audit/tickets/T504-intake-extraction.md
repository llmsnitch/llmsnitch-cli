# T504 — Intake extraction design

`labels: wayfinder:grilling`
`parent: ../map.md`
`blocked by: —`
`blocks: T505, T507`
`status: OPEN`

## Question

How an **intake** (agent-installed package evidence) is extracted from
what's already on disk. HITL grilling over:

1. Install-command grammar: which commands count (`pip install`,
   `uv add`, `uv pip install`, `pipx install`, `python -m pip …`,
   requirements-file installs) and how loose the parse is — a missed
   install is a silent hole, an over-match pollutes intakes.
2. Retroactive sweep: mining existing session NDJSON + harness ledgers
   (ingest-cursor style) vs from-now-on only; idempotency.
3. Intake record shape + storage: package × project × session × time,
   flat file under `~/.llmsnitch/` per house style.
4. Version truth: intake stores the *claim*; the env's `dist-info` at
   scan time is authoritative (command says `requests`, disk says which
   version landed — and whether it's still installed).
