import { lastTypeKey } from './config.js';
import { generateId, createTimestamp, sumForType, migrateToEventLog, weeklyRescueSummary } from './tracker.js';
import { buildReportHtml } from './report.js';
import { loadEntries, saveEntries, loadRitalinEntries, saveRitalinEntries } from './storage.js';
import { toast, renderAsthmaHistory, renderAsthmaChart, renderRitalinHistory, renderRitalinChart, renderWeeklySummary } from './ui.js';
import { initAsthmaEditDialog, openAsthmaEditDialog, initRitalinEditDialog, openRitalinEditDialog } from './editDialog.js';
import { initSyncService, deleteEventsFromCloud, deleteRitalinEventsFromCloud } from './syncService.js';

// DOM elements
const usageDate = /** @type {HTMLInputElement} */ (document.getElementById('usage-date'));
const countEl = /** @type {HTMLElement} */ (document.getElementById('count'));
const incBtn = /** @type {HTMLButtonElement} */ (document.getElementById('increment'));
const decBtn = /** @type {HTMLButtonElement} */ (document.getElementById('decrement'));
const saveBtn = /** @type {HTMLButtonElement} */ (document.getElementById('save'));
const resetBtn = /** @type {HTMLButtonElement} */ (document.getElementById('reset-day'));
const exportBtn = /** @type {HTMLButtonElement} */ (document.getElementById('export'));
const doctorReportBtn = /** @type {HTMLButtonElement} */ (document.getElementById('doctor-report'));
const medicineTypeButtons = /** @type {NodeListOf<HTMLButtonElement>} */ (document.querySelectorAll('.medicine-type:not(.edit-asthma-type)'));
const preventiveBtn = /** @type {HTMLButtonElement} */ (document.getElementById('preventive-toggle'));

usageDate.value = typeof Temporal !== 'undefined'
  ? Temporal.Now.plainDateISO().toString()
  : new Date().toISOString().slice(0, 10);

/** @type {MedicineType} */
let selectedMedicineType = /** @type {MedicineType} */ (localStorage.getItem(lastTypeKey) || 'ventoline');
let preventive = false;


/** @param {UsageEvent[]} events @returns {void} */
function renderAll(events) {
  renderWeeklySummary(weeklyRescueSummary(events));
  renderAsthmaHistory(events, (date) => {
    const removedIds = entries.filter((e) => e.date === date).map((e) => e.id);
    entries = entries.filter((e) => e.date !== date);
    saveEntries(entries);
    deleteEventsFromCloud(removedIds);
    renderAll(entries);
    toast('Entry removed');
  }, openAsthmaEditDialog);
  renderAsthmaChart(events);
}

/** @param {string} value @returns {string} */
function formatDate(value) {
  return Temporal.PlainDate.from(value).toString();
}

/** @param {number} value @returns {void} */
function updateCount(value) {
  countEl.textContent = String(value);
}

/** @returns {void} */
function updateCountForCurrentSelection() {
  const dateKey = formatDate(usageDate.value);
  updateCount(sumForType(entries, dateKey, selectedMedicineType));
}

/** @returns {void} */
function resetPreventive() {
  preventive = false;
  preventiveBtn.classList.remove('active');
}

let entries = loadEntries();
const migrationKey = 'asthma-migrated-v2';
if (!localStorage.getItem(migrationKey)) {
  entries = migrateToEventLog(entries);
  localStorage.setItem(migrationKey, 'true');
  saveEntries(entries);
}

// Set active medicine type button based on stored preference
medicineTypeButtons.forEach((btn) => {
  if (btn.dataset['type'] === selectedMedicineType) {
    btn.classList.add('active');
  } else {
    btn.classList.remove('active');
  }
});

updateCountForCurrentSelection();

medicineTypeButtons.forEach((btn) => {
  btn.addEventListener('click', () => {
    medicineTypeButtons.forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    selectedMedicineType = /** @type {MedicineType} */ (btn.dataset['type'] || 'ventoline');
    resetPreventive();
    updateCountForCurrentSelection();
  });
});

incBtn.addEventListener('click', () => {
  const current = Number(countEl.textContent) || 0;
  updateCount(current + 1);
});

decBtn.addEventListener('click', () => {
  const current = Number(countEl.textContent) || 0;
  updateCount(Math.max(0, current - 1));
});

usageDate.addEventListener('change', () => {
  resetPreventive();
  updateCountForCurrentSelection();
});

preventiveBtn.addEventListener('click', () => {
  preventive = !preventive;
  preventiveBtn.classList.toggle('active', preventive);
});

saveBtn.addEventListener('click', () => {
  const dateKey = formatDate(usageDate.value);
  const newCount = Number(countEl.textContent) || 0;
  if (newCount > 0) {
    entries.push({ id: generateId(), date: dateKey, timestamp: createTimestamp(dateKey), type: selectedMedicineType, count: newCount, preventive });
  }
  saveEntries(entries);
  localStorage.setItem(lastTypeKey, selectedMedicineType);
  updateCount(0);
  renderAll(entries);
  toast('Saved');
});

resetBtn.addEventListener('click', () => {
  const dateKey = formatDate(usageDate.value);
  entries = entries.filter((e) => e.date !== dateKey);
  updateCount(0);
  saveEntries(entries);
  renderAll(entries);
  toast('Reset for day');
});

