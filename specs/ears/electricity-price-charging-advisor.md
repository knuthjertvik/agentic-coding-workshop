# Electricity Price Charging Advisor

> Show today's (and tomorrow's, when available) hourly Norwegian electricity prices and recommend the cheapest hours to charge an EV.

**Type:** New feature
**System:** Charging Advisor (FastAPI backend + vanilla-JS frontend in this repo)
**Date:** 2026-05-28

## Context

This repo ships a minimal FastAPI + SQLite + vanilla-JS template. We are adding a new feature that fetches Norwegian spot prices from the public `hvakosterstrommen.no` API, applies VAT and a time-of-use grid tariff, and displays the result with a recommended charging window. Prices are fetched server-side and cached in SQLite to limit API calls. The app is hosted locally — no notifications, no auth, no external accounts.

## Pending changes

- [ ] **REQ-001** — On app open, fetch today's hourly spot prices for the selected zone from hvakosterstrommen.no.
- [ ] **REQ-002** — Apply 25% VAT to fetched spot prices before display.
- [ ] **REQ-003** — Add time-of-use grid tariff (36.40 / 26.40 øre/kWh) on top of the VAT-inclusive price.
- [ ] **REQ-004** — Display hourly prices labelled in CET/CEST with the date visible.
- [ ] **REQ-005** — Store fetched price data in SQLite keyed by zone and date.
- [ ] **REQ-006** — Offer NO1–NO5 as selectable zones, default NO1.
- [ ] **REQ-007** — When clock passes 12:45 CET/CEST, fetch tomorrow's prices for the selected zone.
- [ ] **REQ-008** — Display remaining hours of today together with fetched hours of tomorrow.
- [ ] **REQ-009** — Reload prices without page reload when the zone changes.
- [ ] **REQ-010** — Show "price is nothing to worry about" message when Norgespris is enabled.
- [ ] **REQ-011** — While Norgespris is enabled, hide all UI elements other than the confirmation text.
- [ ] **REQ-012** — Highlight N individually cheapest hours (over remaining today + tomorrow when available) when contiguous mode is off.
- [ ] **REQ-013** — Highlight contiguous block of N hours with lowest average (over remaining today + tomorrow when available) when contiguous mode is on.
- [ ] **REQ-014** — Show a configuration prompt while zone or charging-hours are unset.
- [ ] **REQ-015** — Show a loading indicator while price data is being fetched.
- [ ] **REQ-016** — Withhold the recommendation while the API request is in flight.
- [ ] **REQ-017** — On app open, serve SQLite-cached data when the next 12:45 publish window has not yet passed since fetch.
- [ ] **REQ-018** — Persist the selected zone in `localStorage`.
- [ ] **REQ-019** — On upstream API error/timeout, fall back to the most-recent cached data.
- [ ] **REQ-020** — When upstream fails and no cache exists, show an unavailable-prices error.
- [ ] **REQ-021** — Show a message when requested charging hours exceed available hours.
- [ ] **REQ-022** — Render a line graph colour-coded cheap / medium / expensive vs. today's average.
- [ ] **REQ-023** — Expose price data via a backend `/api/` endpoint; the browser does not call hvakosterstrommen.no directly.
- [ ] **REQ-024** — Vendor a single static JS chart library under `frontend/vendor/` (version pinned, SHA-256 in header) for the line graph.

## Requirements

### Functional requirements

REQ-001 `[NEW]`: When the user opens the application, the system shall fetch today's hourly spot prices for the selected zone from the hvakosterstrommen.no API.

REQ-002 `[NEW]`: The system shall apply 25% VAT to fetched spot prices before display.

REQ-003 `[NEW]`: The system shall add a grid-tariff energy component to the VAT-inclusive price of 36.40 øre/kWh during weekday hours 06:00–22:00 CET/CEST, and 26.40 øre/kWh during weekday hours 22:00–06:00 CET/CEST and during all weekend hours.

REQ-004 `[NEW]`: The system shall display all hourly prices labelled in the CET/CEST time zone with the date clearly visible.

REQ-005 `[NEW]`: The system shall store fetched price data in SQLite, keyed by zone and date.

REQ-006 `[NEW]`: The system shall offer NO1, NO2, NO3, NO4, and NO5 as the selectable price zones, with NO1 as the default selection.

REQ-007 `[NEW]`: When the local clock passes 12:45 CET/CEST, the system shall fetch tomorrow's hourly prices for the selected zone from the hvakosterstrommen.no API.

REQ-008 `[NEW]`: When tomorrow's prices have been fetched, the system shall display the remaining hours of today together with the fetched hours of tomorrow.

REQ-009 `[NEW]`: When the user selects a different electricity zone, the system shall load prices for the new zone without reloading the page.

REQ-010 `[NEW]`: When the user enables the "I have Norgespris" option, the system shall display the message "price is nothing to worry about".

REQ-011 `[CHANGED]`: While the "I have Norgespris" option is enabled, the system shall hide all UI elements other than the Norgespris confirmation text, including charging-hour inputs, the price graph, and recommendations.

