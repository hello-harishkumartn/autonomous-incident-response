"""Machine-verifiable stopping conditions and a dedup-hash helper.

Every check here is a plain function over persisted state — nothing here
depends on interpreting model output, which is what makes the conditions
machine-verifiable rather than judgment calls.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json

from app import models_db as m
from app.enums import StoppingReason


def dedup_hash(tool_name: str, args: dict) -> str:
    payload = json.dumps({"tool": tool_name, "args": args}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def check_budgets(incident: m.Incident) -> StoppingReason | None:
    if incident.iteration >= incident.max_iterations:
        return StoppingReason.BUDGET_EXHAUSTED
    elapsed = (dt.datetime.now(dt.timezone.utc) - _aware(incident.created_at)).total_seconds()
    if elapsed >= incident.max_seconds:
        return StoppingReason.BUDGET_EXHAUSTED
    if incident.tokens_used >= incident.max_tokens:
        return StoppingReason.BUDGET_EXHAUSTED
    return None


def _aware(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)


def budgets_remaining(incident: m.Incident) -> dict:
    elapsed = (dt.datetime.now(dt.timezone.utc) - _aware(incident.created_at)).total_seconds()
    return {
        "iterations_remaining": max(0, incident.max_iterations - incident.iteration),
        "seconds_remaining": max(0.0, incident.max_seconds - elapsed),
        "tokens_remaining": max(0, incident.max_tokens - incident.tokens_used),
    }
