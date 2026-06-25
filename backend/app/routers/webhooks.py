from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_api_key
from app.database import get_db
from app.models import ApiKey, Webhook, WebhookDelivery

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


class CreateWebhookBody(BaseModel):
    url: str
    secret: str | None = None
    events: list[str] = ["drift.detected"]


@router.post("", status_code=201)
async def create_webhook(
    body: CreateWebhookBody,
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    wh = Webhook(api_key_id=api_key.id, url=body.url, secret=body.secret, events=body.events)
    db.add(wh)
    await db.commit()
    await db.refresh(wh)
    return {"id": wh.id, "url": wh.url, "events": wh.events, "created_at": wh.created_at.isoformat()}


@router.get("")
async def list_webhooks(
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Webhook).where(Webhook.api_key_id == api_key.id, Webhook.is_active.is_(True))
    )
    webhooks = result.scalars().all()
    return {
        "webhooks": [
            {
                "id": w.id,
                "url": w.url,
                "events": w.events,
                "last_delivery_at": w.last_delivery_at.isoformat() if w.last_delivery_at else None,
                "last_delivery_status": w.last_delivery_status,
            }
            for w in webhooks
        ]
    }


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: int,
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(Webhook).where(Webhook.id == webhook_id, Webhook.api_key_id == api_key.id)
    )
    wh = result.scalar_one_or_none()
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found.")
    wh.is_active = False
    await db.commit()


@router.get("/{webhook_id}/deliveries")
async def webhook_deliveries(
    webhook_id: int,
    limit: int = 20,
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Webhook).where(Webhook.id == webhook_id, Webhook.api_key_id == api_key.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Webhook not found.")

    deliveries_result = await db.execute(
        select(WebhookDelivery)
        .where(WebhookDelivery.webhook_id == webhook_id)
        .order_by(WebhookDelivery.attempted_at.desc())
        .limit(limit)
    )
    deliveries = deliveries_result.scalars().all()
    return {
        "deliveries": [
            {
                "id": d.id,
                "attempted_at": d.attempted_at.isoformat(),
                "status_code": d.status_code,
                "success": d.success,
                "attempt": d.attempt,
                "error": d.error,
            }
            for d in deliveries
        ]
    }