exportBtn.addEventListener('click', () => {
  const sorted = [...entries].sort((a, b) => a.date.localeCompare(b.date) || a.timestamp.localeCompare(b.timestamp));
  const rows = [
    ['date', 'timestamp', 'type', 'count', 'preventive'],
    ...sorted.map((e) => [e.date, e.timestamp, e.type, e.count, e.preventive])
  ];
  const csv = rows.map((r) => r.join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'asthma-usage.csv';
  a.click();
  URL.revokeObjectURL(url);
  toast('CSV exported');
});

doctorReportBtn.addEventListener('click', () => {
  const win = window.open('', '_blank');
  if (!win) return;
  win.document.write(buildReportHtml(entries));
  win.document.close();
});

// --- Tab navigation ---
const tabButtons = document.querySelectorAll('.tab');
const tabPanels = document.querySelectorAll('.tab-panel');

tabButtons.forEach((btn) => {
  btn.addEventListener('click', () => {
    tabButtons.forEach((b) => {
      b.classList.remove('active');
      b.setAttribute('aria-selected', 'false');
    });
    tabPanels.forEach((p) => p.setAttribute('hidden', ''));

    btn.classList.add('active');
    btn.setAttribute('aria-selected', 'true');
    const panel = document.querySelector(`.tab-panel[data-panel="${/** @type {HTMLElement} */ (btn).dataset['tab']}"]`);
    if (panel) panel.removeAttribute('hidden');
  });
});

/** @param {RitalinEvent[]} events @returns {void} */
function renderRitalinAll(events) {
  renderRitalinHistory(events, (date) => {
    const removedIds = ritalinEntries.filter((e) => e.date === date).map((e) => e.id);
    ritalinEntries = ritalinEntries.filter((e) => e.date !== date);
    saveRitalinEntries(ritalinEntries);
    deleteRitalinEventsFromCloud(removedIds);
    renderRitalinAll(ritalinEntries);
    toast('Entry removed');
  }, openRitalinEditDialog);
  renderRitalinChart(events);
}

// --- Ritalin DOM elements ---
const ritalinDateEl = /** @type {HTMLInputElement} */ (document.getElementById('ritalin-date'));
const ritalinCountEl = /** @type {HTMLElement} */ (document.getElementById('ritalin-count'));
const ritalinIncBtn = /** @type {HTMLButtonElement} */ (document.getElementById('ritalin-increment'));
const ritalinDecBtn = /** @type {HTMLButtonElement} */ (document.getElementById('ritalin-decrement'));
const ritalinSaveBtn = /** @type {HTMLButtonElement} */ (document.getElementById('ritalin-save'));
const ritalinResetBtn = /** @type {HTMLButtonElement} */ (document.getElementById('ritalin-reset-day'));
const ritalinExportBtn = /** @type {HTMLButtonElement} */ (document.getElementById('ritalin-export'));

ritalinDateEl.value = typeof Temporal !== 'undefined'
  ? Temporal.Now.plainDateISO().toString()
  : new Date().toISOString().slice(0, 10);

let ritalinEntries = loadRitalinEntries();

/** @returns {void} */
function updateRitalinCountForDate() {
  const date = formatDate(ritalinDateEl.value);
  const total = ritalinEntries
    .filter((e) => e.date === date)
    .reduce((sum, e) => sum + e.count, 0);
  ritalinCountEl.textContent = String(total);
}

ritalinDateEl.addEventListener('change', updateRitalinCountForDate);

ritalinIncBtn.addEventListener('click', () => {
  ritalinCountEl.textContent = String((Number(ritalinCountEl.textContent) || 0) + 1);
});

ritalinDecBtn.addEventListener('click', () => {
  ritalinCountEl.textContent = String(Math.max(0, (Number(ritalinCountEl.textContent) || 0) - 1));
});

ritalinSaveBtn.addEventListener('click', () => {
  const dateKey = formatDate(ritalinDateEl.value);
  const newCount = Number(ritalinCountEl.textContent) || 0;
  if (newCount > 0) {
    ritalinEntries.push({ id: generateId(), date: dateKey, timestamp: createTimestamp(dateKey), count: newCount });
  }
  saveRitalinEntries(ritalinEntries);
  ritalinCountEl.textContent = '0';
  renderRitalinAll(ritalinEntries);
  toast('Saved');
});

ritalinResetBtn.addEventListener('click', () => {
  const dateKey = formatDate(ritalinDateEl.value);
  ritalinEntries = ritalinEntries.filter((e) => e.date !== dateKey);
  ritalinCountEl.textContent = '0';
  saveRitalinEntries(ritalinEntries);
  renderRitalinAll(ritalinEntries);
  toast('Reset for day');
});

ritalinExportBtn.addEventListener('click', () => {
  const sorted = [...ritalinEntries].sort((a, b) => a.date.localeCompare(b.date) || a.timestamp.localeCompare(b.timestamp));
  const rows = [
    ['date', 'timestamp', 'count'],
    ...sorted.map((e) => [e.date, e.timestamp, e.count])
  ];
  const csv = rows.map((r) => r.join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'ritalin-usage.csv';
  a.click();
  URL.revokeObjectURL(url);
  toast('CSV exported');
});

updateRitalinCountForDate();
renderRitalinAll(ritalinEntries);

initAsthmaEditDialog(
  () => entries,
  (e) => { entries = e; },
  renderAll
);

initRitalinEditDialog(
  () => ritalinEntries,
  (e) => { ritalinEntries = e; },
  renderRitalinAll
);

initSyncService({
  getEntries: () => entries,
  setEntries: (e) => { entries = e; },
  getRitalinEntries: () => ritalinEntries,
  setRitalinEntries: (e) => { ritalinEntries = e; },
  onSynced: (newEntries) => renderAll(newEntries),
  onRitalinSynced: (newEntries) => renderRitalinAll(newEntries),
  onLocalDataCleared: () => { updateCount(0); renderAll(entries); }
});

const BASE_PATH = '/codex/';

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    const swUrl = new URL('service-worker.js', new URL(BASE_PATH, window.location.origin));
    navigator.serviceWorker.register(swUrl, { scope: BASE_PATH }).catch(() => {});
  });
}

renderAll(entries);
