import { sumForType } from './tracker.js';
import { buildAsthmaChartSvg, buildRitalinChartSvg } from './charts.js';

/** @param {string} message @returns {void} */
export function toast(message) {
  const toastEl = /** @type {HTMLElement} */ (document.getElementById('toast'));
  toastEl.textContent = message;
  toastEl.classList.add('show');
  setTimeout(() => toastEl.classList.remove('show'), 1800);
}

/**
 * @param {UsageEvent[]} events
 * @param {(date: string) => void} onDeleteDate
 * @param {((event: UsageEvent) => void) | null} onEditEntry
 * @returns {void}
 */
export function renderAsthmaHistory(events, onDeleteDate, onEditEntry) {
  const entriesEl = /** @type {HTMLElement} */ (document.getElementById('entries'));
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

/** @param {UsageEvent[]} events @returns {void} */
export function renderAsthmaChart(events) {
  const chartEl = /** @type {HTMLElement} */ (document.getElementById('chart'));
  const svg = buildAsthmaChartSvg(events);
  chartEl.innerHTML = svg ?? '<div class="hint">No data yet.</div>';
}

/**
 * @param {RitalinEvent[]} events
 * @param {(date: string) => void} onDeleteDate
 * @param {((event: RitalinEvent) => void) | null} onEditEntry
 * @returns {void}
 */
export function renderRitalinHistory(events, onDeleteDate, onEditEntry) {
  const entriesEl = /** @type {HTMLElement} */ (document.getElementById('ritalin-entries'));
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

/** @param {RitalinEvent[]} events @returns {void} */
export function renderRitalinChart(events) {
  const chartEl = /** @type {HTMLElement} */ (document.getElementById('ritalin-chart'));
  const svg = buildRitalinChartSvg(events);
  chartEl.innerHTML = svg ?? '<div class="hint">No data yet.</div>';
}

/**
 * @typedef {Object} SyncElements
 * @property {HTMLElement | null} syncStatusText
 * @property {Element | null} syncStatusDot
 * @property {HTMLElement | null} syncSetupSection
 * @property {HTMLElement | null} syncConfiguredSection
 * @property {HTMLElement | null} syncFromCloudBtn
 * @property {HTMLElement | null} syncToCloudBtn
 * @property {HTMLElement | null} ritalinSyncFromCloudBtn
 * @property {HTMLElement | null} ritalinSyncToCloudBtn
 */

/**
 * @param {boolean} isConfigured
 * @param {SyncElements} elements
 * @returns {void}
 */
export function updateSyncStatus(isConfigured, elements) {
  const { syncStatusText, syncStatusDot, syncSetupSection, syncConfiguredSection,
          syncFromCloudBtn, syncToCloudBtn, ritalinSyncFromCloudBtn, ritalinSyncToCloudBtn } = elements;
  if (isConfigured) {
    if (syncStatusText) syncStatusText.textContent = 'Connected';
    if (syncStatusDot) syncStatusDot.classList.add('connected');
    if (syncSetupSection) syncSetupSection.style.display = 'none';
    if (syncConfiguredSection) syncConfiguredSection.style.display = 'block';
    if (syncFromCloudBtn) syncFromCloudBtn.style.display = 'block';
    if (syncToCloudBtn) syncToCloudBtn.style.display = 'block';
    if (ritalinSyncFromCloudBtn) ritalinSyncFromCloudBtn.style.display = 'block';
    if (ritalinSyncToCloudBtn) ritalinSyncToCloudBtn.style.display = 'block';
  } else {
    if (syncStatusText) syncStatusText.textContent = 'Not configured';
    if (syncStatusDot) syncStatusDot.classList.remove('connected');
    if (syncSetupSection) syncSetupSection.style.display = 'block';
    if (syncConfiguredSection) syncConfiguredSection.style.display = 'none';
    if (syncFromCloudBtn) syncFromCloudBtn.style.display = 'none';
    if (syncToCloudBtn) syncToCloudBtn.style.display = 'none';
    if (ritalinSyncFromCloudBtn) ritalinSyncFromCloudBtn.style.display = 'none';
    if (ritalinSyncToCloudBtn) ritalinSyncToCloudBtn.style.display = 'none';
  }
}

/**
 * @param {WeeklySummary} stats
 * @returns {string}
 */
export function buildWeeklySummaryHtml(stats) {
  const { thisWeek, lastWeek, delta } = stats;
  if (thisWeek === 0 && lastWeek === 0) {
    return '<span class="weekly-none">No rescue uses in the last 2 weeks</span>';
  }
  const arrow = delta < 0 ? '↓' : delta > 0 ? '↑' : '→';
  const cls = delta < 0 ? 'better' : delta > 0 ? 'worse' : 'same';
  const absDelta = Math.abs(delta);
  const changeText = delta === 0 ? 'same as last week' : `${arrow}${absDelta} from last week`;
  return `
    <span class="weekly-count">${thisWeek} rescue ${thisWeek === 1 ? 'use' : 'uses'} this week</span>
    <span class="weekly-delta ${cls}">${changeText}</span>
  `;
}

/**
 * @param {WeeklySummary} stats
 * @returns {void}
 */
export function renderWeeklySummary(stats) {
  const el = document.getElementById('weekly-summary');
  if (!el) return;
  el.innerHTML = buildWeeklySummaryHtml(stats);
}
