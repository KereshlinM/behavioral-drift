"""Compute behavioral metrics from a list of raw events."""

from __future__ import annotations

from typing import Any


def compute_session_metrics(events: list[dict[str, Any]], duration_ms: int | None) -> dict[str, float]:
    """
    Derive scalar behavioral metrics from a session's events.
    All returned values are floats; missing data yields -1.0 as sentinel.
    """
    if not events:
        return {}

    events_sorted = sorted(events, key=lambda e: e["ts"])
    total = len(events_sorted)
    duration_s = (duration_ms / 1000) if duration_ms else None

    clicks = [e for e in events_sorted if e["event_type"] == "click"]
    scrolls = [e for e in events_sorted if e["event_type"] == "scroll"]
    keypresses = [e for e in events_sorted if e["event_type"] == "keypress"]
    navs = [e for e in events_sorted if e["event_type"] == "navigation"]
    idles = [e for e in events_sorted if e["event_type"] == "idle"]

    metrics: dict[str, float] = {}

    # --- actions per minute ---
    if duration_s and duration_s > 0:
        metrics["actions_per_minute"] = total / (duration_s / 60)
    else:
        metrics["actions_per_minute"] = -1.0

    # --- click rate (clicks/minute) ---
    if duration_s and duration_s > 0:
        metrics["click_rate"] = len(clicks) / (duration_s / 60)
    else:
        metrics["click_rate"] = -1.0

    # --- inter-click interval mean (ms) ---
    if len(clicks) >= 2:
        intervals = [clicks[i]["ts"] - clicks[i - 1]["ts"] for i in range(1, len(clicks))]
        metrics["mean_click_interval_ms"] = sum(intervals) / len(intervals)
    else:
        metrics["mean_click_interval_ms"] = -1.0

    # --- typing speed (keypresses per minute, excluding backspace) ---
    char_presses = [k for k in keypresses if k.get("data", {}).get("key_type") == "char"]
    if duration_s and duration_s > 0 and char_presses:
        metrics["typing_speed"] = len(char_presses) / (duration_s / 60)
    else:
        metrics["typing_speed"] = -1.0

    # --- backspace rate (backspaces / total keypresses) ---
    backspaces = [k for k in keypresses if k.get("data", {}).get("key_type") == "backspace"]
    if keypresses:
        metrics["backspace_rate"] = len(backspaces) / len(keypresses)
    else:
        metrics["backspace_rate"] = -1.0

    # --- hesitation rate (pauses > 2s between consecutive events) ---
    if len(events_sorted) >= 2:
        gaps = [events_sorted[i]["ts"] - events_sorted[i - 1]["ts"] for i in range(1, len(events_sorted))]
        hesitations = sum(1 for g in gaps if g > 2000)
        metrics["hesitation_rate"] = hesitations / len(gaps)
    else:
        metrics["hesitation_rate"] = -1.0

    # --- scroll velocity (mean delta magnitude per scroll) ---
    scroll_deltas = [abs(s.get("data", {}).get("delta", 0)) for s in scrolls]
    if scroll_deltas:
        metrics["scroll_velocity"] = sum(scroll_deltas) / len(scroll_deltas)
    else:
        metrics["scroll_velocity"] = -1.0

    # --- navigation back rate ---
    back_navs = [n for n in navs if n.get("data", {}).get("is_back", False)]
    if navs:
        metrics["nav_back_rate"] = len(back_navs) / len(navs)
    else:
        metrics["nav_back_rate"] = -1.0

    # --- idle ratio (idle time / total session time) ---
    total_idle_ms = sum(e.get("data", {}).get("duration_ms", 0) for e in idles)
    if duration_ms and duration_ms > 0:
        metrics["idle_ratio"] = total_idle_ms / duration_ms
    else:
        metrics["idle_ratio"] = -1.0

    # --- repeated click ratio (clicks on same element consecutively) ---
    if len(clicks) >= 2:
        same = sum(
            1 for i in range(1, len(clicks))
            if clicks[i].get("data", {}).get("element_id")
            and clicks[i].get("data", {}).get("element_id") == clicks[i - 1].get("data", {}).get("element_id")
        )
        metrics["repeated_click_ratio"] = same / (len(clicks) - 1)
    else:
        metrics["repeated_click_ratio"] = -1.0

    # --- session duration (seconds) ---
    metrics["session_duration_s"] = duration_s if duration_s else -1.0

    return metrics
