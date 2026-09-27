# Safety

## Risk classification

Three levels (`backend/app/enums.py:RiskLevel`), assigned per tool call via
`Tool.risk_for(args)` — a function of the *specific call*, not a static
label on the tool name (see [TOOLS.md](TOOLS.md) for why `restart_service`
isn't one risk level):

- **READ_ONLY** — cannot affect simulated infrastructure. Always executes
  automatically.
- **LOW_RISK** — a real but bounded/reversible action (e.g. restarting a
  stateless app service). Auto-executes when
  `Settings.auto_approve_low_risk` is true (the default) — this is the
  spec's "can be configured for automatic execution."
- **HIGH_RISK** — restarting shared/stateful infrastructure
  (Postgres/Redis) or rolling back a deployment. **Never** auto-executes
  in the interactive/demo path, regardless of any config flag.

## The approval gate

```mermaid
flowchart TD
    A[Remediation proposed] --> B{risk_for(args)}
    B -->|READ_ONLY| C[NOT_REQUIRED]
    B -->|LOW_RISK| D{auto_approve_low_risk?}
    D -->|true| E[AUTO_APPROVED]
    D -->|false| F[PENDING]
    B -->|HIGH_RISK| G{for_eval AND auto_approve_high_risk_for_eval?}
    G -->|true, eval run only| E
    G -->|false — the normal path| F
    C --> H[Execute via SandboxExecutor]
    E --> H
    F --> I[AgentLoop pauses:<br/>phase=awaiting_approval<br/>run_to_completion returns None]
    I --> J[Human calls approval.decide via API/CLI]
    J -->|approved| H
    J -->|rejected| K[Loop resumes investigating<br/>without this action]
    H --> L[run_health_check]
```

`safety/risk.py:initial_approval_status` is the only place this decision
is made, and it's a pure function — no model is ever asked "should this be
approved?"; the model proposes an action, the code classifies and gates it.

`auto_approve_high_risk_for_eval` is the one flag that can bypass a
HIGH_RISK gate, and it is scoped tightly on purpose:

- it's only read when `propose_action(..., for_eval=True)`, and `for_eval`
  is only ever `True` from `backend/app/eval/benchmark.py` — the CLI
  (`scripts/run_agent.py`), the FastAPI investigate endpoint, and every
  interactive path all construct `AgentLoop` with the default `for_eval=False`;
- `run_benchmark()` flips it to `True` for the duration of the benchmark
  and restores the previous value in a `finally` block, so it can never
  leak into a subsequent interactive run in the same process.

This is what "never give unrestricted shell access" and "high-risk actions
require human approval" mean operationally here: the gate is enforced in
code that the model cannot influence, not in a prompt instruction the
model is asked to follow.

## Approve/reject is a real pause, not a fake one

When a `HIGH_RISK` action is proposed, `AgentLoop._do_remediate` sets
`Incident.phase = "awaiting_approval"`, writes a `PENDING` `ActionLog` row,
and `run_to_completion()` returns `None` — the Python call stack unwinds
completely. Nothing is polling or blocked in memory. A decision is
recorded by `safety/approval.py:decide()` (called from a *different*
process — the FastAPI approvals endpoint, or a second CLI invocation)
purely by updating that `ActionLog` row. `AgentLoop.resume_after_approval()`
reconstructs everything it needs (`agent/factory.py:load_agent_loop`) from
`(session, incident_id)` alone and continues:

- **approved** → `SandboxExecutor.execute()` runs the action, then
  verification, then either resolves or returns to investigating;
- **rejected** → the loop returns to `collecting_observations` and keeps
  investigating *without* that action — it doesn't retry the same rejected
  action; the next proposal has to come from re-evaluating the evidence
  (see `test_agent_loop_e2e.py::test_rejected_approval_continues_investigation_then_can_be_reapproved`).

## The sandbox executor

`backend/app/safety/sandbox.py:SandboxExecutor` is a ~15-line hard
allowlist:

```python
ALLOWED_ACTION_TOOLS = frozenset({"restart_service", "rollback_deployment"})
```

Anything else raises `SandboxViolation` and the loop stops with
`NO_VALID_ACTIONS_REMAINING` rather than attempting it. Both allowed tools
only ever call methods on `SimulationEngine` — there is no shell,
subprocess, or network call anywhere in the remediation path. This holds
for every caller: the built-in loop, the FastAPI approval-resume path, and
the MCP server (`mcp_server/server.py` routes remediation calls through
the exact same `SandboxExecutor`).

## What's *not* covered

This is a simulator's safety model, scoped to what the simulator can do —
`restart_service`/`rollback_deployment` mutate rows in `service_states` and
`deployments` tables, nothing external. The design (typed args, risk
classification independent of the model, a hard allowlist, an approval
gate that's a real pause) is meant to generalize to a system where those
two tools call real infrastructure APIs; this project doesn't claim to
have built that integration.
