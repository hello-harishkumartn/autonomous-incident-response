"""ORM row -> plain JSON-safe dict, for API responses."""
from __future__ import annotations

import datetime as dt
from typing import Any

from app import models_db as m


def _iso(value: dt.datetime | None) -> str | None:
    return value.isoformat() if value else None


def incident_summary(row: m.Incident) -> dict[str, Any]:
    return {
        "id": row.id, "scenario_type": row.scenario_type, "seed": row.seed, "phase": row.phase,
        "stopping_reason": row.stopping_reason, "alert_summary": row.alert_summary,
        "iteration": row.iteration, "tool_call_count": row.tool_call_count, "tokens_used": row.tokens_used,
        "created_at": _iso(row.created_at), "resolved_at": _iso(row.resolved_at),
    }


def incident_detail(row: m.Incident) -> dict[str, Any]:
    return {
        **incident_summary(row),
        "ground_truth_root_cause": row.ground_truth_root_cause,
        "ground_truth_fix_tool": row.ground_truth_fix_tool,
        "confirmed_root_cause": row.confirmed_root_cause,
        "max_iterations": row.max_iterations, "max_seconds": row.max_seconds, "max_tokens": row.max_tokens,
    }


def event_dict(row: m.IncidentEvent) -> dict[str, Any]:
    return {
        "id": row.id, "iteration": row.iteration, "phase": row.phase, "kind": row.kind,
        "summary": row.summary, "detail": row.detail, "created_at": _iso(row.created_at),
    }


def hypothesis_dict(row: m.Hypothesis) -> dict[str, Any]:
    return {
        "id": row.id, "description": row.description, "target_service": row.target_service,
        "confidence": row.confidence, "status": row.status,
        "created_iteration": row.created_iteration, "updated_iteration": row.updated_iteration,
    }


def tool_call_dict(row: m.ToolCallLog) -> dict[str, Any]:
    return {
        "id": row.id, "iteration": row.iteration, "tool_name": row.tool_name, "risk_level": row.risk_level,
        "args": row.args, "result": row.result, "status": row.status, "started_at": _iso(row.started_at),
    }


def action_dict(row: m.ActionLog) -> dict[str, Any]:
    return {
        "id": row.id, "iteration": row.iteration, "tool_name": row.tool_name, "risk_level": row.risk_level,
        "args": row.args, "rationale": row.rationale, "approval_status": row.approval_status,
        "approved_by": row.approved_by, "approval_reason": row.approval_reason, "executed": row.executed,
        "result": row.result, "created_at": _iso(row.created_at), "decided_at": _iso(row.decided_at),
        "executed_at": _iso(row.executed_at),
    }


def verification_dict(row: m.VerificationResult) -> dict[str, Any]:
    return {
        "id": row.id, "iteration": row.iteration, "action_id": row.action_id, "healthy": row.healthy,
        "checks": row.checks, "created_at": _iso(row.created_at),
    }


def note_dict(row: m.IncidentNote) -> dict[str, Any]:
    return {"id": row.id, "iteration": row.iteration, "text": row.text, "created_at": _iso(row.created_at)}


def service_state_dict(row: m.ServiceState) -> dict[str, Any]:
    return {
        "service": row.service_name, "cpu_pct": row.cpu_pct, "memory_pct": row.memory_pct,
        "latency_p50_ms": row.latency_p50_ms, "latency_p99_ms": row.latency_p99_ms,
        "error_rate": row.error_rate, "connections_active": row.connections_active,
        "connections_max": row.connections_max, "is_healthy": row.is_healthy,
    }
