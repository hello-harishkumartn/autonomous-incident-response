"""Shared bootstrap for CLI scripts: puts backend/ on sys.path and prints timelines
in the decision/evidence/action/result form the UI uses — never raw chain-of-thought."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

KIND_LABEL = {"decision": "DECISION", "evidence": "EVIDENCE", "action": "ACTION ", "result": "RESULT "}


def print_incident_header(incident) -> None:
    print(f"\nIncident {incident.id}")
    print(f"  scenario : {incident.scenario_type}  (seed={incident.seed})")
    print(f"  alert    : {incident.alert_summary}")
    print("-" * 78)


def print_new_events(session, incident_id: str, after_index: int) -> int:
    from sqlalchemy import select

    from app import models_db as m

    stmt = select(m.IncidentEvent).where(m.IncidentEvent.incident_id == incident_id).order_by(m.IncidentEvent.created_at)
    events = list(session.execute(stmt).scalars())
    for event in events[after_index:]:
        label = KIND_LABEL.get(event.kind, event.kind.upper())
        print(f"[iter {event.iteration:>2}] {event.phase:<24} {label} | {event.summary}")
    return len(events)


def print_final_status(incident) -> None:
    print("-" * 78)
    print(f"Final phase     : {incident.phase}")
    print(f"Stopping reason : {incident.stopping_reason}")
    print(f"Confirmed cause : {incident.confirmed_root_cause}")
    print(f"Ground truth    : {incident.ground_truth_root_cause}")
    print(f"Iterations      : {incident.iteration}   Tool calls: {incident.tool_call_count}   Tokens: {incident.tokens_used}")
