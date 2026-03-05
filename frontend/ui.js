import { sumForType } from './tracker.js';
import { buildAsthmaChartSvg, buildRitalinChartSvg } from './charts.js';

export function toast(message) {
  const toastEl = document.getElementById('toast');
  toastEl.textContent = message;
  toastEl.classList.add('show');
  setTimeout(() => toastEl.classList.remove('show'), 1800);
}

export function renderAsthmaHistory(events, onDeleteDate, onEditEntry) {
  const entriesEl = document.getElementById('entries');
  entriesEl.innerHTML = '';
  const dates = [...new Set(events.map((e) => e.date))].sort((a, b) => Temporal.PlainDate.compare(b, a));
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

    if (onEditEntry) {
      const dayEvents = events.filter((e) => e.date === date);
      for (const event of dayEvents) {
        const subRow = document.createElement('div');
        subRow.className = 'entry-subrow';
        const time = Temporal.Instant.from(event.timestamp).toZonedDateTimeISO(Temporal.Now.timeZoneId()).toPlainTime().toLocaleString('en-GB', { hour: '2-digit', minute: '2-digit' });
        const typeLabel = event.type === 'spray' ? 'Spray' : 'Ventoline';
        const preventiveLabel = event.preventive ? ' · preventive' : '';
        subRow.innerHTML = `<span class="subrow-detail">${typeLabel} × ${event.count}${preventiveLabel} <span class="breakdown">(${time})</span></span>`;
        const editBtn = document.createElement('button');
        editBtn.textContent = 'Edit';
        editBtn.className = 'ghost';
        editBtn.addEventListener('click', () => onEditEntry(event));
        subRow.appendChild(editBtn);
        entriesEl.appendChild(subRow);
      }
    }
  }
}

export function renderAsthmaChart(events) {
  const chartEl = document.getElementById('chart');
  const svg = buildAsthmaChartSvg(events);
  chartEl.innerHTML = svg ?? '<div class="hint">No data yet.</div>';
}

export function renderRitalinHistory(events, onDeleteDate, onEditEntry) {
  const entriesEl = document.getElementById('ritalin-entries');
  entriesEl.innerHTML = '';
  const dates = [...new Set(events.map((e) => e.date))].sort((a, b) => Temporal.PlainDate.compare(b, a));
  if (!dates.length) {
    entriesEl.innerHTML = '<div class="hint">No history yet. Log your first dose.</div>';
    return;
  }
  for (const date of dates) {
    const dayEvents = events.filter((e) => e.date === date);
    const total = dayEvents.reduce((sum, e) => sum + e.count, 0);
    const times = dayEvents
      .filter((e) => e.timestamp)
      .map((e) => Temporal.Instant.from(e.timestamp).toZonedDateTimeISO(Temporal.Now.timeZoneId()).toPlainTime().toLocaleString('en-GB', { hour: '2-digit', minute: '2-digit' }))
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

    if (onEditEntry) {
      for (const event of dayEvents) {
        const subRow = document.createElement('div');
        subRow.className = 'entry-subrow';
        const time = event.timestamp
          ? Temporal.Instant.from(event.timestamp).toZonedDateTimeISO(Temporal.Now.timeZoneId()).toPlainTime().toLocaleString('en-GB', { hour: '2-digit', minute: '2-digit' })
          : '';
        subRow.innerHTML = `<span class="subrow-detail">${event.count} ${event.count === 1 ? 'dose' : 'doses'}${time ? ` <span class="breakdown">(${time})</span>` : ''}</span>`;
        const editBtn = document.createElement('button');
        editBtn.textContent = 'Edit';
        editBtn.className = 'ghost';
        editBtn.addEventListener('click', () => onEditEntry(event));
        subRow.appendChild(editBtn);
        entriesEl.appendChild(subRow);
      }
    }
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
