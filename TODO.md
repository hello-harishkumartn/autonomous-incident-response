# TODO

Legend: [ ] pending, [x] done, [~] partial/in progress

## 0. Planning
- [x] PLAN.md
- [x] TODO.md

## 1. Backend skeleton
- [x] Directory layout (`backend/app/...`)
- [x] `requirements.txt`, venv, install
- [x] `config.py` (pydantic-settings)
- [x] `db.py` (SQLAlchemy engine/session)
- [x] `models_db.py` (ORM models)
- [~] `schemas.py` (Pydantic API/tool schemas) — tool schemas done (per-tool args models); API response schemas pending with FastAPI app
- [x] pytest scaffolding + smoke test passes

## 2. Simulator
- [x] `simulator/world.py` (services, state)
- [x] `simulator/generators.py` (logs/metrics/traces/deploys/config/git commits)
- [x] `simulator/engine.py` (SimulationEngine, seeded clock)
- [x] `simulator/scenarios.py` (10 incident scenarios + ground truth)
- [~] tests for simulator determinism — implicitly covered by e2e tests using fixed seed; dedicated determinism test still pending

## 3. Tools
- [x] `tools/base.py` (Tool interface, typed schemas, risk levels)
- [x] `tools/registry.py`
- [x] read tools: query_logs, query_metrics, get_trace, inspect_service, get_deployment, get_git_diff, get_config
- [x] diagnostic tools: execute_diagnostic, run_health_check
- [x] action tools: restart_service, rollback_deployment
- [x] create_incident_note
- [~] tool tests — covered indirectly via e2e loop tests; direct unit tests pending

## 4. LLM client
- [x] `llm/base.py` provider protocol
- [x] `llm/offline_provider.py` (deterministic heuristic, default for tests)
- [x] `llm/gemini_provider.py`
- [x] `llm/ollama_provider.py`
- [x] `llm/client.py` fallback chain + token accounting
- [x] tests (offline provider only, no network in CI) — via e2e tests (AIRE_LLM_PROVIDER=offline)

## 5. Agent loop
- [x] `agent/stopping.py` (budgets, duplicate/loop detection, stopping conditions)
- [x] `agent/prompts.py` (in llm/prompts.py)
- [x] `agent/loop.py` (full state machine per spec diagram)
- [x] `agent/factory.py` (create_incident / load_agent_loop — resumability)
- [x] tests: loop reaches resolution end-to-end for ALL 10 scenarios (test_agent_loop_e2e.py, 14 tests passing)

## 6. Safety
- [x] `safety/risk.py`
- [x] `safety/approval.py`
- [x] `safety/sandbox.py` (allowlisted executor)
- [x] tests: high-risk action blocks without approval; approved action executes; rejection path

## 7. CLI end-to-end proof (milestone)
- [ ] `scripts/inject_incident.py`
- [ ] `scripts/run_agent.py`
- [x] proven end-to-end via automated tests (all 10 scenarios resolve; approval gate + budget exhaustion verified) — manual CLI run still pending

## 8. FastAPI app
- [x] `main.py` + routers (incidents, tools)
- [x] SSE stream of incident events
- [x] CORS for Next.js dev
- [x] verified live: create -> investigate -> poll resolves correctly over HTTP

## 9. MCP server
- [x] `mcp_server/` exposing tool registry over MCP (stdio), scoped by incident_id, remediation via SandboxExecutor
- [x] tests (direct handler invocation, no stdio transport needed)

## 10. Frontend (Next.js)
- [x] scaffold app (Next 16, App Router, TypeScript, no component library)
- [x] incident list page + scenario injection grid
- [x] incident detail: timeline, hypotheses, tool calls, remediation+verification, service health
- [x] execution graph view (grouped flowchart, visited/current highlighting)
- [x] polling wired to FastAPI
- [x] `npm run build` passes; verified live against running backend (curl + SSR check — no in-session browser tool to screenshot interactively, see PLAN.md)

## 11. Evaluation
- [x] `eval/benchmark.py`
- [x] `scripts/run_eval.py`
- [x] ran all 10 scenarios x 3 trials -> `eval/results/baseline_offline_provider.json` (30/30 resolved, 100% root-cause accuracy)

## 12. Infra + CI
- [x] `docker-compose.yml` (untested locally — no Docker on this machine)
- [x] `.github/workflows/ci.yml` (mirrors locally-verified commands; untested against a real runner)
- [x] `scripts/demo.sh` — verified end-to-end (both --list and a full inject+investigate+resolve run)

## 13. Docs
- [x] README.md
- [x] docs/ARCHITECTURE.md (+ Mermaid)
- [x] docs/AGENT_LOOP.md (+ Mermaid, transcribed from api/graph.py)
- [x] docs/TOOLS.md
- [x] docs/SAFETY.md (+ Mermaid)
- [x] docs/EVALUATION.md
- [x] docs/INCIDENT_SCENARIOS.md
- [x] docs/RESUME.md
- [x] docs/DEMO.md

## 14. Final pass
- [x] full pytest run green (19 tests)
- [x] eval run stored
- [x] demo.sh run verified (bad_deployment, dependency_timeout, redis_failure all confirmed working)
- [x] final commit + review — repo clean, 8 commits, no stray db/build files tracked

## Known gaps (deprioritized, honest accounting)
- No dedicated simulator-determinism unit test (same seed -> same telemetry) —
  implicitly relied upon by every e2e test using fixed seeds, but not asserted directly.
- No direct per-tool unit tests — covered indirectly through e2e loop tests
  and MCP handler tests, which exercise every tool at least once.
- docker-compose.yml / Dockerfiles / CI workflow are written carefully but
  unverified against real Docker or a GitHub Actions runner (no Docker on
  this machine — see PLAN.md environment constraints).
- Frontend was verified via `npm run build`, `npm run dev` + curl/SSR checks
  against the live backend, not an interactive browser session (no browser
  automation tool available in this session).
