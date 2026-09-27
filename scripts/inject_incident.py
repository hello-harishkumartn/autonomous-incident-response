#!/usr/bin/env python
"""Inject a reproducible incident into the simulated fleet.

Usage:
    python scripts/inject_incident.py --type bad_deployment
    python scripts/inject_incident.py --type redis_failure --seed 123 --investigate
    python scripts/inject_incident.py --list
"""
from __future__ import annotations

import argparse
import sys

import _common  # noqa: F401  (adds backend/ to sys.path)


def main() -> None:
    from app.db import init_db, session_scope
    from app.enums import IncidentType

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--type", choices=[t.value for t in IncidentType], help="Incident scenario to inject.")
    parser.add_argument("--seed", type=int, default=None, help="Determinism seed (default from config).")
    parser.add_argument("--investigate", action="store_true", help="Immediately run the agent investigation after injecting.")
    parser.add_argument("--approve-all", action="store_true", help="With --investigate: auto-approve HIGH_RISK actions as they arise.")
    parser.add_argument("--list", action="store_true", help="List available incident types and exit.")
    args = parser.parse_args()

    if args.list or not args.type:
        print("Available incident types:")
        for t in IncidentType:
            print(f"  {t.value}")
        if not args.type:
            sys.exit(0 if args.list else 1)

    init_db()
    from app.agent.factory import create_incident

    with session_scope() as session:
        incident = create_incident(session, args.type, seed=args.seed)
        incident_id = incident.id
        print(f"Injected incident {incident_id} ({args.type}), seed={incident.seed}")
        print(f"Alert: {incident.alert_summary}")

    if args.investigate:
        from run_agent import investigate

        result = investigate(incident_id, approve_all=args.approve_all)
        resolved = result is not None and result.value == "incident_resolved"
        sys.exit(0 if resolved else 1)
    else:
        print(f"\nTo investigate: python scripts/run_agent.py --incident-id {incident_id}")


if __name__ == "__main__":
    main()
