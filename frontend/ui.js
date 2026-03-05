import { sumForType } from './tracker.js';
import { buildAsthmaChartSvg, buildRitalinChartSvg } from './charts.js';

export function toast(message) {
  const toastEl = document.getElementById('toast');
  toastEl.textContent = message;
  toastEl.classList.add('show');
  setTimeout(() => toastEl.classList.remove('show'), 1800);
}

export function renderAsthmaHistory(events, onDeleteDate) {
  const entriesEl = document.getElementById('entries');
  entriesEl.innerHTML = '';
  const dates = [...new Set(events.map((e) => e.date))].sort((a, b) => new Date(b) - new Date(a));
  if (!dates.length) {
    entriesEl.innerHTML = '<div class="hint">No history yet. Save your first day.</div>';
    return;
  }
  for (const date of dates) {
    const item = document.createElement('div');
    item.className = 'entry';
    const sprayTotal = sumForType(events, date, 'spray');
    const ventolineTotal = sumForType(events, date, 'ventoline');
    const total = sprayTotal + ventolineTotal;
    const breakdown = [];
    if (sprayTotal > 0) breakdown.push(`Spray: ${sprayTotal}`);
    if (ventolineTotal > 0) breakdown.push(`Ventoline: ${ventolineTotal}`);
    const countText = breakdown.length > 0
      ? `${total} doses <span class="breakdown">(${breakdown.join(', ')})</span>`
      : `${total} doses`;
    item.innerHTML = `<div><div class="date">${date}</div><div class="count">${countText}</div></div>`;
    const del = document.createElement('button');
    del.textContent = 'Delete';
    del.className = 'ghost';
    del.addEventListener('click', () => onDeleteDate(date));
    item.appendChild(del);
    entriesEl.appendChild(item);
  }
}

export function renderAsthmaChart(events) {
  const chartEl = document.getElementById('chart');
  const svg = buildAsthmaChartSvg(events);
  chartEl.innerHTML = svg ?? '<div class="hint">No data yet.</div>';
}

export function renderRitalinHistory(events, onDeleteDate) {
  const entriesEl = document.getElementById('ritalin-entries');
  entriesEl.innerHTML = '';
  const dates = [...new Set(events.map((e) => e.date))].sort((a, b) => new Date(b) - new Date(a));
  if (!dates.length) {
    entriesEl.innerHTML = '<div class="hint">No history yet. Log your first dose.</div>';
    return;
  }
  for (const date of dates) {
    const dayEvents = events.filter((e) => e.date === date);
    const total = dayEvents.reduce((sum, e) => sum + e.count, 0);
    const times = dayEvents
      .filter((e) => e.timestamp)
      .map((e) => new Date(e.timestamp).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }))
      .join(', ');
    const item = document.createElement('div');
    item.className = 'entry';
    item.innerHTML = `<div><div class="date">${date}</div><div class="count">${total} ${total === 1 ? 'dose' : 'doses'}${times ? ` <span class="breakdown">(${times})</span>` : ''}</div></div>`;
    const del = document.createElement('button');
    del.textContent = 'Delete';
    del.className = 'ghost';
    del.addEventListener('click', () => onDeleteDate(date));
    item.appendChild(del);
    entriesEl.appendChild(item);
  }
}

export function renderRitalinChart(events) {
  const chartEl = document.getElementById('ritalin-chart');
  const svg = buildRitalinChartSvg(events);
  chartEl.innerHTML = svg ?? '<div class="hint">No data yet.</div>';
}

export function updateSyncStatus(isConfigured, elements) {
  const { syncStatusText, syncStatusDot, syncSetupSection, syncConfiguredSection,
          syncFromCloudBtn, syncToCloudBtn, ritalinSyncFromCloudBtn, ritalinSyncToCloudBtn } = elements;
  if (isConfigured) {
    syncStatusText.textContent = 'Connected';
    syncStatusDot.classList.add('connected');
    syncSetupSection.style.display = 'none';
    syncConfiguredSection.style.display = 'block';
    syncFromCloudBtn.style.display = 'block';
    syncToCloudBtn.style.display = 'block';
    ritalinSyncFromCloudBtn.style.display = 'block';
    ritalinSyncToCloudBtn.style.display = 'block';
  } else {
    syncStatusText.textContent = 'Not configured';
    syncStatusDot.classList.remove('connected');
    syncSetupSection.style.display = 'block';
    syncConfiguredSection.style.display = 'none';
    syncFromCloudBtn.style.display = 'none';
    syncToCloudBtn.style.display = 'none';
    ritalinSyncFromCloudBtn.style.display = 'none';
    ritalinSyncToCloudBtn.style.display = 'none';
  }
}
