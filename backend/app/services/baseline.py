"""Build and update per-user baselines from completed session metrics."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Baseline, Session, TrackedUser

settings = get_settings()


async def rebuild_baseline(db: AsyncSession, user: TrackedUser) -> Baseline | None:
    """
    Recompute the baseline for a user from their last N completed sessions.
    Returns the updated Baseline or None if not enough sessions yet.
    """
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user.id, Session.metrics.is_not(None))
        .order_by(Session.started_at.desc())
        .limit(settings.baseline_window)
    )
    sessions = result.scalars().all()

    if len(sessions) < settings.min_baseline_sessions:
        return None

    # Collect all metric values across sessions
    metric_values: dict[str, list[float]] = {}
    for s in sessions:
        for k, v in (s.metrics or {}).items():
            if isinstance(v, (int, float)) and v >= 0:
                metric_values.setdefault(k, []).append(float(v))

    stats: dict[str, dict[str, float]] = {}
    for metric, values in metric_values.items():
        if len(values) < 2:
            continue
        arr = np.array(values)
        std = float(np.std(arr))
        stats[metric] = {
            "mean": float(np.mean(arr)),
            "std": max(std, 1e-6),  # avoid zero-division in z-score
        }

    result2 = await db.execute(select(Baseline).where(Baseline.user_id == user.id))
    baseline = result2.scalar_one_or_none()

    if baseline is None:
        baseline = Baseline(user_id=user.id)
        db.add(baseline)

    baseline.stats = stats
    baseline.session_count = len(sessions)

    user.baseline_ready = True
    await db.commit()
    await db.refresh(baseline)
    return baseline


def z_score(value: float, mean: float, std: float) -> float:
    return (value - mean) / std


def score_metric(value: float, stat: dict[str, float]) -> float | None:
    """Return signed z-score if value is valid, else None."""
    if value < 0:
        return None
    return z_score(value, stat["mean"], stat["std"])


def compute_drift(
    metrics: dict[str, float],
    baseline_stats: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Compare session metrics against baseline stats.
    Returns a drift result dict or None if no significant drift detected.

    Drift types and their driving signals:
      cognitive_overload  -- slow typing, high backspace, many hesitations, long session
      disengagement       -- fast actions, low idle, few clicks, short session
      unusual_urgency     -- much faster than baseline, low hesitation, high click rate
      context_switch_fatigue -- high nav_back_rate, high repeated_click_ratio
      confusion           -- high repeated_click_ratio, high nav_back_rate, low typing speed
    """
    z: dict[str, float] = {}
    for metric, stat in baseline_stats.items():
        v = metrics.get(metric)
        if v is not None:
            s = score_metric(v, stat)
            if s is not None:
                z[metric] = s

    if not z:
        return None

    th = settings.drift_z_threshold

    def sig(key: str, direction: int = 0) -> float:
        """Return magnitude if z-score breaches threshold in the given direction (0=either)."""
        val = z.get(key, 0.0)
        if direction > 0 and val > th:
            return val
        if direction < 0 and val < -th:
            return abs(val)
        if direction == 0 and abs(val) > th:
            return abs(val)
        return 0.0

    drift_scores: dict[str, float] = {
        "cognitive_overload": (
            sig("session_duration_s", 1) * 1.2 +
            sig("backspace_rate", 1) * 1.0 +
            sig("hesitation_rate", 1) * 1.5 +
            sig("mean_click_interval_ms", 1) * 0.8 +
            sig("typing_speed", -1) * 0.8
        ) / 5.3,
        "disengagement": (
            sig("session_duration_s", -1) * 1.0 +
            sig("idle_ratio", -1) * 1.2 +
            sig("actions_per_minute", -1) * 1.0 +
            sig("hesitation_rate", -1) * 0.8
        ) / 4.0,
        "unusual_urgency": (
            sig("actions_per_minute", 1) * 1.5 +
            sig("click_rate", 1) * 1.2 +
            sig("hesitation_rate", -1) * 1.0 +
            sig("session_duration_s", -1) * 0.8
        ) / 4.5,
        "context_switch_fatigue": (
            sig("nav_back_rate", 1) * 1.5 +
            sig("repeated_click_ratio", 1) * 1.0 +
            sig("hesitation_rate", 1) * 0.8
        ) / 3.3,
        "confusion": (
            sig("repeated_click_ratio", 1) * 1.5 +
            sig("nav_back_rate", 1) * 1.2 +
            sig("typing_speed", -1) * 0.8 +
            sig("backspace_rate", 1) * 0.8
        ) / 4.3,
    }

    best_type = max(drift_scores, key=lambda k: drift_scores[k])
    best_score = drift_scores[best_type]

    if best_score < settings.drift_score_threshold:
        return None

    severity = "low" if best_score < 2.5 else "medium" if best_score < 4.0 else "high"

    return {
        "drift_type": best_type,
        "score": round(best_score, 3),
        "severity": severity,
        "signals": {
            k: round(v, 3)
            for k, v in z.items()
            if abs(v) > th
        },
        "all_scores": {k: round(v, 3) for k, v in drift_scores.items()},
    }
