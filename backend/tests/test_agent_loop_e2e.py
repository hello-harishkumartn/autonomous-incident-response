"""End-to-end proof: inject -> investigate -> (approve if needed) -> resolve, per scenario."""
from __future__ import annotations

import pytest

from app.agent.factory import create_incident, load_agent_loop
from app.enums import ApprovalStatus, IncidentPhase, IncidentType, StoppingReason
from app.safety import approval

ALL_TYPES = list(IncidentType)


@pytest.mark.parametrize("incident_type", ALL_TYPES)
def test_scenario_resolves_end_to_end(session, incident_type):
    incident = create_incident(session, incident_type, seed=7)
    session.commit()

    loop = load_agent_loop(session, incident.id)
    result = loop.run_to_completion()
    session.commit()

    if result is None:
        # paused awaiting human approval on a HIGH_RISK action — approve it and resume
        pending = approval.list_pending(session, incident.id)
        assert len(pending) == 1, "expected exactly one pending high-risk action"
        approval.decide(session, pending[0].id, approved=True, decided_by="test-operator")
        session.commit()
        result = loop.resume_after_approval()
        session.commit()

    assert result == StoppingReason.INCIDENT_RESOLVED, f"{incident_type}: {result}, phase={incident.phase}"
    assert incident.phase == IncidentPhase.RESOLVED.value
    assert incident.confirmed_root_cause is not None
    assert incident.tool_call_count > 0
    assert incident.iteration > 0


def test_high_risk_action_blocks_without_approval(session):
    incident = create_incident(session, IncidentType.BAD_DEPLOYMENT, seed=7)
    session.commit()

    loop = load_agent_loop(session, incident.id)
    result = loop.run_to_completion()
    session.commit()

    assert result is None
    assert incident.phase == IncidentPhase.AWAITING_APPROVAL.value
    pending = approval.list_pending(session, incident.id)
    assert len(pending) == 1
    assert pending[0].tool_name == "rollback_deployment"
    assert pending[0].risk_level == "HIGH_RISK"
    assert pending[0].approval_status == ApprovalStatus.PENDING.value


def test_rejected_approval_continues_investigation_then_can_be_reapproved(session):
    incident = create_incident(session, IncidentType.BAD_DEPLOYMENT, seed=7)
    session.commit()
    loop = load_agent_loop(session, incident.id)
    loop.run_to_completion()
    session.commit()

    pending = approval.list_pending(session, incident.id)
    approval.decide(session, pending[0].id, approved=False, decided_by="test-operator", reason="want more evidence")
    session.commit()

    result = loop.resume_after_approval()
    session.commit()
    # offline provider will re-propose the same rollback (it's the only known fix) -> pauses again
    assert result is None
    assert incident.phase == IncidentPhase.AWAITING_APPROVAL.value


def test_low_risk_scenarios_never_pause(session):
    incident = create_incident(session, IncidentType.MEMORY_SPIKE, seed=7)
    session.commit()
    loop = load_agent_loop(session, incident.id)
    result = loop.run_to_completion()
    session.commit()
    assert result == StoppingReason.INCIDENT_RESOLVED


def test_budget_exhaustion_is_machine_verifiable(session):
    incident = create_incident(session, IncidentType.DB_CONNECTION_EXHAUSTION, seed=7)
    incident.max_iterations = 2
    session.commit()

    loop = load_agent_loop(session, incident.id)
    result = loop.run_to_completion()
    session.commit()

    assert result == StoppingReason.BUDGET_EXHAUSTED
    assert incident.phase == IncidentPhase.BUDGET_EXHAUSTED.value
    assert incident.resolved_at is not None
