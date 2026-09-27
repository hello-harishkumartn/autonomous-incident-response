import type { ServiceStateItem } from "@/lib/types";

export function ServiceHealthGrid({ services }: { services: ServiceStateItem[] }) {
  if (services.length === 0) return <div className="empty">No service data yet.</div>;
  return (
    <div className="service-grid">
      {services.map((s) => (
        <div key={s.service} className={`service-tile ${s.is_healthy ? "" : "unhealthy"}`}>
          <div className="name">{s.service}</div>
          <div className="metric">
            <span>cpu</span>
            <span>{s.cpu_pct.toFixed(0)}%</span>
          </div>
          <div className="metric">
            <span>memory</span>
            <span>{s.memory_pct.toFixed(0)}%</span>
          </div>
          <div className="metric">
            <span>p99</span>
            <span>{s.latency_p99_ms.toFixed(0)}ms</span>
          </div>
          <div className="metric">
            <span>error rate</span>
            <span>{(s.error_rate * 100).toFixed(1)}%</span>
          </div>
          <div className="metric">
            <span>connections</span>
            <span>
              {s.connections_active}/{s.connections_max}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
