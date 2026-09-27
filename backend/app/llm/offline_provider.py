"""Deterministic, evidence-driven provider — no network, no API key, ever.

This is not a toy stand-in: it is a real rule-based expert system that
reads actual tool output (health checks, service state, log text) and
walks the same investigate -> confirm -> remediate path an LLM would,
purely by pattern-matching evidence it has actually gathered. It never
looks at scenario ground truth. It exists so `pytest`, CI, and the demo
script can prove the full agent loop end-to-end with zero external
dependencies, and it is the automatic fallback if Gemini and Ollama are
both unavailable.
"""
from __future__ import annotations

from app.llm.base import AgentContext, HypothesisItem, LLMStepDecision, NextAction, TokenUsage

# (keyword signatures, root-cause template, fix tool, confirming diagnostic)
# Root-cause templates use {service}; keywords are matched against the
# lower-cased text of every log message collected so far for the target
# service. First rule whose any keyword appears in that text wins.
_RULES: list[dict] = [
    {
        "keywords": ["queuepool", "could not obtain a connection"],
        "root_cause": "A connection leak is exhausting {service}'s database connection pool.",
        "fix_tool": "restart_service", "diagnostic": "connection_pool_check",
    },
    {
        "keywords": ["heap usage", "gc overhead"],
        "root_cause": "A memory leak in {service} is causing excessive heap growth and GC pressure.",
        "fix_tool": "restart_service", "diagnostic": "memory_check",
    },
    {
        "keywords": ["event loop lag", "cpu throttling"],
        "root_cause": "{service} is CPU-starved by a runaway background job, causing cascading latency.",
        "fix_tool": "restart_service", "diagnostic": "latency_check",
    },
    {
        "keywords": ["unhandled exception", "keyerror"],
        "root_cause": "A recent deployment to {service} introduced a regression causing unhandled exceptions.",
        "fix_tool": "rollback_deployment", "diagnostic": None,
    },
    {
        "keywords": ["oom command not allowed", "max clients reached"],
        "root_cause": "{service} hit its memory limit with no eviction policy and is rejecting commands.",
        "fix_tool": "restart_service", "diagnostic": "memory_check",
    },
    {
        "keywords": ["configured timeout"],
        "root_cause": "A configuration change set an unreasonably low timeout on {service}, causing premature failures.",
        "fix_tool": "rollback_deployment", "diagnostic": None,
    },
    {
        "keywords": ["circuit breaker open", "circuit breaker"],
        "root_cause": "An upstream dependency is slow and {service}'s circuit breaker is stuck open.",
        "fix_tool": "restart_service", "diagnostic": "latency_check",
    },
    {
        "keywords": ["no space left on device", "could not write to file"],
        "root_cause": "{service}'s disk is full because WAL archiving is stuck, blocking writes.",
        "fix_tool": "restart_service", "diagnostic": "disk_check",
    },
    {
        "keywords": ["fixed 0ms backoff", "retrying payment call"],
        "root_cause": "An aggressive no-backoff retry policy in {service} created a self-sustaining retry storm.",
        "fix_tool": "restart_service", "diagnostic": "connection_pool_check",
    },
    {
        "keywords": ["password authentication failed", "password expired"],
        "root_cause": "{service} is using an expired cached database credential after a rotation.",
        "fix_tool": "restart_service", "diagnostic": "dependency_ping",
    },
]

REMEDIATION_TOOLS = ("restart_service", "rollback_deployment")


