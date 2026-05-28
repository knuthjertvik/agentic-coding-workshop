# Electricity Price Charging Advisor — Implementation Plan

## Context

We are adding a new feature to the existing FastAPI + SQLite + vanilla-JS template: a Norwegian electricity price viewer that fetches hourly spot prices from `hvakosterstrommen.no`, applies VAT + grid tariff, caches results in SQLite, and recommends the cheapest hours to charge an EV. The full requirements are in `specs/ears/electricity-price-charging-advisor.md` (REQ-001…REQ-024).

The implementation is split into **six end-to-end-verifiable verticals**. Each vertical includes its own tests (written first, TDD-style) and ships a slice the user can actually click through in the browser before we move on. This guards against the "all backend, no frontend" trap and keeps every step demonstrable.

## Conventions for every vertical

- **TDD per vertical**: write failing tests → implement → green. Run `uv run pytest backend/tests/` (<5s).
- **Backend tests** follow `backend/tests/conftest.py` patterns — in-memory SQLite via `StaticPool`, `client` fixture, dependency override of `get_db`. Mock upstream HTTP with `respx` (add to dev deps) or monkeypatch the `httpx.AsyncClient`.
- **Schema changes**: after editing `backend/app/models.py`, delete `workshop.db` (per `AGENTS.md`).
- **Frontend** stays buildless — extend `frontend/app.js` and `frontend/index.html`. No npm.
- **Atomic commits per vertical** on a feature branch.
- **Manual verification per vertical**: `uv run uvicorn app.main:app --reload --app-dir backend --port 8000`, open http://localhost:8000.

---

## Vertical 1 — Today's prices for selected zone (backend + frontend)

**REQs**: 001, 002, 003, 004, 005, 006, 009, 015, 017, 018, 023

**Backend**
- New module `backend/app/prices.py` — pure pricing math: `apply_vat(spot_ore_per_kwh)`, `grid_tariff_ore(dt_cet)` returning 36.40 day-weekday / 26.40 night-or-weekend, `build_hour_row(spot, dt_cet)` returning `{start, spot, vat, tariff, total}`. No I/O.
- New module `backend/app/strompris_client.py` — `async fetch_day(zone, date) -> list[HourRow]` using `httpx.AsyncClient`, URL `https://www.hvakosterstrommen.no/api/v1/prices/{YYYY}/{MM}-{DD}_{zone}.json`. 5s timeout.
- New model `PriceDay` in `backend/app/models.py` — columns `zone` (str), `date` (Date), `fetched_at` (DateTime), `payload_json` (Text — list of HourRow). Composite unique on (zone, date). **Delete `workshop.db` after this edit.**
- New router `backend/app/routers/prices.py`:
  - `GET /api/prices?zone=NO1&date=YYYY-MM-DD` → returns `{zone, date, hours:[{start, total, ...}]}`.
  - Cache rule (REQ-017): if a `PriceDay` row exists for (zone, date) **and** `fetched_at` is after the most recent 12:45 CET/CEST boundary, return cached payload. Otherwise call upstream, persist, return.
- Wire router into `backend/app/main.py`.

**Frontend** (`frontend/index.html`, `frontend/app.js`)
- Replace ping UI with: zone `<select>` (NO1…NO5, default NO1), date label, hourly table showing each hour's total øre/kWh in CET/CEST.
- On load: read zone from `localStorage` (fallback NO1), call `/api/prices?zone=…&date=today`, render rows. Show "Loading…" indicator while in flight (REQ-015).
- On zone change: re-fetch without page reload (REQ-009), persist new zone to `localStorage` (REQ-018).

