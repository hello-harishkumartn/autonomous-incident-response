import type { GraphResponse } from "@/lib/types";

const GROUPS: { label: string; nodes: string[]; note?: string }[] = [
  {
    label: "1. Investigate",
    nodes: [
      "alerted",
      "collecting_observations",
      "generating_hypotheses",
      "selecting_investigation",
      "calling_tool",
      "analyzing_results",
      "updating_hypotheses",
      "root_cause_check",
    ],
    note: "root_cause_check loops back to collecting_observations until the model confirms a cause",
  },
  {
    label: "2. Remediate",
    nodes: [
      "generating_remediation",
      "risk_classification",
      "awaiting_approval",
      "executing_remediation",
      "verifying_health",
      "rolling_back",
    ],
    note: "verifying_health loops back to collecting_observations (via rolling_back) if the fix didn't work",
  },
  {
    label: "3. Stopping conditions",
    nodes: ["resolved", "escalated", "budget_exhausted", "no_valid_actions"],
  },
];

export function ExecutionGraph({ graph }: { graph: GraphResponse | null }) {
  if (!graph) return <div className="empty">No graph data yet.</div>;
  const byId = new Map(graph.nodes.map((n) => [n.id, n]));

  return (
    <div>
      {GROUPS.map((group) => (
        <div key={group.label} style={{ marginBottom: 16 }}>
          <div className="phase-label" style={{ marginBottom: 6 }}>
            {group.label}
          </div>
          <div className="row" style={{ gap: 6 }}>
            {group.nodes.map((nodeId, i) => {
              const node = byId.get(nodeId);
              const classes = ["badge", "phase-node"];
              let style: React.CSSProperties = { padding: "4px 10px" };
              if (node?.current) {
                style = { ...style, borderColor: "var(--accent)", color: "var(--accent)", background: "#152233" };
              } else if (node?.visited) {
                style = { ...style, borderColor: "var(--green)", color: "var(--green)" };
              } else {
                style = { ...style, color: "var(--text-dim)" };
              }
              return (
                <span key={nodeId} className="row" style={{ gap: 6 }}>
                  <span className="badge" style={style}>
                    {nodeId}
                  </span>
                  {i < group.nodes.length - 1 && <span style={{ color: "var(--text-dim)" }}>&rarr;</span>}
                </span>
              );
            })}
          </div>
          {group.note && (
            <div className="empty" style={{ marginTop: 4 }}>
              {group.note}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
