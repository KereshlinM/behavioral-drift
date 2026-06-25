from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON, BigInteger, Boolean, DateTime, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    key_hash: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    key_prefix: Mapped[str] = mapped_column(String(12))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    sessions: Mapped[list["Session"]] = relationship(back_populates="api_key")
    webhooks: Mapped[list["Webhook"]] = relationship(back_populates="api_key")


class TrackedUser(Base):
    """A user being observed -- identified by client-provided external_id."""
    __tablename__ = "tracked_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    api_key_id: Mapped[int] = mapped_column(ForeignKey("api_keys.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    session_count: Mapped[int] = mapped_column(Integer, default=0)
    baseline_ready: Mapped[bool] = mapped_column(Boolean, default=False)

    sessions: Mapped[list["Session"]] = relationship(back_populates="user", order_by="Session.started_at")
    baseline: Mapped["Baseline | None"] = relationship(back_populates="user", uselist=False)
    drift_events: Mapped[list["DriftEvent"]] = relationship(back_populates="user")

    __table_args__ = (UniqueConstraint("external_id", "api_key_id"),)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("tracked_users.id"), index=True)
    api_key_id: Mapped[int] = mapped_column(ForeignKey("api_keys.id"))
    context: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    event_count: Mapped[int] = mapped_column(Integer, default=0)

    # Computed session metrics (populated on session end)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    user: Mapped["TrackedUser"] = relationship(back_populates="sessions")
    api_key: Mapped["ApiKey"] = relationship(back_populates="sessions")
    events: Mapped[list["Event"]] = relationship(back_populates="session")
    drift_events: Mapped[list["DriftEvent"]] = relationship(back_populates="session")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    ts: Mapped[float] = mapped_column(Float)        # client unix timestamp ms
    data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    session: Mapped["Session"] = relationship(back_populates="events")


class Baseline(Base):
    """Rolling per-user behavioral baseline."""
    __tablename__ = "baselines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("tracked_users.id"), unique=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    session_count: Mapped[int] = mapped_column(Integer, default=0)

    # Metric means and standard deviations stored as JSON
    # { "metric_name": {"mean": float, "std": float} }
    stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    user: Mapped["TrackedUser"] = relationship(back_populates="baseline")


class DriftEvent(Base):
    __tablename__ = "drift_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("tracked_users.id"), index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    drift_type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))    # low / medium / high
    score: Mapped[float] = mapped_column(Float)
    signals: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    webhook_delivered: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["TrackedUser"] = relationship(back_populates="drift_events")
    session: Mapped["Session"] = relationship(back_populates="drift_events")


class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    api_key_id: Mapped[int] = mapped_column(ForeignKey("api_keys.id"))
    url: Mapped[str] = mapped_column(Text)
    secret: Mapped[str | None] = mapped_column(String(128), nullable=True)
    events: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_delivery_status: Mapped[int | None] = mapped_column(Integer, nullable=True)

    api_key: Mapped["ApiKey"] = relationship(back_populates="webhooks")
    deliveries: Mapped[list["WebhookDelivery"]] = relationship(back_populates="webhook")


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    webhook_id: Mapped[int] = mapped_column(ForeignKey("webhooks.id"), index=True)
    drift_event_id: Mapped[int | None] = mapped_column(ForeignKey("drift_events.id"), nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    webhook: Mapped["Webhook"] = relationship(back_populates="deliveries")
