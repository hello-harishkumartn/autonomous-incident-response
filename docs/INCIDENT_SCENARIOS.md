# Incident Scenarios

All 10 are defined in `backend/app/simulator/scenarios.py`. Each is a pure
function of a seeded `SimulationEngine`: given the same `(scenario_type,
seed)`, `bootstrap()` + `apply()` produce byte-identical telemetry every
time — that's the "reproducible" in "reproducible incidents."

```bash
python scripts/inject_incident.py --type <scenario_type> --seed 42 --investigate --approve-all
```

| Scenario type | Affected service(s) | Ground truth root cause | Correct fix | Fix risk |
| --- | --- | --- | --- | --- |
| `db_connection_exhaustion` | order_service, postgres | Connection leak in order_service exhausts its DB pool against Postgres | `restart_service(order_service)` | LOW_RISK |
| `memory_spike` | user_service | Memory leak in user_service's session cache causes unbounded heap growth | `restart_service(user_service)` | LOW_RISK |
| `api_latency_increase` | api_gateway, order_service | order_service CPU-starved by a runaway background job, cascading latency to api_gateway | `restart_service(order_service)` | LOW_RISK |
| `bad_deployment` | payment_service | Deployment v1.9.4 introduced a regression in the gateway response parser | `rollback_deployment(payment_service)` | HIGH_RISK |
| `redis_failure` | redis, user_service, order_service | Redis hit maxmemory with no eviction, cache-miss storm hits Postgres | `restart_service(redis)` | HIGH_RISK |
| `config_error` | order_service | Config deploy set `payment_call_timeout_ms=50`, far too low | `rollback_deployment(order_service)` | HIGH_RISK |
| `dependency_timeout` | payment_service | External payment gateway intermittently slow; circuit breaker stuck open | `restart_service(payment_service)` | LOW_RISK |
| `disk_space_exhaustion` | postgres | WAL accumulated because archiving is stuck, disk full | `restart_service(postgres)` | HIGH_RISK |
| `cascading_retry_storm` | order_service, payment_service | No-backoff retry policy in order_service turns a blip into a retry storm | `restart_service(order_service)` | LOW_RISK |
| `credential_expiry` | user_service | DB credential rotated; process still using cached, expired token | `restart_service(user_service)` | LOW_RISK |

Risk follows two rules (see [SAFETY.md](SAFETY.md)): `rollback_deployment`
is always HIGH_RISK; `restart_service` is HIGH_RISK only when the target is
stateful/shared infrastructure (`postgres`, `redis`) and LOW_RISK for the
four stateless app services. That's why 6 of the 10 scenarios resolve
without a human in the loop and 4 require an approval — a deliberate mix,
not an accident of which faults happen to exist.

## What "ground truth" is used for, and what it isn't

`ground_truth_root_cause` and `fix_tool`/`fix_target` are stored on the
`IncidentScenario` and copied onto `Incident.ground_truth_*` at creation —
but never exposed to the LLM/offline-provider decision context
(`AgentContext` in `llm/base.py` has no such field). They're used for two
things only: (1) `SimulationEngine.restart_service`/`rollback_deployment`
check them internally to decide whether an attempted fix actually clears
the fault (`extra={"fault": None}`) or is a no-op that leaves it broken —
this is what makes "recovered? no → rollback + continue investigating" a
real branch instead of always succeeding; and (2) the eval harness scores
`correct_fix` by comparing the *executed, successful* action against them.

## Adding an 11th scenario

1. Write an `_apply` function in `scenarios.py` following the existing
   pattern: `e.set_fault(...)`, then `e.add_log`/`e.add_metric_point`/
   `e.add_deployment`/`e.mark_config_suspect` calls that make the fault
   observable through the existing tools.
2. Add an `IncidentType` value in `enums.py`.
3. Register an `IncidentScenario(...)` entry in `SCENARIOS`.
4. If the correct fix's log signature doesn't already match a rule in
   `llm/offline_provider.py:_RULES`, add one — otherwise the offline
   provider (and therefore CI) can't resolve it and will escalate.
