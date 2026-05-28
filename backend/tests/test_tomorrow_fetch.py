"""Tests for the 12:45 CET/CEST tomorrow-fetch trigger.

REQ-007 / REQ-008 — pending. Clock is injected through `app.prices.now_cet`
so tests can pin the wall-clock without freezegun.
"""

from datetime import date, datetime, timedelta


def _fake_upstream(zone, day):
    return [
        {"start": datetime(day.year, day.month, day.day, h).isoformat(),
         "spot_ore": 50.0 + h}
        for h in range(24)
    ]


def test_before_1245_cet_does_not_fetch_tomorrow(client, monkeypatch):
    # REQ-007 — tomorrow's prices are not yet published before 12:45
    from app import prices as prices_module
    from app import strompris_client

    today = date(2026, 5, 28)
    monkeypatch.setattr(prices_module, "now_cet",
                        lambda: datetime(2026, 5, 28, 12, 30))
    requested_days = []
    monkeypatch.setattr(strompris_client, "fetch_day",
                        lambda z, d: (requested_days.append(d) or _fake_upstream(z, d)))

    client.get("/api/prices", params={"zone": "NO1"})
    assert today + timedelta(days=1) not in requested_days


def test_after_1245_cet_fetches_tomorrow(client, monkeypatch):
    # REQ-007
    from app import prices as prices_module
    from app import strompris_client

    today = date(2026, 5, 28)
    monkeypatch.setattr(prices_module, "now_cet",
                        lambda: datetime(2026, 5, 28, 12, 46))
    requested_days = []
    monkeypatch.setattr(strompris_client, "fetch_day",
                        lambda z, d: (requested_days.append(d) or _fake_upstream(z, d)))

    client.get("/api/prices", params={"zone": "NO1"})
    assert today + timedelta(days=1) in requested_days


def test_response_combines_remaining_today_and_tomorrow(client, monkeypatch):
    # REQ-008 — payload includes remaining hours of today + all of tomorrow
    from app import prices as prices_module
    from app import strompris_client

    monkeypatch.setattr(prices_module, "now_cet",
                        lambda: datetime(2026, 5, 28, 15, 0))
    monkeypatch.setattr(strompris_client, "fetch_day",
                        lambda z, d: _fake_upstream(z, d))

    body = client.get("/api/prices", params={"zone": "NO1"}).json()
    starts = [h["start"] for h in body["hours"]]
    # Remaining hours of today: 15..23 → 9 hours; plus 24 of tomorrow = 33
    assert len(starts) == 33
    assert any("2026-05-28T15" in s for s in starts)
    assert any("2026-05-29T00" in s for s in starts)
    assert any("2026-05-29T23" in s for s in starts)
