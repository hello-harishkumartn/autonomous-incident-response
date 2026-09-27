#!/usr/bin/env python
"""Run the agent investigation loop against an already-injected incident.

Usage:
    python scripts/run_agent.py --incident-id <id>
    python scripts/run_agent.py --incident-id <id> --approve-all   # non-interactive, for demos/CI
"""
from __future__ import annotations

import argparse
import sys

import _common  # noqa: F401
from _common import print_final_status, print_incident_header, print_new_events


def investigate(incident_id: str, approve_all: bool = False):
    from app.agent.factory import load_agent_loop
    from app.db import session_scope
    from app.safety import approval

    with session_scope() as session:
        loop = load_agent_loop(session, incident_id)
        print_incident_header(loop.incident)

        printed = 0
        result = loop.run_to_completion()
        session.commit()
        printed = print_new_events(session, incident_id, printed)

        while result is None:
            pending = approval.list_pending(session, incident_id)
            if not pending:
                break
            action = pending[0]
            print(f"\n>>> APPROVAL REQUIRED: {action.tool_name} on {action.args.get('service')} "
                  f"(risk={action.risk_level})")
            print(f"    rationale: {action.rationale}")
            if approve_all:
                decision = True
                print("    --approve-all set -> auto-approving.")
            else:
                decision = input("    Approve? [y/N] ").strip().lower() == "y"

            approval.decide(session, action.id, approved=decision, decided_by="cli-operator")
            session.commit()
            result = loop.resume_after_approval()
            session.commit()
            printed = print_new_events(session, incident_id, printed)

        print_final_status(loop.incident)
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incident-id", required=True)
    parser.add_argument("--approve-all", action="store_true", help="Auto-approve HIGH_RISK actions non-interactively.")
    args = parser.parse_args()

    result = investigate(args.incident_id, approve_all=args.approve_all)
    resolved = result is not None and result.value == "incident_resolved"
    sys.exit(0 if resolved else 1)


if __name__ == "__main__":
    main()
