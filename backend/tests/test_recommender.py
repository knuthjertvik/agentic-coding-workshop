"""Recommendation-logic tests.

REQ-012 / REQ-013 / REQ-021 — pending.
"""

from datetime import datetime

import pytest


def _series(start_hour, prices):
    """Build a list of {start, total} rows starting at the given hour."""
    return [
        {"start": datetime(2026, 5, 28, start_hour + i).isoformat(),
         "total": p}
        for i, p in enumerate(prices)
    ]


@pytest.mark.xfail(reason="REQ-012: not yet implemented")
def test_individual_cheapest_returns_n_lowest_hours():
    # REQ-012
    from app.recommender import cheapest_individual

    hours = _series(0, [50, 30, 70, 20, 90, 40, 10, 80])
    now = datetime(2026, 5, 28, 0, 0)
    picks = cheapest_individual(hours, n=3, now=now)
    starts = {p["start"] for p in picks}
    # Cheapest three are indices 6 (10), 3 (20), 1 (30)
    assert starts == {
        datetime(2026, 5, 28, 6).isoformat(),
        datetime(2026, 5, 28, 3).isoformat(),
        datetime(2026, 5, 28, 1).isoformat(),
    }


@pytest.mark.xfail(reason="REQ-013: not yet implemented")
def test_contiguous_cheapest_returns_window_with_lowest_average():
    # REQ-013
    from app.recommender import cheapest_contiguous

    hours = _series(0, [90, 80, 70, 10, 20, 30, 80, 90])
    now = datetime(2026, 5, 28, 0, 0)
    picks = cheapest_contiguous(hours, n=3, now=now)
    starts = [p["start"] for p in picks]
    # Contiguous window 3..5 has avg 20 — the lowest
    assert starts == [
        datetime(2026, 5, 28, 3).isoformat(),
        datetime(2026, 5, 28, 4).isoformat(),
        datetime(2026, 5, 28, 5).isoformat(),
    ]


@pytest.mark.xfail(reason="REQ-012/013: not yet implemented")
def test_recommendation_filters_to_future_hours_only():
    # REQ-012/013 — "remaining hours today + tomorrow when available"
    from app.recommender import cheapest_individual

    hours = _series(0, [1, 2, 3, 4, 5, 100, 100, 100])
    now = datetime(2026, 5, 28, 5, 0)
    picks = cheapest_individual(hours, n=2, now=now)
    # Past hours 0..4 must be excluded even though they're the cheapest
    for p in picks:
        assert p["start"] >= datetime(2026, 5, 28, 5).isoformat()


@pytest.mark.xfail(reason="REQ-021: not yet implemented")
def test_request_more_hours_than_available_returns_error_message(client, monkeypatch):
    # REQ-021
    from app import strompris_client

    # 24 hours available, ask for 30
    monkeypatch.setattr(
        strompris_client, "fetch_day",
        lambda z, d: [
            {"start": datetime(d.year, d.month, d.day, h).isoformat(),
             "spot_ore": 50.0 + h}
            for h in range(24)
        ],
    )
    resp = client.get("/api/recommendation",
                      params={"zone": "NO1", "hours": 30, "contiguous": False})
    # Either 4xx with message, or 200 with an explicit "cannot fulfill" body
    body = resp.json()
    if resp.status_code == 200:
        assert body.get("error") or body.get("message")
    else:
        assert resp.status_code in (400, 409, 422)
