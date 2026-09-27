# Evaluation

## Running it

```bash
python scripts/run_eval.py --trials 3          # 10 scenarios x 3 = 30 runs
python scripts/run_eval.py --trials 5 --seed 200 --out eval/results/my_run.json
```

`backend/app/eval/benchmark.py:run_benchmark` runs every `IncidentType`
`trials_per_scenario` times (seed `base_seed + i` per trial) through the
real `AgentLoop` — same code path as the CLI/API, not a special eval-only
shortcut — with one deliberate difference: `auto_approve_high_risk_for_eval`
is set for the duration of the run so a benchmark of 30+ runs doesn't block
on human approval 4/10 of the time. See [SAFETY.md](SAFETY.md) for why that
flag can't leak into interactive use.

## Metrics (`backend/app/eval/benchmark.py:_score`)

| Metric | Definition |
| --- | --- |
| `root_cause_accuracy` | Resolved **and** the executed action that fixed it matches the scenario's ground-truth `(fix_tool, fix_target)` |
| `remediation_success_rate` | Fraction of runs whose `StoppingReason == INCIDENT_RESOLVED` |
| `human_escalation_rate` | Fraction whose `StoppingReason == HUMAN_ESCALATION_REQUIRED` (genuine escalation — HIGH_RISK approval pauses don't count, they're auto-approved for this run) |
| `mean_tool_calls` / `mean_iterations` | `Incident.tool_call_count` / `Incident.iteration`, averaged |
| `mean_time_to_diagnosis_s` | Wall-clock from `Incident.created_at` to the first `IncidentEvent` carrying a `confirmed` hypothesis |
| `mean_time_to_completion_s` | Wall-clock from creation to `Incident.resolved_at` (set on every terminal state, not just success) |
| `mean_tokens_used` | `Incident.tokens_used`, averaged — real usage from Gemini's `usage_metadata`, or the offline provider's character-count estimate |
| `unnecessary_action_rate` | (executed remediation actions that were *not* the one that fixed it) / (all executed remediation actions), across the run set |

## Baseline results (offline provider, committed)

`eval/results/baseline_offline_provider.json` — 30 runs (10 scenarios × 3
trials, seeds 100–102), generated 2026-09-27 on this machine with no
Gemini/Ollama available:

| Metric | Value |
| --- | --- |
| root_cause_accuracy | 1.00 |
| remediation_success_rate | 1.00 |
| human_escalation_rate | 0.00 |
| unnecessary_action_rate | 0.00 |
| mean_iterations | 5.0 |
| mean_tool_calls | 5.0 |
| mean_tokens_used | ~3,267 |
| mean_time_to_diagnosis_s | ~4.4s |
| mean_time_to_completion_s | ~4.4s |

**Read this baseline for what it is, not more.** The offline provider
(`llm/offline_provider.py`) is a deterministic rule-based expert system —
given the same evidence, it makes the same call every time, so 100%
accuracy here mostly certifies that the simulator's fault signatures, the
tool surface, and the loop's state machine are wired correctly end-to-end,
not that "the AI is good at SRE." It has no failure modes to measure
(hence 0% escalation, 0% unnecessary actions) because it never guesses. The
~4.4s "time to diagnosis" is dominated by `SimulationEngine.bootstrap()`'s
per-service SQLAlchemy inserts (~1,000 rows of seed telemetry per
incident), not model latency — the offline provider itself decides in
microseconds.

**The metrics earn their keep once a real LLM is in the loop.** Set
`GEMINI_API_KEY` and rerun the same command: `root_cause_accuracy` can
drop below 1.0 (a real model can misread evidence), `unnecessary_action_rate`
can go above 0 (a wrong first guess that a healthy-check catches and the
loop retries — see [AGENT_LOOP.md](AGENT_LOOP.md)'s rollback-and-continue
path), `human_escalation_rate` can rise (the model gives up or the sandbox
rejects something), and `mean_tokens_used`/cost becomes real spend instead
of a character-count estimate. That comparison — offline baseline vs. a
real model's numbers — is the actual point of the harness.

## Storage

Every run writes `{"summary": {...}, "trials": [...]}` — the `trials` list
is the full per-run `TrialResult` (one row per incident), so you can slice
by scenario, by seed, or recompute a metric differently without rerunning.
Ad-hoc runs (`eval/results/run_*.json`) are gitignored; only the committed
baseline is tracked, so the repo doesn't accumulate stale benchmark noise.
