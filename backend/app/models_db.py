"""SQLAlchemy ORM models.

These tables ARE the agent's persistent memory for a run (observations,
hypotheses, tool calls, actions, verification results) plus the simulated
world's telemetry (logs/metrics/traces/deploys/config/git commits), scoped
per incident so runs are isolated and reproducible.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.enums import (
    ApprovalStatus,
    HypothesisStatus,
    IncidentPhase,
    IncidentType,
    RiskLevel,
    ToolCallStatus,
)


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scenario_type: Mapped[str] = mapped_column(String(64))
    seed: Mapped[int] = mapped_column(Integer)
    phase: Mapped[str] = mapped_column(String(64), default=IncidentPhase.ALERTED.value)
    stopping_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    alert_summary: Mapped[str] = mapped_column(Text, default="")
    ground_truth_root_cause: Mapped[str] = mapped_column(Text, default="")
    ground_truth_fix_tool: Mapped[str] = mapped_column(String(64), default="")
    confirmed_root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)

    iteration: Mapped[int] = mapped_column(Integer, default=0)
    tool_call_count: Mapped[int] = mapped_column(Integer, default=0)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)

    max_iterations: Mapped[int] = mapped_column(Integer, default=15)
    max_seconds: Mapped[int] = mapped_column(Integer, default=120)
    max_tokens: Mapped[int] = mapped_column(Integer, default=60_000)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    observations: Mapped[list["Observation"]] = relationship(back_populates="incident", cascade="all, delete-orphan")
    hypotheses: Mapped[list["Hypothesis"]] = relationship(back_populates="incident", cascade="all, delete-orphan")
    tool_calls: Mapped[list["ToolCallLog"]] = relationship(back_populates="incident", cascade="all, delete-orphan")
    actions: Mapped[list["ActionLog"]] = relationship(back_populates="incident", cascade="all, delete-orphan")
    verifications: Mapped[list["VerificationResult"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )
    notes: Mapped[list["IncidentNote"]] = relationship(back_populates="incident", cascade="all, delete-orphan")
    events: Mapped[list["IncidentEvent"]] = relationship(back_populates="incident", cascade="all, delete-orphan")


class IncidentEvent(Base):
    """Flat, ordered timeline of everything shown to the UI — decision/evidence/action/result only."""

    __tablename__ = "incident_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id"))
    iteration: Mapped[int] = mapped_column(Integer)
    phase: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(32))  # decision | evidence | action | result
    summary: Mapped[str] = mapped_column(Text)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    incident: Mapped[Incident] = relationship(back_populates="events")


class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id"))
    iteration: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    incident: Mapped[Incident] = relationship(back_populates="observations")


class Hypothesis(Base):
    __tablename__ = "hypotheses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id"))
    description: Mapped[str] = mapped_column(Text)
    target_service: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[str] = mapped_column(String(16), default=HypothesisStatus.ACTIVE.value)
    evidence_for: Mapped[list] = mapped_column(JSON, default=list)
    evidence_against: Mapped[list] = mapped_column(JSON, default=list)
    created_iteration: Mapped[int] = mapped_column(Integer, default=0)
    updated_iteration: Mapped[int] = mapped_column(Integer, default=0)

    incident: Mapped[Incident] = relationship(back_populates="hypotheses")


class ToolCallLog(Base):
    __tablename__ = "tool_calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id"))
    iteration: Mapped[int] = mapped_column(Integer)
    tool_name: Mapped[str] = mapped_column(String(64))
    risk_level: Mapped[str] = mapped_column(String(16))
    args: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default=ToolCallStatus.SUCCESS.value)
    dedup_hash: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)

    incident: Mapped[Incident] = relationship(back_populates="tool_calls")


class ActionLog(Base):
    """A proposed/attempted remediation action — distinct from read-only tool calls."""

    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id"))
    iteration: Mapped[int] = mapped_column(Integer)
    tool_name: Mapped[str] = mapped_column(String(64))
    risk_level: Mapped[str] = mapped_column(String(16))
    args: Mapped[dict] = mapped_column(JSON, default=dict)
    rationale: Mapped[str] = mapped_column(Text, default="")
    approval_status: Mapped[str] = mapped_column(String(16), default=ApprovalStatus.NOT_REQUIRED.value)
    approved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approval_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed: Mapped[bool] = mapped_column(default=False)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    incident: Mapped[Incident] = relationship(back_populates="actions")


class VerificationResult(Base):
    __tablename__ = "verification_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id"))
    iteration: Mapped[int] = mapped_column(Integer)
    action_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("actions.id"), nullable=True)
    healthy: Mapped[bool] = mapped_column(default=False)
    checks: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    incident: Mapped[Incident] = relationship(back_populates="verifications")


class IncidentNote(Base):
    __tablename__ = "incident_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id"))
    iteration: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    incident: Mapped[Incident] = relationship(back_populates="notes")


# ---------------------------------------------------------------------------
# Simulated world telemetry — scoped per incident so each run is an isolated,
# reproducible fleet snapshot.
# ---------------------------------------------------------------------------


class ServiceState(Base):
    __tablename__ = "service_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id"), index=True)
    service_name: Mapped[str] = mapped_column(String(64))
    cpu_pct: Mapped[float] = mapped_column(Float, default=20.0)
    memory_pct: Mapped[float] = mapped_column(Float, default=30.0)
    latency_p50_ms: Mapped[float] = mapped_column(Float, default=20.0)
    latency_p99_ms: Mapped[float] = mapped_column(Float, default=80.0)
    error_rate: Mapped[float] = mapped_column(Float, default=0.001)
    connections_active: Mapped[int] = mapped_column(Integer, default=5)
    connections_max: Mapped[int] = mapped_column(Integer, default=100)
    is_healthy: Mapped[bool] = mapped_column(default=True)
    last_deploy_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class LogEntry(Base):
    __tablename__ = "log_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id"), index=True)
    service_name: Mapped[str] = mapped_column(String(64))
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    level: Mapped[str] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(Text)
    trace_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class MetricPoint(Base):
    __tablename__ = "metric_points"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id"), index=True)
    service_name: Mapped[str] = mapped_column(String(64))
    metric_name: Mapped[str] = mapped_column(String(64))
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    value: Mapped[float] = mapped_column(Float)


class TraceSpan(Base):
    __tablename__ = "trace_spans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id"), index=True)
    trace_id: Mapped[str] = mapped_column(String(36), index=True)
    span_id: Mapped[str] = mapped_column(String(36))
    parent_span_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    service_name: Mapped[str] = mapped_column(String(64))
    operation: Mapped[str] = mapped_column(String(128))
    start_ms: Mapped[float] = mapped_column(Float)
    duration_ms: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default="ok")


class Deployment(Base):
    __tablename__ = "deployments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id"), index=True)
    service_name: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(32))
    git_sha: Mapped[str] = mapped_column(String(40))
    deployed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    deployed_by: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="active")
    diff_summary: Mapped[str] = mapped_column(Text, default="")
    is_rollback_of: Mapped[str | None] = mapped_column(String(36), nullable=True)


class GitCommitRecord(Base):
    __tablename__ = "git_commits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id"), index=True)
    sha: Mapped[str] = mapped_column(String(40))
    service_name: Mapped[str] = mapped_column(String(64))
    author: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    files_changed: Mapped[list] = mapped_column(JSON, default=list)
    diff: Mapped[str] = mapped_column(Text, default="")


class ConfigSnapshot(Base):
    __tablename__ = "config_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id"), index=True)
    service_name: Mapped[str] = mapped_column(String(64))
    key: Mapped[str] = mapped_column(String(128))
    value: Mapped[str] = mapped_column(Text)
    last_changed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    changed_by: Mapped[str] = mapped_column(String(64))
    is_suspect: Mapped[bool] = mapped_column(default=False)
