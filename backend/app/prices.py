"""Pure pricing math: VAT, grid tariff, and per-hour row assembly.

No I/O — all functions are deterministic on their inputs so the math
is trivially unit-testable.
"""

from datetime import datetime

VAT_RATE = 1.25
TARIFF_DAY_ORE = 36.40   # REQ-003 — weekday 06:00–22:00 CET/CEST
TARIFF_NIGHT_ORE = 26.40  # REQ-003 — weekday 22:00–06:00 and all weekend


def apply_vat(spot_ore_per_kwh: float) -> float:
    # REQ-002 — 25% VAT on top of the spot price.
    return spot_ore_per_kwh * VAT_RATE


def grid_tariff_ore(dt: datetime) -> float:
    # REQ-003 — weekday day rate 06:00 (inclusive) to 22:00 (exclusive);
    # otherwise night rate. Weekends are always night rate.
    is_weekend = dt.weekday() >= 5
    is_day_hour = 6 <= dt.hour < 22
    if is_weekend or not is_day_hour:
        return TARIFF_NIGHT_ORE
    return TARIFF_DAY_ORE


def build_hour_row(spot_ore: float, dt: datetime) -> dict:
    vat = apply_vat(spot_ore) - spot_ore
    tariff = grid_tariff_ore(dt)
    return {
        "start": dt.isoformat(),
        "spot": spot_ore,
        "vat": vat,
        "tariff": tariff,
        "total": apply_vat(spot_ore) + tariff,
    }
