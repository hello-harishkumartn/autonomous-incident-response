# PLAN — Autonomous Incident Response Engineer (AIRE)

## What this is

A real agentic system, not a chatbot: it watches a simulated microservice
fleet, gets paged by synthetic alerts, and runs a closed investigate →
diagnose → remediate → verify loop against typed tools with an explicit
state machine, budgets, safety gates, and machine-verifiable stopping
conditions. A human approves high-risk actions. Everything is inspectable:
persistent run state, an eval harness, and a UI that shows the
investigation evolving.

## Environment constraints discovered (2026-09-27)

- Python 3.12 is installed but **not on PATH** (Windows Store alias shadows
  it). Real binary: `C:\Users\Harish\AppData\Local\Programs\Python\Python312\python.exe`.
  Backend tooling (venv, scripts) references this directly.
- Docker/Docker Compose and Ollama are **not installed** on this machine.
  Per user decision: skip installing Docker/Ollama for now. Consequence:
  - `docker-compose.yml` is written and intended to be correct, but is
    **untested locally** (flagged in docs).
  - Local dev/tests/demo run natively: SQLite by default via
    `DATABASE_URL`, swappable to real Postgres (docker-compose or a local
    install) without code changes (SQLAlchemy, no dialect-specific SQL).
  - LLM: Gemini is primary (user will supply `GEMINI_API_KEY`), Ollama
    adapter is implemented but won't be exercised locally, and a
    deterministic **offline heuristic provider** is the automatic fallback
    so tests/CI/demo never depend on network or secrets.
- Node.js v24 is available → Next.js UI is buildable/runnable directly.

## Architecture at a glance

```
scripts/inject_incident.py --type X
        │
        ▼
Postgres/SQLite  ←──────────────┐
   world state, telemetry,      │
   incident + run state         │
        ▲                       │
        │ read/write            │ persists every step
   ┌────┴─────┐           ┌─────┴──────┐
   │  Tools    │◄──calls───│ Agent Loop │◄──LLM (Gemini→Ollama→offline)
   │ (typed,   │           │ (state     │
   │ risk-tag) │──results─►│  machine)  │
   └────┬─────┘           └─────┬──────┘
        │                       │ approval needed?
        │                       ▼
        │                 Safety/Approval gate
        │                       │
        ▼                       ▼
  Sandbox executor        FastAPI (REST + SSE)
  (allowlisted only)             │
                                 ▼
                          Next.js observability UI
```

## Build order (incremental, each phase ends runnable + tested)

1. **PLAN.md / TODO.md** (this phase).
2. **Backend skeleton**: package layout, config, DB models (SQLAlchemy),
   Pydantic schemas, venv + requirements, pytest wired up with a smoke test.
3. **Simulator core**: world model for the 6 services, deterministic seeded
   generators for logs/metrics/traces/deploys/config/git commits.
4. **Incident scenarios (10)**: each a pure function that perturbs world
   state + has a ground-truth root cause/fix for eval scoring.
5. **Tools layer**: common `Tool` interface, typed schemas, risk
   classification, registry; all 12 spec'd tools implemented against the
   simulator/DB (no real shell access anywhere).
6. **LLM client**: provider abstraction, Gemini + Ollama + offline
   heuristic provider, automatic fallback, token accounting.
7. **Agent loop**: explicit state machine per the spec's diagram, persistent
   `IncidentState`, budgets (iterations/time/tokens), duplicate-action and
   loop detection, stopping conditions.
8. **Safety/approval**: READ_ONLY auto-run, LOW_RISK configurable
   auto-run, HIGH_RISK blocks on a human decision recorded in the DB;
   sandbox executor is the only thing allowed to mutate simulated world
   state.
9. **CLI end-to-end proof**: `scripts/inject_incident.py` +
   `scripts/run_agent.py` take one scenario from injection to resolution
   with visible decision/evidence/action/result trace. This is the
   milestone that must work before moving on.
10. **FastAPI app**: wraps the same engine/loop for the UI (REST + SSE
    incident stream, approvals endpoint).
11. **MCP-compatible tool server**: same tool registry exposed over MCP.
12. **Next.js observability UI**: incident list, timeline, hypotheses,
    tool calls, evidence, remediation, verification, execution graph.
    Shows decision/evidence/action/result — never raw model
    chain-of-thought.
13. **Evaluation harness**: runs all 10 scenarios N times, computes the
    spec'd metrics, writes results to `eval/results/`.
14. **docker-compose.yml** (Postgres + backend + frontend), CI workflow,
    remaining docs (`ARCHITECTURE`, `AGENT_LOOP`, `TOOLS`, `SAFETY`,
    `EVALUATION`, `INCIDENT_SCENARIOS`, `RESUME`, `DEMO`), `scripts/demo.sh`.
15. **Final pass**: run full test suite + eval + demo script, fix gaps,
    commit.

## Key design decisions

- **SQLAlchemy over Postgres, SQLite default locally.** Same schema, zero
  dialect-specific features, so `DATABASE_URL` alone switches between them.
  Keeps the project usable without Docker while staying faithful to the
  stack requirement.
- **Simulator is synthetic, not six real containers.** "API Gateway",
  "Order Service", etc. are modeled entities whose telemetry is generated
  deterministically from a seeded RNG plus incident-specific perturbation
  functions — reproducible or replayable at will (spec asks for
  reproducible incidents).
- **Offline LLM provider is not a mock of convenience — it's a hard
  requirement for hermetic tests/CI.** It implements the same hypothesis
  generation and remediation-selection contract as Gemini/Ollama via
  evidence-driven heuristics, so `pytest`/CI never call the network.
- **Sandbox executor is the only mutator of world state for actions.**
  Tools never get shell access; `restart_service`/`rollback_deployment`/etc.
  are allowlisted operations against the simulation engine only.
- **Everything the agent does is persisted**, not just logged — the DB rows
  for an incident run ARE the state machine's memory, so a run can be
  inspected or resumed from any point.
- **Metrics/traces borrow the concepts, not the wire protocol.** `MetricPoint`
  rows are Prometheus-shaped (service label + metric name + timestamp +
  value) and `TraceSpan` rows follow OTel's span model (trace/span/parent
  IDs, service, operation, start/duration, status) — enough for the
  `query_metrics`/`get_trace` tools to be realistic and for a reader
  familiar with either system to recognize the shape immediately. Neither
  exposes an actual `/metrics` text-exposition endpoint or OTLP wire
  format; the spec asked for this "if practical," and building a real
  Prometheus scrape target added no value the agent loop could use that
  the DB-backed tool couldn't already provide.

## Definition of done

- `pytest` passes locally for backend.
- `scripts/demo.sh` runs: starts backend (+ frontend if node present),
  injects `bad_deployment`, agent investigates and resolves it, prints a
  clear summary.
- All 10 scenarios have at least one clean resolved run in
  `eval/results/`.
- Docs listed above exist with Mermaid diagrams and match the code.
- CI config present (untested against a real runner in this session, but
  mirrors the exact local commands that were verified to pass).
