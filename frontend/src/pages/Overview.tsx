import { api } from "../api";
import { formatTime, useAsync } from "../hooks";

const SEVERITY_COLOR: Record<string, string> = {
  low: "#f59e0b",
  medium: "#f97316",
  high: "#ef4444",
};

const DRIFT_LABELS: Record<string, string> = {
  cognitive_overload: "Cognitive Overload",
  disengagement: "Disengagement",
  unusual_urgency: "Unusual Urgency",
  context_switch_fatigue: "Context Switch Fatigue",
  confusion: "Confusion",
};

export default function Overview() {
  const { data, loading, error, refresh } = useAsync(api.overview, []);

  if (loading) return <p className="muted">Loading...</p>;
  if (error) return <div className="error">{error.detail}</div>;
  if (!data) return null;

  const byType = data.drift_events.by_type;
  const totalDrift = data.drift_events.total;

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h1 className="page-title" style={{ margin: 0 }}>Overview</h1>
        <button className="btn btn-secondary" onClick={refresh} style={{ fontSize: 12 }}>Refresh</button>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Total Users</div>
          <div className="stat-value">{data.users.total}</div>
          <div className="stat-sub">{data.users.baseline_ready} with baseline</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Sessions</div>
          <div className="stat-value">{data.sessions.total}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Drift Events</div>
          <div className="stat-value">{totalDrift}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Drift Rate</div>
          <div className="stat-value">
            {data.sessions.total > 0
              ? `${((totalDrift / data.sessions.total) * 100).toFixed(1)}%`
              : "--"}
          </div>
          <div className="stat-sub">of sessions</div>
        </div>
      </div>

      {Object.keys(byType).length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <h3>Drift Breakdown</h3>
          {Object.entries(byType)
            .sort(([, a], [, b]) => b - a)
            .map(([type, count]) => (
              <div key={type} style={{ marginBottom: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
                  <span>{DRIFT_LABELS[type] ?? type}</span>
                  <span className="muted">{count} ({totalDrift > 0 ? ((count / totalDrift) * 100).toFixed(0) : 0}%)</span>
                </div>
                <div style={{ background: "var(--surface-2)", borderRadius: 4, height: 6 }}>
                  <div style={{
                    width: `${totalDrift > 0 ? (count / totalDrift) * 100 : 0}%`,
                    height: 6,
                    borderRadius: 4,
                    background: "var(--accent)",
                  }} />
                </div>
              </div>
            ))}
        </div>
      )}

      <div className="card">
        <h3>Recent Drift Events</h3>
        {data.recent_drift.length === 0 && (
          <p className="muted">No drift events detected yet.</p>
        )}
        {data.recent_drift.map((d) => (
          <div key={d.id} className="event-row">
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span
                className="severity-dot"
                style={{ background: SEVERITY_COLOR[d.severity] ?? "#888" }}
              />
              <div>
                <div style={{ fontSize: 13, fontWeight: 500 }}>
                  {DRIFT_LABELS[d.drift_type] ?? d.drift_type}
                </div>
                <div className="muted" style={{ fontSize: 12 }}>
                  User: {d.user_id} · Session #{d.session_id}
                </div>
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div
                className="severity-badge"
                style={{ color: SEVERITY_COLOR[d.severity] ?? "#888" }}
              >
                {d.severity}
              </div>
              <div className="muted" style={{ fontSize: 12 }}>{formatTime(d.detected_at)}</div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
