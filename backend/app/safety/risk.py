"""Risk policy: turns a tool's declared risk level into an approval decision.

READ_ONLY always auto-runs. HIGH_RISK NEVER auto-runs, regardless of any
config flag — the only override is `auto_approve_high_risk_for_eval`,
which is exclusively for headless benchmark runs against the simulator and
is never reachable from the interactive/demo path.
"""
from __future__ import annotations

from app.config import settings
from app.enums import ApprovalStatus, RiskLevel


def initial_approval_status(risk: RiskLevel, *, for_eval: bool = False) -> ApprovalStatus:
    if risk == RiskLevel.READ_ONLY:
        return ApprovalStatus.NOT_REQUIRED
    if risk == RiskLevel.LOW_RISK:
        return ApprovalStatus.AUTO_APPROVED if settings.auto_approve_low_risk else ApprovalStatus.PENDING
    if risk == RiskLevel.HIGH_RISK:
        if for_eval and settings.auto_approve_high_risk_for_eval:
            return ApprovalStatus.AUTO_APPROVED
        return ApprovalStatus.PENDING
    raise ValueError(f"Unknown risk level: {risk}")


def is_actionable(status: ApprovalStatus) -> bool:
    return status in (ApprovalStatus.NOT_REQUIRED, ApprovalStatus.AUTO_APPROVED, ApprovalStatus.APPROVED)
