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

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import strompris_client
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
    return datetime.now(CET).date()


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


def _hours_for(zone: str, target_date: date, db: Session) -> list[dict]:
    """Return cached or freshly-fetched hours for (zone, date), honouring REQ-017."""
    boundary = most_recent_1245_cet_boundary()
    cached = (
        db.query(PriceDay)
        .filter(PriceDay.zone == zone, PriceDay.date == target_date)
        .one_or_none()
    )
    if cached is not None and cached.fetched_at >= boundary:
        return json.loads(cached.payload_json)

    upstream_rows = strompris_client.fetch_day(zone, target_date)
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
    target_date = date.fromisoformat(date_param) if date_param else _today_cet()
    hours = _hours_for(zone, target_date, db)
    return {"zone": zone, "date": target_date.isoformat(), "hours": hours}


@router.get("/recommendation")
def get_recommendation(
    zone: str = Query("NO1"),
    hours: int = Query(..., ge=1, le=48),
    contiguous: bool = Query(False),
    db: Session = Depends(get_db),
):
    # REQ-012/013 — pick cheapest individual or contiguous hours from now onward.
    _validate_zone(zone)
    target_date = _today_cet()
    rows = _hours_for(zone, target_date, db)
    now = datetime.now(CET).replace(tzinfo=None)
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
