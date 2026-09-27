import type { IncidentEvent } from "@/lib/types";

export function Timeline({ events }: { events: IncidentEvent[] }) {
  if (events.length === 0) return <div className="empty">No events yet.</div>;
  return (
    <div>
      {events.map((event) => (
        <div key={event.id} className="timeline-item">
          <div className="iter">#{event.iteration}</div>
          <div>
            <span className={`kind-tag kind-${event.kind}`}>{event.kind}</span>
            <div className="phase-label" style={{ marginTop: 4 }}>
              {event.phase}
            </div>
          </div>
          <div className="summary-text">{event.summary}</div>
        </div>
      ))}
    </div>
  );
}
