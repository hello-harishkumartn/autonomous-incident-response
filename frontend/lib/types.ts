export type RiskLevel = "READ_ONLY" | "LOW_RISK" | "HIGH_RISK";
export type ApprovalStatus = "not_required" | "auto_approved" | "pending" | "approved" | "rejected";
export type EventKind = "decision" | "evidence" | "action" | "result";

export interface ScenarioInfo {
  type: string;
  title: string;
  affected_services: string[];
}

export interface IncidentSummary {
  id: string;
  scenario_type: string;
  seed: number;
  phase: string;
  stopping_reason: string | null;
  alert_summary: string;
  iteration: number;
  tool_call_count: number;
  tokens_used: number;
  created_at: string;
  resolved_at: string | null;
}

export interface IncidentDetail extends IncidentSummary {
  ground_truth_root_cause: string;
  ground_truth_fix_tool: string;
  confirmed_root_cause: string | null;
  max_iterations: number;
  max_seconds: number;
  max_tokens: number;
}

export interface IncidentEvent {
  id: string;
  iteration: number;
  phase: string;
  kind: EventKind;
  summary: string;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface HypothesisItem {
  id: string;
  description: string;
  target_service: string;
  confidence: number;
  status: "active" | "confirmed" | "rejected";
  created_iteration: number;
  updated_iteration: number;
}

export interface ToolCallItem {
  id: string;
  iteration: number;
  tool_name: string;
  risk_level: RiskLevel;
  args: Record<string, unknown>;
  result: Record<string, unknown>;
  status: "success" | "error";
  started_at: string;
}

export interface ActionItem {
  id: string;
  iteration: number;
  tool_name: string;
  risk_level: RiskLevel;
  args: Record<string, unknown>;
  rationale: string;
  approval_status: ApprovalStatus;
  approved_by: string | null;
  approval_reason: string | null;
  executed: boolean;
  result: Record<string, unknown>;
  created_at: string;
  decided_at: string | null;
  executed_at: string | null;
}

export interface VerificationItem {
  id: string;
  iteration: number;
  action_id: string | null;
  healthy: boolean;
  checks: Record<string, unknown>;
  created_at: string;
}

export interface ServiceStateItem {
  service: string;
  cpu_pct: number;
  memory_pct: number;
  latency_p50_ms: number;
  latency_p99_ms: number;
  error_rate: number;
  connections_active: number;
  connections_max: number;
  is_healthy: boolean;
}

export interface GraphNode {
  id: string;
  visited: boolean;
  current: boolean;
}

export interface GraphEdge {
  from: string;
  to: string;
  visited: boolean;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}
