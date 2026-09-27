"""Creates a new incident run and reconstructs an AgentLoop for an existing one.

Reconstruction from just `(session, incident_id)` is what makes runs
resumable across process boundaries (a CLI run, then inspected/approved via
the API, then resumed) — everything the loop needs lives in the DB.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models_db as m
from app.agent.loop import AgentLoop
from app.config import settings
from app.enums import IncidentType
from app.llm.client import LLMClient
from app.simulator.engine import SimulationEngine
from app.simulator.scenarios import get_scenario


def create_incident(session: Session, scenario_type: IncidentType | str, seed: int | None = None) -> m.Incident:
    scenario = get_scenario(scenario_type)
    seed = seed if seed is not None else settings.default_seed

    incident = m.Incident(
        scenario_type=scenario.type.value, seed=seed, alert_summary=scenario.alert_summary,
        ground_truth_root_cause=scenario.ground_truth_root_cause, ground_truth_fix_tool=scenario.fix_tool,
        max_iterations=settings.max_iterations, max_seconds=settings.max_seconds, max_tokens=settings.max_tokens,
    )
    session.add(incident)
    session.flush()

    engine = SimulationEngine(session, incident.id, seed)
    engine.bootstrap()
    scenario.apply(engine)
    session.flush()
    return incident


def load_agent_loop(session: Session, incident_id: str, llm_client: LLMClient | None = None, for_eval: bool = False) -> AgentLoop:
    incident = session.execute(select(m.Incident).where(m.Incident.id == incident_id)).scalar_one()
    scenario = get_scenario(incident.scenario_type)
    engine = SimulationEngine(session, incident.id, incident.seed)
    return AgentLoop(session, incident, engine, scenario, llm_client=llm_client, for_eval=for_eval)