REQ-012 `[NEW]`: When the user has specified a number of charging hours and contiguous mode is disabled, the system shall highlight the N individually cheapest hours within the window of remaining hours today plus all hours of tomorrow when tomorrow's prices are available.

REQ-013 `[NEW]`: When the user has specified a number of charging hours and contiguous mode is enabled, the system shall highlight the contiguous block of N hours with the lowest average price within the window of remaining hours today plus all hours of tomorrow when tomorrow's prices are available.

REQ-014 `[NEW]`: While the user has not selected a zone or specified the number of charging hours, the system shall display a prompt instructing the user to complete the required selections.

REQ-015 `[NEW]`: While price data is being loaded, the system shall display a loading indicator.

REQ-016 `[NEW]`: While the price API request has not returned a response, the system shall withhold the charging recommendation from the display.

REQ-017 `[NEW]`: While cached price data for the requested zone and date exists in SQLite and the next 12:45 CET/CEST publish window has not yet passed since the data was fetched, when the user opens the application, the system shall serve the cached data instead of calling the upstream API.

REQ-018 `[NEW]`: The system shall persist the user's selected zone in `localStorage` so the choice survives across browser sessions.

### Unwanted behavior / error handling

REQ-019 `[NEW]`: If the hvakosterstrommen.no API returns an error response or times out, then the system shall serve the most recent cached price data for the requested zone and date.

REQ-020 `[NEW]`: If the upstream API fails and no cached data exists for the requested zone and date, then the system shall display an error message indicating that prices are unavailable.

REQ-021 `[NEW]`: If the user requests more charging hours than are present in the loaded price window, then the system shall display a message indicating that the request cannot be fulfilled.

### Optional features

REQ-022 `[CHANGED]`: Where today's prices are available, the system shall display a line graph of hourly prices with points colour-coded as cheap, medium, or expensive relative to today's average price.

### Constraints

REQ-023 `[NEW]`: The system shall expose price data to the frontend through a backend endpoint under `/api/` rather than calling hvakosterstrommen.no from the browser.

REQ-024 `[NEW]`: The system shall render the line graph using a single static JavaScript chart library vendored under `frontend/vendor/`, with its version pinned and SHA-256 recorded in a header comment per `frontend/README.md`.

## Verification notes

- **API + caching (REQ-001, 005, 017, 019, 020, 023):** Unit-test the backend endpoint with a mocked upstream — verify cache hits skip the call, cache misses trigger it, upstream errors fall back to cache, and missing cache returns an error.
- **Pricing math (REQ-002, 003):** Unit-test the price-builder with fixed input timestamps covering weekday day, weekday night, Saturday, and Sunday.
- **Zone + persistence (REQ-006, 009, 018):** Manual browser check — switch zones, reload, confirm last selection is restored from `localStorage`; confirm zone change re-fetches without a full page reload.
- **Recommendation logic (REQ-012, 013, 021):** Unit-test the recommender against a fixed price array for both individually-cheapest and contiguous modes; assert the message when N exceeds available hours.
- **Time-of-day trigger (REQ-007, 008):** Integration test with a clock fixture verifying tomorrow's fetch fires at 12:45 CET/CEST.
- **Norgespris mode (REQ-010, 011):** Manual UI check — enabling the toggle hides recommendations and shows the confirmation message.
- **States (REQ-014, 015, 016):** Manual UI check — fresh load shows the prompt; in-flight fetch shows the loading indicator; recommendation only appears after the response.
- **Chart (REQ-022):** Manual UI check — bars rendered, three colour buckets relative to daily average.

## Implementation tooling (non-requirement)

Not part of the product, but recommended for the build phase:

- **`strompris` MCP server** (see `docs/warmup-mcp-server.md`): wraps the hvakosterstrommen.no API as a Claude Code tool. Build and register at project scope before `/plan` or `/ws-gogogo`. Lets the implementing agent validate response shape, zone availability, and date edge-cases against the live API while writing the backend client and tests. The production code in REQ-001/023 still calls the API directly via `httpx` — the MCP is for agent introspection only.

Considered and rejected: Playwright MCP (overlaps with `agent-browser` already referenced by `/ws-gogogo`); SQLite MCP (`sqlite3 workshop.db` from a shell is enough); GitHub MCP (`gh` CLI already available).

## Open questions

None identified.

## Changelog

- 2026-05-28: Initial spec.
- 2026-05-28: Resolved open questions — REQ-017 cache validity bound to the 12:45 publish window; REQ-012/013 recommendation window extended to "remaining today + tomorrow when available"; REQ-022 changed from bar chart to line graph; REQ-011 strengthened to hide all non-text UI when Norgespris is enabled.
- 2026-05-28: Added REQ-024 — line graph must use a vendored static JS chart library under `frontend/vendor/`.
- 2026-05-28: Added "Implementation tooling" section recommending the `strompris` MCP server for agent introspection during the build (not a product requirement).
