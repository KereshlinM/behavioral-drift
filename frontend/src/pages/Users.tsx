import { useState } from "react";
import { api } from "../api";
import { formatMs, formatTime, useAsync } from "../hooks";

const DRIFT_LABELS: Record<string, string> = {
  cognitive_overload: "Cognitive Overload",
  disengagement: "Disengagement",
  unusual_urgency: "Unusual Urgency",
  context_switch_fatigue: "Context Switch Fatigue",
  confusion: "Confusion",
};

const SEVERITY_COLOR: Record<string, string> = {
  low: "#f59e0b",
  medium: "#f97316",
  high: "#ef4444",
};

function MetricRow({ label, stat }: { label: string; stat: { mean: number; std: number } }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, padding: "4px 0", borderBottom: "1px solid var(--border)" }}>
      <span className="muted">{label}</span>
      <span>
        <span style={{ fontVariantNumeric: "tabular-nums" }}>{stat.mean.toFixed(2)}</span>
        <span className="muted"> ± {stat.std.toFixed(2)}</span>
      </span>
    </div>
  );
}

function UserPanel({ externalId }: { externalId: string }) {
  const { data: user, loading } = useAsync(() => api.user(externalId), [externalId]);
  const { data: sessions } = useAsync(() => api.userSessions(externalId), [externalId]);
  const { data: driftHistory } = useAsync(() => api.userDrift(externalId), [externalId]);
  const [tab, setTab] = useState<"baseline" | "sessions" | "drift">("baseline");

  if (loading) return <p className="muted" style={{ padding: 16 }}>Loading...</p>;
  if (!user) return null;

  return (
    <div className="user-panel">
      <div className="user-panel-header">
        <div>
          <div style={{ fontWeight: 600, fontSize: 15 }}>{user.external_id}</div>
          <div className="muted" style={{ fontSize: 12 }}>
            {user.session_count} sessions · joined {formatTime(user.created_at)}
          </div>
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          {user.baseline_ready ? (
            <span className="badge-ok">baseline ready</span>
          ) : (
            <span className="badge-warn">building baseline</span>
          )}
        </div>
      </div>

      <div className="tab-bar">
        {(["baseline", "sessions", "drift"] as const).map((t) => (
          <button key={t} className={`tab ${tab === t ? "active" : ""}`} onClick={() => setTab(t)}>
            {t === "baseline" ? "Baseline" : t === "sessions" ? `Sessions (${sessions?.sessions.length ?? 0})` : `Drift (${driftHistory?.drift_events.length ?? 0})`}
          </button>
        ))}
      </div>

      {tab === "baseline" && (
        <div style={{ padding: 16 }}>
          {!user.baseline ? (
            <p className="muted">
              Baseline not yet built. Needs {5 - user.session_count} more session{5 - user.session_count !== 1 ? "s" : ""}.
            </p>
          ) : (
            <>
              <div className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
                Built from {user.baseline.session_count} sessions · updated {formatTime(user.baseline.updated_at)}
              </div>
              {Object.entries(user.baseline.metrics).map(([k, stat]) => (
                <MetricRow key={k} label={k.replace(/_/g, " ")} stat={stat} />
              ))}
            </>
          )}
        </div>
      )}

      {tab === "sessions" && (
        <div style={{ padding: 16 }}>
          {(sessions?.sessions ?? []).map((s) => (
            <div key={s.id} className="session-row">
              <div style={{ fontSize: 12 }}>
                <span style={{ fontWeight: 500 }}>#{s.id}</span>
                {s.context && <span className="muted"> · {s.context}</span>}
              </div>
              <div className="muted" style={{ fontSize: 12 }}>
                {formatMs(s.duration_ms)} · {s.event_count} events · {formatTime(s.started_at)}
              </div>
            </div>
          ))}
          {(sessions?.sessions.length ?? 0) === 0 && <p className="muted">No sessions yet.</p>}
        </div>
      )}

      {tab === "drift" && (
        <div style={{ padding: 16 }}>
          {(driftHistory?.drift_events ?? []).map((d) => (
            <div key={d.id} className="session-row">
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <span className="severity-dot" style={{ background: SEVERITY_COLOR[d.severity] ?? "#888" }} />
                <div>
                  <div style={{ fontSize: 13 }}>{DRIFT_LABELS[d.drift_type] ?? d.drift_type}</div>
                  <div className="muted" style={{ fontSize: 11 }}>
                    Session #{d.session_id} · score {d.score.toFixed(2)} · {formatTime(d.detected_at)}
                  </div>
                </div>
              </div>
              {Object.keys(d.signals).length > 0 && (
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6, marginLeft: 20 }}>
                  {Object.entries(d.signals).map(([k, v]) => (
                    <span key={k} className="signal-chip">
                      {k.replace(/_/g, " ")} {v > 0 ? "+" : ""}{v.toFixed(1)}σ
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
          {(driftHistory?.drift_events.length ?? 0) === 0 && <p className="muted">No drift events detected.</p>}
        </div>
      )}
    </div>
  );
}

export default function Users() {
  const { data, loading, error } = useAsync(api.users, []);
  const [selected, setSelected] = useState<string | null>(null);
  const users = data?.users ?? [];

  return (
    <div className="users-layout">
      <div className="users-list">
        <h2 style={{ margin: "0 0 14px", fontSize: 15 }}>Users ({users.length})</h2>
        {loading && <p className="muted">Loading...</p>}
        {error && <div className="error">{error.detail}</div>}
        {users.map((u) => (
          <div
            key={u.id}
            className={`user-row ${selected === u.external_id ? "selected" : ""}`}
            onClick={() => setSelected(u.external_id)}
          >
            <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 2 }}>{u.external_id}</div>
            <div className="muted" style={{ fontSize: 12 }}>
              {u.session_count} sessions
              {u.baseline_ready && <span style={{ color: "var(--ok)", marginLeft: 6 }}>● ready</span>}
            </div>
          </div>
        ))}
        {!loading && users.length === 0 && (
          <p className="muted">No users tracked yet.</p>
        )}
      </div>
      <div className="users-detail">
        {selected ? (
          <UserPanel externalId={selected} />
        ) : (
          <div className="empty-detail">
            <p className="muted">Select a user to view their baseline and drift history.</p>
          </div>
        )}
      </div>
    </div>
  );
}
