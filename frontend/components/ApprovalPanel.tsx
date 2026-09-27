"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { ActionItem } from "@/lib/types";

export function ApprovalPanel({ incidentId, approvals }: { incidentId: string; approvals: ActionItem[] }) {
  const [busy, setBusy] = useState<string | null>(null);

  if (approvals.length === 0) return null;

  async function decide(actionId: string, approved: boolean) {
    setBusy(actionId);
    try {
      await api.decideApproval(incidentId, actionId, approved);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="panel">
      <h2>Approval required</h2>
      {approvals.map((a) => (
        <div key={a.id} className="approval-card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <strong>
              {a.tool_name} on {String(a.args.service)}
            </strong>
            <span className="badge high-risk">{a.risk_level}</span>
          </div>
          <div className="summary-text" style={{ marginTop: 6 }}>
            {a.rationale}
          </div>
          <div className="row" style={{ marginTop: 10 }}>
            <button className="btn" disabled={busy === a.id} onClick={() => decide(a.id, true)}>
              Approve &amp; execute
            </button>
            <button className="btn secondary" disabled={busy === a.id} onClick={() => decide(a.id, false)}>
              Reject
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