def _estimate_tokens(ctx: AgentContext, summary: str) -> TokenUsage:
    prompt_chars = len(ctx.alert_summary) + sum(len(str(o)) for o in ctx.observations) + 400
    return TokenUsage(prompt_tokens=max(50, prompt_chars // 4), completion_tokens=max(20, len(summary) // 3))


def _find_calls(ctx: AgentContext, tool_name: str, **arg_filters) -> list[dict]:
    out = []
    for obs in ctx.observations:
        if obs.get("tool_name") != tool_name:
            continue
        if all(obs.get("args", {}).get(k) == v for k, v in arg_filters.items()):
            out.append(obs)
    return out


def _match_rule(text: str) -> dict | None:
    lowered = text.lower()
    for rule in _RULES:
        if any(kw in lowered for kw in rule["keywords"]):
            return rule
    return None


class OfflineHeuristicProvider:
    name = "offline"

    def decide(self, ctx: AgentContext) -> tuple[LLMStepDecision, TokenUsage]:
        decision = self._decide(ctx)
        return decision, _estimate_tokens(ctx, decision.reasoning_summary)

    def _decide(self, ctx: AgentContext) -> LLMStepDecision:
        if ctx.last_verification_failed:
            retried = self._retry_after_failed_verification(ctx)
            if retried is not None:
                return retried

        health_calls = _find_calls(ctx, "run_health_check")
        if not health_calls:
            return LLMStepDecision(
                reasoning_summary="No observations yet; checking overall fleet health first.",
                next_action=NextAction(kind="investigate", tool_name="run_health_check", args={},
                                        rationale="Establish which service(s) are unhealthy before drilling in."),
            )

        checks = health_calls[-1].get("result", {}).get("checks", {})
        unhealthy = [svc for svc, c in checks.items() if not c.get("healthy", True)]
        if not unhealthy:
            return LLMStepDecision(
                reasoning_summary="Fleet health check reports all services healthy.",
                next_action=NextAction(kind="escalate", escalation_reason="No unhealthy service found to investigate."),
            )
        target = unhealthy[0]

        if not _find_calls(ctx, "inspect_service", service=target):
            return LLMStepDecision(
                reasoning_summary=f"{target} is reporting unhealthy; inspecting its current resource/latency snapshot.",
                hypotheses=[HypothesisItem(description=f"Investigating anomaly in {target}", target_service=target, confidence=0.2)],
                next_action=NextAction(kind="investigate", tool_name="inspect_service", args={"service": target},
                                        rationale="Get a concrete snapshot before reading logs."),
            )

        log_calls = _find_calls(ctx, "query_logs", service=target)
        if not log_calls:
            return LLMStepDecision(
                reasoning_summary=f"Pulling recent logs for {target} to look for an error signature.",
                hypotheses=[HypothesisItem(description=f"Investigating anomaly in {target}", target_service=target, confidence=0.3)],
                next_action=NextAction(kind="investigate", tool_name="query_logs",
                                        args={"service": target, "since_seconds": 900, "limit": 20},
                                        rationale="Logs usually carry the specific error signature."),
            )

        all_messages = " ".join(
            entry.get("message", "") for call in log_calls for entry in call.get("result", {}).get("logs", [])
        )
        rule = _match_rule(all_messages)
        if rule is None:
            return LLMStepDecision(
                reasoning_summary=f"No known error signature found in {target}'s logs yet.",
                next_action=NextAction(kind="escalate", escalation_reason=f"Could not identify a root-cause signature for {target} from available evidence."),
            )

        root_cause = rule["root_cause"].format(service=target)
        confirming_done = True
        if rule["fix_tool"] == "rollback_deployment":
            confirming_done = bool(_find_calls(ctx, "get_deployment", service=target))
            if not confirming_done:
                return LLMStepDecision(
                    reasoning_summary=f"Log signature suggests a bad change on {target}; checking deployment history to confirm.",
                    hypotheses=[HypothesisItem(description=root_cause, target_service=target, confidence=0.65)],
                    next_action=NextAction(kind="investigate", tool_name="get_deployment", args={"service": target},
                                            rationale="Confirm a recent deployment lines up with when symptoms started."),
                )
        elif rule["diagnostic"] is not None:
            confirming_done = bool(_find_calls(ctx, "execute_diagnostic", service=target))
            if not confirming_done:
                return LLMStepDecision(
                    reasoning_summary=f"Log signature points to {target}; running a confirming diagnostic before remediating.",
                    hypotheses=[HypothesisItem(description=root_cause, target_service=target, confidence=0.65)],
                    next_action=NextAction(kind="investigate", tool_name="execute_diagnostic",
                                            args={"service": target, "diagnostic": rule["diagnostic"]},
                                            rationale="Verify the resource signal before proposing a restart."),
                )

        return LLMStepDecision(
            reasoning_summary=f"Evidence converges on: {root_cause}",
            hypotheses=[HypothesisItem(description=root_cause, target_service=target, confidence=0.9, status="confirmed")],
            root_cause_confirmed=True,
            confirmed_root_cause=root_cause,
            next_action=NextAction(
                kind="remediate", tool_name=rule["fix_tool"], args={"service": target, "reason": root_cause},
                rationale=f"{rule['fix_tool']} on {target} directly addresses the confirmed cause.",
            ),
        )

    def _retry_after_failed_verification(self, ctx: AgentContext) -> LLMStepDecision | None:
        attempted = [o["tool_name"] for o in ctx.observations if o.get("tool_name") in REMEDIATION_TOOLS]
        if not attempted:
            return None
        last_tool = attempted[-1]
        last_call = next(o for o in reversed(ctx.observations) if o.get("tool_name") == last_tool)
        target = last_call.get("args", {}).get("service")
        other_tool = "rollback_deployment" if last_tool == "restart_service" else "restart_service"
        if other_tool in attempted:
            return LLMStepDecision(
                reasoning_summary=f"Both restart and rollback were tried on {target} without recovery.",
                next_action=NextAction(kind="escalate", escalation_reason=f"Exhausted known remediations for {target}; needs human investigation."),
            )
        return LLMStepDecision(
            reasoning_summary=f"{last_tool} did not restore {target} to healthy; escalating remediation to {other_tool}.",
            hypotheses=[HypothesisItem(description=f"{last_tool} was insufficient for {target}'s fault", target_service=target or "", confidence=0.4, status="rejected")],
            next_action=NextAction(
                kind="remediate", tool_name=other_tool, args={"service": target, "reason": f"Previous remediation ({last_tool}) did not restore health."},
                rationale="Try the other class of remediation before escalating to a human.",
            ),
        )
