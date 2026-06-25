from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_api_key
from app.database import get_db
from app.models import ApiKey, Baseline, DriftEvent, Session, TrackedUser

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("")
async def list_users(
    limit: int = 50,
    offset: int = 0,
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(TrackedUser)
        .where(TrackedUser.api_key_id == api_key.id)
        .order_by(TrackedUser.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    users = result.scalars().all()
    return {
        "users": [
            {
                "id": u.id,
                "external_id": u.external_id,
                "session_count": u.session_count,
                "baseline_ready": u.baseline_ready,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ]
    }


@router.get("/{external_id}")
async def get_user(
    external_id: str,
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(TrackedUser).where(
            TrackedUser.external_id == external_id,
            TrackedUser.api_key_id == api_key.id,
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    baseline_result = await db.execute(select(Baseline).where(Baseline.user_id == user.id))
    baseline = baseline_result.scalar_one_or_none()

    drift_result = await db.execute(
        select(DriftEvent)
        .where(DriftEvent.user_id == user.id)
        .order_by(DriftEvent.detected_at.desc())
        .limit(10)
    )
    recent_drift = drift_result.scalars().all()

    return {
        "id": user.id,
        "external_id": user.external_id,
        "session_count": user.session_count,
        "baseline_ready": user.baseline_ready,
        "created_at": user.created_at.isoformat(),
        "baseline": {
            "session_count": baseline.session_count,
            "updated_at": baseline.updated_at.isoformat(),
            "metrics": baseline.stats,
        } if baseline else None,
        "recent_drift": [
            {
                "id": d.id,
                "session_id": d.session_id,
                "drift_type": d.drift_type,
                "severity": d.severity,
                "score": d.score,
                "detected_at": d.detected_at.isoformat(),
            }
            for d in recent_drift
        ],
    }


@router.get("/{external_id}/drift")
async def user_drift_history(
    external_id: str,
    limit: int = 50,
    offset: int = 0,
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user_result = await db.execute(
        select(TrackedUser).where(
            TrackedUser.external_id == external_id,
            TrackedUser.api_key_id == api_key.id,
        )
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    result = await db.execute(
        select(DriftEvent)
        .where(DriftEvent.user_id == user.id)
        .order_by(DriftEvent.detected_at.desc())
        .limit(limit)
        .offset(offset)
    )
    events = result.scalars().all()
    return {
        "user_id": external_id,
        "drift_events": [
            {
                "id": d.id,
                "session_id": d.session_id,
                "drift_type": d.drift_type,
                "severity": d.severity,
                "score": d.score,
                "signals": d.signals,
                "detected_at": d.detected_at.isoformat(),
                "webhook_delivered": d.webhook_delivered,
            }
            for d in events
        ],
    }


@router.get("/{external_id}/sessions")
async def user_sessions(
    external_id: str,
    limit: int = 20,
    offset: int = 0,
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user_result = await db.execute(
        select(TrackedUser).where(
            TrackedUser.external_id == external_id,
            TrackedUser.api_key_id == api_key.id,
        )
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    result = await db.execute(
        select(Session)
        .where(Session.user_id == user.id)
        .order_by(Session.started_at.desc())
        .limit(limit)
        .offset(offset)
    )
    sessions = result.scalars().all()
    return {
        "user_id": external_id,
        "sessions": [
            {
                "id": s.id,
                "context": s.context,
                "started_at": s.started_at.isoformat(),
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "duration_ms": s.duration_ms,
                "event_count": s.event_count,
                "metrics": s.metrics,
            }
            for s in sessions
        ],
    }
