"""AgentLoop — the state machine described in AGENT_LOOP.md, made real.

Alert -> collect observations -> generate hypotheses -> select investigation
-> call tool -> analyze -> update hypotheses -> root cause? -> [loop] or
generate remediation -> risk classification -> human approval if required ->
execute in sandbox -> verify -> resolved, or rollback + continue.

Every transition is (a) persisted as a DB row and (b) logged as an
IncidentEvent with kind in {decision, evidence, action, result} — that pair
is what the UI renders and what makes a run inspectable/resumable without
ever exposing raw model chain-of-thought.
"""
from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass, field

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models_db as m
from app.agent.stopping import budgets_remaining, check_budgets, dedup_hash
from app.enums import ApprovalStatus, IncidentPhase, RiskLevel, ServiceName, StoppingReason, ToolCallStatus
from app.llm.base import AgentContext, LLMStepDecision, NextAction, ProviderError
from app.llm.client import LLMClient
from app.safety.approval import propose_action
from app.safety.sandbox import SandboxExecutor, SandboxViolation
from app.simulator.engine import SimulationEngine
from app.simulator.scenarios import IncidentScenario
from app.tools.base import ToolContext
from app.tools.registry import REMEDIATION_TOOLS, get_tool, list_tool_schemas

PAUSED_FOR_APPROVAL = "PAUSED_FOR_APPROVAL"
VERIFY_FAILED = "VERIFY_FAILED"
CONTINUE = None
StepResult = StoppingReason | str | None


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


@dataclass
class _Cache:
    tool_calls: list[m.ToolCallLog] = field(default_factory=list)
    known_hashes: set[str] = field(default_factory=set)
    consecutive_stalls: int = 0


