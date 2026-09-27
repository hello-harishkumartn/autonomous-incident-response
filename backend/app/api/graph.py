"""Static execution-graph topology + which nodes/edges a given run actually visited."""
from __future__ import annotations

from app.enums import IncidentPhase

NODES: list[str] = [
    IncidentPhase.ALERTED.value,
    IncidentPhase.COLLECTING_OBSERVATIONS.value,
    IncidentPhase.GENERATING_HYPOTHESES.value,
    IncidentPhase.SELECTING_INVESTIGATION.value,
    IncidentPhase.CALLING_TOOL.value,
    IncidentPhase.ANALYZING_RESULTS.value,
    IncidentPhase.UPDATING_HYPOTHESES.value,
    IncidentPhase.ROOT_CAUSE_CHECK.value,
    IncidentPhase.GENERATING_REMEDIATION.value,
    IncidentPhase.RISK_CLASSIFICATION.value,
    IncidentPhase.AWAITING_APPROVAL.value,
    IncidentPhase.EXECUTING_REMEDIATION.value,
    IncidentPhase.VERIFYING_HEALTH.value,
    IncidentPhase.ROLLING_BACK.value,
    IncidentPhase.RESOLVED.value,
    IncidentPhase.ESCALATED.value,
    IncidentPhase.BUDGET_EXHAUSTED.value,
    IncidentPhase.NO_VALID_ACTIONS.value,
]

EDGES: list[tuple[str, str]] = [
    (IncidentPhase.ALERTED.value, IncidentPhase.COLLECTING_OBSERVATIONS.value),
    (IncidentPhase.COLLECTING_OBSERVATIONS.value, IncidentPhase.GENERATING_HYPOTHESES.value),
    (IncidentPhase.GENERATING_HYPOTHESES.value, IncidentPhase.SELECTING_INVESTIGATION.value),
    (IncidentPhase.GENERATING_HYPOTHESES.value, IncidentPhase.GENERATING_REMEDIATION.value),
    (IncidentPhase.GENERATING_HYPOTHESES.value, IncidentPhase.ESCALATED.value),
    (IncidentPhase.SELECTING_INVESTIGATION.value, IncidentPhase.CALLING_TOOL.value),
    (IncidentPhase.CALLING_TOOL.value, IncidentPhase.ANALYZING_RESULTS.value),
    (IncidentPhase.ANALYZING_RESULTS.value, IncidentPhase.UPDATING_HYPOTHESES.value),
    (IncidentPhase.UPDATING_HYPOTHESES.value, IncidentPhase.ROOT_CAUSE_CHECK.value),
    (IncidentPhase.ROOT_CAUSE_CHECK.value, IncidentPhase.COLLECTING_OBSERVATIONS.value),
    (IncidentPhase.ROOT_CAUSE_CHECK.value, IncidentPhase.GENERATING_REMEDIATION.value),
    (IncidentPhase.GENERATING_REMEDIATION.value, IncidentPhase.RISK_CLASSIFICATION.value),
    (IncidentPhase.RISK_CLASSIFICATION.value, IncidentPhase.AWAITING_APPROVAL.value),
    (IncidentPhase.RISK_CLASSIFICATION.value, IncidentPhase.EXECUTING_REMEDIATION.value),
    (IncidentPhase.AWAITING_APPROVAL.value, IncidentPhase.EXECUTING_REMEDIATION.value),
    (IncidentPhase.EXECUTING_REMEDIATION.value, IncidentPhase.VERIFYING_HEALTH.value),
    (IncidentPhase.VERIFYING_HEALTH.value, IncidentPhase.RESOLVED.value),
    (IncidentPhase.VERIFYING_HEALTH.value, IncidentPhase.ROLLING_BACK.value),
    (IncidentPhase.ROLLING_BACK.value, IncidentPhase.COLLECTING_OBSERVATIONS.value),
]


def build_graph(visited_phases: set[str], current_phase: str) -> dict:
    return {
        "nodes": [{"id": n, "visited": n in visited_phases, "current": n == current_phase} for n in NODES],
        "edges": [
            {"from": a, "to": b, "visited": a in visited_phases and b in visited_phases}
            for a, b in EDGES
        ],
    }
