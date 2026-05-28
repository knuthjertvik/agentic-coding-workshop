// REQ-001/006/009/015/018 — fetch today's hourly prices, render, persist zone.

const ZONE_KEY = 'zone';
const DEFAULT_ZONE = 'NO1';

function fmt(n) {
  return Number(n).toFixed(2);
}

function hourLabel(iso) {
  // Upstream timestamps are CET/CEST; show only HH:MM.
  const t = iso.split('T')[1] || '';
  return t.slice(0, 5);
}

async function loadPrices() {
  const zone = document.getElementById('zone').value;
  const loading = document.getElementById('loading');
  const tbody = document.getElementById('hours-body');
  loading.hidden = false;
  try {
    const r = await fetch(`/api/prices?zone=${encodeURIComponent(zone)}`);
    if (!r.ok) throw new Error(`prices request failed: ${r.status}`);
    const data = await r.json();
    document.getElementById('date-label').textContent = data.date;
    tbody.innerHTML = '';
    for (const hour of data.hours) {
      const tr = document.createElement('tr');
      tr.className = 'border-b border-slate-100';
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

function showError(msg) {
  const el = document.getElementById('error');
  el.textContent = msg;
  el.hidden = false;
}

document.addEventListener('DOMContentLoaded', () => {
  const select = document.getElementById('zone');
  const savedZone = localStorage.getItem(ZONE_KEY) || DEFAULT_ZONE;
  select.value = savedZone;
  select.addEventListener('change', () => {
    localStorage.setItem(ZONE_KEY, select.value);
    loadPrices();
  });
  loadPrices();
});
