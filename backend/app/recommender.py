"""Charging recommendation logic — pure functions.

REQ-012: pick the N cheapest individual hours.
REQ-013: pick the N consecutive hours with the lowest mean total.
Both filter to hours starting at-or-after `now` so we never recommend
the past. Caller passes `now` so the helpers stay deterministic.
"""

from datetime import datetime


def _future_hours(hours: list[dict], now: datetime) -> list[dict]:
    return [h for h in hours if datetime.fromisoformat(h["start"]) >= now]


def cheapest_individual(hours: list[dict], n: int, now: datetime) -> list[dict]:
    future = _future_hours(hours, now)
    picks = sorted(future, key=lambda h: h["total"])[:n]
    return sorted(picks, key=lambda h: h["start"])


def cheapest_contiguous(hours: list[dict], n: int, now: datetime) -> list[dict]:
    future = _future_hours(hours, now)
    if n <= 0 or len(future) < n:
        # Shortfall — caller surfaces a 200+error body (REQ-021).
        return []
    best_start = min(
        range(len(future) - n + 1),
        key=lambda i: sum(h["total"] for h in future[i:i + n]),
    )
    return future[best_start:best_start + n]
