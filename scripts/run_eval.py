#!/usr/bin/env python
"""Run the incident benchmark across all 10 scenarios and store results.

Usage:
    python scripts/run_eval.py --trials 3
    python scripts/run_eval.py --trials 5 --seed 200 --out eval/results/run_001.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

import _common  # noqa: F401

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    from app.db import init_db
    from app.eval.benchmark import results_to_dicts, run_benchmark, summarize

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=3, help="Trials per scenario (10 scenarios total).")
    parser.add_argument("--seed", type=int, default=100, help="Base seed; trial i uses seed+i.")
    parser.add_argument("--out", default=None, help="Output JSON path (default: eval/results/<timestamp>.json)")
    args = parser.parse_args()

    init_db()
    print(f"Running benchmark: {args.trials} trial(s) x 10 scenarios = {args.trials * 10} runs...")
    results = run_benchmark(trials_per_scenario=args.trials, base_seed=args.seed)
    summary = summarize(results)

    out_path = Path(args.out) if args.out else REPO_ROOT / "eval" / "results" / f"run_{dt.datetime.now():%Y%m%d_%H%M%S}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"summary": summary, "trials": results_to_dicts(results)}, indent=2, default=str))

    overall = summary["overall"]
    print("\n=== Overall ===")
    for key, value in overall.items():
        print(f"  {key:28s}: {value}")

    print("\n=== By scenario ===")
    for scenario, s in summary["by_scenario"].items():
        print(f"  {scenario:28s} acc={s['root_cause_accuracy']:.2f}  success={s['remediation_success_rate']:.2f}  "
              f"tool_calls={s['mean_tool_calls']:.1f}  iters={s['mean_iterations']:.1f}")

    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
