"""Incident benchmark: runs every scenario N times headlessly and scores it.

Headless means HIGH_RISK actions auto-approve for the duration of the run
(`auto_approve_high_risk_for_eval`) — this is the one place that flag is
ever set to True, and it is restored afterwards. It exists so the
benchmark measures the agent's diagnostic/remediation quality, not whether
a human happened to be watching; the interactive/demo path never touches it.
"""
from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass

from sqlalchemy import select

from app import models_db as m
from app.agent.factory import create_incident, load_agent_loop
from app.config import settings
from app.db import SessionLocal
from app.enums import IncidentType, StoppingReason
from app.safety import approval
from app.simulator.scenarios import get_scenario


@dataclass
class TrialResult:
    incident_id: str
    scenario_type: str
    seed: int
    resolved: bool
    correct_fix: bool
    iterations: int
    tool_calls: int
    tokens_used: int
    time_to_diagnosis_s: float | None
    time_to_completion_s: float
    stopping_reason: str | None
    unnecessary_actions: int
    total_remediation_actions: int
    escalated: bool
    llm_provider: str | None


def _find_diagnosis_time(session, incident: m.Incident):
    stmt = (
        select(m.IncidentEvent)
        .where(m.IncidentEvent.incident_id == incident.id, m.IncidentEvent.phase == "generating_hypotheses")
        .order_by(m.IncidentEvent.created_at)
    )
    for event in session.execute(stmt).scalars():
        hyps = (event.detail or {}).get("hypotheses", [])
        if any(h.get("status") == "confirmed" for h in hyps):
            return event.created_at, (event.detail or {}).get("provider")
    return None, None


def run_trial(scenario_type: IncidentType, seed: int) -> TrialResult:
    session = SessionLocal()
    try:
        incident = create_incident(session, scenario_type, seed=seed)
        session.commit()

        loop = load_agent_loop(session, incident.id, for_eval=True)
        result = loop.run_to_completion()
        while result is None:
            pending = approval.list_pending(session, incident.id)
            if not pending:
                break
            approval.decide(session, pending[0].id, approved=True, decided_by="eval-harness")
            session.commit()
            result = loop.resume_after_approval()
        session.commit()

        scenario = get_scenario(scenario_type)
        stmt = select(m.ActionLog).where(m.ActionLog.incident_id == incident.id, m.ActionLog.executed.is_(True))
        executed = list(session.execute(stmt).scalars())
        correct_action = next(
            (a for a in executed if a.tool_name == scenario.fix_tool and a.args.get("service") == scenario.fix_target.value),
            None,
        )
        resolved = result == StoppingReason.INCIDENT_RESOLVED
        diagnosis_at, provider = _find_diagnosis_time(session, incident)

        return TrialResult(
            incident_id=incident.id, scenario_type=scenario_type.value, seed=seed,
            resolved=resolved, correct_fix=resolved and correct_action is not None,
            iterations=incident.iteration, tool_calls=incident.tool_call_count, tokens_used=incident.tokens_used,
            time_to_diagnosis_s=(diagnosis_at - incident.created_at).total_seconds() if diagnosis_at else None,
            time_to_completion_s=((incident.resolved_at or incident.updated_at) - incident.created_at).total_seconds(),
            stopping_reason=result.value if result else None,
            unnecessary_actions=len([a for a in executed if a is not correct_action]),
            total_remediation_actions=len(executed),
            escalated=result == StoppingReason.HUMAN_ESCALATION_REQUIRED,
            llm_provider=provider,
        )
    finally:
        session.close()


def run_benchmark(trials_per_scenario: int = 3, base_seed: int = 100) -> list[TrialResult]:
    previous = settings.auto_approve_high_risk_for_eval
    settings.auto_approve_high_risk_for_eval = True
    try:
        results = []
        for scenario_type in IncidentType:
            for i in range(trials_per_scenario):
                results.append(run_trial(scenario_type, seed=base_seed + i))
        return results
    finally:
        settings.auto_approve_high_risk_for_eval = previous


def _rate(rows: list[TrialResult], pred) -> float:
    return sum(1 for r in rows if pred(r)) / len(rows) if rows else 0.0


def _mean(values: list[float]) -> float | None:
    values = [v for v in values if v is not None]
    return statistics.mean(values) if values else None


def _score(rows: list[TrialResult]) -> dict:
    total_actions = sum(r.total_remediation_actions for r in rows)
    unnecessary = sum(r.unnecessary_actions for r in rows)
    return {
        "trials": len(rows),
        "root_cause_accuracy": _rate(rows, lambda r: r.correct_fix),
        "remediation_success_rate": _rate(rows, lambda r: r.resolved),
        "human_escalation_rate": _rate(rows, lambda r: r.escalated),
        "mean_tool_calls": _mean([r.tool_calls for r in rows]),
        "mean_iterations": _mean([r.iterations for r in rows]),
        "mean_time_to_diagnosis_s": _mean([r.time_to_diagnosis_s for r in rows]),
        "mean_time_to_completion_s": _mean([r.time_to_completion_s for r in rows]),
        "mean_tokens_used": _mean([r.tokens_used for r in rows]),
        "unnecessary_action_rate": (unnecessary / total_actions) if total_actions else 0.0,
    }


def summarize(results: list[TrialResult]) -> dict:
    by_scenario: dict[str, list[TrialResult]] = {}
    for r in results:
        by_scenario.setdefault(r.scenario_type, []).append(r)
    return {
        "overall": _score(results),
        "by_scenario": {scenario: _score(rows) for scenario, rows in by_scenario.items()},
    }


def results_to_dicts(results: list[TrialResult]) -> list[dict]:
    return [asdict(r) for r in results]