class AgentLoop:
    def __init__(
        self, session: Session, incident: m.Incident, engine: SimulationEngine,
        scenario: IncidentScenario, llm_client: LLMClient | None = None, for_eval: bool = False,
    ):
        self.session = session
        self.incident = incident
        self.engine = engine
        self.scenario = scenario
        self.llm = llm_client or LLMClient()
        self.for_eval = for_eval
        self.tool_ctx = ToolContext(session=session, engine=engine, incident=incident, scenario=scenario)
        self._cache = _Cache()
        self._cache.tool_calls = self._query_tool_calls()
        self._cache.known_hashes = {tc.dedup_hash for tc in self._cache.tool_calls}

    # ------------------------------------------------------------ queries
    def _query_tool_calls(self) -> list[m.ToolCallLog]:
        stmt = select(m.ToolCallLog).where(m.ToolCallLog.incident_id == self.incident.id).order_by(m.ToolCallLog.started_at)
        return list(self.session.execute(stmt).scalars())

    def _query_hypotheses(self, status: str | None = None) -> list[m.Hypothesis]:
        stmt = select(m.Hypothesis).where(m.Hypothesis.incident_id == self.incident.id)
        if status:
            stmt = stmt.where(m.Hypothesis.status == status)
        return list(self.session.execute(stmt).scalars().unique())

    # -------------------------------------------------------------- utils
    def _log_event(self, phase: IncidentPhase, kind: str, summary: str, detail: dict | None = None) -> None:
        self.session.add(m.IncidentEvent(
            incident_id=self.incident.id, iteration=self.incident.iteration, phase=phase.value,
            kind=kind, summary=summary, detail=detail or {},
        ))
        self.session.flush()

    def _set_phase(self, phase: IncidentPhase) -> None:
        self.incident.phase = phase.value
        self.session.flush()

    def _resolve(self, phase: IncidentPhase, reason: StoppingReason) -> None:
        self.incident.phase = phase.value
        self.incident.stopping_reason = reason.value
        self.incident.resolved_at = _now()
        self.session.flush()

    def _build_context(self, last_verification_failed: bool) -> AgentContext:
        tool_calls = self._query_tool_calls()
        observations = [{"tool_name": tc.tool_name, "args": tc.args, "result": tc.result} for tc in tool_calls]
        active = [
            {"description": h.description, "target_service": h.target_service, "confidence": h.confidence}
            for h in self._query_hypotheses(status="active")
        ]
        failed = [
            {"description": h.description, "target_service": h.target_service}
            for h in self._query_hypotheses(status="rejected")
        ]
        return AgentContext(
            alert_summary=self.incident.alert_summary,
            iteration=self.incident.iteration,
            observations=observations,
            current_hypotheses=active,
            failed_hypotheses=failed,
            past_tool_calls=[{"tool_name": tc.tool_name, "args": tc.args} for tc in tool_calls],
            available_tools=list_tool_schemas(),
            budgets_remaining=budgets_remaining(self.incident),
            last_verification_failed=last_verification_failed,
        )

    def _persist_hypotheses(self, decision: LLMStepDecision) -> None:
        for item in decision.hypotheses:
            self.session.add(m.Hypothesis(
                incident_id=self.incident.id, description=item.description, target_service=item.target_service,
                confidence=item.confidence, status=item.status,
                created_iteration=self.incident.iteration, updated_iteration=self.incident.iteration,
            ))
        self.session.flush()

    # --------------------------------------------------------------- run
    def run_to_completion(self, step_delay: float = 0.0) -> StoppingReason | None:
        """Runs until a terminal StoppingReason or an approval pause (returns None).

        Commits after every iteration (not just at the end) so a concurrent
        reader — the API's polling GET endpoints, in particular — sees the
        investigation progress in real time. `step_delay` is purely a UX
        knob for the UI demo ("watch it evolve"); CLI/tests leave it at 0.
        """
        if self.incident.phase == IncidentPhase.ALERTED.value and not self._cache.tool_calls:
            self._log_event(IncidentPhase.ALERTED, "decision", f"Alert received: {self.incident.alert_summary}")
            self.session.commit()

        last_verification_failed = False
        while True:
            budget_hit = check_budgets(self.incident)
            if budget_hit:
                self._log_event(IncidentPhase.BUDGET_EXHAUSTED, "result", "Iteration/time/token budget exhausted.")
                self._resolve(IncidentPhase.BUDGET_EXHAUSTED, budget_hit)
                self.session.commit()
                return budget_hit

            result = self.step(last_verification_failed)
            self.session.commit()
            last_verification_failed = False

            if step_delay:
                time.sleep(step_delay)

            if result == VERIFY_FAILED:
                last_verification_failed = True
                continue
            if result == PAUSED_FOR_APPROVAL:
                return None  # not terminal — resume_after_approval() continues this later
            if result is not None:
                return result  # terminal StoppingReason
            # else: an investigation step happened; keep looping

    def resume_after_approval(self, step_delay: float = 0.0) -> StoppingReason | None:
        """Call after a human has approved/rejected the most recent pending action."""
        pending_action = self._latest_action()
        if pending_action is None or pending_action.approval_status == ApprovalStatus.PENDING.value:
            raise ValueError("No decided action to resume from.")

        if pending_action.approval_status == ApprovalStatus.REJECTED.value:
            self._log_event(
                IncidentPhase.COLLECTING_OBSERVATIONS, "decision",
                f"Human rejected {pending_action.tool_name} on {pending_action.args.get('service')}; "
                f"continuing investigation without it.",
            )
            self.incident.phase = IncidentPhase.COLLECTING_OBSERVATIONS.value
            self.session.commit()
            return self.run_to_completion(step_delay=step_delay)

        result = self._execute_approved_action(pending_action)
        self.session.commit()
        if result == VERIFY_FAILED:
            self.incident.phase = IncidentPhase.COLLECTING_OBSERVATIONS.value
            self.session.commit()
            budget_hit = check_budgets(self.incident)
            if budget_hit:
                self._resolve(IncidentPhase.BUDGET_EXHAUSTED, budget_hit)
                self.session.commit()
                return budget_hit
            return self.run_to_completion(step_delay=step_delay)
        return result

    def _latest_action(self) -> m.ActionLog | None:
        stmt = select(m.ActionLog).where(m.ActionLog.incident_id == self.incident.id).order_by(m.ActionLog.created_at.desc()).limit(1)
        return self.session.execute(stmt).scalar_one_or_none()

    # ------------------------------------------------------------- step
    def step(self, last_verification_failed: bool) -> StepResult:
        self.incident.iteration += 1
        self._set_phase(IncidentPhase.COLLECTING_OBSERVATIONS)
        ctx = self._build_context(last_verification_failed)

        self._set_phase(IncidentPhase.GENERATING_HYPOTHESES)
        try:
            decision, usage, provider_name = self.llm.decide(ctx)
        except ProviderError as exc:
            self._log_event(IncidentPhase.ESCALATED, "result", f"LLM decision failed on all providers: {exc}")
            self._resolve(IncidentPhase.ESCALATED, StoppingReason.HUMAN_ESCALATION_REQUIRED)
            return StoppingReason.HUMAN_ESCALATION_REQUIRED

        self.incident.tokens_used += usage.total
        self._log_event(
            IncidentPhase.GENERATING_HYPOTHESES, "decision", decision.reasoning_summary,
            {"provider": provider_name, "hypotheses": [h.model_dump() for h in decision.hypotheses]},
        )
        self._persist_hypotheses(decision)
        if decision.root_cause_confirmed and decision.confirmed_root_cause:
            self.incident.confirmed_root_cause = decision.confirmed_root_cause

        action = decision.next_action
        if action.kind == "escalate":
            self._log_event(IncidentPhase.ESCALATED, "decision", action.escalation_reason or "Escalating to a human.")
            self._resolve(IncidentPhase.ESCALATED, StoppingReason.HUMAN_ESCALATION_REQUIRED)
            return StoppingReason.HUMAN_ESCALATION_REQUIRED
        if action.kind == "investigate":
            return self._do_investigate(action)
        if action.kind == "remediate":
            return self._do_remediate(action)

        self._log_event(IncidentPhase.NO_VALID_ACTIONS, "result", f"Unknown action kind '{action.kind}'.")
        self._resolve(IncidentPhase.NO_VALID_ACTIONS, StoppingReason.NO_VALID_ACTIONS_REMAINING)
        return StoppingReason.NO_VALID_ACTIONS_REMAINING

    def _do_investigate(self, action: NextAction) -> StepResult:
        self._set_phase(IncidentPhase.SELECTING_INVESTIGATION)
        tool_name, args = action.tool_name, action.args
        if not tool_name:
            self._log_event(IncidentPhase.NO_VALID_ACTIONS, "result", "Investigation action missing a tool_name.")
            self._resolve(IncidentPhase.NO_VALID_ACTIONS, StoppingReason.NO_VALID_ACTIONS_REMAINING)
            return StoppingReason.NO_VALID_ACTIONS_REMAINING

        h = dedup_hash(tool_name, args)
        if h in self._cache.known_hashes:
            self._cache.consecutive_stalls += 1
            self._log_event(
                IncidentPhase.CALLING_TOOL, "decision",
                f"Duplicate action detected: {tool_name}({args}) was already called; reusing cached result.",
            )
            if self._cache.consecutive_stalls >= 2:
                self._log_event(IncidentPhase.ESCALATED, "result", "Loop detected: no new evidence across repeated proposals.")
                self._resolve(IncidentPhase.ESCALATED, StoppingReason.LOOP_DETECTED)
                return StoppingReason.LOOP_DETECTED
            return CONTINUE

        self._cache.consecutive_stalls = 0
        self._set_phase(IncidentPhase.CALLING_TOOL)
        self._log_event(IncidentPhase.CALLING_TOOL, "action", f"Calling {tool_name} with {args}", {"rationale": action.rationale})
        try:
            result, risk = self._execute_tool(tool_name, args)
        except (ValidationError, KeyError) as exc:
            self._record_tool_call(tool_name, args, {"error": str(exc)}, ToolCallStatus.ERROR, RiskLevel.READ_ONLY)
            self._log_event(IncidentPhase.ANALYZING_RESULTS, "result", f"{tool_name} failed: {exc}")
            return CONTINUE

        self._record_tool_call(tool_name, args, result, ToolCallStatus.SUCCESS, risk)
        self.incident.tool_call_count += 1
        self._set_phase(IncidentPhase.ANALYZING_RESULTS)
        self._log_event(IncidentPhase.ANALYZING_RESULTS, "evidence", f"Result from {tool_name}", {"tool_name": tool_name, "result": result})
        self._set_phase(IncidentPhase.UPDATING_HYPOTHESES)
        self._set_phase(IncidentPhase.ROOT_CAUSE_CHECK)
        return CONTINUE

    def _execute_tool(self, tool_name: str, args: dict) -> tuple[dict, RiskLevel]:
        tool = get_tool(tool_name)
        parsed = tool.args_model.model_validate(args)
        risk = tool.risk_for(parsed)
        return tool.run(self.tool_ctx, parsed), risk

    def _record_tool_call(self, tool_name: str, args: dict, result: dict, status: ToolCallStatus, risk: RiskLevel) -> m.ToolCallLog:
        row = m.ToolCallLog(
            incident_id=self.incident.id, iteration=self.incident.iteration, tool_name=tool_name,
            risk_level=risk.value, args=args, result=result, status=status.value,
            dedup_hash=dedup_hash(tool_name, args),
        )
        self.session.add(row)
        self.session.flush()
        self._cache.tool_calls.append(row)
        self._cache.known_hashes.add(row.dedup_hash)
        return row

    def _do_remediate(self, action: NextAction) -> StepResult:
        self._set_phase(IncidentPhase.GENERATING_REMEDIATION)
        tool_name, args = action.tool_name, action.args
        if tool_name not in REMEDIATION_TOOLS:
            self._log_event(IncidentPhase.NO_VALID_ACTIONS, "result", f"'{tool_name}' is not a valid remediation tool.")
            self._resolve(IncidentPhase.NO_VALID_ACTIONS, StoppingReason.NO_VALID_ACTIONS_REMAINING)
            return StoppingReason.NO_VALID_ACTIONS_REMAINING

        tool = get_tool(tool_name)
        try:
            parsed = tool.args_model.model_validate(args)
        except ValidationError as exc:
            self._log_event(IncidentPhase.NO_VALID_ACTIONS, "result", f"Invalid args for {tool_name}: {exc}")
            self._resolve(IncidentPhase.NO_VALID_ACTIONS, StoppingReason.NO_VALID_ACTIONS_REMAINING)
            return StoppingReason.NO_VALID_ACTIONS_REMAINING

        risk = tool.risk_for(parsed)
        self._set_phase(IncidentPhase.RISK_CLASSIFICATION)
        self._log_event(
            IncidentPhase.RISK_CLASSIFICATION, "decision",
            f"Classified {tool_name} on {args.get('service')} as {risk.value}.", {"risk_level": risk.value},
        )
        action_row = propose_action(
            self.session, self.incident, self.incident.iteration, tool_name, args, risk, action.rationale,
            for_eval=self.for_eval,
        )

        if action_row.approval_status == ApprovalStatus.PENDING.value:
            self._set_phase(IncidentPhase.AWAITING_APPROVAL)
            self._log_event(
                IncidentPhase.AWAITING_APPROVAL, "decision",
                f"{tool_name} on {args.get('service')} is HIGH_RISK and requires human approval before executing.",
                {"action_id": action_row.id},
            )
            return PAUSED_FOR_APPROVAL

        self._log_event(
            IncidentPhase.RISK_CLASSIFICATION, "decision",
            f"{risk.value} action auto-approved by policy.", {"action_id": action_row.id},
        )
        return self._execute_approved_action(action_row)

    def _execute_approved_action(self, action_row: m.ActionLog) -> StepResult:
        self._set_phase(IncidentPhase.EXECUTING_REMEDIATION)
        sandbox = SandboxExecutor()
        started = time.monotonic()
        try:
            result = sandbox.execute(action_row.tool_name, action_row.args, self.tool_ctx)
        except SandboxViolation as exc:
            self._log_event(IncidentPhase.NO_VALID_ACTIONS, "result", str(exc))
            self._resolve(IncidentPhase.NO_VALID_ACTIONS, StoppingReason.NO_VALID_ACTIONS_REMAINING)
            return StoppingReason.NO_VALID_ACTIONS_REMAINING

        action_row.executed = True
        action_row.executed_at = _now()
        action_row.result = result
        self.incident.tool_call_count += 1
        self.session.flush()
        duration_ms = int((time.monotonic() - started) * 1000)
        self._log_event(
            IncidentPhase.EXECUTING_REMEDIATION, "action",
            f"Executed {action_row.tool_name} on {action_row.args.get('service')}.",
            {"result": result, "duration_ms": duration_ms},
        )

        self._set_phase(IncidentPhase.VERIFYING_HEALTH)
        target = action_row.args.get("service")
        health = self.engine.run_health_check(ServiceName(target) if target else None)
        healthy = health["healthy"]
        self.session.add(m.VerificationResult(
            incident_id=self.incident.id, iteration=self.incident.iteration, action_id=action_row.id,
            healthy=healthy, checks=health["checks"],
        ))
        self.session.flush()
        self._log_event(
            IncidentPhase.VERIFYING_HEALTH, "result",
            f"Post-remediation health check: {'healthy' if healthy else 'still unhealthy'}.",
            {"checks": health["checks"]},
        )

        if healthy:
            self._resolve(IncidentPhase.RESOLVED, StoppingReason.INCIDENT_RESOLVED)
            return StoppingReason.INCIDENT_RESOLVED

        self._set_phase(IncidentPhase.ROLLING_BACK)
        self._log_event(IncidentPhase.ROLLING_BACK, "decision", "Remediation did not restore health; continuing investigation.")
        return VERIFY_FAILED
