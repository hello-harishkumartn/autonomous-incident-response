"""The single decision contract every LLM provider (or heuristic) must implement.

One call per agent-loop iteration returns everything that iteration's
reasoning covers: updated hypotheses, whether the root cause is confirmed,
and the next step. This intentionally collapses "generate hypotheses /
select investigation / analyze results / update hypotheses / root-cause
check / generate remediation" from the spec's loop diagram into one
structured reasoning act per iteration — the code (agent/loop.py) still
enforces each phase as a distinct, logged state-machine transition. This
keeps token/API-call usage bounded and predictable, which matters because
budgets are a first-class stopping condition.
"""
from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field


class HypothesisItem(BaseModel):
    description: str
    target_service: str
    confidence: float = Field(ge=0.0, le=1.0)
    status: Literal["active", "confirmed", "rejected"] = "active"


class NextAction(BaseModel):
    kind: Literal["investigate", "remediate", "escalate"]
    tool_name: str | None = None
    args: dict = Field(default_factory=dict)
    rationale: str = ""
    escalation_reason: str | None = None


class LLMStepDecision(BaseModel):
    reasoning_summary: str = Field(..., description="One or two sentences, safe to show a human. Not chain-of-thought.")
    hypotheses: list[HypothesisItem] = Field(default_factory=list)
    root_cause_confirmed: bool = False
    confirmed_root_cause: str | None = None
    next_action: NextAction


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class ProviderError(RuntimeError):
    """Raised when a provider can't produce a decision — triggers fallback."""


class AgentContext(BaseModel):
    """Everything the model is shown. No hidden ground truth ever enters this."""

    alert_summary: str
    iteration: int
    observations: list[dict] = Field(default_factory=list)
    current_hypotheses: list[dict] = Field(default_factory=list)
    failed_hypotheses: list[dict] = Field(default_factory=list)
    past_tool_calls: list[dict] = Field(default_factory=list)
    available_tools: list[dict] = Field(default_factory=list)
    budgets_remaining: dict = Field(default_factory=dict)
    last_verification_failed: bool = False


class LLMProvider(Protocol):
    name: str

    def decide(self, ctx: AgentContext) -> tuple[LLMStepDecision, TokenUsage]:
        ...
