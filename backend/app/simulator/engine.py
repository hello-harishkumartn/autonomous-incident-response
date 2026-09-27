"""SimulationEngine: the only thing allowed to read or mutate simulated world state.

Tools and the sandbox executor go through this class exclusively — nothing
in the agent layer touches the DB tables in `models_db.py` for telemetry
directly, and nothing anywhere touches real infrastructure. That boundary
is what makes "no unrestricted shell access" true by construction.
"""
from __future__ import annotations

import datetime as dt
import random
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models_db as m
from app.enums import ServiceName
from app.simulator import generators as gen
from app.simulator.world import ALL_SERVICES, BASELINES, DEPENDENCIES

if TYPE_CHECKING:
    from app.simulator.scenarios import IncidentScenario

STANDARD_METRICS = [
    "cpu_pct", "memory_pct", "latency_p50_ms", "latency_p99_ms", "error_rate", "connections_active",
]


class SimulationEngine:
    def __init__(self, session: Session, incident_id: str, seed: int):
        self.session = session
        self.incident_id = incident_id
        self.seed = seed
        self.rng = random.Random(seed)
        self.now = dt.datetime.now(dt.timezone.utc)

    # ------------------------------------------------------------------ setup
    def bootstrap(self) -> None:
        """Seed a healthy fleet: baseline states, history, config, telemetry."""
        for service in ALL_SERVICES:
            baseline = BASELINES[service]
            state = m.ServiceState(
                incident_id=self.incident_id,
                service_name=service.value,
                cpu_pct=baseline.cpu_pct,
                memory_pct=baseline.memory_pct,
                latency_p50_ms=baseline.latency_p50_ms,
                latency_p99_ms=baseline.latency_p99_ms,
                error_rate=baseline.error_rate,
                connections_active=baseline.connections_active,
                connections_max=baseline.connections_max,
                is_healthy=True,
                extra={"fault": None, "version": baseline.version},
            )
            self.session.add(state)
            self.session.flush()

            commits = gen.generate_git_history(self.rng, service, count=8, end_time=self.now)
            for c in commits:
                self.session.add(
                    m.GitCommitRecord(
                        incident_id=self.incident_id, service_name=service.value, sha=c["sha"],
                        author=c["author"], message=c["message"], timestamp=c["timestamp"],
                        files_changed=c["files_changed"], diff=c["diff"],
                    )
                )

            deploys = gen.generate_deployment_history(self.rng, service, commits, count=4, end_time=self.now)
            last_deploy_id = None
            for d in deploys:
                row = m.Deployment(
                    incident_id=self.incident_id, service_name=service.value, version=d["version"],
                    git_sha=d["git_sha"], deployed_at=d["deployed_at"], deployed_by=d["deployed_by"],
                    status="active", diff_summary=d["diff_summary"],
                )
                self.session.add(row)
                self.session.flush()
                last_deploy_id = row.id
            state.last_deploy_id = last_deploy_id

            for key, value in baseline.config.items():
                self.session.add(
                    m.ConfigSnapshot(
                        incident_id=self.incident_id, service_name=service.value, key=key, value=value,
                        last_changed_at=self.now - dt.timedelta(days=self.rng.randint(5, 60)),
                        changed_by=self.rng.choice(gen.AUTHORS), is_suspect=False,
                    )
                )

            for log in gen.generate_baseline_logs(self.rng, service, count=15, end_time=self.now):
                self.session.add(m.LogEntry(incident_id=self.incident_id, service_name=service.value, **log))

            for metric in STANDARD_METRICS:
                base_value = getattr(baseline, metric) if hasattr(baseline, metric) else baseline.connections_active
                for point in gen.generate_baseline_metric_series(
                    self.rng, service, metric, base_value, count=20, end_time=self.now
                ):
                    self.session.add(
                        m.MetricPoint(
                            incident_id=self.incident_id, service_name=service.value, metric_name=metric,
                            timestamp=point["timestamp"], value=point["value"],
                        )
                    )

        for entry_service, deps in DEPENDENCIES.items():
            if not deps:
                continue
            trace_id, spans = gen.generate_trace(self.rng, entry_service, deps, self.now)
            for span in spans:
                self.session.add(m.TraceSpan(incident_id=self.incident_id, trace_id=trace_id, **span))
        self.session.flush()

    # ------------------------------------------------------------------- read
    def get_service_state(self, service: ServiceName) -> m.ServiceState:
        stmt = select(m.ServiceState).where(
            m.ServiceState.incident_id == self.incident_id, m.ServiceState.service_name == service.value
        )
        return self.session.execute(stmt).scalar_one()

    def list_service_states(self) -> list[m.ServiceState]:
        stmt = select(m.ServiceState).where(m.ServiceState.incident_id == self.incident_id)
        return list(self.session.execute(stmt).scalars())

    def get_logs(
        self, service: ServiceName | None = None, level: str | None = None,
        since_seconds: int = 900, limit: int = 50, contains: str | None = None,
    ) -> list[m.LogEntry]:
        cutoff = self.now - dt.timedelta(seconds=since_seconds)
        stmt = select(m.LogEntry).where(m.LogEntry.incident_id == self.incident_id, m.LogEntry.timestamp >= cutoff)
        if service is not None:
            stmt = stmt.where(m.LogEntry.service_name == service.value)
        if level is not None:
            stmt = stmt.where(m.LogEntry.level == level)
        stmt = stmt.order_by(m.LogEntry.timestamp.desc()).limit(limit)
        rows = list(self.session.execute(stmt).scalars())
        if contains:
            rows = [r for r in rows if contains.lower() in r.message.lower()]
        return rows

    def get_metrics(self, service: ServiceName, metric_name: str, since_seconds: int = 900) -> list[m.MetricPoint]:
        cutoff = self.now - dt.timedelta(seconds=since_seconds)
        stmt = (
            select(m.MetricPoint)
            .where(
                m.MetricPoint.incident_id == self.incident_id,
                m.MetricPoint.service_name == service.value,
                m.MetricPoint.metric_name == metric_name,
                m.MetricPoint.timestamp >= cutoff,
            )
            .order_by(m.MetricPoint.timestamp.asc())
        )
        return list(self.session.execute(stmt).scalars())

    def get_recent_trace(self, service: ServiceName | None = None) -> tuple[str, list[m.TraceSpan]] | None:
        stmt = select(m.TraceSpan).where(m.TraceSpan.incident_id == self.incident_id)
        if service is not None:
            stmt = stmt.where(m.TraceSpan.service_name == service.value)
        stmt = stmt.order_by(m.TraceSpan.start_ms.desc()).limit(1)
        span = self.session.execute(stmt).scalar_one_or_none()
        if span is None:
            return None
        return self.get_trace_by_id(span.trace_id)

    def get_trace_by_id(self, trace_id: str) -> tuple[str, list[m.TraceSpan]]:
        stmt = select(m.TraceSpan).where(
            m.TraceSpan.incident_id == self.incident_id, m.TraceSpan.trace_id == trace_id
        ).order_by(m.TraceSpan.start_ms.asc())
        return trace_id, list(self.session.execute(stmt).scalars())

    def get_deployment(self, service: ServiceName, version: str | None = None) -> m.Deployment | None:
        stmt = select(m.Deployment).where(
            m.Deployment.incident_id == self.incident_id, m.Deployment.service_name == service.value
        )
        if version is not None:
            stmt = stmt.where(m.Deployment.version == version)
        stmt = stmt.order_by(m.Deployment.deployed_at.desc()).limit(1)
        return self.session.execute(stmt).scalar_one_or_none()

    def list_deployments(self, service: ServiceName, limit: int = 5) -> list[m.Deployment]:
        stmt = (
            select(m.Deployment)
            .where(m.Deployment.incident_id == self.incident_id, m.Deployment.service_name == service.value)
            .order_by(m.Deployment.deployed_at.desc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars())

    def get_git_diff(self, service: ServiceName, sha: str | None = None) -> m.GitCommitRecord | None:
        stmt = select(m.GitCommitRecord).where(
            m.GitCommitRecord.incident_id == self.incident_id, m.GitCommitRecord.service_name == service.value
        )
        if sha is not None:
            stmt = stmt.where(m.GitCommitRecord.sha == sha)
        stmt = stmt.order_by(m.GitCommitRecord.timestamp.desc()).limit(1)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_config(self, service: ServiceName) -> list[m.ConfigSnapshot]:
        stmt = select(m.ConfigSnapshot).where(
            m.ConfigSnapshot.incident_id == self.incident_id, m.ConfigSnapshot.service_name == service.value
        )
        return list(self.session.execute(stmt).scalars())

    # ----------------------------------------------------------- mutation
    def add_log(self, service: ServiceName, level: str, message: str, offset_seconds: float = 0.0) -> None:
        self.session.add(
            m.LogEntry(
                incident_id=self.incident_id, service_name=service.value, level=level, message=message,
                timestamp=self.now - dt.timedelta(seconds=offset_seconds), trace_id=None,
            )
        )

    def add_metric_point(self, service: ServiceName, metric_name: str, value: float, offset_seconds: float = 0.0) -> None:
        self.session.add(
            m.MetricPoint(
                incident_id=self.incident_id, service_name=service.value, metric_name=metric_name,
                timestamp=self.now - dt.timedelta(seconds=offset_seconds), value=value,
            )
        )

    def add_deployment(
        self, service: ServiceName, version: str, diff_summary: str, offset_seconds: float = 30.0,
        git_sha: str | None = None,
    ) -> m.Deployment:
        row = m.Deployment(
            incident_id=self.incident_id, service_name=service.value, version=version,
            git_sha=git_sha or "".join(self.rng.choice("0123456789abcdef") for _ in range(40)),
            deployed_at=self.now - dt.timedelta(seconds=offset_seconds),
            deployed_by=self.rng.choice(gen.AUTHORS), status="active", diff_summary=diff_summary,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def mark_config_suspect(self, service: ServiceName, key: str, new_value: str) -> None:
        stmt = select(m.ConfigSnapshot).where(
            m.ConfigSnapshot.incident_id == self.incident_id,
            m.ConfigSnapshot.service_name == service.value,
            m.ConfigSnapshot.key == key,
        )
        row = self.session.execute(stmt).scalar_one_or_none()
        if row is None:
            row = m.ConfigSnapshot(
                incident_id=self.incident_id, service_name=service.value, key=key, value=new_value,
                last_changed_at=self.now, changed_by="deploy-bot", is_suspect=True,
            )
            self.session.add(row)
        else:
            row.value = new_value
            row.last_changed_at = self.now
            row.changed_by = "deploy-bot"
            row.is_suspect = True

    def set_fault(
        self, service: ServiceName, fault: str | None, *, fix_tool: str | None = None, **state_updates,
    ) -> None:
        state = self.get_service_state(service)
        for key, value in state_updates.items():
            setattr(state, key, value)
        state.is_healthy = fault is None
        extra = dict(state.extra or {})
        extra["fault"] = fault
        if fix_tool is not None:
            extra["fix_tool"] = fix_tool
        state.extra = extra

    # ------------------------------------------------------------- actions
    def restart_service(self, service: ServiceName, scenario: "IncidentScenario | None" = None) -> dict:
        state = self.get_service_state(service)
        baseline = BASELINES[service]
        fixed = bool(scenario and scenario.fix_tool == "restart_service" and scenario.fix_target == service)
        state.connections_active = baseline.connections_active
        state.cpu_pct = baseline.cpu_pct
        if fixed:
            state.memory_pct = baseline.memory_pct
            state.latency_p50_ms = baseline.latency_p50_ms
            state.latency_p99_ms = baseline.latency_p99_ms
            state.error_rate = baseline.error_rate
            state.is_healthy = True
            extra = dict(state.extra or {})
            extra["fault"] = None
            state.extra = extra
        self.add_log(service, "INFO", f"Service {service.value} restarted by remediation action.")
        self.add_metric_point(service, "connections_active", state.connections_active)
        return {"service": service.value, "restarted": True, "healthy_after": state.is_healthy}

    def rollback_deployment(self, service: ServiceName, scenario: "IncidentScenario | None" = None) -> dict:
        deploys = self.list_deployments(service, limit=2)
        if len(deploys) < 2:
            return {"service": service.value, "rolled_back": False, "reason": "no previous deployment to roll back to"}
        current, previous = deploys[0], deploys[1]
        current.status = "rolled_back"
        rollback = m.Deployment(
            incident_id=self.incident_id, service_name=service.value, version=previous.version,
            git_sha=previous.git_sha, deployed_at=self.now, deployed_by="aire-agent", status="active",
            diff_summary=f"Rollback of {current.version} ({current.git_sha[:8]}) to {previous.version}",
            is_rollback_of=current.id,
        )
        self.session.add(rollback)
        self.session.flush()

        state = self.get_service_state(service)
        state.last_deploy_id = rollback.id
        fixed = bool(scenario and scenario.fix_tool == "rollback_deployment" and scenario.fix_target == service)
        if fixed:
            baseline = BASELINES[service]
            state.error_rate = baseline.error_rate
            state.latency_p50_ms = baseline.latency_p50_ms
            state.latency_p99_ms = baseline.latency_p99_ms
            state.is_healthy = True
            extra = dict(state.extra or {})
            extra["fault"] = None
            state.extra = extra
        self.add_log(service, "INFO", f"Rolled back {service.value} from {current.version} to {previous.version}.")
        return {"service": service.value, "rolled_back": True, "to_version": previous.version, "healthy_after": state.is_healthy}

    def run_health_check(self, service: ServiceName | None = None) -> dict:
        states = [self.get_service_state(service)] if service else self.list_service_states()
        checks = {
            s.service_name: {
                "healthy": s.is_healthy,
                "error_rate": round(s.error_rate, 4),
                "latency_p99_ms": round(s.latency_p99_ms, 1),
                "connections_active": s.connections_active,
                "connections_max": s.connections_max,
            }
            for s in states
        }
        return {"healthy": all(c["healthy"] for c in checks.values()), "checks": checks}

    def execute_diagnostic(self, service: ServiceName, diagnostic: str) -> dict:
        state = self.get_service_state(service)
        diagnostics = {
            "connection_pool_check": {
                "active": state.connections_active, "max": state.connections_max,
                "utilization_pct": round(100 * state.connections_active / max(state.connections_max, 1), 1),
            },
            "memory_check": {"memory_pct": state.memory_pct, "threshold_pct": 90},
            "latency_check": {"p50_ms": state.latency_p50_ms, "p99_ms": state.latency_p99_ms},
            "dependency_ping": {
                "dependencies": [d.value for d in DEPENDENCIES.get(service, [])],
                "reachable": state.is_healthy or self.rng.random() > 0.3,
            },
            "disk_check": {
                "disk_pct": (state.extra or {}).get("disk_pct", 22), "threshold_pct": 90,
            },
        }
        return diagnostics.get(diagnostic, {"error": f"unknown diagnostic '{diagnostic}'"})
