"""Incident REST endpoints + SSE stream. Investigation runs in a background
thread with its own DB session so polling/streaming GETs see live progress."""
from __future__ import annotations

import asyncio
import logging
import threading

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from app import models_db as m
from app.agent.factory import create_incident, load_agent_loop
from app.api import graph, serializers as ser
from app.db import SessionLocal, session_scope
from app.enums import ApprovalStatus, IncidentType
from app.safety import approval

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/incidents", tags=["incidents"])

_running_lock = threading.Lock()
_running_ids: set[str] = set()


class CreateIncidentRequest(BaseModel):
    scenario_type: IncidentType
    seed: int | None = None


class InvestigateRequest(BaseModel):
    approve_all: bool = False
    step_delay: float = 0.6


class ApprovalDecisionRequest(BaseModel):
    approved: bool
    decided_by: str = "ui-operator"
    reason: str | None = None


@router.get("/scenarios")
def list_scenarios():
    from app.simulator.scenarios import SCENARIOS

    return [
        {"type": s.type.value, "title": s.title, "affected_services": [svc.value for svc in s.affected_services]}
        for s in SCENARIOS.values()
    ]


@router.post("")
def create(req: CreateIncidentRequest):
    with session_scope() as session:
        incident = create_incident(session, req.scenario_type, req.seed)
        return ser.incident_detail(incident)


@router.get("")
def list_incidents():
    with session_scope() as session:
        rows = session.execute(select(m.Incident).order_by(m.Incident.created_at.desc())).scalars().all()
        return [ser.incident_summary(r) for r in rows]


def _get_incident_or_404(session, incident_id: str) -> m.Incident:
    incident = session.get(m.Incident, incident_id)
    if incident is None:
        raise HTTPException(404, f"Incident {incident_id} not found")
    return incident


@router.get("/{incident_id}")
def get_incident(incident_id: str):
    with session_scope() as session:
        return ser.incident_detail(_get_incident_or_404(session, incident_id))


@router.get("/{incident_id}/events")
def get_events(incident_id: str):
    with session_scope() as session:
        _get_incident_or_404(session, incident_id)
        stmt = select(m.IncidentEvent).where(m.IncidentEvent.incident_id == incident_id).order_by(m.IncidentEvent.created_at)
        return [ser.event_dict(r) for r in session.execute(stmt).scalars()]


@router.get("/{incident_id}/hypotheses")
def get_hypotheses(incident_id: str):
    with session_scope() as session:
        _get_incident_or_404(session, incident_id)
        stmt = select(m.Hypothesis).where(m.Hypothesis.incident_id == incident_id).order_by(m.Hypothesis.created_iteration)
        return [ser.hypothesis_dict(r) for r in session.execute(stmt).scalars()]


@router.get("/{incident_id}/tool-calls")
def get_tool_calls(incident_id: str):
    with session_scope() as session:
        _get_incident_or_404(session, incident_id)
        stmt = select(m.ToolCallLog).where(m.ToolCallLog.incident_id == incident_id).order_by(m.ToolCallLog.started_at)
        return [ser.tool_call_dict(r) for r in session.execute(stmt).scalars()]


@router.get("/{incident_id}/actions")
def get_actions(incident_id: str):
    with session_scope() as session:
        _get_incident_or_404(session, incident_id)
        stmt = select(m.ActionLog).where(m.ActionLog.incident_id == incident_id).order_by(m.ActionLog.created_at)
        return [ser.action_dict(r) for r in session.execute(stmt).scalars()]


@router.get("/{incident_id}/verifications")
def get_verifications(incident_id: str):
    with session_scope() as session:
        _get_incident_or_404(session, incident_id)
        stmt = select(m.VerificationResult).where(m.VerificationResult.incident_id == incident_id).order_by(m.VerificationResult.created_at)
        return [ser.verification_dict(r) for r in session.execute(stmt).scalars()]


@router.get("/{incident_id}/services")
def get_services(incident_id: str):
    with session_scope() as session:
        _get_incident_or_404(session, incident_id)
        stmt = select(m.ServiceState).where(m.ServiceState.incident_id == incident_id)
        return [ser.service_state_dict(r) for r in session.execute(stmt).scalars()]


