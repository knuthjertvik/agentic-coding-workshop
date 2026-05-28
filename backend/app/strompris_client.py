"""Client for hvakosterstrommen.no hourly spot price API.

Synchronous on purpose — the test suite monkeypatches `fetch_day` with
a plain lambda, so the FastAPI route stays sync too. The upstream
publishes once per day; one blocking 5s call per cache miss is fine.
"""

from datetime import date

import httpx

BASE_URL = "https://www.hvakosterstrommen.no/api/v1/prices"
TIMEOUT_SECONDS = 5.0


def fetch_day(zone: str, day: date) -> list[dict]:
    """Return one row per hour: {start: ISO CET/CEST string, spot_ore: float}.

    Upstream returns NOK_per_kWh; we convert to øre/kWh (× 100).
    """
    url = f"{BASE_URL}/{day.year:04d}/{day.month:02d}-{day.day:02d}_{zone}.json"
    with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
        resp = client.get(url)
        resp.raise_for_status()
        payload = resp.json()
    return [
        {"start": row["time_start"], "spot_ore": float(row["NOK_per_kWh"]) * 100.0}
        for row in payload
    ]
