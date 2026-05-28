"""Tests for the /api/prices endpoint.

All REQs are pending — tests are xfail until the prices router and
strompris client land.
"""

from datetime import date, datetime

import pytest


def _fake_upstream(zone, day):
    """Return a deterministic 24-hour spot-price list for a given zone/date.

    Shape matches what we'd build from hvakosterstrommen.no — one row per
    hour with a CET/CEST start timestamp and a spot price in øre/kWh.
    """
    return [
        {"start": datetime(day.year, day.month, day.day, h).isoformat(),
         "spot_ore": 50.0 + h}
        for h in range(24)
    ]


def test_prices_endpoint_returns_today_hours_for_no1(client, monkeypatch):
    # REQ-001, REQ-023
    from app import prices as prices_module
    from app import strompris_client

    monkeypatch.setattr(prices_module, "now_cet",
                        lambda: datetime(2026, 5, 28, 10, 0))
    monkeypatch.setattr(strompris_client, "fetch_day",
                        lambda zone, day: _fake_upstream(zone, day))
    resp = client.get("/api/prices", params={"zone": "NO1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["zone"] == "NO1"
    assert len(body["hours"]) == 24


def test_prices_endpoint_defaults_to_no1_when_zone_omitted(client, monkeypatch):
    # REQ-006
    from app import strompris_client

    seen = {}

    def spy(zone, day):
        seen["zone"] = zone
        return _fake_upstream(zone, day)

    monkeypatch.setattr(strompris_client, "fetch_day", spy)
    resp = client.get("/api/prices")
    assert resp.status_code == 200
    assert seen["zone"] == "NO1"


@pytest.mark.parametrize("zone", ["NO1", "NO2", "NO3", "NO4", "NO5"])
def test_prices_endpoint_accepts_all_no_zones(client, monkeypatch, zone):
    # REQ-006
    from app import strompris_client

    monkeypatch.setattr(strompris_client, "fetch_day",
                        lambda z, d: _fake_upstream(z, d))
    resp = client.get("/api/prices", params={"zone": zone})
    assert resp.status_code == 200


def test_prices_endpoint_rejects_unknown_zone(client):
    # REQ-006 — only NO1..NO5 are valid
    resp = client.get("/api/prices", params={"zone": "NO9"})
    assert resp.status_code in (400, 422)


def test_prices_response_includes_cet_labeled_timestamps_and_date(client, monkeypatch):
    # REQ-004
    from app import prices as prices_module
    from app import strompris_client

    monkeypatch.setattr(prices_module, "now_cet",
                        lambda: datetime(2026, 5, 28, 10, 0))
    monkeypatch.setattr(strompris_client, "fetch_day",
                        lambda z, d: _fake_upstream(z, d))
    body = client.get("/api/prices", params={"zone": "NO1"}).json()
    assert "date" in body
    first = body["hours"][0]
    # Either explicit timezone or a CET-naive timestamp paired with the date.
    assert "start" in first
    assert body["date"] in first["start"]


def test_prices_persisted_to_sqlite_keyed_by_zone_and_date(client, db_session, monkeypatch):
    # REQ-005
    from app import prices as prices_module
    from app import strompris_client
    from app.models import PriceDay

    # Pin to before 12:45 so only today's row is persisted (tomorrow-fetch
    # would otherwise add a second row after the publish window).
    monkeypatch.setattr(prices_module, "now_cet",
                        lambda: datetime(2026, 5, 28, 10, 0))
    monkeypatch.setattr(strompris_client, "fetch_day",
                        lambda z, d: _fake_upstream(z, d))
    client.get("/api/prices", params={"zone": "NO1"})
    rows = db_session.query(PriceDay).filter_by(zone="NO1").all()
    assert len(rows) == 1
    assert rows[0].date == date(2026, 5, 28)


def test_cache_hit_within_publish_window_skips_upstream(client, monkeypatch):
    # REQ-017 — second call within the same publish window must not hit upstream
    from app import prices as prices_module
    from app import strompris_client

    monkeypatch.setattr(prices_module, "now_cet",
                        lambda: datetime(2026, 5, 28, 10, 0))
    calls = {"n": 0}

    def counting(zone, day):
        calls["n"] += 1
        return _fake_upstream(zone, day)

    monkeypatch.setattr(strompris_client, "fetch_day", counting)
    client.get("/api/prices", params={"zone": "NO1"})
    client.get("/api/prices", params={"zone": "NO1"})
    assert calls["n"] == 1


def test_stale_cache_refreshed_when_upstream_succeeds(client, db_session, monkeypatch):
    # REQ-017 — a row older than the most recent 12:45 boundary must be
    # refetched and its fetched_at advanced to the current clock.
    import json
    from datetime import date as date_t
    from app import prices as prices_module
    from app import strompris_client
    from app.models import PriceDay

    target = date_t(2026, 5, 28)
    # Before yesterday's 12:45 boundary relative to pinned_now → stale.
    stale_when = datetime(2026, 5, 26, 13, 0)
    db_session.add(PriceDay(zone="NO1", date=target, fetched_at=stale_when,
                            payload_json=json.dumps([])))
    db_session.commit()

    pinned_now = datetime(2026, 5, 28, 10, 0)
    monkeypatch.setattr(prices_module, "now_cet", lambda: pinned_now)
    monkeypatch.setattr(strompris_client, "fetch_day",
                        lambda z, d: _fake_upstream(z, d))

    resp = client.get("/api/prices", params={"zone": "NO1"})
    assert resp.status_code == 200
    assert len(resp.json()["hours"]) == 24

    row = db_session.query(PriceDay).filter_by(zone="NO1", date=target).one()
    assert row.fetched_at == pinned_now
    assert row.fetched_at > stale_when
    assert json.loads(row.payload_json), "payload replaced with fresh hours"


def test_cache_miss_triggers_upstream_call(client, monkeypatch):
    # REQ-001
    from app import prices as prices_module
    from app import strompris_client

    monkeypatch.setattr(prices_module, "now_cet",
                        lambda: datetime(2026, 5, 28, 10, 0))
    calls = {"n": 0}

    def counting(zone, day):
        calls["n"] += 1
        return _fake_upstream(zone, day)

    monkeypatch.setattr(strompris_client, "fetch_day", counting)
    client.get("/api/prices", params={"zone": "NO1"})
    # Different zone = different cache key
    client.get("/api/prices", params={"zone": "NO2"})
    assert calls["n"] == 2
