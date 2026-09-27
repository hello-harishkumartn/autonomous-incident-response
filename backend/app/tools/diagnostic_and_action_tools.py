"""LOW_RISK diagnostics and the two HIGH/LOW-risk remediation actions.

`restart_service` and `rollback_deployment` are the ONLY tools that mutate
simulated infrastructure, and they go exclusively through
`SimulationEngine` — there is no shell, no subprocess, no network call.
That is the entire "sandbox executor": a hard allowlist of two methods.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.enums import RiskLevel, ServiceName
from app.tools.base import Tool, ToolContext

# Restarting shared, stateful infrastructure is riskier than restarting a
# stateless app service — this is what makes risk_for() depend on args.
_HIGH_RISK_RESTART_TARGETS = {ServiceName.POSTGRES, ServiceName.REDIS}

DiagnosticName = Literal["connection_pool_check", "memory_check", "latency_check", "dependency_ping", "disk_check"]


class ExecuteDiagnosticArgs(BaseModel):
    service: ServiceName
    diagnostic: DiagnosticName


class ExecuteDiagnosticTool(Tool):
    name = "execute_diagnostic"
    description = "Run a targeted, allowlisted diagnostic probe against a service (no state mutation)."
    args_model = ExecuteDiagnosticArgs
    default_risk = RiskLevel.LOW_RISK

    def run(self, ctx: ToolContext, args: ExecuteDiagnosticArgs) -> dict:
        return ctx.engine.execute_diagnostic(args.service, args.diagnostic)


class RestartServiceArgs(BaseModel):
    service: ServiceName
    reason: str = Field(..., description="Why this restart is expected to help.")


class RestartServiceTool(Tool):
    name = "restart_service"
    description = "Restart a service, clearing transient in-process state (connections, GC pressure, stuck breakers)."
    args_model = RestartServiceArgs
    default_risk = RiskLevel.LOW_RISK  # overridden for stateful infra in risk_for()

    def risk_for(self, args: RestartServiceArgs) -> RiskLevel:
        return RiskLevel.HIGH_RISK if args.service in _HIGH_RISK_RESTART_TARGETS else RiskLevel.LOW_RISK

    def run(self, ctx: ToolContext, args: RestartServiceArgs) -> dict:
        return ctx.engine.restart_service(args.service, scenario=ctx.scenario)


class RollbackDeploymentArgs(BaseModel):
    service: ServiceName
    reason: str = Field(..., description="Why the current deployment is suspected to be the cause.")


class RollbackDeploymentTool(Tool):
    name = "rollback_deployment"
    description = "Roll back a service's active deployment to its previous version."
    args_model = RollbackDeploymentArgs
    default_risk = RiskLevel.HIGH_RISK

    def run(self, ctx: ToolContext, args: RollbackDeploymentArgs) -> dict:
        return ctx.engine.rollback_deployment(args.service, scenario=ctx.scenario)


class CreateIncidentNoteArgs(BaseModel):
    text: str = Field(..., description="Human-readable note to attach to the incident timeline.")


class CreateIncidentNoteTool(Tool):
    name = "create_incident_note"
    description = "Attach a free-text note to the incident record (does not affect simulated infrastructure)."
    args_model = CreateIncidentNoteArgs
    default_risk = RiskLevel.READ_ONLY

    def run(self, ctx: ToolContext, args: CreateIncidentNoteArgs) -> dict:
        from app import models_db as m

        note = m.IncidentNote(incident_id=ctx.incident.id, iteration=ctx.incident.iteration, text=args.text)
        ctx.session.add(note)
        ctx.session.flush()
        return {"note_id": note.id, "text": args.text}
