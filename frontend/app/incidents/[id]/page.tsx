"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import { Timeline } from "@/components/Timeline";
import { HypothesisPanel } from "@/components/HypothesisPanel";
import { ToolCallPanel } from "@/components/ToolCallPanel";
import { ActionPanel } from "@/components/ActionPanel";
import { ApprovalPanel } from "@/components/ApprovalPanel";
import { ServiceHealthGrid } from "@/components/ServiceHealthGrid";
import { ExecutionGraph } from "@/components/ExecutionGraph";

function phaseBadgeClass(phase: string): string {
  if (phase === "resolved") return "badge resolved";
  if (phase === "escalated" || phase === "budget_exhausted" || phase === "no_valid_actions") return "badge escalated";
  if (phase === "awaiting_approval") return "badge pending";
  return "badge phase";
}

export default function IncidentDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [starting, setStarting] = useState(false);
  const [autoApprove, setAutoApprove] = useState(false);

  const { data: incident } = usePolling(() => api.getIncident(id), 1500, [id]);
  const { data: events } = usePolling(() => api.getEvents(id), 1500, [id]);
  const { data: hypotheses } = usePolling(() => api.getHypotheses(id), 1500, [id]);
  const { data: toolCalls } = usePolling(() => api.getToolCalls(id), 1500, [id]);
  const { data: actions } = usePolling(() => api.getActions(id), 1500, [id]);
  const { data: verifications } = usePolling(() => api.getVerifications(id), 1500, [id]);
  const { data: services } = usePolling(() => api.getServices(id), 1500, [id]);
  const { data: graph } = usePolling(() => api.getGraph(id), 1500, [id]);
  const { data: approvals } = usePolling(() => api.getApprovals(id), 1500, [id]);
  const { data: runStatus } = usePolling(() => api.investigationStatus(id), 1500, [id]);

  async function start() {
    setStarting(true);
    try {
      await api.startInvestigation(id, autoApprove);
    } finally {
      setStarting(false);
    }
  }

  if (!incident) return <div className="container">Loading...</div>;

  const canStart = incident.phase === "alerted" && !runStatus?.running;

  return (
    <div className="container">
      <div className="header">
        <div>
          <Link href="/" className="subtitle">
            &larr; back
          </Link>
          <h1 style={{ marginTop: 6 }}>{incident.alert_summary}</h1>
          <div className="subtitle">
            {incident.scenario_type} · seed={incident.seed} · id={incident.id}
          </div>
        </div>
        <div className="row">
          <span className={phaseBadgeClass(incident.phase)}>{incident.phase}</span>
          {runStatus?.running && <span className="badge pending">investigating...</span>}
        </div>
      </div>

      {canStart && (
        <div className="panel">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <label className="row" style={{ gap: 6 }}>
              <input type="checkbox" checked={autoApprove} onChange={(e) => setAutoApprove(e.target.checked)} />
              Auto-approve HIGH_RISK actions (non-interactive demo mode)
            </label>
            <button className="btn" disabled={starting} onClick={start}>
              {starting ? "Starting..." : "Start investigation"}
            </button>
          </div>
        </div>
      )}

      {approvals && approvals.length > 0 && <ApprovalPanel incidentId={id} approvals={approvals} />}

      <div className="panel">
        <h2>Root cause</h2>
        <div className="summary-text">
          <strong>Confirmed:</strong> {incident.confirmed_root_cause ?? "(not yet confirmed)"}
        </div>
        {incident.resolved_at && (
          <div className="summary-text" style={{ marginTop: 6, color: "var(--text-dim)" }}>
            <strong>Ground truth (hidden from agent during investigation):</strong> {incident.ground_truth_root_cause}
          </div>
        )}
        <div className="row" style={{ marginTop: 10, gap: 16 }}>
          <span className="phase-label">iterations: {incident.iteration}</span>
          <span className="phase-label">tool calls: {incident.tool_call_count}</span>
          <span className="phase-label">tokens: {incident.tokens_used}</span>
          {incident.stopping_reason && <span className="phase-label">stopping reason: {incident.stopping_reason}</span>}
        </div>
      </div>

      <div className="panel">
        <h2>Service health</h2>
        <ServiceHealthGrid services={services ?? []} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr", gap: 16 }}>
        <div className="panel">
          <h2>Timeline (decision / evidence / action / result)</h2>
          <Timeline events={events ?? []} />
        </div>
        <div>
          <div className="panel">
            <h2>Hypotheses</h2>
            <HypothesisPanel hypotheses={hypotheses ?? []} />
          </div>
          <div className="panel">
            <h2>Remediation</h2>
            <ActionPanel actions={actions ?? []} verifications={verifications ?? []} />
          </div>
        </div>
      </div>

      <div className="panel">
        <h2>Tool calls</h2>
        <ToolCallPanel calls={toolCalls ?? []} />
      </div>

      <div className="panel">
        <h2>Execution graph</h2>
        <ExecutionGraph graph={graph ?? null} />
      </div>
    </div>
  );
}
