import type { HypothesisItem } from "@/lib/types";

function statusColor(status: string): string {
  if (status === "confirmed") return "var(--green)";
  if (status === "rejected") return "var(--red)";
  return "var(--accent)";
}

export function HypothesisPanel({ hypotheses }: { hypotheses: HypothesisItem[] }) {
  if (hypotheses.length === 0) return <div className="empty">No hypotheses yet.</div>;
  const latestByService = new Map<string, HypothesisItem>();
  for (const h of hypotheses) {
    latestByService.set(`${h.target_service}:${h.description}`, h);
  }
  const items = Array.from(latestByService.values()).sort((a, b) => b.updated_iteration - a.updated_iteration);

  return (
    <div>
      {items.map((h) => (
        <div key={h.id} className="hypothesis-item">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span style={{ color: statusColor(h.status) }}>
              [{h.status}] {h.target_service}
            </span>
            <span className="phase-label">{Math.round(h.confidence * 100)}%</span>
          </div>
          <div className="summary-text" style={{ marginTop: 4 }}>
            {h.description}
          </div>
          <div className="confidence-bar">
            <div
              className="confidence-fill"
              style={{ width: `${h.confidence * 100}%`, background: statusColor(h.status) }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
