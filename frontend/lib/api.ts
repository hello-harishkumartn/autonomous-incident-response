import type {
  ActionItem,
  GraphResponse,
  HypothesisItem,
  IncidentDetail,
  IncidentEvent,
  IncidentSummary,
  ScenarioInfo,
  ServiceStateItem,
  ToolCallItem,
  VerificationItem,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${init?.method ?? "GET"} ${path} failed (${res.status}): ${body}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listScenarios: () => request<ScenarioInfo[]>("/incidents/scenarios"),
  listIncidents: () => request<IncidentSummary[]>("/incidents"),
  createIncident: (scenario_type: string, seed?: number) =>
    request<IncidentDetail>("/incidents", { method: "POST", body: JSON.stringify({ scenario_type, seed }) }),
  getIncident: (id: string) => request<IncidentDetail>(`/incidents/${id}`),
  getEvents: (id: string) => request<IncidentEvent[]>(`/incidents/${id}/events`),
  getHypotheses: (id: string) => request<HypothesisItem[]>(`/incidents/${id}/hypotheses`),
  getToolCalls: (id: string) => request<ToolCallItem[]>(`/incidents/${id}/tool-calls`),
  getActions: (id: string) => request<ActionItem[]>(`/incidents/${id}/actions`),
  getVerifications: (id: string) => request<VerificationItem[]>(`/incidents/${id}/verifications`),
  getServices: (id: string) => request<ServiceStateItem[]>(`/incidents/${id}/services`),
  getGraph: (id: string) => request<GraphResponse>(`/incidents/${id}/graph`),
  getApprovals: (id: string) => request<ActionItem[]>(`/incidents/${id}/approvals`),
  startInvestigation: (id: string, approveAll: boolean, stepDelay = 0.6) =>
    request<{ status: string }>(`/incidents/${id}/investigate`, {
      method: "POST",
      body: JSON.stringify({ approve_all: approveAll, step_delay: stepDelay }),
    }),
  investigationStatus: (id: string) => request<{ running: boolean }>(`/incidents/${id}/investigate/status`),
  decideApproval: (id: string, actionId: string, approved: boolean, reason?: string) =>
    request<{ status: string }>(`/incidents/${id}/approvals/${actionId}`, {
      method: "POST",
      body: JSON.stringify({ approved, decided_by: "ui-operator", reason }),
    }),
};
