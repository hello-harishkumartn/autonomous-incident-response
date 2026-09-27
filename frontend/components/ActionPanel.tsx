import type { ActionItem, VerificationItem } from "@/lib/types";

function statusBadge(a: ActionItem): { label: string; cls: string } {
  if (a.approval_status === "pending") return { label: "pending approval", cls: "badge pending" };
  if (a.approval_status === "rejected") return { label: "rejected", cls: "badge error" };
  if (a.executed) return { label: "executed", cls: "badge resolved" };
  return { label: a.approval_status, cls: "badge" };
}

export function ActionPanel({ actions, verifications }: { actions: ActionItem[]; verifications: VerificationItem[] }) {
  if (actions.length === 0) return <div className="empty">No remediation actions proposed yet.</div>;
  return (
    <div>
      {actions.map((a) => {
        const badge = statusBadge(a);
        const verification = verifications.find((v) => v.action_id === a.id);
        return (
          <div key={a.id} className="hypothesis-item">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <strong>
                {a.tool_name} &rarr; {String(a.args.service)}
              </strong>
              <span className="row" style={{ gap: 6 }}>
                <span className={`badge ${a.risk_level === "HIGH_RISK" ? "high-risk" : "low-risk"}`}>{a.risk_level}</span>
                <span className={badge.cls}>{badge.label}</span>
              </span>
            </div>
            <div className="summary-text" style={{ marginTop: 4 }}>
              {a.rationale}
            </div>
            {verification && (
              <div className="summary-text" style={{ marginTop: 6, color: verification.healthy ? "var(--green)" : "var(--red)" }}>
                Post-remediation health check: {verification.healthy ? "healthy" : "still unhealthy"}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
