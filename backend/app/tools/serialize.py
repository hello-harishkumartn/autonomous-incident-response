"""Turn ORM rows into plain JSON-safe dicts for tool results / event logs."""
from __future__ import annotations

import datetime as dt
from typing import Any

from app import models_db as m


def _iso(value: dt.datetime | None) -> str | None:
    return value.isoformat() if value else None


def log_to_dict(row: m.LogEntry) -> dict[str, Any]:
    return {"timestamp": _iso(row.timestamp), "level": row.level, "message": row.message, "service": row.service_name}


def metric_to_dict(row: m.MetricPoint) -> dict[str, Any]:
    return {"timestamp": _iso(row.timestamp), "value": row.value}


def span_to_dict(row: m.TraceSpan) -> dict[str, Any]:
    return {
        "span_id": row.span_id, "parent_span_id": row.parent_span_id, "service": row.service_name,
        "operation": row.operation, "start_ms": row.start_ms, "duration_ms": row.duration_ms, "status": row.status,
    }


def deployment_to_dict(row: m.Deployment) -> dict[str, Any]:
    return {
        "service": row.service_name, "version": row.version, "git_sha": row.git_sha,
        "deployed_at": _iso(row.deployed_at), "deployed_by": row.deployed_by, "status": row.status,
        "diff_summary": row.diff_summary, "is_rollback_of": row.is_rollback_of,
    }


def commit_to_dict(row: m.GitCommitRecord) -> dict[str, Any]:
    return {
        "sha": row.sha, "author": row.author, "message": row.message, "timestamp": _iso(row.timestamp),
        "files_changed": row.files_changed, "diff": row.diff,
    }


def config_to_dict(row: m.ConfigSnapshot) -> dict[str, Any]:
    return {
        "key": row.key, "value": row.value, "last_changed_at": _iso(row.last_changed_at),
        "changed_by": row.changed_by, "is_suspect": row.is_suspect,
    }


def service_state_to_dict(row: m.ServiceState) -> dict[str, Any]:
    return {
        "service": row.service_name, "cpu_pct": row.cpu_pct, "memory_pct": row.memory_pct,
        "latency_p50_ms": row.latency_p50_ms, "latency_p99_ms": row.latency_p99_ms,
        "error_rate": row.error_rate, "connections_active": row.connections_active,
        "connections_max": row.connections_max, "is_healthy": row.is_healthy, "extra": row.extra,
    }
