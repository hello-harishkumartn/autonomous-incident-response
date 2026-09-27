"""READ_ONLY observation tools — never mutate simulated world state."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.enums import RiskLevel, ServiceName
from app.tools import serialize as ser
from app.tools.base import Tool, ToolContext


class QueryLogsArgs(BaseModel):
    service: ServiceName | None = Field(None, description="Restrict to one service; omit for all services.")
    level: str | None = Field(None, description="Filter by level, e.g. ERROR, WARN, INFO, DEBUG.")
    since_seconds: int = Field(900, description="Look back this many seconds from now.")
    limit: int = Field(50, le=200)
    contains: str | None = Field(None, description="Case-insensitive substring filter on the message.")


class QueryLogsTool(Tool):
    name = "query_logs"
    description = "Search recent log entries, optionally filtered by service, level, and text."
    args_model = QueryLogsArgs
    default_risk = RiskLevel.READ_ONLY

    def run(self, ctx: ToolContext, args: QueryLogsArgs) -> dict:
        rows = ctx.engine.get_logs(
            service=args.service, level=args.level, since_seconds=args.since_seconds,
            limit=args.limit, contains=args.contains,
        )
        return {"count": len(rows), "logs": [ser.log_to_dict(r) for r in rows]}


class QueryMetricsArgs(BaseModel):
    service: ServiceName
    metric_name: str = Field(..., description="One of cpu_pct, memory_pct, latency_p50_ms, latency_p99_ms, error_rate, connections_active.")
    since_seconds: int = Field(900, description="Look back this many seconds from now.")


class QueryMetricsTool(Tool):
    name = "query_metrics"
    description = "Fetch a time series for one metric on one service."
    args_model = QueryMetricsArgs
    default_risk = RiskLevel.READ_ONLY

    def run(self, ctx: ToolContext, args: QueryMetricsArgs) -> dict:
        rows = ctx.engine.get_metrics(args.service, args.metric_name, args.since_seconds)
        return {
            "service": args.service.value, "metric_name": args.metric_name,
            "points": [ser.metric_to_dict(r) for r in rows],
            "latest": ser.metric_to_dict(rows[-1]) if rows else None,
        }


class GetTraceArgs(BaseModel):
    service: ServiceName | None = Field(None, description="Get the most recent trace touching this service.")
    trace_id: str | None = Field(None, description="Fetch a specific trace by id instead.")


class GetTraceTool(Tool):
    name = "get_trace"
    description = "Fetch a distributed trace (spans across services) — the most recent one by default."
    args_model = GetTraceArgs
    default_risk = RiskLevel.READ_ONLY

    def run(self, ctx: ToolContext, args: GetTraceArgs) -> dict:
        if args.trace_id:
            trace_id, spans = ctx.engine.get_trace_by_id(args.trace_id)
        else:
            result = ctx.engine.get_recent_trace(args.service)
            if result is None:
                return {"trace_id": None, "spans": []}
            trace_id, spans = result
        return {"trace_id": trace_id, "spans": [ser.span_to_dict(s) for s in spans]}


class InspectServiceArgs(BaseModel):
    service: ServiceName


class InspectServiceTool(Tool):
    name = "inspect_service"
    description = "Get the current resource/latency/error/connection snapshot for a service."
    args_model = InspectServiceArgs
    default_risk = RiskLevel.READ_ONLY

    def run(self, ctx: ToolContext, args: InspectServiceArgs) -> dict:
        state = ctx.engine.get_service_state(args.service)
        return ser.service_state_to_dict(state)


class GetDeploymentArgs(BaseModel):
    service: ServiceName
    version: str | None = Field(None, description="Specific version; omit for the currently active deployment.")


class GetDeploymentTool(Tool):
    name = "get_deployment"
    description = "Get deployment metadata (version, git sha, who/when, diff summary) for a service."
    args_model = GetDeploymentArgs
    default_risk = RiskLevel.READ_ONLY

    def run(self, ctx: ToolContext, args: GetDeploymentArgs) -> dict:
        row = ctx.engine.get_deployment(args.service, args.version)
        history = ctx.engine.list_deployments(args.service, limit=5)
        return {
            "current": ser.deployment_to_dict(row) if row else None,
            "recent_history": [ser.deployment_to_dict(r) for r in history],
        }


class GetGitDiffArgs(BaseModel):
    service: ServiceName
    sha: str | None = Field(None, description="Specific commit sha; omit for the latest commit.")


class GetGitDiffTool(Tool):
    name = "get_git_diff"
    description = "Get a git commit (message, author, files changed, diff) for a service — latest by default."
    args_model = GetGitDiffArgs
    default_risk = RiskLevel.READ_ONLY

    def run(self, ctx: ToolContext, args: GetGitDiffArgs) -> dict:
        row = ctx.engine.get_git_diff(args.service, args.sha)
        return {"commit": ser.commit_to_dict(row) if row else None}


class GetConfigArgs(BaseModel):
    service: ServiceName


class GetConfigTool(Tool):
    name = "get_config"
    description = "Get current configuration key/values for a service, flagging recently-changed/suspect keys."
    args_model = GetConfigArgs
    default_risk = RiskLevel.READ_ONLY

    def run(self, ctx: ToolContext, args: GetConfigArgs) -> dict:
        rows = ctx.engine.get_config(args.service)
        return {"service": args.service.value, "config": [ser.config_to_dict(r) for r in rows]}


class RunHealthCheckArgs(BaseModel):
    service: ServiceName | None = Field(None, description="Omit to check the whole fleet.")


class RunHealthCheckTool(Tool):
    name = "run_health_check"
    description = "Run a synthetic health check against one service or the whole fleet."
    args_model = RunHealthCheckArgs
    default_risk = RiskLevel.READ_ONLY

    def run(self, ctx: ToolContext, args: RunHealthCheckArgs) -> dict:
        return ctx.engine.run_health_check(args.service)
