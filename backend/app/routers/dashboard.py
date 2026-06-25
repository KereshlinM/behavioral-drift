from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_api_key
from app.database import get_db
from app.models import ApiKey, DriftEvent, Session, TrackedUser

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/overview")
async def overview(
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user_count = (await db.execute(
        select(func.count()).select_from(TrackedUser).where(TrackedUser.api_key_id == api_key.id)
    )).scalar_one()

    baseline_ready = (await db.execute(
        select(func.count()).select_from(TrackedUser).where(
            TrackedUser.api_key_id == api_key.id, TrackedUser.baseline_ready.is_(True)
        )
    )).scalar_one()

    session_count = (await db.execute(
        select(func.count()).select_from(Session).where(Session.api_key_id == api_key.id)
    )).scalar_one()

    # Drift events via join through sessions
    drift_count = (await db.execute(
        select(func.count()).select_from(DriftEvent)
        .join(TrackedUser, DriftEvent.user_id == TrackedUser.id)
        .where(TrackedUser.api_key_id == api_key.id)
    )).scalar_one()

    # Drift type breakdown
    type_rows = (await db.execute(
        select(DriftEvent.drift_type, func.count().label("n"))
        .join(TrackedUser, DriftEvent.user_id == TrackedUser.id)
        .where(TrackedUser.api_key_id == api_key.id)
        .group_by(DriftEvent.drift_type)
    )).all()

    # Recent drift events
    recent_result = await db.execute(
        select(DriftEvent, TrackedUser.external_id)
        .join(TrackedUser, DriftEvent.user_id == TrackedUser.id)
        .where(TrackedUser.api_key_id == api_key.id)
        .order_by(DriftEvent.detected_at.desc())
        .limit(10)
    )
    recent = recent_result.all()

    return {
        "users": {"total": user_count, "baseline_ready": baseline_ready},
        "sessions": {"total": session_count},
        "drift_events": {
            "total": drift_count,
            "by_type": {row.drift_type: row.n for row in type_rows},
        },
        "recent_drift": [
            {
                "id": d.id,
                "user_id": ext_id,
                "session_id": d.session_id,
                "drift_type": d.drift_type,
                "severity": d.severity,
                "score": d.score,
                "detected_at": d.detected_at.isoformat(),
            }
            for d, ext_id in recent
        ],
    }
