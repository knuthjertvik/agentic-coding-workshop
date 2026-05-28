"""GET /api/prices — today's hourly spot prices with VAT and grid tariff.

Caching rule (REQ-017): a cached row is fresh if its `fetched_at`
timestamp is at or after the most recent 12:45 CET publish boundary —
that's when hvakosterstrommen.no publishes the next day. A second hit
in the same publish window is served from SQLite without touching the
upstream.
"""

import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import prices, strompris_client
from ..database import get_db
from ..models import PriceDay
from ..prices import build_hour_row
from ..recommender import cheapest_contiguous, cheapest_individual

router = APIRouter()

CET = ZoneInfo("Europe/Oslo")
VALID_ZONES = {"NO1", "NO2", "NO3", "NO4", "NO5"}
PUBLISH_HOUR = 12
PUBLISH_MINUTE = 45


def most_recent_1245_cet_boundary(now: datetime | None = None) -> datetime:
    """Return the most recent 12:45 Europe/Oslo boundary as a naive CET datetime."""
    if now is None:
        now = datetime.now(CET)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=CET)
    today_boundary = now.replace(hour=PUBLISH_HOUR, minute=PUBLISH_MINUTE,
                                 second=0, microsecond=0)
    if now >= today_boundary:
        boundary = today_boundary
    else:
        boundary = today_boundary - timedelta(days=1)
    # Strip tz so it compares cleanly with naive `fetched_at` written by us.
    return boundary.replace(tzinfo=None)


def _today_cet() -> date:
    # REQ-007 — go through the injectable clock so tests can pin wall-time.
    return prices.now_cet().date()


PUBLISH_TIME = (PUBLISH_HOUR, PUBLISH_MINUTE)


def _past_publish_window(now: datetime) -> bool:
    # REQ-007 — tomorrow's day-ahead prices land at 12:45 Europe/Oslo.
    return (now.hour, now.minute) >= PUBLISH_TIME


def _build_hours(upstream_rows: list[dict]) -> list[dict]:
    hours = []
    for row in upstream_rows:
        # Upstream `start` may carry a tz offset (real client) or be naive (test fake).
        # `fromisoformat` handles both; we then drop tz for the math helpers.
        dt = datetime.fromisoformat(row["start"])
        if dt.tzinfo is not None:
            dt = dt.astimezone(CET).replace(tzinfo=None)
        hours.append(build_hour_row(row["spot_ore"], dt))
    return hours


def _validate_zone(zone: str) -> None:
    # REQ-006 — only the five Norwegian bidding zones are valid.
    if zone not in VALID_ZONES:
        raise HTTPException(status_code=422, detail=f"Invalid zone {zone!r}")


def _hours_for(
    zone: str, target_date: date, db: Session, *, required: bool = True,
) -> list[dict] | None:
    """Return cached or freshly-fetched hours for (zone, date), honouring REQ-017.

    On upstream failure (REQ-019), fall back to the most recent cached row for
    (zone, date) regardless of staleness. If no cache exists and `required` is
    True, raise 503 (REQ-020); if `required` is False (e.g. tomorrow's slice
    after the publish window), return None so the caller can omit it.
    """
    boundary = most_recent_1245_cet_boundary()
    cached = (
        db.query(PriceDay)
        .filter(PriceDay.zone == zone, PriceDay.date == target_date)
        .one_or_none()
    )
    if cached is not None and cached.fetched_at >= boundary:
        return json.loads(cached.payload_json)

    try:
        upstream_rows = strompris_client.fetch_day(zone, target_date)
    except (httpx.HTTPError, httpx.TimeoutException):
        # REQ-019 — serve stale cache when upstream is unreachable.
        if cached is not None:
            return json.loads(cached.payload_json)
        if required:
            # REQ-020 — no cache, no upstream, primary day requested.
            raise HTTPException(status_code=503, detail="Prices unavailable")
        return None

    hours = _build_hours(upstream_rows)
    payload_json = json.dumps(hours)
    if cached is None:
        db.add(PriceDay(
            zone=zone,
            date=target_date,
            fetched_at=datetime.now(),
            payload_json=payload_json,
        ))
    else:
        cached.fetched_at = datetime.now()
        cached.payload_json = payload_json
    db.commit()
    return hours


@router.get("/prices")
def get_prices(
    zone: str = Query("NO1"),
    date_param: str | None = Query(None, alias="date"),
    db: Session = Depends(get_db),
):
    _validate_zone(zone)
    if date_param:
        target_date = date.fromisoformat(date_param)
        hours = _hours_for(zone, target_date, db)
        return {"zone": zone, "date": target_date.isoformat(), "hours": hours}

    now = prices.now_cet()
    today = now.date()
    hours = _hours_for(zone, today, db)
    # REQ-007/REQ-008 — after the 12:45 publish window, also fetch tomorrow
    # and trim today to the still-upcoming hours so the UI shows a rolling
    # window spanning the day boundary.
    if _past_publish_window(now):
        tomorrow_hours = _hours_for(
            zone, today + timedelta(days=1), db, required=False,
        )
        # REQ-019/020 — if tomorrow is unavailable, today still serves.
        hours = [h for h in hours
                 if datetime.fromisoformat(h["start"]) >= now] + (tomorrow_hours or [])
    return {"zone": zone, "date": today.isoformat(), "hours": hours}


@router.get("/recommendation")
def get_recommendation(
    zone: str = Query("NO1"),
    hours: int = Query(..., ge=1, le=48),
    contiguous: bool = Query(False),
    db: Session = Depends(get_db),
):
    # REQ-012/013 — pick cheapest individual or contiguous hours from now onward.
    _validate_zone(zone)
    now = prices.now_cet()
    target_date = now.date()
    rows = _hours_for(zone, target_date, db)
    if _past_publish_window(now):
        tomorrow = _hours_for(
            zone, target_date + timedelta(days=1), db, required=False,
        )
        rows = rows + (tomorrow or [])
    future = [r for r in rows if datetime.fromisoformat(r["start"]) >= now]
    if hours > len(future):
        # REQ-021 — surface the shortfall as a 200 with an explicit error body
        # so the frontend can render a banner without special status handling.
        return {
            "error": f"requested {hours} hours exceeds available {len(future)}",
            "available": len(future),
            "requested": hours,
        }
    picker = cheapest_contiguous if contiguous else cheapest_individual
    picks = picker(rows, hours, now)
    return {
        "zone": zone,
        "date": target_date.isoformat(),
        "contiguous": contiguous,
        "picks": picks,
    }
