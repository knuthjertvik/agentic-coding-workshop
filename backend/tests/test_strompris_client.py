"""Contract test for the hvakosterstrommen.no client.

Locks the NOK→øre conversion (× 100) and the URL shape using respx so
the rest of the suite can keep monkeypatching `fetch_day` with lambdas.
"""

from datetime import date

import respx
from httpx import Response


def test_fetch_day_converts_nok_per_kwh_to_ore():
    from app.strompris_client import fetch_day

    url = "https://www.hvakosterstrommen.no/api/v1/prices/2026/05-28_NO1.json"
    payload = [{"NOK_per_kWh": 0.5, "time_start": "2026-05-28T00:00:00+02:00"}]
    with respx.mock(assert_all_called=True) as mock:
        mock.get(url).mock(return_value=Response(200, json=payload))
        rows = fetch_day("NO1", date(2026, 5, 28))

    assert rows == [{"start": "2026-05-28T00:00:00+02:00", "spot_ore": 50.0}]
