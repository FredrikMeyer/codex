import { lastTypeKey } from './config.js';
import { generateId, createTimestamp, sumForType, migrateToEventLog, weeklyRescueSummary } from './tracker.js';
import { buildReportHtml } from './report.js';
import { loadEntries, saveEntries, loadRitalinEntries, saveRitalinEntries } from './storage.js';
import { toast, renderAsthmaHistory, renderAsthmaChart, renderRitalinHistory, renderRitalinChart, renderWeeklySummary } from './ui.js';
import { initAsthmaEditDialog, openAsthmaEditDialog, initRitalinEditDialog, openRitalinEditDialog } from './editDialog.js';
import { initSyncService, deleteEventsFromCloud, deleteRitalinEventsFromCloud } from './syncService.js';

// DOM elements
const usageDate = document.getElementById('usage-date');
const countEl = document.getElementById('count');
const incBtn = document.getElementById('increment');
const decBtn = document.getElementById('decrement');
const saveBtn = document.getElementById('save');
const resetBtn = document.getElementById('reset-day');
const exportBtn = document.getElementById('export');
const doctorReportBtn = document.getElementById('doctor-report');
const medicineTypeButtons = document.querySelectorAll('.medicine-type:not(.edit-asthma-type)');
const preventiveBtn = document.getElementById('preventive-toggle');

usageDate.value = Temporal.Now.plainDateISO().toString();

let selectedMedicineType = localStorage.getItem(lastTypeKey) || 'ventoline';
let preventive = false;


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

function formatDate(value) {
  return Temporal.PlainDate.from(value).toString();
}

function updateCount(value) {
  countEl.textContent = value;
}

function updateCountForCurrentSelection() {
  const dateKey = formatDate(usageDate.value);
  updateCount(sumForType(entries, dateKey, selectedMedicineType));
}

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
  if (btn.dataset.type === selectedMedicineType) {
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
    selectedMedicineType = btn.dataset.type;
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
    const panel = document.querySelector(`.tab-panel[data-panel="${btn.dataset.tab}"]`);
    if (panel) panel.removeAttribute('hidden');
  });
});

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
const ritalinDateEl = document.getElementById('ritalin-date');
const ritalinCountEl = document.getElementById('ritalin-count');
const ritalinIncBtn = document.getElementById('ritalin-increment');
const ritalinDecBtn = document.getElementById('ritalin-decrement');
const ritalinSaveBtn = document.getElementById('ritalin-save');
const ritalinResetBtn = document.getElementById('ritalin-reset-day');
const ritalinExportBtn = document.getElementById('ritalin-export');

ritalinDateEl.value = Temporal.Now.plainDateISO().toString();

let ritalinEntries = loadRitalinEntries();

function updateRitalinCountForDate() {
  const date = formatDate(ritalinDateEl.value);
  const total = ritalinEntries
    .filter((e) => e.date === date)
    .reduce((sum, e) => sum + e.count, 0);
  ritalinCountEl.textContent = total;
}

ritalinDateEl.addEventListener('change', updateRitalinCountForDate);

ritalinIncBtn.addEventListener('click', () => {
  ritalinCountEl.textContent = (Number(ritalinCountEl.textContent) || 0) + 1;
});

ritalinDecBtn.addEventListener('click', () => {
  ritalinCountEl.textContent = Math.max(0, (Number(ritalinCountEl.textContent) || 0) - 1);
});

ritalinSaveBtn.addEventListener('click', () => {
  const dateKey = formatDate(ritalinDateEl.value);
  const newCount = Number(ritalinCountEl.textContent) || 0;
  if (newCount > 0) {
    ritalinEntries.push({ id: generateId(), date: dateKey, timestamp: createTimestamp(dateKey), count: newCount });
  }
  saveRitalinEntries(ritalinEntries);
  ritalinCountEl.textContent = 0;
  renderRitalinAll(ritalinEntries);
  toast('Saved');
});

ritalinResetBtn.addEventListener('click', () => {
  const dateKey = formatDate(ritalinDateEl.value);
  ritalinEntries = ritalinEntries.filter((e) => e.date !== dateKey);
  ritalinCountEl.textContent = 0;
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
