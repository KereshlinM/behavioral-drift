# Behavioral Drift

Detect when users act unlike themselves. Behavioral Drift is an API-first service that streams user interaction events, builds a per-user behavioral baseline, and fires webhooks when significant drift is detected.

## How it works

1. Embed the JavaScript SDK in your app. It auto-captures clicks, scrolls, keypresses, and idle periods.
2. Sessions are streamed to the API. When a session ends, per-session metrics are computed (typing speed, click rate, hesitation rate, scroll velocity, etc.).
3. After a user accumulates enough sessions, a baseline is built from the rolling average of their metrics.
4. Each new session is scored against the user's own baseline using z-scores. Drift above the configured threshold fires a webhook.

## Drift types

| Type | Description |
|---|---|
| `cognitive_overload` | Unusually high error rate, backspacing, and hesitation |
| `disengagement` | Low activity, high idle ratio, slow interactions |
| `unusual_urgency` | Atypically fast clicking and navigation |
| `context_switch_fatigue` | Elevated back-navigation and fragmented session patterns |
| `confusion` | Repeated clicks on the same targets, high hesitation |

## Stack

- **Backend** - FastAPI, PostgreSQL, async SQLAlchemy (asyncpg)
- **SDK** - TypeScript browser SDK with beacon-based flush on page unload
- **Dashboard** - React + Vite, dark theme, no external UI library

## Getting started

### With Docker

```bash
cp backend/.env.example backend/.env
docker compose up
```

The API will be at `http://localhost:8000`. Create your first API key:

```bash
curl -X POST http://localhost:8000/api/v1/keys \
  -H "Content-Type: application/json" \
  -H "X-API-Key: any-key-to-bootstrap" \
  -d '{"name": "my-key"}'
```

> On first run with no keys in the database, the API accepts any value for `X-API-Key` so you can bootstrap.

### Without Docker

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Set DATABASE_URL in .env, then:
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install && npm run dev
```

## SDK usage

```typescript
import { DriftClient } from "@behavioral-drift/sdk";

const client = new DriftClient({
  apiUrl: "https://your-api.example.com",
  apiKey: "dk_your_key",
  userId: "user-123",
  context: "checkout-flow",       // optional label for this session
  flushIntervalMs: 5000,          // batch flush every 5s (default)
});

client.start();

// Events are captured automatically:
// clicks, scrolls, keypresses, idle detection

// On page unload, sendBeacon flushes any remaining events.
```

## Webhooks

Configure a webhook endpoint to receive drift events in real time.

```bash
curl -X POST http://localhost:8000/api/v1/webhooks \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dk_your_key" \
  -d '{
    "url": "https://your-server.example.com/drift",
    "secret": "signing-secret",
    "events": ["drift.detected"]
  }'
```

Each request is signed with `X-Drift-Signature: sha256=<hmac>` so you can verify authenticity.

**Payload:**

```json
{
  "event": "drift.detected",
  "user_id": "user-123",
  "session_id": 42,
  "drift_type": "cognitive_overload",
  "severity": "high",
  "score": 3.4,
  "signals": {
    "backspace_rate": 2.8,
    "hesitation_rate": 3.1
  },
  "detected_at": "2026-06-25T10:00:00Z"
}
```

## API reference

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/keys` | Create API key |
| `GET` | `/api/v1/keys` | List API keys |
| `DELETE` | `/api/v1/keys/{id}` | Revoke API key |
| `POST` | `/api/v1/sessions/start` | Start a session |
| `POST` | `/api/v1/sessions/{id}/events` | Ingest events |
| `POST` | `/api/v1/sessions/{id}/end` | End session and score drift |
| `GET` | `/api/v1/users` | List tracked users |
| `GET` | `/api/v1/users/{id}` | User detail with baseline |
| `GET` | `/api/v1/users/{id}/drift` | Drift history |
| `GET` | `/api/v1/webhooks` | List webhooks |
| `POST` | `/api/v1/webhooks` | Create webhook |
| `DELETE` | `/api/v1/webhooks/{id}` | Delete webhook |
| `GET` | `/api/v1/dashboard/overview` | Aggregate stats |
