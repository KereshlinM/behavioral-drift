"""Webhook delivery with retry logic."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import DriftEvent, Webhook, WebhookDelivery

settings = get_settings()


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


async def deliver_drift_event(db: AsyncSession, drift_event: DriftEvent) -> None:
    result = await db.execute(
        select(Webhook).where(
            Webhook.api_key_id == drift_event.user.api_key_id,
            Webhook.is_active.is_(True),
        )
    )
    webhooks = result.scalars().all()
    if not webhooks:
        return

    payload = {
        "event": "drift.detected",
        "drift_event_id": drift_event.id,
        "user_id": drift_event.user.external_id,
        "session_id": drift_event.session_id,
        "drift_type": drift_event.drift_type,
        "severity": drift_event.severity,
        "score": drift_event.score,
        "signals": drift_event.signals,
        "detected_at": drift_event.detected_at.isoformat(),
    }
    body = json.dumps(payload)

    async with httpx.AsyncClient(timeout=settings.webhook_timeout_s) as http:
        for webhook in webhooks:
            if webhook.events and "drift.detected" not in webhook.events:
                continue
            headers = {"Content-Type": "application/json", "X-Drift-Event": "drift.detected"}
            if webhook.secret:
                headers["X-Drift-Signature"] = _sign(body, webhook.secret)

            success = False
            status_code = None
            response_body = None
            error = None

            for attempt in range(1, settings.webhook_max_retries + 1):
                try:
                    resp = await http.post(webhook.url, content=body, headers=headers)
                    status_code = resp.status_code
                    response_body = resp.text[:512]
                    success = resp.status_code < 300
                    if success:
                        break
                except Exception as exc:
                    error = str(exc)[:256]

            delivery = WebhookDelivery(
                webhook_id=webhook.id,
                drift_event_id=drift_event.id,
                status_code=status_code,
                success=success,
                attempt=attempt,
                response_body=response_body,
                error=error,
            )
            db.add(delivery)

            webhook.last_delivery_at = datetime.now(timezone.utc)
            webhook.last_delivery_status = status_code

    drift_event.webhook_delivered = True
    await db.commit()
