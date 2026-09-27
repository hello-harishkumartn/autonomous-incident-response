"""Approval lifecycle for proposed remediation actions."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models_db as m
from app.enums import ApprovalStatus, RiskLevel
from app.safety.risk import initial_approval_status


def propose_action(
    session: Session, incident: m.Incident, iteration: int, tool_name: str, args: dict,
    risk_level: RiskLevel, rationale: str, *, for_eval: bool = False,
) -> m.ActionLog:
    status = initial_approval_status(risk_level, for_eval=for_eval)
    action = m.ActionLog(
        incident_id=incident.id, iteration=iteration, tool_name=tool_name, risk_level=risk_level.value,
        args=args, rationale=rationale, approval_status=status.value,
        decided_at=dt.datetime.now(dt.timezone.utc) if status != ApprovalStatus.PENDING else None,
        approved_by="system" if status == ApprovalStatus.AUTO_APPROVED else None,
    )
    session.add(action)
    session.flush()
    return action


def decide(session: Session, action_id: str, approved: bool, decided_by: str, reason: str | None = None) -> m.ActionLog:
    action = session.execute(select(m.ActionLog).where(m.ActionLog.id == action_id)).scalar_one()
    if action.approval_status != ApprovalStatus.PENDING.value:
        raise ValueError(f"Action {action_id} is not pending (status={action.approval_status})")
    action.approval_status = ApprovalStatus.APPROVED.value if approved else ApprovalStatus.REJECTED.value
    action.approved_by = decided_by
    action.approval_reason = reason
    action.decided_at = dt.datetime.now(dt.timezone.utc)
    session.flush()
    return action


def list_pending(session: Session, incident_id: str | None = None) -> list[m.ActionLog]:
    stmt = select(m.ActionLog).where(m.ActionLog.approval_status == ApprovalStatus.PENDING.value)
    if incident_id:
        stmt = stmt.where(m.ActionLog.incident_id == incident_id)
    return list(session.execute(stmt).scalars())