@router.get("/{incident_id}/graph")
def get_graph(incident_id: str):
    with session_scope() as session:
        incident = _get_incident_or_404(session, incident_id)
        stmt = select(m.IncidentEvent.phase).where(m.IncidentEvent.incident_id == incident_id).distinct()
        visited = {row[0] for row in session.execute(stmt)}
        return graph.build_graph(visited, incident.phase)


def _run_investigation(incident_id: str, approve_all: bool, step_delay: float) -> None:
    session = SessionLocal()
    try:
        loop = load_agent_loop(session, incident_id)
        result = loop.run_to_completion(step_delay=step_delay)
        while result is None and approve_all:
            pending = approval.list_pending(session, incident_id)
            if not pending:
                break
            approval.decide(session, pending[0].id, approved=True, decided_by="auto-approver")
            session.commit()
            result = loop.resume_after_approval(step_delay=step_delay)
    except Exception:  # noqa: BLE001
        logger.exception("Investigation failed for incident %s", incident_id)
    finally:
        with _running_lock:
            _running_ids.discard(incident_id)
        session.close()


@router.post("/{incident_id}/investigate")
def start_investigation(incident_id: str, req: InvestigateRequest, background_tasks: BackgroundTasks):
    with session_scope() as session:
        _get_incident_or_404(session, incident_id)
    with _running_lock:
        if incident_id in _running_ids:
            raise HTTPException(409, "Investigation already running for this incident")
        _running_ids.add(incident_id)
    background_tasks.add_task(_run_investigation, incident_id, req.approve_all, req.step_delay)
    return {"status": "started"}


@router.get("/{incident_id}/investigate/status")
def investigation_status(incident_id: str):
    with _running_lock:
        running = incident_id in _running_ids
    return {"running": running}


@router.get("/{incident_id}/approvals")
def get_pending_approvals(incident_id: str):
    with session_scope() as session:
        _get_incident_or_404(session, incident_id)
        return [ser.action_dict(a) for a in approval.list_pending(session, incident_id)]


@router.post("/{incident_id}/approvals/{action_id}")
def decide_approval(incident_id: str, action_id: str, req: ApprovalDecisionRequest, background_tasks: BackgroundTasks):
    with session_scope() as session:
        _get_incident_or_404(session, incident_id)
        try:
            approval.decide(session, action_id, req.approved, req.decided_by, req.reason)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    with _running_lock:
        if incident_id in _running_ids:
            raise HTTPException(409, "Investigation already running for this incident")
        _running_ids.add(incident_id)
    background_tasks.add_task(_resume_after_decision, incident_id)
    return {"status": "resuming"}


def _resume_after_decision(incident_id: str) -> None:
    session = SessionLocal()
    try:
        loop = load_agent_loop(session, incident_id)
        loop.resume_after_approval(step_delay=0.6)
    except Exception:  # noqa: BLE001
        logger.exception("Resume-after-approval failed for incident %s", incident_id)
    finally:
        with _running_lock:
            _running_ids.discard(incident_id)
        session.close()


@router.get("/{incident_id}/stream")
async def stream_incident(incident_id: str):
    """SSE stream: pushes the incident summary + latest event whenever new events land."""

    async def event_generator():
        last_count = -1
        while True:
            with session_scope() as session:
                incident = session.get(m.Incident, incident_id)
                if incident is None:
                    yield {"event": "error", "data": "not_found"}
                    return
                stmt = select(m.IncidentEvent).where(m.IncidentEvent.incident_id == incident_id).order_by(m.IncidentEvent.created_at)
                events = list(session.execute(stmt).scalars())
                payload = {"incident": ser.incident_summary(incident), "new_events": [ser.event_dict(e) for e in events[last_count + 1:]]}
                terminal = incident.resolved_at is not None
                last_count = len(events) - 1
            yield {"event": "update", "data": _json(payload)}
            if terminal:
                yield {"event": "done", "data": "{}"}
                return
            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())


def _json(payload: dict) -> str:
    import json

    return json.dumps(payload, default=str)
