"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";

function phaseBadgeClass(phase: string, stoppingReason: string | null): string {
  if (phase === "resolved") return "badge resolved";
  if (phase === "escalated" || phase === "budget_exhausted" || phase === "no_valid_actions") return "badge escalated";
  if (phase === "awaiting_approval") return "badge pending";
  return "badge phase";
}

export default function HomePage() {
  const router = useRouter();
  const [creating, setCreating] = useState<string | null>(null);
  const { data: scenarios } = usePolling(() => api.listScenarios(), 60_000);
  const { data: incidents } = usePolling(() => api.listIncidents(), 2_000);

  async function inject(scenarioType: string) {
    setCreating(scenarioType);
    try {
      const incident = await api.createIncident(scenarioType);
      router.push(`/incidents/${incident.id}`);
    } finally {
      setCreating(null);
    }
  }

  return (
    <div className="container">
      <div className="header">
        <div>
          <h1>AIRE — Autonomous Incident Response Engineer</h1>
          <div className="subtitle">Inject a reproducible incident, then watch the agent investigate and resolve it.</div>
        </div>
      </div>

      <div className="panel">
        <h2>Inject an incident</h2>
        <div className="grid">
          {(scenarios ?? []).map((s) => (
            <button key={s.type} className="scenario-card" disabled={creating !== null} onClick={() => inject(s.type)}>
              <div className="type">{creating === s.type ? "injecting..." : s.type}</div>
              <div style={{ marginTop: 6, fontWeight: 600 }}>{s.title}</div>
              <div className="services">
                {s.affected_services.map((svc) => (
                  <span key={svc} className="badge service">
                    {svc}
                  </span>
                ))}
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="panel">
        <h2>Incidents</h2>
        {!incidents || incidents.length === 0 ? (
          <div className="empty">No incidents yet — inject one above.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Alert</th>
                <th>Scenario</th>
                <th>Phase</th>
                <th>Iter</th>
                <th>Tools</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {incidents.map((inc) => (
                <tr key={inc.id} onClick={() => router.push(`/incidents/${inc.id}`)} style={{ cursor: "pointer" }}>
                  <td>{inc.alert_summary}</td>
                  <td>{inc.scenario_type}</td>
                  <td>
                    <span className={phaseBadgeClass(inc.phase, inc.stopping_reason)}>{inc.phase}</span>
                  </td>
                  <td>{inc.iteration}</td>
                  <td>{inc.tool_call_count}</td>
                  <td>{new Date(inc.created_at).toLocaleTimeString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
