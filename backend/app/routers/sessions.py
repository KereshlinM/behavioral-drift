"""Session lifecycle and event ingestion."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_api_key
from app.database import get_db
from app.models import ApiKey, Baseline, DriftEvent, Event, Session, TrackedUser
from app.services.baseline import compute_drift, rebuild_baseline
from app.services.metrics import compute_session_metrics
from app.services.webhook import deliver_drift_event

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def _session_out(s: Session) -> dict:
    return {
        "id": s.id,
        "user_id": s.user_id,
        "context": s.context,
        "started_at": s.started_at.isoformat(),
        "ended_at": s.ended_at.isoformat() if s.ended_at else None,
        "duration_ms": s.duration_ms,
        "event_count": s.event_count,
        "metrics": s.metrics,
    }


class StartSessionBody(BaseModel):
    user_id: str
    context: str | None = None


@router.post("", status_code=201)
async def start_session(
    body: StartSessionBody,
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(TrackedUser).where(
            TrackedUser.external_id == body.user_id,
            TrackedUser.api_key_id == api_key.id,
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        user = TrackedUser(external_id=body.user_id, api_key_id=api_key.id)
        db.add(user)
        await db.flush()

    session = Session(user_id=user.id, api_key_id=api_key.id, context=body.context)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {"session_id": session.id, **_session_out(session)}


class EventIn(BaseModel):
    type: str
    ts: float
    data: dict[str, Any] | None = None


class IngestEventsBody(BaseModel):
    events: list[EventIn]


@router.post("/{session_id}/events", status_code=202)
async def ingest_events(
    session_id: int,
    body: IngestEventsBody,
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.api_key_id == api_key.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.ended_at:
        raise HTTPException(status_code=409, detail="Session already ended.")

    for ev in body.events:
        db.add(Event(session_id=session.id, event_type=ev.type, ts=ev.ts, data=ev.data))

    session.event_count += len(body.events)
    await db.commit()
    return {"accepted": len(body.events), "total": session.event_count}


@router.post("/{session_id}/end")
async def end_session(
    session_id: int,
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.api_key_id == api_key.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.ended_at:
        return {"session_id": session.id, "drift": None, **_session_out(session)}

    now = datetime.now(timezone.utc)
    session.ended_at = now
    session.duration_ms = int((now - session.started_at).total_seconds() * 1000)

    # Load events and compute metrics
    ev_result = await db.execute(select(Event).where(Event.session_id == session.id))
    events = [{"event_type": e.event_type, "ts": e.ts, "data": e.data or {}} for e in ev_result.scalars().all()]
    session.metrics = compute_session_metrics(events, session.duration_ms)

    # Load user
    user_result = await db.execute(select(TrackedUser).where(TrackedUser.id == session.user_id))
    user = user_result.scalar_one()
    user.session_count += 1
    await db.commit()

    # Rebuild baseline
    baseline = await rebuild_baseline(db, user)

    drift_result = None
    if baseline and user.baseline_ready and session.metrics:
        drift_result = compute_drift(session.metrics, baseline.stats)
        if drift_result:
            drift_event = DriftEvent(
                user_id=user.id,
                session_id=session.id,
                drift_type=drift_result["drift_type"],
                severity=drift_result["severity"],
                score=drift_result["score"],
                signals=drift_result["signals"],
            )
            db.add(drift_event)
            await db.commit()
            await db.refresh(drift_event)
            await db.refresh(user)
            await deliver_drift_event(db, drift_event)

    await db.refresh(session)
    return {"session_id": session.id, "drift": drift_result, **_session_out(session)}


@router.get("/{session_id}")
async def get_session(
    session_id: int,
    api_key: ApiKey = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.api_key_id == api_key.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    drift_result = await db.execute(
        select(DriftEvent).where(DriftEvent.session_id == session_id)
    )
    drift = drift_result.scalar_one_or_none()

    return {
        **_session_out(session),
        "drift": {
            "drift_type": drift.drift_type,
            "severity": drift.severity,
            "score": drift.score,
            "signals": drift.signals,
        } if drift else None,
    }
