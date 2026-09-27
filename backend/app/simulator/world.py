"""Static topology and healthy baselines for the simulated fleet.

Six services, modeled as a dependency graph, each with baseline resource/
latency/error characteristics. Incident scenarios perturb these baselines;
tools read the (perturbed) state back out as telemetry.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.enums import ServiceName

# Who calls whom. Used by the trace generator to build realistic call chains
# and by scenarios to decide which upstream services see symptoms.
DEPENDENCIES: dict[ServiceName, list[ServiceName]] = {
    ServiceName.API_GATEWAY: [ServiceName.USER_SERVICE, ServiceName.ORDER_SERVICE],
    ServiceName.USER_SERVICE: [ServiceName.POSTGRES, ServiceName.REDIS],
    ServiceName.ORDER_SERVICE: [ServiceName.POSTGRES, ServiceName.REDIS, ServiceName.PAYMENT_SERVICE],
    ServiceName.PAYMENT_SERVICE: [ServiceName.POSTGRES],
    ServiceName.POSTGRES: [],
    ServiceName.REDIS: [],
}


def upstream_of(service: ServiceName) -> list[ServiceName]:
    return [svc for svc, deps in DEPENDENCIES.items() if service in deps]


@dataclass(frozen=True)
class ServiceBaseline:
    cpu_pct: float
    memory_pct: float
    latency_p50_ms: float
    latency_p99_ms: float
    error_rate: float
    connections_active: int
    connections_max: int
    version: str
    config: dict[str, str] = field(default_factory=dict)


BASELINES: dict[ServiceName, ServiceBaseline] = {
    ServiceName.API_GATEWAY: ServiceBaseline(
        cpu_pct=18, memory_pct=35, latency_p50_ms=12, latency_p99_ms=45,
        error_rate=0.002, connections_active=40, connections_max=500, version="v1.14.2",
        config={"request_timeout_ms": "5000", "rate_limit_per_min": "6000"},
    ),
    ServiceName.USER_SERVICE: ServiceBaseline(
        cpu_pct=22, memory_pct=40, latency_p50_ms=18, latency_p99_ms=60,
        error_rate=0.001, connections_active=15, connections_max=100, version="v2.7.0",
        config={"db_pool_size": "20", "cache_ttl_seconds": "300"},
    ),
    ServiceName.ORDER_SERVICE: ServiceBaseline(
        cpu_pct=28, memory_pct=45, latency_p50_ms=25, latency_p99_ms=90,
        error_rate=0.003, connections_active=18, connections_max=100, version="v3.4.1",
        config={"db_pool_size": "20", "payment_call_timeout_ms": "3000"},
    ),
    ServiceName.PAYMENT_SERVICE: ServiceBaseline(
        cpu_pct=20, memory_pct=38, latency_p50_ms=40, latency_p99_ms=150,
        error_rate=0.002, connections_active=10, connections_max=80, version="v1.9.3",
        config={"gateway_timeout_ms": "4000", "retry_max_attempts": "3"},
    ),
    ServiceName.POSTGRES: ServiceBaseline(
        cpu_pct=30, memory_pct=50, latency_p50_ms=2, latency_p99_ms=15,
        error_rate=0.0, connections_active=45, connections_max=100, version="15.4",
        config={"max_connections": "100", "shared_buffers_mb": "2048"},
    ),
    ServiceName.REDIS: ServiceBaseline(
        cpu_pct=10, memory_pct=25, latency_p50_ms=1, latency_p99_ms=5,
        error_rate=0.0, connections_active=30, connections_max=200, version="7.2",
        config={"maxmemory_mb": "1024", "maxmemory_policy": "allkeys-lru"},
    ),
}

ALL_SERVICES: list[ServiceName] = list(ServiceName)
