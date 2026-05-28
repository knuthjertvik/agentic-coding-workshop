"""Upstream-failure fallback tests.

REQ-019 / REQ-020 — pending.
"""

from datetime import date, datetime, time

import httpx


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


def _pin_clock(monkeypatch):
    # Pin pre-12:45 so the endpoint only fetches today (V3 behavior would
    # also fetch tomorrow after the publish window, polluting the assertions).
    from app import prices as prices_module

    monkeypatch.setattr(
        prices_module, "now_cet",
        lambda: datetime.combine(date.today(), time(10, 0)),
    )


def test_upstream_timeout_serves_stale_cache(client, db_session, monkeypatch):
    # REQ-019
    from app import strompris_client

    _pin_clock(monkeypatch)
    _seed_cache(db_session, "NO1", date.today())

    def boom(zone, day):
        raise httpx.TimeoutException("upstream timed out")

    monkeypatch.setattr(strompris_client, "fetch_day", boom)
    resp = client.get("/api/prices", params={"zone": "NO1"})
    assert resp.status_code == 200
    assert len(resp.json()["hours"]) == 24


def test_upstream_http_error_serves_stale_cache(client, db_session, monkeypatch):
    # REQ-019
    from app import strompris_client

    _pin_clock(monkeypatch)
    _seed_cache(db_session, "NO1", date.today())

    def boom(zone, day):
        raise httpx.HTTPStatusError(
            "500", request=httpx.Request("GET", "http://x"),
            response=httpx.Response(500))

    monkeypatch.setattr(strompris_client, "fetch_day", boom)
    resp = client.get("/api/prices", params={"zone": "NO1"})
    assert resp.status_code == 200
    assert len(resp.json()["hours"]) == 24


def test_upstream_fail_with_no_cache_returns_unavailable_error(client, monkeypatch):
    # REQ-020
    from app import strompris_client

    _pin_clock(monkeypatch)

    def boom(zone, day):
        raise httpx.TimeoutException("upstream timed out")

    monkeypatch.setattr(strompris_client, "fetch_day", boom)
    resp = client.get("/api/prices", params={"zone": "NO1"})
    assert resp.status_code >= 500
    detail = resp.json().get("detail", "").lower()
    assert "unavailable" in detail or "prices" in detail
