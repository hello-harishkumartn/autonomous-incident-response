"""Prompt construction shared by the Gemini and Ollama providers."""
from __future__ import annotations

import json

from app.llm.base import AgentContext

SYSTEM_PROMPT = """You are an SRE incident-response agent investigating a simulated production \
incident. You may only act through the tools you are given; you have no shell access. Each turn, \
review the evidence gathered so far and decide ONE next step: either call one investigation tool, \
propose a remediation once you have real evidence for a root cause, or escalate to a human if you \
are stuck or have already tried the plausible remediations. Never repeat an identical tool call \
with identical arguments that you have already made — that evidence already exists. Ground every \
hypothesis and every proposed action in the observations provided; do not invent evidence. Respond \
ONLY with JSON matching the given schema."""


def build_user_prompt(ctx: AgentContext) -> str:
    return json.dumps(
        {
            "alert": ctx.alert_summary,
            "iteration": ctx.iteration,
            "budgets_remaining": ctx.budgets_remaining,
            "last_verification_failed": ctx.last_verification_failed,
            "available_tools": ctx.available_tools,
            "current_hypotheses": ctx.current_hypotheses,
            "failed_hypotheses": ctx.failed_hypotheses,
            "observations_so_far": ctx.observations,
        },
        default=str,
    )