**Tests (write first)**
- `backend/tests/test_prices_math.py` — fixed timestamps for weekday day (Mon 10:00), weekday night (Tue 23:00), Saturday 14:00, Sunday 03:00 covering REQ-002, 003.
- `backend/tests/test_prices_endpoint.py` — monkeypatch `fetch_day`; assert cache miss triggers upstream, cache hit (fresh `fetched_at`) skips upstream, stale cache (before today's 12:45) triggers refetch. Asserts payload shape (REQ-001, 005, 017, 023).
- Manual: open in browser, switch zones, reload — confirm last zone restored.

**Vertical 1 done when**: Browser shows today's hourly prices for the selected zone with VAT + tariff, zone selector persists, second hit in same publish window is cache-only.

---

## Vertical 2 — Charging recommendation (cheapest hours)

**REQs**: 012, 013, 014, 016, 021

**Backend**
- New module `backend/app/recommender.py` — pure functions: `cheapest_individual(hours, n)` returns sorted list of N hour-start timestamps; `cheapest_contiguous(hours, n)` returns the start of the lowest-average N-hour window; both filter to `hours[i].start >= now_cet` (REQ-012/013 "remaining today + tomorrow"). Caller passes `now`.
- Extend `/api/prices` response or add `GET /api/recommendation?zone&hours=N&contiguous=bool` (cleaner: separate endpoint reusing cached price rows). Returns 422-style payload `{message: "requested N hours exceeds available M"}` when N > available (REQ-021).

**Frontend**
- Add inputs: number-of-charging-hours (number input) and contiguous toggle (checkbox).
- Show config prompt (REQ-014) until zone and hours are both set.
- While `/api/recommendation` is in flight, hide the recommendation panel (REQ-016).
- Highlight matching `<tr>`s in the hourly table when recommendation returns.

**Tests (write first)**
- `backend/tests/test_recommender.py` — fixed hour array of 24 hours: assert `cheapest_individual([prices], 3)` returns the 3 lowest indices; `cheapest_contiguous(prices, 3)` returns the correct window; N > available returns the exceeded message (REQ-012, 013, 021).
- Manual: enter N=3, toggle contiguous, observe different highlights.

**Vertical 2 done when**: User sets N charging hours, sees the N cheapest (or contiguous N) highlighted in the table; over-large N shows an error message.

---

## Vertical 3 — Tomorrow's prices and combined window

**REQs**: 007, 008

**Backend**
- Extend `GET /api/prices` (or add `?include_tomorrow=true`) so it returns today's remaining hours plus tomorrow's hours **when** the current CET/CEST time is past 12:45. Reuse `fetch_day(zone, tomorrow)`, persist as a separate `PriceDay` row.
- Skip the upstream call for tomorrow before 12:45 (REQ-007).

**Frontend**
- Render today's remaining hours + tomorrow's hours in a single list with date-separating header rows (REQ-008).
- Recommendation now spans the combined window automatically (no frontend change beyond passing the merged hours through).

**Tests (write first)**
- `backend/tests/test_tomorrow_fetch.py` — clock fixture (monkeypatch a `now_cet()` helper) asserts fetch fires at 12:45 boundary and not before. Cached tomorrow row served after 12:45 without re-hitting upstream (combined with REQ-017 logic).
- Manual: clock-fixture-driven integration check; manual browser check after 12:45 CET.

**Vertical 3 done when**: Browser at >12:45 CET shows remaining-today + tomorrow's 24 hours in one view.

---

## Vertical 4 — Upstream failure fallback

**REQs**: 019, 020

**Backend**
- In `/api/prices` (and `/api/recommendation`): wrap upstream call in `try`; on `httpx.HTTPError`/timeout, return the most recent cached `PriceDay` for (zone, date) regardless of staleness (REQ-019). If no cached row exists, return HTTP 503 with `{detail: "Prices unavailable"}` (REQ-020).

**Frontend**
- Display 503 detail as a banner; otherwise render returned cached data normally (no special UI needed for REQ-019 — stale-cache vs fresh-cache is invisible to the user, which is the spec intent).

**Tests (write first)**
- `backend/tests/test_prices_fallback.py` — mock upstream to raise `httpx.TimeoutException` with a stale cache row → returns the cached payload (REQ-019). Same exception with no cache → 503 (REQ-020).
- Manual: stop network/point client at a bad URL, confirm cached data still renders; clear DB and confirm error banner.

**Vertical 4 done when**: Killing upstream still serves prices when cache exists, otherwise shows "prices unavailable".

---

## Vertical 5 — Norgespris mode

**REQs**: 010, 011

**Frontend only** — purely client-side toggle.
- Add Norgespris checkbox above the main UI.
- When enabled: hide every other element (zone selector, hours input, table, recommendation, chart) and show only the text "price is nothing to worry about".
- Persist Norgespris flag in `localStorage` alongside zone.

**Tests (write first)**
- Manual UI check is the only verification path the spec calls out (REQ-010/011). Add a brief comment in `app.js` referencing the requirement IDs; no automated test.

**Vertical 5 done when**: Toggling Norgespris in the browser hides everything except the confirmation text.

---

## Vertical 6 — Line graph

**REQs**: 022, 024

**Frontend**
- Vendor **Chart.js UMD** (single file) under `frontend/vendor/chart.umd.min.js`. Pin version, record SHA-256 in header comment, update `frontend/README.md` per existing Tailwind precedent.
- Compute today's average from the hourly data; bucket each hour as `cheap` (< avg − 10%), `medium`, `expensive` (> avg + 10%) — bucket thresholds named in `app.js` and easy to tweak.
- Render a line chart in `<canvas>` with point colours per bucket (REQ-022).

**Tests (write first)**
- No backend test required. Add a small JS helper `bucketHour(price, avg)` that we can sanity-check by hand in the console; verification is the manual UI check from the spec.

**Vertical 6 done when**: Browser shows a line graph above the table, with each point coloured by cheap/medium/expensive against today's average.

---

## Critical files

- `backend/app/main.py` — register prices router.
- `backend/app/models.py` — add `PriceDay` model (then `rm workshop.db`).
- `backend/app/prices.py` *(new)* — VAT + tariff math.
- `backend/app/strompris_client.py` *(new)* — upstream `httpx` client.
- `backend/app/recommender.py` *(new)* — cheapest-hours logic.
- `backend/app/routers/prices.py` *(new)* — `/api/prices`, `/api/recommendation`.
- `backend/tests/test_prices_math.py`, `test_prices_endpoint.py`, `test_recommender.py`, `test_tomorrow_fetch.py`, `test_prices_fallback.py` *(new)* — follow `backend/tests/_template.py` and `conftest.py`.
- `frontend/index.html` — replace ping markup with zone selector, inputs, table, canvas.
- `frontend/app.js` — fetch, render, recommendation highlight, Norgespris toggle, chart.
- `frontend/vendor/chart.umd.min.js` *(new)* + `frontend/README.md` update.
- `pyproject.toml` — add `respx` to dev deps for mocking httpx (optional; monkeypatch also fine).

## End-to-end verification (final)

1. `rm -f workshop.db` (schema reset after model changes).
2. `uv run pytest backend/tests/` — all green.
3. `uv run uvicorn app.main:app --reload --app-dir backend --port 8000`; open http://localhost:8000.
4. Walk through each REQ in the spec's "Verification notes" section, ticking the checkboxes in `specs/ears/electricity-price-charging-advisor.md` as each vertical lands.
5. Stop the network (or block `hvakosterstrommen.no` in hosts) and confirm fallback (REQ-019/020).
