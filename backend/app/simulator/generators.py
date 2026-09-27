"""Deterministic, seeded generation of realistic-looking telemetry.

Every function takes a `random.Random` instance the caller seeded — same
seed in, byte-identical fleet history out. This is what makes incidents
reproducible: `inject_incident.py --seed 42 --type bad_deployment` always
produces the same commits, the same deploy, the same log lines.
"""
from __future__ import annotations

import datetime as dt
import random
import uuid

from app.enums import ServiceName
from app.simulator.world import BASELINES

COMMIT_VERBS = ["Fix", "Add", "Refactor", "Update", "Optimize", "Bump", "Tune", "Guard"]
COMMIT_SUBJECTS = [
    "connection pool handling", "retry backoff", "cache invalidation", "input validation",
    "timeout config", "error logging", "pagination", "auth middleware", "serializer",
    "health check endpoint", "metrics exporter", "rate limiter", "batch job",
]
AUTHORS = ["a.chen", "j.patel", "m.oconnor", "s.kim", "r.diallo", "l.novak"]

NORMAL_LOG_TEMPLATES = [
    ("INFO", "Handled request {method} {path} in {ms}ms"),
    ("INFO", "Cache hit for key user:{n}"),
    ("INFO", "Health check OK"),
    ("DEBUG", "Connection pool: {active}/{max} active"),
    ("INFO", "Processed batch of {n} records"),
]


def _rand_sha(rng: random.Random) -> str:
    return "".join(rng.choice("0123456789abcdef") for _ in range(40))


def generate_git_history(
    rng: random.Random, service: ServiceName, count: int, end_time: dt.datetime
) -> list[dict]:
    """Oldest-first list of commit dicts for a service's simulated repo history."""
    commits = []
    t = end_time - dt.timedelta(days=count)
    for _ in range(count):
        t += dt.timedelta(hours=rng.randint(4, 30))
        verb = rng.choice(COMMIT_VERBS)
        subject = rng.choice(COMMIT_SUBJECTS)
        files = [f"{service.value}/src/{subject.split()[0].lower()}.py"]
        commits.append(
            {
                "sha": _rand_sha(rng),
                "author": rng.choice(AUTHORS),
                "message": f"{verb} {subject}",
                "timestamp": t,
                "files_changed": files,
                "diff": f"--- a/{files[0]}\n+++ b/{files[0]}\n@@ -12,3 +12,4 @@\n+# {verb.lower()} {subject}\n",
            }
        )
    return commits


def generate_deployment_history(
    rng: random.Random, service: ServiceName, commits: list[dict], count: int, end_time: dt.datetime
) -> list[dict]:
    """Most deploys map to a commit; version numbers increment plausibly."""
    baseline = BASELINES[service]
    parts = [int(x.lstrip("v")) for x in baseline.version.split(".")]
    while len(parts) < 3:
        parts.append(0)
    major, minor, patch = parts[:3]
    deploys = []
    t = end_time - dt.timedelta(days=count * 2)
    chosen_commits = rng.sample(commits, k=min(count, len(commits)))
    chosen_commits.sort(key=lambda c: c["timestamp"])
    for commit in chosen_commits:
        t = commit["timestamp"] + dt.timedelta(minutes=rng.randint(5, 60))
        patch += 1
        deploys.append(
            {
                "version": f"v{major}.{minor}.{patch}",
                "git_sha": commit["sha"],
                "deployed_at": t,
                "deployed_by": rng.choice(AUTHORS),
                "status": "active",
                "diff_summary": commit["message"],
            }
        )
    if deploys:
        deploys[-1]["version"] = baseline.version  # last deploy matches current baseline
    return deploys


def generate_baseline_logs(
    rng: random.Random, service: ServiceName, count: int, end_time: dt.datetime, window_seconds: int = 600
) -> list[dict]:
    logs = []
    baseline = BASELINES[service]
    for _ in range(count):
        ts = end_time - dt.timedelta(seconds=rng.uniform(0, window_seconds))
        level, template = rng.choice(NORMAL_LOG_TEMPLATES)
        msg = template.format(
            method=rng.choice(["GET", "POST"]),
            path=rng.choice(["/api/users", "/api/orders", "/api/payments", "/health"]),
            ms=round(rng.gauss(baseline.latency_p50_ms, 5), 1),
            n=rng.randint(1, 9999),
            active=baseline.connections_active,
            max=baseline.connections_max,
        )
        logs.append({"timestamp": ts, "level": level, "message": msg, "trace_id": None})
    logs.sort(key=lambda entry: entry["timestamp"])
    return logs


def generate_baseline_metric_series(
    rng: random.Random,
    service: ServiceName,
    metric_name: str,
    base_value: float,
    count: int,
    end_time: dt.datetime,
    window_seconds: int = 600,
    noise_pct: float = 0.08,
) -> list[dict]:
    step = window_seconds / max(count, 1)
    points = []
    for i in range(count):
        ts = end_time - dt.timedelta(seconds=window_seconds - i * step)
        value = max(0.0, rng.gauss(base_value, base_value * noise_pct))
        points.append({"timestamp": ts, "value": round(value, 3)})
    return points


def generate_trace(
    rng: random.Random, entry_service: ServiceName, call_chain: list[ServiceName], end_time: dt.datetime
) -> tuple[str, list[dict]]:
    """A single request trace fanning out across `call_chain`, all children of entry_service's span."""
    trace_id = str(uuid.uuid4())
    spans = []
    root_start = 0.0
    root_span_id = str(uuid.uuid4())
    child_total = 0.0
    child_spans = []
    for svc in call_chain:
        baseline = BASELINES[svc]
        duration = max(0.5, rng.gauss(baseline.latency_p50_ms, baseline.latency_p50_ms * 0.2))
        start = root_start + child_total + rng.uniform(0.1, 0.5)
        child_spans.append(
            {
                "span_id": str(uuid.uuid4()),
                "parent_span_id": root_span_id,
                "service_name": svc.value,
                "operation": "handle_request",
                "start_ms": round(start, 2),
                "duration_ms": round(duration, 2),
                "status": "ok",
            }
        )
        child_total += duration
    root_duration = child_total + rng.uniform(1, 4)
    spans.append(
        {
            "span_id": root_span_id,
            "parent_span_id": None,
            "service_name": entry_service.value,
            "operation": "handle_request",
            "start_ms": 0.0,
            "duration_ms": round(root_duration, 2),
            "status": "ok",
        }
    )
    spans.extend(child_spans)
    return trace_id, spans
