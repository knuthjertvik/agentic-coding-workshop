"""Pricing-math tests for the Electricity Price Charging Advisor.

All REQs here are [NEW] / pending — tests are marked xfail until the
`app.prices` module exists with `apply_vat` and `grid_tariff_ore`.
"""

from datetime import datetime

import pytest

VAT_RATE = 1.25


def test_vat_25_percent_applied_to_spot():
    # REQ-002
    from app.prices import apply_vat

    assert apply_vat(100.0) == pytest.approx(125.0)
    assert apply_vat(0.0) == pytest.approx(0.0)
    assert apply_vat(40.0) == pytest.approx(50.0)


def test_grid_tariff_weekday_day_is_36_40():
    # REQ-003 — weekday 06:00–22:00 CET/CEST → 36.40 øre/kWh
    from app.prices import grid_tariff_ore

    # Monday 10:00 CET
    assert grid_tariff_ore(datetime(2026, 5, 25, 10, 0)) == pytest.approx(36.40)
    # Friday 21:59 CET (still day)
    assert grid_tariff_ore(datetime(2026, 5, 29, 21, 59)) == pytest.approx(36.40)
    # Monday 06:00 boundary — inclusive of day rate
    assert grid_tariff_ore(datetime(2026, 5, 25, 6, 0)) == pytest.approx(36.40)


def test_grid_tariff_weekday_night_is_26_40():
    # REQ-003 — weekday 22:00–06:00 CET/CEST → 26.40 øre/kWh
    from app.prices import grid_tariff_ore

    # Tuesday 23:00 CET
    assert grid_tariff_ore(datetime(2026, 5, 26, 23, 0)) == pytest.approx(26.40)
    # Wednesday 03:00 CET
    assert grid_tariff_ore(datetime(2026, 5, 27, 3, 0)) == pytest.approx(26.40)
    # Monday 22:00 boundary — inclusive of night rate
    assert grid_tariff_ore(datetime(2026, 5, 25, 22, 0)) == pytest.approx(26.40)


def test_grid_tariff_saturday_all_hours_night_rate():
    # REQ-003 — all weekend hours use 26.40 øre/kWh
    from app.prices import grid_tariff_ore

    # Saturday 2026-05-30 at 14:00 — would be "day" on a weekday
    assert grid_tariff_ore(datetime(2026, 5, 30, 14, 0)) == pytest.approx(26.40)
    assert grid_tariff_ore(datetime(2026, 5, 30, 8, 0)) == pytest.approx(26.40)


def test_grid_tariff_sunday_all_hours_night_rate():
    # REQ-003
    from app.prices import grid_tariff_ore

    # Sunday 2026-05-31
    assert grid_tariff_ore(datetime(2026, 5, 31, 3, 0)) == pytest.approx(26.40)
    assert grid_tariff_ore(datetime(2026, 5, 31, 12, 0)) == pytest.approx(26.40)
    assert grid_tariff_ore(datetime(2026, 5, 31, 20, 0)) == pytest.approx(26.40)
