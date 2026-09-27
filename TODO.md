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
- [ ] `main.py` + routers (incidents, approvals, tools)
- [ ] SSE stream of incident events
- [ ] CORS for Next.js dev

## 9. MCP server
- [ ] `mcp_server/` exposing tool registry over MCP

## 10. Frontend (Next.js)
- [ ] scaffold app
- [ ] incident list page
- [ ] incident detail: timeline, hypotheses, tool calls, evidence, remediation, verification
- [ ] execution graph view
- [ ] polling wired to FastAPI

## 11. Evaluation
- [ ] `eval/benchmark.py`
- [ ] `scripts/run_eval.py`
- [ ] run all 10 scenarios × N, store `eval/results/*.json`

## 12. Infra + CI
- [ ] `docker-compose.yml` (untested locally — no Docker on this machine)
- [ ] `.github/workflows/ci.yml`
- [ ] `scripts/demo.sh`

## 13. Docs
- [ ] README.md
- [ ] docs/ARCHITECTURE.md (+ Mermaid)
- [ ] docs/AGENT_LOOP.md (+ Mermaid)
- [ ] docs/TOOLS.md
- [ ] docs/SAFETY.md
- [ ] docs/EVALUATION.md
- [ ] docs/INCIDENT_SCENARIOS.md
- [ ] docs/RESUME.md
- [ ] docs/DEMO.md

## 14. Final pass
- [ ] full pytest run green
- [ ] eval run stored
- [ ] demo.sh run verified
- [ ] commit
