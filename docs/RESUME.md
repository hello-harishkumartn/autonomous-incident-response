# Resume / Portfolio Summary

## One-liner

> Built an autonomous SRE agent that investigates and resolves simulated
> production incidents through a closed-loop, budget-bounded state
> machine — typed tools, risk-gated human approval, and a hard-sandboxed
> executor — evaluated against a 10-scenario benchmark, not a demo script.

## Resume bullets

- **Designed and implemented an agentic incident-response system** (Python/FastAPI
  backend, Next.js UI) that autonomously investigates simulated production
  incidents end-to-end: alert → hypothesis generation → tool-driven
  evidence gathering → root-cause confirmation → risk-classified
  remediation → human approval gate → sandboxed execution → health
  verification → resolution or rollback.
- **Built a deterministic incident simulator** modeling 6 interdependent
  microservices with seeded, reproducible generation of logs, metrics,
  distributed traces, deployments, git history, and configuration; authored
  10 distinct, reproducible fault-injection scenarios with scored ground truth.
- **Implemented a risk-based safety system**: 12 typed tools classified
  READ_ONLY/LOW_RISK/HIGH_RISK (risk computed per-call, not per-tool — e.g.
  restarting stateful infra is HIGH_RISK, stateless services LOW_RISK), a
  human-approval gate that genuinely pauses and resumes execution across
  process boundaries, and a hard-allowlisted sandbox executor with zero
  code paths to a real shell.
- **Engineered the agent loop as an explicit, persistent state machine**,
  not a bare while-loop around an LLM call: iteration/time/token budgets,
  duplicate-action detection via content hashing, consecutive-stall loop
  detection, and 5 machine-verifiable stopping conditions — all
  reconstructible from DB state alone, making runs resumable from a
  different process.
- **Built an LLM provider abstraction with automatic fallback**
  (Gemini → Ollama → a deterministic rule-based offline provider), making
  the exact same code path run hermetically in CI/tests with zero network
  or API-key dependency, and against a real hosted model in production —
  verified by running the identical test suite against both.
- **Built an evaluation harness** scoring root-cause accuracy, remediation
  success rate, human-escalation rate, unnecessary-action rate, mean
  tool-calls/iterations, time-to-diagnosis, and token cost across repeated
  runs of every scenario; committed a reproducible baseline (30/30 runs
  resolved correctly, ~5 iterations, ~3,270 tokens per incident).
- **Shipped an observability UI** (Next.js, live SSE/polling) rendering the
  investigation as it happens — timeline, hypotheses with confidence,
  tool-call log, remediation + verification, service health, and an
  execution-graph view — deliberately surfacing only
  decision/evidence/action/result, never raw model chain-of-thought.
- **Also exposed the same tool surface over MCP** (Model Context Protocol),
  so any MCP-compatible client can drive an investigation through the
  identical safety/sandbox boundary as the built-in agent.

## Skills demonstrated

Agentic system design (state machines over prompt loops) · LLM provider
abstraction & graceful degradation · safety-by-construction (allowlisting,
risk-based approval gating) · SQLAlchemy/relational modeling of persistent
agent state · FastAPI (REST + SSE, background task orchestration) ·
Next.js/TypeScript · deterministic simulation design · evaluation
methodology for non-deterministic systems · Docker/Compose (written,
documented as untested where infrastructure wasn't available — see
[PLAN.md](../PLAN.md)) · CI configuration.

## If asked "walk me through it" in an interview

1. Start from `scripts/demo.sh` — one command, no setup, resolves a real
   incident in your terminal. This proves it's not vaporware.
2. Open [docs/AGENT_LOOP.md](AGENT_LOOP.md)'s state diagram and point at
   the code: every node is a real phase transition in `agent/loop.py`, not
   a description of what an LLM *could* do.
3. Show the approval gate resolving a `HIGH_RISK` action from the UI —
   this is the one part that visibly demonstrates "the model doesn't get
   to just act."
4. Show `eval/results/baseline_offline_provider.json` and explain honestly
   what it does and doesn't prove (see [EVALUATION.md](EVALUATION.md)) —
   that intellectual honesty is itself worth signaling.
