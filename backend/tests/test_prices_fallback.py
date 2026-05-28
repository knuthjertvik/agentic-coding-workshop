"""Upstream-failure fallback tests.

REQ-019 / REQ-020 — pending.
"""

from datetime import date, datetime

import httpx
import pytest


def _hours(day):
    return [
        {"start": datetime(day.year, day.month, day.day, h).isoformat(),
         "spot_ore": 50.0 + h}
        for h in range(24)
    ]


def _seed_cache(db_session, zone, day):
    # Insert a stale cache row directly so the test does not depend on a
    # prior successful upstream call.
    from app.models import PriceDay

    row = PriceDay(zone=zone, date=day, fetched_at=datetime(2026, 5, 27, 13, 0),
                   payload_json=__import__("json").dumps(_hours(day)))
    db_session.add(row)
    db_session.commit()


@pytest.mark.xfail(reason="REQ-019: not yet implemented")
def test_upstream_timeout_serves_stale_cache(client, db_session, monkeypatch):
    # REQ-019
    from app import strompris_client

    _seed_cache(db_session, "NO1", date.today())

    def boom(zone, day):
        raise httpx.TimeoutException("upstream timed out")

    monkeypatch.setattr(strompris_client, "fetch_day", boom)
    resp = client.get("/api/prices", params={"zone": "NO1"})
    assert resp.status_code == 200
    assert len(resp.json()["hours"]) == 24


@pytest.mark.xfail(reason="REQ-019: not yet implemented")
def test_upstream_http_error_serves_stale_cache(client, db_session, monkeypatch):
    # REQ-019
    from app import strompris_client

    _seed_cache(db_session, "NO1", date.today())

    def boom(zone, day):
        raise httpx.HTTPStatusError(
            "500", request=httpx.Request("GET", "http://x"),
            response=httpx.Response(500))

    monkeypatch.setattr(strompris_client, "fetch_day", boom)
    resp = client.get("/api/prices", params={"zone": "NO1"})
    assert resp.status_code == 200
    assert len(resp.json()["hours"]) == 24


@pytest.mark.xfail(reason="REQ-020: not yet implemented")
def test_upstream_fail_with_no_cache_returns_unavailable_error(client, monkeypatch):
    # REQ-020
    from app import strompris_client

    def boom(zone, day):
        raise httpx.TimeoutException("upstream timed out")

    monkeypatch.setattr(strompris_client, "fetch_day", boom)
    resp = client.get("/api/prices", params={"zone": "NO1"})
    assert resp.status_code >= 500
    detail = resp.json().get("detail", "").lower()
    assert "unavailable" in detail or "prices" in detail
