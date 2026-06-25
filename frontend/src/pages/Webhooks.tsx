import { useState } from "react";
import { api, DeliverySummary, WebhookSummary } from "../api";
import { formatTime, useAsync } from "../hooks";

const EVENT_OPTIONS = ["drift.detected", "drift.high_severity", "drift.session_end"];

function DeliveriesPanel({ webhookId }: { webhookId: number }) {
  const { data, loading } = useAsync(() => api.webhookDeliveries(webhookId), [webhookId]);

  if (loading) return <p className="muted" style={{ padding: "8px 0" }}>Loading deliveries...</p>;

  const deliveries = data?.deliveries ?? [];
  if (deliveries.length === 0) return <p className="muted" style={{ padding: "8px 0" }}>No deliveries yet.</p>;

  return (
    <div style={{ marginTop: 10 }}>
      {deliveries.map((d) => (
        <div key={d.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "6px 0", borderBottom: "1px solid var(--border)", fontSize: 12 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{ color: d.success ? "var(--ok)" : "var(--error)", fontWeight: 600 }}>
              {d.success ? "OK" : "FAIL"}
            </span>
            {d.status_code != null && <span className="muted">HTTP {d.status_code}</span>}
            {d.attempt > 1 && <span className="muted">attempt {d.attempt}</span>}
          </div>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            {d.error && <span style={{ color: "var(--error)" }}>{d.error}</span>}
            <span className="muted">{formatTime(d.attempted_at)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function WebhookCard({ wh, onDelete }: { wh: WebhookSummary; onDelete: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async () => {
    if (!window.confirm(`Delete webhook for ${wh.url}?`)) return;
    setDeleting(true);
    try { await api.deleteWebhook(wh.id); onDelete(); }
    catch { setDeleting(false); }
  };

  return (
    <div className="webhook-card">
      <div className="webhook-card-header">
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {wh.url}
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 4 }}>
            {wh.events.map((e) => <span key={e} className="signal-chip">{e}</span>)}
          </div>
          {wh.last_delivery_at && (
            <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
              Last delivery: {formatTime(wh.last_delivery_at)}
              {wh.last_delivery_status != null && (
                <span style={{ marginLeft: 6, color: wh.last_delivery_status < 300 ? "var(--ok)" : "var(--error)" }}>
                  HTTP {wh.last_delivery_status}
                </span>
              )}
            </div>
          )}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-start", flexShrink: 0 }}>
          <button className="btn btn-secondary" style={{ fontSize: 12 }} onClick={() => setExpanded((e) => !e)}>
            {expanded ? "Hide" : "Deliveries"}
          </button>
          <button className="btn btn-danger" style={{ fontSize: 12 }} onClick={handleDelete} disabled={deleting}>
            {deleting ? "..." : "Delete"}
          </button>
        </div>
      </div>
      {expanded && <DeliveriesPanel webhookId={wh.id} />}
    </div>
  );
}

function AddWebhookForm({ onCreated }: { onCreated: () => void }) {
  const [url, setUrl] = useState("");
  const [secret, setSecret] = useState("");
  const [selectedEvents, setSelectedEvents] = useState<string[]>(["drift.detected"]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleEvent = (e: string) => {
    setSelectedEvents((prev) =>
      prev.includes(e) ? prev.filter((x) => x !== e) : [...prev, e]
    );
  };

  const handleSubmit = async () => {
    if (!url.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await api.createWebhook(url.trim(), secret.trim() || undefined, selectedEvents);
      setUrl("");
      setSecret("");
      setSelectedEvents(["drift.detected"]);
      onCreated();
    } catch (e: any) {
      setError(e?.detail ?? "Failed to create webhook");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="card" style={{ marginBottom: 24 }}>
      <h3 style={{ marginTop: 0 }}>Add Webhook</h3>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div>
          <label className="form-label">Endpoint URL</label>
          <input
            className="form-input"
            placeholder="https://example.com/webhooks/drift"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
        </div>
        <div>
          <label className="form-label">Secret (optional, for HMAC signing)</label>
          <input
            className="form-input"
            placeholder="your-signing-secret"
            type="password"
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
          />
        </div>
        <div>
          <label className="form-label">Events</label>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {EVENT_OPTIONS.map((e) => (
              <label key={e} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 13, cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={selectedEvents.includes(e)}
                  onChange={() => toggleEvent(e)}
                />
                {e}
              </label>
            ))}
          </div>
        </div>
        {error && <div className="error">{error}</div>}
        <div>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={saving || !url.trim()}>
            {saving ? "Adding..." : "Add Webhook"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Webhooks() {
  const { data, loading, error, refresh } = useAsync(api.webhooks, []);
  const webhooks = data?.webhooks ?? [];

  return (
    <>
      <h1 className="page-title">Webhooks</h1>
      <AddWebhookForm onCreated={refresh} />
      {loading && <p className="muted">Loading...</p>}
      {error && <div className="error">{error.detail}</div>}
      {webhooks.map((wh) => (
        <WebhookCard key={wh.id} wh={wh} onDelete={refresh} />
      ))}
      {!loading && webhooks.length === 0 && (
        <p className="muted">No webhooks configured.</p>
      )}
    </>
  );
}
