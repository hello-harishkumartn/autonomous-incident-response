"""The 10 reproducible incident scenarios.

Each scenario is a pure perturbation of a bootstrapped, healthy
`SimulationEngine`: it writes anomalous logs/metrics/deploys/config and
flips the affected service(s) unhealthy. `fix_tool`/`fix_target` encode the
ground truth used by `SimulationEngine.restart_service` /
`rollback_deployment` to decide whether an attempted remediation actually
resolves the fault (used for eval scoring too — never exposed to the agent).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.enums import IncidentType, ServiceName
from app.simulator.engine import SimulationEngine


@dataclass(frozen=True)
class IncidentScenario:
    type: IncidentType
    title: str
    alert_summary: str
    ground_truth_root_cause: str
    fix_tool: str  # "restart_service" | "rollback_deployment"
    fix_target: ServiceName
    affected_services: list[ServiceName]
    apply: Callable[[SimulationEngine], None]


def _db_connection_exhaustion(e: SimulationEngine) -> None:
    svc = ServiceName.ORDER_SERVICE
    e.set_fault(svc, "db_connection_exhaustion", fix_tool="restart_service",
                connections_active=98, error_rate=0.35, latency_p50_ms=280, latency_p99_ms=1800)
    e.add_log(svc, "ERROR", "QueuePool limit of size 20 overflow 0 reached, connection timed out", 20)
    e.add_log(svc, "ERROR", "TimeoutError: could not obtain a connection from the pool within 30s", 15)
    e.add_log(svc, "WARN", "Connection pool: 98/100 active, 0 idle", 10)
    for i, off in enumerate([300, 240, 180, 120, 60, 20]):
        e.add_metric_point(svc, "connections_active", 40 + i * 10, off)
        e.add_metric_point(svc, "error_rate", 0.02 + i * 0.06, off)
    pg = ServiceName.POSTGRES
    e.add_metric_point(pg, "connections_active", 96, 20)
    e.add_log(pg, "WARN", "remaining connection slots are reserved for non-replication superuser connections", 15)


def _memory_spike(e: SimulationEngine) -> None:
    svc = ServiceName.USER_SERVICE
    e.set_fault(svc, "memory_spike", fix_tool="restart_service",
                memory_pct=94, latency_p50_ms=120, latency_p99_ms=900, error_rate=0.08)
    e.add_log(svc, "WARN", "Heap usage at 89% after full GC, up from 41% baseline", 40)
    e.add_log(svc, "WARN", "GC overhead limit approaching: full GC pauses now averaging 1200ms", 20)
    e.add_log(svc, "ERROR", "Request handler timed out waiting for GC pause to complete", 10)
    for i, off in enumerate([300, 240, 180, 120, 60, 20]):
        e.add_metric_point(svc, "memory_pct", 40 + i * 9, off)


def _api_latency_increase(e: SimulationEngine) -> None:
    root = ServiceName.ORDER_SERVICE
    symptom = ServiceName.API_GATEWAY
    e.set_fault(root, "api_latency_increase", fix_tool="restart_service",
                cpu_pct=97, latency_p50_ms=310, latency_p99_ms=2100, error_rate=0.05)
    e.add_log(root, "WARN", "Event loop lag detected: 1840ms, background job 'inventory_resync' running unbounded", 25)
    e.add_log(root, "WARN", "CPU throttling triggered at 97% sustained utilization", 15)
    state = e.get_service_state(symptom)
    state.latency_p50_ms = 140
    state.latency_p99_ms = 950
    e.add_log(symptom, "WARN", "Upstream order_service p99 latency elevated (950ms), client timeouts increasing", 10)
    for i, off in enumerate([300, 240, 180, 120, 60, 20]):
        e.add_metric_point(root, "cpu_pct", 25 + i * 12, off)
        e.add_metric_point(symptom, "latency_p99_ms", 60 + i * 150, off)


def _bad_deployment(e: SimulationEngine) -> None:
    svc = ServiceName.PAYMENT_SERVICE
    deploy = e.add_deployment(
        svc, version="v1.9.4", diff_summary="Update gateway response parser to new provider schema", offset_seconds=95,
    )
    e.set_fault(svc, "bad_deployment", fix_tool="rollback_deployment",
                error_rate=0.42, latency_p50_ms=55, latency_p99_ms=210)
    state = e.get_service_state(svc)
    state.last_deploy_id = deploy.id
    e.add_log(svc, "ERROR", "Unhandled exception in parse_gateway_response: KeyError('status')", 60)
    e.add_log(svc, "ERROR", "Unhandled exception in parse_gateway_response: KeyError('status')", 30)
    e.add_log(svc, "INFO", f"Deployed {deploy.version} ({deploy.git_sha[:8]}): {deploy.diff_summary}", 95)
    for i, off in enumerate([80, 60, 40, 20]):
        e.add_metric_point(svc, "error_rate", 0.05 + i * 0.12, off)


def _redis_failure(e: SimulationEngine) -> None:
    svc = ServiceName.REDIS
    e.set_fault(svc, "redis_failure", fix_tool="restart_service",
                memory_pct=100, error_rate=0.6, latency_p50_ms=400, latency_p99_ms=3000)
    e.add_log(svc, "ERROR", "OOM command not allowed when used memory > 'maxmemory'", 20)
    e.add_log(svc, "ERROR", "Client connection rejected: max clients reached", 10)
    for downstream in (ServiceName.USER_SERVICE, ServiceName.ORDER_SERVICE):
        state = e.get_service_state(downstream)
        state.latency_p99_ms *= 3
        e.add_log(downstream, "WARN", "Cache miss storm detected, falling back to postgres for all reads", 15)
    pg = ServiceName.POSTGRES
    e.get_service_state(pg).cpu_pct = 88
    e.add_log(pg, "WARN", "Query volume 4x baseline, likely cache-miss fallback traffic", 12)
    for i, off in enumerate([200, 150, 100, 50, 15]):
        e.add_metric_point(svc, "memory_pct", 60 + i * 8, off)


def _config_error(e: SimulationEngine) -> None:
    svc = ServiceName.ORDER_SERVICE
    e.mark_config_suspect(svc, "payment_call_timeout_ms", "50")
    deploy = e.add_deployment(svc, version="v3.4.2", diff_summary="Tune payment_call_timeout_ms for faster failover", offset_seconds=110)
    e.set_fault(svc, "config_error", fix_tool="rollback_deployment", error_rate=0.31, latency_p50_ms=45)
    e.get_service_state(svc).last_deploy_id = deploy.id
    e.add_log(svc, "ERROR", "TimeoutError calling payment_service after 50ms (configured timeout)", 40)
    e.add_log(svc, "ERROR", "TimeoutError calling payment_service after 50ms (configured timeout)", 15)
    e.add_log(svc, "INFO", f"Deployed {deploy.version} ({deploy.git_sha[:8]}): {deploy.diff_summary}", 110)
    for i, off in enumerate([90, 60, 30]):
        e.add_metric_point(svc, "error_rate", 0.08 + i * 0.08, off)


def _dependency_timeout(e: SimulationEngine) -> None:
    svc = ServiceName.PAYMENT_SERVICE
    e.set_fault(svc, "dependency_timeout", fix_tool="restart_service",
                error_rate=0.55, latency_p50_ms=4000, latency_p99_ms=4200)
    e.add_log(svc, "ERROR", "TimeoutError calling external payment-gateway after 4000ms", 30)
    e.add_log(svc, "WARN", "Circuit breaker OPEN for payment-gateway after 12 consecutive timeouts", 20)
    e.add_log(svc, "ERROR", "Request rejected: circuit breaker open for dependency 'payment-gateway'", 10)
    for i, off in enumerate([200, 150, 100, 50, 15]):
        e.add_metric_point(svc, "latency_p99_ms", 150 + i * 800, off)


def _disk_space_exhaustion(e: SimulationEngine) -> None:
    svc = ServiceName.POSTGRES
    e.set_fault(svc, "disk_space_exhaustion", fix_tool="restart_service", error_rate=0.4, cpu_pct=55)
    state = e.get_service_state(svc)
    extra = dict(state.extra or {})
    extra["disk_pct"] = 98
    state.extra = extra
    e.add_log(svc, "ERROR", "could not extend file \"base/16401/2683\": No space left on device", 25)
    e.add_log(svc, "ERROR", "PANIC: could not write to file \"pg_wal/000000010000000000000042\"", 12)
    e.add_log(svc, "WARN", "WAL archiving stuck: archive_command has failed 340 times in a row", 40)
    for i, off in enumerate([300, 200, 100, 30]):
        e.add_metric_point(svc, "error_rate", 0.05 + i * 0.1, off)


def _cascading_retry_storm(e: SimulationEngine) -> None:
    svc = ServiceName.ORDER_SERVICE
    e.set_fault(svc, "cascading_retry_storm", fix_tool="restart_service",
                cpu_pct=96, connections_active=97, error_rate=0.22)
    e.add_log(svc, "WARN", "Retrying payment call (attempt 6/6) with fixed 0ms backoff", 20)
    e.add_log(svc, "WARN", "Retrying payment call (attempt 6/6) with fixed 0ms backoff", 10)
    pay = ServiceName.PAYMENT_SERVICE
    e.get_service_state(pay).error_rate = 0.18
    e.add_log(pay, "WARN", "Request volume 6x baseline from order_service, latency degrading under load", 15)
    for i, off in enumerate([180, 120, 60, 20]):
        e.add_metric_point(svc, "connections_active", 40 + i * 15, off)


def _credential_expiry(e: SimulationEngine) -> None:
    svc = ServiceName.USER_SERVICE
    e.set_fault(svc, "credential_expiry", fix_tool="restart_service", error_rate=0.5, latency_p50_ms=30)
    e.mark_config_suspect(svc, "db_credential_rotated_at", "just now (process still using cached token)")
    e.add_log(svc, "ERROR", "FATAL: password authentication failed for user \"user_service_app\"", 30)
    e.add_log(svc, "ERROR", "FATAL: role \"user_service_app\" password expired", 15)
    for i, off in enumerate([120, 80, 40, 10]):
        e.add_metric_point(svc, "error_rate", 0.1 + i * 0.12, off)


SCENARIOS: dict[IncidentType, IncidentScenario] = {
    IncidentType.DB_CONNECTION_EXHAUSTION: IncidentScenario(
        type=IncidentType.DB_CONNECTION_EXHAUSTION,
        title="Order service database connection pool exhaustion",
        alert_summary="High error rate and request timeouts on order_service; connection pool near saturation.",
        ground_truth_root_cause=(
            "A connection leak in order_service is not releasing DB connections back to the pool, "
            "exhausting its connection pool against Postgres."
        ),
        fix_tool="restart_service", fix_target=ServiceName.ORDER_SERVICE,
        affected_services=[ServiceName.ORDER_SERVICE, ServiceName.POSTGRES], apply=_db_connection_exhaustion,
    ),
    IncidentType.MEMORY_SPIKE: IncidentScenario(
        type=IncidentType.MEMORY_SPIKE,
        title="User service memory spike",
        alert_summary="user_service memory utilization climbing steadily, latency degrading with GC pauses.",
        ground_truth_root_cause="A memory leak in user_service's session cache causes unbounded heap growth.",
        fix_tool="restart_service", fix_target=ServiceName.USER_SERVICE,
        affected_services=[ServiceName.USER_SERVICE], apply=_memory_spike,
    ),
    IncidentType.API_LATENCY_INCREASE: IncidentScenario(
        type=IncidentType.API_LATENCY_INCREASE,
        title="API gateway latency increase",
        alert_summary="api_gateway p99 latency up 10x; client timeout reports increasing.",
        ground_truth_root_cause=(
            "order_service is CPU-starved by a runaway background job, causing cascading latency at api_gateway."
        ),
        fix_tool="restart_service", fix_target=ServiceName.ORDER_SERVICE,
        affected_services=[ServiceName.API_GATEWAY, ServiceName.ORDER_SERVICE], apply=_api_latency_increase,
    ),
    IncidentType.BAD_DEPLOYMENT: IncidentScenario(
        type=IncidentType.BAD_DEPLOYMENT,
        title="Bad deployment to payment service",
        alert_summary="payment_service error rate spiked immediately following a deployment.",
        ground_truth_root_cause=(
            "Deployment v1.9.4 of payment_service introduced a regression in the gateway response parser."
        ),
        fix_tool="rollback_deployment", fix_target=ServiceName.PAYMENT_SERVICE,
        affected_services=[ServiceName.PAYMENT_SERVICE], apply=_bad_deployment,
    ),
    IncidentType.REDIS_FAILURE: IncidentScenario(
        type=IncidentType.REDIS_FAILURE,
        title="Redis cache failure",
        alert_summary="Redis rejecting connections and commands; downstream services show cache-miss storms.",
        ground_truth_root_cause=(
            "Redis hit maxmemory with no eviction configured, becoming unresponsive and forcing "
            "cache-miss fallback load onto Postgres."
        ),
        fix_tool="restart_service", fix_target=ServiceName.REDIS,
        affected_services=[ServiceName.REDIS, ServiceName.USER_SERVICE, ServiceName.ORDER_SERVICE],
        apply=_redis_failure,
    ),
    IncidentType.CONFIG_ERROR: IncidentScenario(
        type=IncidentType.CONFIG_ERROR,
        title="Bad configuration change on order service",
        alert_summary="order_service error rate rising; timeouts calling payment_service.",
        ground_truth_root_cause=(
            "A config deployment set payment_call_timeout_ms to 50ms, far too low, causing premature timeouts."
        ),
        fix_tool="rollback_deployment", fix_target=ServiceName.ORDER_SERVICE,
        affected_services=[ServiceName.ORDER_SERVICE], apply=_config_error,
    ),
    IncidentType.DEPENDENCY_TIMEOUT: IncidentScenario(
        type=IncidentType.DEPENDENCY_TIMEOUT,
        title="Payment gateway dependency timeout",
        alert_summary="payment_service latency and error rate spiking; circuit breaker events in logs.",
        ground_truth_root_cause=(
            "The external payment gateway is intermittently slow; payment_service's circuit breaker got "
            "stuck open after a burst of timeouts, rejecting all calls."
        ),
        fix_tool="restart_service", fix_target=ServiceName.PAYMENT_SERVICE,
        affected_services=[ServiceName.PAYMENT_SERVICE], apply=_dependency_timeout,
    ),
    IncidentType.DISK_SPACE_EXHAUSTION: IncidentScenario(
        type=IncidentType.DISK_SPACE_EXHAUSTION,
        title="Postgres disk space exhaustion",
        alert_summary="Postgres write errors; WAL archiving failing repeatedly.",
        ground_truth_root_cause=(
            "Postgres WAL accumulated because archiving was stuck, filling the data disk to capacity."
        ),
        fix_tool="restart_service", fix_target=ServiceName.POSTGRES,
        affected_services=[ServiceName.POSTGRES], apply=_disk_space_exhaustion,
    ),
    IncidentType.CASCADING_RETRY_STORM: IncidentScenario(
        type=IncidentType.CASCADING_RETRY_STORM,
        title="Cascading retry storm from order to payment service",
        alert_summary="order_service CPU and connections pegged; payment_service under abnormal load.",
        ground_truth_root_cause=(
            "An aggressive no-backoff retry policy in order_service turned a brief payment_service blip "
            "into a self-sustaining retry storm."
        ),
        fix_tool="restart_service", fix_target=ServiceName.ORDER_SERVICE,
        affected_services=[ServiceName.ORDER_SERVICE, ServiceName.PAYMENT_SERVICE], apply=_cascading_retry_storm,
    ),
    IncidentType.CREDENTIAL_EXPIRY: IncidentScenario(
        type=IncidentType.CREDENTIAL_EXPIRY,
        title="Expired database credential on user service",
        alert_summary="user_service failing to authenticate against Postgres; error rate spiking.",
        ground_truth_root_cause=(
            "The database credential for user_service was rotated, but the running process kept using "
            "the cached, now-expired token."
        ),
        fix_tool="restart_service", fix_target=ServiceName.USER_SERVICE,
        affected_services=[ServiceName.USER_SERVICE], apply=_credential_expiry,
    ),
}


def get_scenario(incident_type: IncidentType | str) -> IncidentScenario:
    if isinstance(incident_type, str):
        incident_type = IncidentType(incident_type)
    return SCENARIOS[incident_type]
