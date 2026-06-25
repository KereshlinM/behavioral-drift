const API_KEY = localStorage.getItem("drift_api_key") ?? "";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", "X-API-Key": API_KEY, ...((init?.headers) as Record<string, string> ?? {}) },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { const b = await res.json(); detail = b.detail ?? detail; } catch {}
    throw { status: res.status, detail };
  }
  return res.json();
}

export const api = {
  health: () => req<{ status: string; version: string }>("/api/v1/health"),

  overview: () => req<{
    users: { total: number; baseline_ready: number };
    sessions: { total: number };
    drift_events: { total: number; by_type: Record<string, number> };
    recent_drift: DriftSummary[];
  }>("/api/v1/dashboard/overview"),

  users: (limit = 50, offset = 0) =>
    req<{ users: UserSummary[] }>(`/api/v1/users?limit=${limit}&offset=${offset}`),

  user: (id: string) => req<UserDetail>(`/api/v1/users/${encodeURIComponent(id)}`),

  userSessions: (id: string, limit = 20) =>
    req<{ user_id: string; sessions: SessionSummary[] }>(
      `/api/v1/users/${encodeURIComponent(id)}/sessions?limit=${limit}`
    ),

  userDrift: (id: string, limit = 50) =>
    req<{ user_id: string; drift_events: DriftEventDetail[] }>(
      `/api/v1/users/${encodeURIComponent(id)}/drift?limit=${limit}`
    ),

  session: (id: number) => req<SessionDetail>(`/api/v1/sessions/${id}`),

  webhooks: () => req<{ webhooks: WebhookSummary[] }>("/api/v1/webhooks"),
  createWebhook: (url: string, secret?: string, events?: string[]) =>
    req("/api/v1/webhooks", { method: "POST", body: JSON.stringify({ url, secret, events: events ?? ["drift.detected"] }) }),
  deleteWebhook: (id: number) =>
    req(`/api/v1/webhooks/${id}`, { method: "DELETE" }),
  webhookDeliveries: (id: number) =>
    req<{ deliveries: DeliverySummary[] }>(`/api/v1/webhooks/${id}/deliveries`),

  createKey: (name: string) =>
    req<{ id: number; key: string; prefix: string; note: string }>("/api/v1/keys", {
      method: "POST", body: JSON.stringify({ name }),
    }),
};

export interface UserSummary {
  id: number;
  external_id: string;
  session_count: number;
  baseline_ready: boolean;
  created_at: string;
}

export interface UserDetail extends UserSummary {
  baseline: {
    session_count: number;
    updated_at: string;
    metrics: Record<string, { mean: number; std: number }>;
  } | null;
  recent_drift: DriftSummary[];
}

export interface SessionSummary {
  id: number;
  context: string | null;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  event_count: number;
  metrics: Record<string, number> | null;
}

export interface SessionDetail extends SessionSummary {
  user_id: number;
  drift: { drift_type: string; severity: string; score: number; signals: Record<string, number> } | null;
}

export interface DriftSummary {
  id: number;
  user_id: string;
  session_id: number;
  drift_type: string;
  severity: string;
  score: number;
  detected_at: string;
}

export interface DriftEventDetail extends DriftSummary {
  signals: Record<string, number>;
  webhook_delivered: boolean;
}

export interface WebhookSummary {
  id: number;
  url: string;
  events: string[];
  last_delivery_at: string | null;
  last_delivery_status: number | null;
}

export interface DeliverySummary {
  id: number;
  attempted_at: string;
  status_code: number | null;
  success: boolean;
  attempt: number;
  error: string | null;
}
