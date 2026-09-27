import type { ToolCallItem } from "@/lib/types";

function riskClass(risk: string): string {
  if (risk === "HIGH_RISK") return "badge high-risk";
  if (risk === "LOW_RISK") return "badge low-risk";
  return "badge read-only";
}

export function ToolCallPanel({ calls }: { calls: ToolCallItem[] }) {
  if (calls.length === 0) return <div className="empty">No tool calls yet.</div>;
  return (
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Tool</th>
          <th>Risk</th>
          <th>Args</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {calls.map((c) => (
          <tr key={c.id}>
            <td>{c.iteration}</td>
            <td>{c.tool_name}</td>
            <td>
              <span className={riskClass(c.risk_level)}>{c.risk_level}</span>
            </td>
            <td style={{ fontSize: 12, color: "var(--text-dim)" }}>{JSON.stringify(c.args)}</td>
            <td>
              <span className={c.status === "success" ? "badge resolved" : "badge error"}>{c.status}</span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
