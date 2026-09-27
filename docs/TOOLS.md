# Tools

Every tool implements the same interface (`backend/app/tools/base.py:Tool`):
a name, a description, a typed Pydantic `args_model`, a `default_risk`
(overridable per-call via `risk_for(args)`), and a `run(ctx, args)` method
that receives a `ToolContext` — never raw session/engine access, and never
anything resembling a shell. `ToolContext` bundles the DB session, the
`SimulationEngine` for this incident, the `Incident` row, and the
`IncidentScenario` (used internally only to score whether a remediation
actually fixed the fault — the agent never reads it).

`GET /tools` (FastAPI) and the MCP server's `list_tools()` both serve
`registry.list_tool_schemas()` — the exact same schemas, so there is one
source of truth for what a caller can invoke, whether that caller is the
built-in loop, a human via the UI's tool-call log, or an external MCP client.

## READ_ONLY (auto-execute, never touch simulated infrastructure state)

| Tool | Args | Returns |
| --- | --- | --- |
| `query_logs` | `service?`, `level?`, `since_seconds=900`, `limit≤200`, `contains?` | matching log entries |
| `query_metrics` | `service`, `metric_name`, `since_seconds=900` | a time series + latest point |
| `get_trace` | `service?` or `trace_id?` | spans for the most recent (or specified) distributed trace |
| `inspect_service` | `service` | current cpu/memory/latency/error-rate/connections snapshot |
| `get_deployment` | `service`, `version?` | current + recent deployment history (version, git sha, diff summary) |
| `get_git_diff` | `service`, `sha?` | a commit's message/author/files/diff — latest by default |
| `get_config` | `service` | current config key/values, flagging recently-changed/suspect keys |
| `run_health_check` | `service?` | per-service healthy/error-rate/latency/connections, or whole fleet |
| `create_incident_note` | `text` | attaches a free-text note to the incident timeline |

`create_incident_note` mutates the DB (it writes a note) but never touches
simulated infrastructure, which is the distinction `READ_ONLY` actually
encodes here — see [SAFETY.md](SAFETY.md).

## LOW_RISK (auto-execute if `auto_approve_low_risk`, else queued for approval)

| Tool | Args | Returns |
| --- | --- | --- |
| `execute_diagnostic` | `service`, `diagnostic` (`connection_pool_check`\|`memory_check`\|`latency_check`\|`dependency_ping`\|`disk_check`) | a targeted synthetic probe result |

## LOW_RISK or HIGH_RISK depending on target, and HIGH_RISK always

| Tool | Args | Risk | Returns |
| --- | --- | --- | --- |
| `restart_service` | `service`, `reason` | `HIGH_RISK` for `postgres`/`redis` (stateful, shared infra); `LOW_RISK` for the four stateless app services | `{restarted, healthy_after}` |
| `rollback_deployment` | `service`, `reason` | always `HIGH_RISK` | `{rolled_back, to_version, healthy_after}` |

`restart_service`'s risk is decided by `RestartServiceTool.risk_for(args)`
(`backend/app/tools/diagnostic_and_action_tools.py`) — risk is a function
of arguments, not just the tool name, which is what lets six of the ten
incident scenarios auto-resolve while the other four (anything touching
Redis/Postgres directly, or any `rollback_deployment`) require a human.

## The sandbox allowlist

`restart_service` and `rollback_deployment` are the **only** tools that can
mutate simulated world state, and both are only reachable through
`SandboxExecutor.execute()` (`backend/app/safety/sandbox.py`), which
hard-codes `ALLOWED_ACTION_TOOLS = {"restart_service", "rollback_deployment"}`
and refuses everything else with a `SandboxViolation`. Both tools then only
ever call `SimulationEngine.restart_service()` /
`.rollback_deployment()` — there is no code path from any tool to a real
shell, subprocess, or socket, anywhere in this project.

## MCP interface

`backend/app/mcp_server/server.py` exposes the same 12 tools over the
Model Context Protocol (stdio transport), for any MCP client — not just
the built-in loop — to drive an investigation. Every call takes a required
`incident_id` (there's no shared/global world; each incident is its own
isolated fleet snapshot), and remediation calls are routed through the
same `SandboxExecutor`, so the allowlist guarantee holds regardless of
which caller is driving:

```bash
cd backend && python -m app.mcp_server.server
```

Run standalone with any MCP-compatible client (Claude Desktop, etc.),
pointed at the incident id printed by `scripts/inject_incident.py`.
