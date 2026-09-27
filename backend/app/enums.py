"""Shared enums — the vocabulary of the state machine, safety system, and simulator."""
from __future__ import annotations

import enum


class ServiceName(str, enum.Enum):
    API_GATEWAY = "api_gateway"
    USER_SERVICE = "user_service"
    ORDER_SERVICE = "order_service"
    PAYMENT_SERVICE = "payment_service"
    POSTGRES = "postgres"
    REDIS = "redis"


class IncidentPhase(str, enum.Enum):
    """Explicit state-machine phases — mirrors the loop diagram in the spec."""

    ALERTED = "alerted"
    COLLECTING_OBSERVATIONS = "collecting_observations"
    GENERATING_HYPOTHESES = "generating_hypotheses"
    SELECTING_INVESTIGATION = "selecting_investigation"
    CALLING_TOOL = "calling_tool"
    ANALYZING_RESULTS = "analyzing_results"
    UPDATING_HYPOTHESES = "updating_hypotheses"
    ROOT_CAUSE_CHECK = "root_cause_check"
    GENERATING_REMEDIATION = "generating_remediation"
    RISK_CLASSIFICATION = "risk_classification"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING_REMEDIATION = "executing_remediation"
    VERIFYING_HEALTH = "verifying_health"
    ROLLING_BACK = "rolling_back"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    BUDGET_EXHAUSTED = "budget_exhausted"
    NO_VALID_ACTIONS = "no_valid_actions"


class StoppingReason(str, enum.Enum):
    SERVICE_HEALTHY = "service_healthy"
    INCIDENT_RESOLVED = "incident_resolved"
    BUDGET_EXHAUSTED = "budget_exhausted"
    HUMAN_ESCALATION_REQUIRED = "human_escalation_required"
    NO_VALID_ACTIONS_REMAINING = "no_valid_actions_remaining"
    LOOP_DETECTED = "loop_detected"


class RiskLevel(str, enum.Enum):
    READ_ONLY = "READ_ONLY"
    LOW_RISK = "LOW_RISK"
    HIGH_RISK = "HIGH_RISK"


class ApprovalStatus(str, enum.Enum):
    NOT_REQUIRED = "not_required"
    AUTO_APPROVED = "auto_approved"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class HypothesisStatus(str, enum.Enum):
    ACTIVE = "active"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ToolCallStatus(str, enum.Enum):
    SUCCESS = "success"
    ERROR = "error"


class IncidentType(str, enum.Enum):
    DB_CONNECTION_EXHAUSTION = "db_connection_exhaustion"
    MEMORY_SPIKE = "memory_spike"
    API_LATENCY_INCREASE = "api_latency_increase"
    BAD_DEPLOYMENT = "bad_deployment"
    REDIS_FAILURE = "redis_failure"
    CONFIG_ERROR = "config_error"
    DEPENDENCY_TIMEOUT = "dependency_timeout"
    DISK_SPACE_EXHAUSTION = "disk_space_exhaustion"
    CASCADING_RETRY_STORM = "cascading_retry_storm"
    CREDENTIAL_EXPIRY = "credential_expiry"
