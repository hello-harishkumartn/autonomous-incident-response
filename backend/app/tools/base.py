"""Common tool interface. Every tool the agent can call implements this.

Design choices that matter for safety:
- Every tool declares a typed Pydantic args model — the agent cannot pass
  arbitrary kwargs, and validation happens before anything touches the
  simulation.
- `risk_for(args)` lets risk depend on arguments (e.g. restarting a
  stateless service is LOW_RISK, restarting Postgres is HIGH_RISK) rather
  than being a static property of the tool name alone.
- `run()` only ever receives a `ToolContext` wrapping the `SimulationEngine`
  — there is no path from a tool to a real shell, socket, or filesystem.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models_db as m
from app.enums import RiskLevel
from app.simulator.engine import SimulationEngine
from app.simulator.scenarios import IncidentScenario


@dataclass
class ToolContext:
    session: Session
    engine: SimulationEngine
    incident: m.Incident
    scenario: IncidentScenario


class Tool(ABC):
    name: str
    description: str
    args_model: type[BaseModel]
    default_risk: RiskLevel

    def risk_for(self, args: BaseModel) -> RiskLevel:
        return self.default_risk

    @abstractmethod
    def run(self, ctx: ToolContext, args: BaseModel) -> dict[str, Any]:
        ...

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "risk_level": self.default_risk.value,
            "input_schema": self.args_model.model_json_schema(),
        }
