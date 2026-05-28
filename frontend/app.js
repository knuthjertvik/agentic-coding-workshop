// REQ-001/006/009/015/018 — fetch today's hourly prices, render, persist zone.
// REQ-012/013/014/016/021 — charging recommendation highlight + config prompt.

// REQ-010/011 — Norgespris mode hides the main app and shows a calm message;
// preference persists in localStorage across reloads.
const NORGESPRIS_KEY = 'norgespris';

function applyNorgespris(enabled) {
  const mainApp = document.getElementById('main-app');
  const msg = document.getElementById('norgespris-msg');
  const chart = document.querySelector('#price-chart');
  mainApp.hidden = enabled;
  msg.hidden = !enabled;
  if (chart) chart.hidden = enabled;
  localStorage.setItem(NORGESPRIS_KEY, enabled ? 'true' : 'false');
}

const ZONE_KEY = 'zone';
const HOURS_KEY = 'hours';
const CONTIGUOUS_KEY = 'contiguous';
const DEFAULT_ZONE = 'NO1';
const HIGHLIGHT_CLASS = 'bg-green-100';

function fmt(n) {
  return Number(n).toFixed(2);
}

function hourLabel(iso) {
  // Upstream timestamps are CET/CEST; show only HH:MM.
  const t = iso.split('T')[1] || '';
  return t.slice(0, 5);
}

function currentZone() {
  return document.getElementById('zone').value;
}

function currentHours() {
  const raw = document.getElementById('charging-hours').value;
  const n = parseInt(raw, 10);
  return Number.isFinite(n) && n > 0 ? n : null;
}

function currentContiguous() {
  return document.getElementById('contiguous').checked;
}

function updateConfigPrompt() {
  // REQ-014 — prompt visible until zone AND hours are both configured.
  const prompt = document.getElementById('config-prompt');
  prompt.hidden = !!(currentZone() && currentHours());
}

async function loadPrices() {
  const zone = currentZone();
  const loading = document.getElementById('loading');
  const tbody = document.getElementById('hours-body');
  loading.hidden = false;
  try {
    const r = await fetch(`/api/prices?zone=${encodeURIComponent(zone)}`);
    if (!r.ok) {
      // REQ-020 — surface upstream-unavailable as the server-reported detail.
      let detail = `prices request failed: ${r.status}`;
      try {
        const body = await r.json();
        if (body && body.detail) detail = body.detail;
      } catch (_) { /* non-JSON body — keep the fallback message */ }
      tbody.innerHTML = '';
      showError(detail);
      return;
    }
    clearError();
    const data = await r.json();
    document.getElementById('date-label').textContent = data.date;
    tbody.innerHTML = '';
    // REQ-008 — when the window spans midnight (after 12:45 publish),
    // insert a date-header row between today and tomorrow.
    let currentDate = null;
    for (const hour of data.hours) {
      const hourDate = hour.start.split('T')[0];
      if (hourDate !== currentDate) {
        if (currentDate !== null) {
          const header = document.createElement('tr');
          header.className = 'bg-slate-100 font-semibold';
          header.innerHTML = `<td class="py-1" colspan="5">${hourDate}</td>`;
          tbody.appendChild(header);
        }
        currentDate = hourDate;
      }
      const tr = document.createElement('tr');
      tr.className = 'border-b border-slate-100';
      tr.dataset.start = hour.start;
      tr.innerHTML = `
        <td class="py-1 font-mono">${hourLabel(hour.start)}</td>
        <td class="py-1 text-right font-mono">${fmt(hour.spot)}</td>
        <td class="py-1 text-right font-mono">${fmt(hour.vat)}</td>
        <td class="py-1 text-right font-mono">${fmt(hour.tariff)}</td>
        <td class="py-1 text-right font-mono font-semibold">${fmt(hour.total)}</td>`;
      tbody.appendChild(tr);
    }
  } catch (e) {
    showError('Could not load prices.');
  } finally {
    loading.hidden = true;
  }
}

function clearHighlights() {
  for (const tr of document.querySelectorAll('#hours-body tr')) {
    tr.classList.remove(HIGHLIGHT_CLASS);
  }
}

function showRecommendationError(msg) {
  const el = document.getElementById('recommendation-error');
  el.textContent = msg;
  el.hidden = false;
}

function clearRecommendationError() {
  const el = document.getElementById('recommendation-error');
  el.textContent = '';
  el.hidden = true;
}

async function loadRecommendation() {
  const hours = currentHours();
  if (!hours) {
    clearHighlights();
    document.getElementById('recommendation-panel').hidden = true;
    return;
  }
  const zone = currentZone();
  const contiguous = currentContiguous();
  const panel = document.getElementById('recommendation-panel');
  // REQ-016 — hide panel while the request is in flight.
  panel.hidden = true;
  clearHighlights();
  clearRecommendationError();
  try {
    const url = `/api/recommendation?zone=${encodeURIComponent(zone)}`
      + `&hours=${hours}&contiguous=${contiguous}`;
    const r = await fetch(url);
    if (!r.ok) {
      showRecommendationError(`Recommendation failed: ${r.status}`);
      return;
    }
    const data = await r.json();
    if (data.error) {
      // REQ-021 — over-request surfaces as an error banner above the table.
      showRecommendationError(data.error);
      return;
    }
    const starts = new Set(data.picks.map((p) => p.start));
    for (const tr of document.querySelectorAll('#hours-body tr')) {
      if (starts.has(tr.dataset.start)) tr.classList.add(HIGHLIGHT_CLASS);
    }
    const mode = data.contiguous ? 'contiguous' : 'individual';
    panel.textContent = `Recommended ${data.picks.length} ${mode} hour(s) highlighted below.`;
    panel.hidden = false;
  } catch (e) {
    showRecommendationError('Could not load recommendation.');
  }
}

async function refreshAll() {
  updateConfigPrompt();
  await loadPrices();
  await loadRecommendation();
}

function showError(msg) {
  const el = document.getElementById('error');
  el.textContent = msg;
  el.hidden = false;
}

function clearError() {
  const el = document.getElementById('error');
  el.textContent = '';
  el.hidden = true;
}

document.addEventListener('DOMContentLoaded', () => {
  const select = document.getElementById('zone');
  const hoursInput = document.getElementById('charging-hours');
  const contiguousInput = document.getElementById('contiguous');
  const norgesprisInput = document.getElementById('norgespris');

  const norgesprisEnabled = localStorage.getItem(NORGESPRIS_KEY) === 'true';
  norgesprisInput.checked = norgesprisEnabled;
  applyNorgespris(norgesprisEnabled);
  norgesprisInput.addEventListener('change', () => {
    applyNorgespris(norgesprisInput.checked);
  });

  select.value = localStorage.getItem(ZONE_KEY) || DEFAULT_ZONE;
  const savedHours = localStorage.getItem(HOURS_KEY);
  if (savedHours) hoursInput.value = savedHours;
  contiguousInput.checked = localStorage.getItem(CONTIGUOUS_KEY) === 'true';

  select.addEventListener('change', () => {
    localStorage.setItem(ZONE_KEY, select.value);
    refreshAll();
  });
  hoursInput.addEventListener('change', () => {
    if (hoursInput.value) localStorage.setItem(HOURS_KEY, hoursInput.value);
    else localStorage.removeItem(HOURS_KEY);
    updateConfigPrompt();
    loadRecommendation();
  });
  contiguousInput.addEventListener('change', () => {
    localStorage.setItem(CONTIGUOUS_KEY, String(contiguousInput.checked));
    loadRecommendation();
  });

  refreshAll();
});
