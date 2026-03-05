import { lastTypeKey } from './config.js';
import { generateId, createTimestamp, sumForType, migrateToEventLog, smartMerge, updateEntry } from './tracker.js';
import { loadEntries, saveEntries, loadRitalinEntries, saveRitalinEntries, getToken, setToken, clearToken, hasToken } from './storage.js';
import { apiGenerateCode, apiGenerateToken, apiFetchCode, apiUploadEvents, apiDownloadEvents, apiUploadRitalinEvents, apiDownloadRitalinEvents } from './api.js';
import { toast, renderAsthmaHistory, renderAsthmaChart, renderRitalinHistory, renderRitalinChart, updateSyncStatus as renderSyncStatus } from './ui.js';

// DOM elements
const usageDate = document.getElementById('usage-date');
const countEl = document.getElementById('count');
const incBtn = document.getElementById('increment');
const decBtn = document.getElementById('decrement');
const saveBtn = document.getElementById('save');
const resetBtn = document.getElementById('reset-day');
const exportBtn = document.getElementById('export');
const syncFromCloudBtn = document.getElementById('sync-from-cloud');
const syncToCloudBtn = document.getElementById('sync-to-cloud');
const medicineTypeButtons = document.querySelectorAll('.medicine-type:not(.edit-asthma-type)');
const preventiveBtn = document.getElementById('preventive-toggle');

usageDate.value = Temporal.Now.plainDateISO().toString();

let selectedMedicineType = localStorage.getItem(lastTypeKey) || 'ventoline';
let preventive = false;


function renderAll(events) {
  renderAsthmaHistory(events, (date) => {
    entries = entries.filter((e) => e.date !== date);
    saveEntries(entries);
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

// Sync setup DOM elements
const syncStatusText = document.getElementById('sync-status-text');
const syncStatusDot = document.querySelector('.status-dot');
const syncSetupSection = document.getElementById('sync-setup');
const syncConfiguredSection = document.getElementById('sync-configured');
const generateCodeBtn = document.getElementById('generate-code');
const generatedCodeDisplay = document.getElementById('generated-code');
const codeInput = document.getElementById('code-input');
const completeSetupBtn = document.getElementById('complete-setup');
const disconnectBtn = document.getElementById('disconnect-sync');
const clearLocalDataBtn = document.getElementById('clear-local-data');
const showCodeBtn = document.getElementById('show-code');

function updateSyncStatus() {
  renderSyncStatus(hasToken(), {
    syncStatusText, syncStatusDot, syncSetupSection, syncConfiguredSection,
    syncFromCloudBtn, syncToCloudBtn, ritalinSyncFromCloudBtn, ritalinSyncToCloudBtn
  });
}

// Generate setup code from backend
async function generateCode() {
  try {
    generateCodeBtn.disabled = true;
    generateCodeBtn.textContent = 'Generating...';

    const data = await apiGenerateCode();
    generatedCodeDisplay.textContent = data.code;
    generatedCodeDisplay.classList.add('show');
    toast('Code generated! Enter it below to complete setup.');
  } catch (error) {
    toast('Failed to generate code. Check your connection.');
    console.error('Generate code error:', error);
  } finally {
    generateCodeBtn.disabled = false;
    generateCodeBtn.textContent = 'Generate Code';
  }
}

// Complete setup by exchanging code for token
async function completeSetup() {
  const code = codeInput.value.trim().toUpperCase();
  if (!code) {
    toast('Please enter a code');
    return;
  }

  if (code.length !== 6) {
    toast('Code must be 6 characters');
    return;
  }

  try {
    completeSetupBtn.disabled = true;
    completeSetupBtn.textContent = 'Connecting...';

    const data = await apiGenerateToken(code);
    setToken(data.token);

    // Clear UI
    codeInput.value = '';
    generatedCodeDisplay.textContent = '';
    generatedCodeDisplay.classList.remove('show');

    updateSyncStatus();
    toast('Cloud sync connected!');
  } catch (error) {
    toast(error.message || 'Failed to connect. Please try again.');
    console.error('Complete setup error:', error);
  } finally {
    completeSetupBtn.disabled = false;
    completeSetupBtn.textContent = 'Complete Setup';
  }
}

// Clear all local data (keeps token/sync config intact)
function clearLocalData() {
  if (confirm('Clear all local data on this device? Your cloud data is unaffected. You can sync it back afterwards.')) {
    entries = [];
    saveEntries(entries);
    renderAll(entries);
    updateCount(0);
    toast('Local data cleared');
  }
}

// Disconnect sync
function disconnectSync() {
  if (confirm('Are you sure you want to disconnect cloud sync? Your local data will remain safe.')) {
    clearToken();
    updateSyncStatus();
    toast('Cloud sync disconnected');
  }
}

// Show user's 6-character code
async function showCode() {
  const token = getToken();
  if (!token) {
    toast('Please set up cloud sync first');
    return;
  }

  try {
    const data = await apiFetchCode(token);
    const code = data.code;

    if (navigator.clipboard) {
      try {
        await navigator.clipboard.writeText(code);
        toast(`Your code: ${code} (copied to clipboard!)`);
      } catch (_) {
        toast(`Your code: ${code}`);
      }
    } else {
      toast(`Your code: ${code}`);
    }
  } catch (error) {
    if (error.status === 401) {
      toast('Session expired. Please reconnect.');
      clearToken();
      updateSyncStatus();
      return;
    }
    toast('Failed to retrieve code. Check your connection.');
    console.error('Show code error:', error);
  }
}

// Sync entries to cloud
async function syncToCloud() {
  const token = getToken();
  if (!token) {
    toast('Please set up cloud sync first');
    return;
  }

  if (entries.length === 0) {
    toast('No entries to sync');
    return;
  }

  try {
    syncToCloudBtn.disabled = true;
    syncToCloudBtn.textContent = 'Syncing...';

    const { successCount, errorCount } = await apiUploadEvents(token, entries);

    if (errorCount === 0) {
      toast(`✓ Synced ${successCount} ${successCount === 1 ? 'event' : 'events'} to cloud`);
    } else if (successCount > 0) {
      toast(`⚠ Synced ${successCount} events, ${errorCount} failed`);
    } else {
      toast('✗ Sync failed. Check your connection.');
    }
  } catch (error) {
    toast('Sync failed. Check your connection.');
    console.error('Sync error:', error);
  } finally {
    syncToCloudBtn.disabled = false;
    syncToCloudBtn.textContent = 'Sync to Cloud';
  }
}

// Sync entries from cloud
async function syncFromCloud() {
  const token = getToken();
  if (!token) {
    toast('Please set up cloud sync first');
    return;
  }

  try {
    syncFromCloudBtn.disabled = true;
    syncFromCloudBtn.textContent = 'Syncing...';

    const data = await apiDownloadEvents(token);
    const cloudEvents = data.events;

    if (cloudEvents.length === 0) {
      toast('No data on cloud yet');
      return;
    }

    const { entries: merged, newCount, idUpdates } = smartMerge(entries, cloudEvents);

    if (newCount === 0 && idUpdates === 0) {
      toast('Already in sync');
      return;
    }

    entries = merged;
    saveEntries(entries);
    renderAll(entries);

    if (newCount > 0) {
      toast(`✓ Synced ${newCount} new ${newCount === 1 ? 'event' : 'events'} from cloud`);
    } else {
      toast('Already in sync');
    }
  } catch (error) {
    toast(error.message || 'Sync failed. Check your connection.');
    console.error('Sync from cloud error:', error);
  } finally {
    syncFromCloudBtn.disabled = false;
    syncFromCloudBtn.textContent = 'Sync from Cloud';
  }
}

// Event listeners for sync setup
generateCodeBtn.addEventListener('click', generateCode);
completeSetupBtn.addEventListener('click', completeSetup);
disconnectBtn.addEventListener('click', disconnectSync);
clearLocalDataBtn.addEventListener('click', clearLocalData);
showCodeBtn.addEventListener('click', showCode);
syncFromCloudBtn.addEventListener('click', syncFromCloud);
syncToCloudBtn.addEventListener('click', syncToCloud);

// Handle Enter key in code input
codeInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') {
    completeSetup();
  }
});

// Ritalin sync buttons — declared here so updateSyncStatus() can reference them
const ritalinSyncFromCloudBtn = document.getElementById('ritalin-sync-from-cloud');
const ritalinSyncToCloudBtn = document.getElementById('ritalin-sync-to-cloud');

// Initialize sync status on page load
updateSyncStatus();

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
    ritalinEntries = ritalinEntries.filter((e) => e.date !== date);
    saveRitalinEntries(ritalinEntries);
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

// --- Ritalin cloud sync ---
async function syncRitalinToCloud() {
  const token = getToken();
  if (!token) { toast('Please set up cloud sync first'); return; }
  if (ritalinEntries.length === 0) { toast('No entries to sync'); return; }

  try {
    ritalinSyncToCloudBtn.disabled = true;
    ritalinSyncToCloudBtn.textContent = 'Syncing...';

    const { successCount, errorCount } = await apiUploadRitalinEvents(token, ritalinEntries);

    if (errorCount === 0) {
      toast(`✓ Synced ${successCount} ${successCount === 1 ? 'event' : 'events'} to cloud`);
    } else if (successCount > 0) {
      toast(`⚠ Synced ${successCount} events, ${errorCount} failed`);
    } else {
      toast('✗ Sync failed. Check your connection.');
    }
  } finally {
    ritalinSyncToCloudBtn.disabled = false;
    ritalinSyncToCloudBtn.textContent = 'Sync to Cloud';
  }
}

async function syncRitalinFromCloud() {
  const token = getToken();
  if (!token) { toast('Please set up cloud sync first'); return; }

  try {
    ritalinSyncFromCloudBtn.disabled = true;
    ritalinSyncFromCloudBtn.textContent = 'Syncing...';

    const data = await apiDownloadRitalinEvents(token);
    const cloudEvents = data.events;

    if (cloudEvents.length === 0) { toast('No data on cloud yet'); return; }

    const localIds = new Set(ritalinEntries.map((e) => e.id));
    const newEvents = cloudEvents.filter((e) => !localIds.has(e.id));

    if (newEvents.length === 0) { toast('Already in sync'); return; }

    ritalinEntries = [...ritalinEntries, ...newEvents];
    saveRitalinEntries(ritalinEntries);
    renderRitalinAll(ritalinEntries);
    toast(`✓ Synced ${newEvents.length} new ${newEvents.length === 1 ? 'event' : 'events'} from cloud`);
  } catch (error) {
    toast(error.message || 'Sync failed. Check your connection.');
  } finally {
    ritalinSyncFromCloudBtn.disabled = false;
    ritalinSyncFromCloudBtn.textContent = 'Sync from Cloud';
  }
}

ritalinSyncToCloudBtn.addEventListener('click', syncRitalinToCloud);
ritalinSyncFromCloudBtn.addEventListener('click', syncRitalinFromCloud);

updateRitalinCountForDate();
renderRitalinAll(ritalinEntries);

// --- Asthma edit dialog ---
const asthmaEditDialog = document.getElementById('asthma-edit-dialog');
const editAsthmaDateEl = document.getElementById('edit-asthma-date');
const editAsthmaTimeEl = document.getElementById('edit-asthma-time');
const editAsthmaCountEl = document.getElementById('edit-asthma-count');
const editAsthmaPreventiveBtn = document.getElementById('edit-asthma-preventive');
const editAsthmaTypeButtons = document.querySelectorAll('.edit-asthma-type');
const editAsthmaSaveBtn = document.getElementById('edit-asthma-save');
const editAsthmaCancelBtn = document.getElementById('edit-asthma-cancel');

let editingAsthmaEntry = null;
let editingAsthmaPreventive = false;
let editingAsthmaType = 'ventoline';

function openAsthmaEditDialog(entry) {
  editingAsthmaEntry = entry;
  editingAsthmaPreventive = entry.preventive;
  editingAsthmaType = entry.type;
  const localTime = Temporal.Instant.from(entry.timestamp)
    .toZonedDateTimeISO(Temporal.Now.timeZoneId())
    .toPlainTime();
  editAsthmaDateEl.value = entry.date;
  editAsthmaTimeEl.value = localTime.toString().slice(0, 5);
  editAsthmaCountEl.value = entry.count;
  editAsthmaTypeButtons.forEach((btn) => btn.classList.toggle('active', btn.dataset.type === editingAsthmaType));
  editAsthmaPreventiveBtn.classList.toggle('active', editingAsthmaPreventive);
  asthmaEditDialog.showModal();
}

editAsthmaTypeButtons.forEach((btn) => {
  btn.addEventListener('click', () => {
    editingAsthmaType = btn.dataset.type;
    editAsthmaTypeButtons.forEach((b) => b.classList.toggle('active', b === btn));
  });
});

editAsthmaPreventiveBtn.addEventListener('click', () => {
  editingAsthmaPreventive = !editingAsthmaPreventive;
  editAsthmaPreventiveBtn.classList.toggle('active', editingAsthmaPreventive);
});

editAsthmaSaveBtn.addEventListener('click', () => {
  const newDate = editAsthmaDateEl.value;
  const newTime = editAsthmaTimeEl.value || '12:00';
  const newCount = Number(editAsthmaCountEl.value) || 1;
  const updated = { ...editingAsthmaEntry, date: newDate, timestamp: Temporal.PlainDateTime.from(`${newDate}T${newTime}:00`).toZonedDateTime(Temporal.Now.timeZoneId()).toInstant().toString(), type: editingAsthmaType, count: newCount, preventive: editingAsthmaPreventive };
  entries = updateEntry(entries, updated);
  saveEntries(entries);
  renderAll(entries);
  asthmaEditDialog.close();
  toast('Entry updated');
});

editAsthmaCancelBtn.addEventListener('click', () => asthmaEditDialog.close());

// --- Ritalin edit dialog ---
const ritalinEditDialog = document.getElementById('ritalin-edit-dialog');
const editRitalinDateEl = document.getElementById('edit-ritalin-date');
const editRitalinTimeEl = document.getElementById('edit-ritalin-time');
const editRitalinCountEl = document.getElementById('edit-ritalin-count');
const editRitalinSaveBtn = document.getElementById('edit-ritalin-save');
const editRitalinCancelBtn = document.getElementById('edit-ritalin-cancel');

let editingRitalinEntry = null;

function openRitalinEditDialog(entry) {
  editingRitalinEntry = entry;
  const localTime = Temporal.Instant.from(entry.timestamp)
    .toZonedDateTimeISO(Temporal.Now.timeZoneId())
    .toPlainTime();
  editRitalinDateEl.value = entry.date;
  editRitalinTimeEl.value = localTime.toString().slice(0, 5);
  editRitalinCountEl.value = entry.count;
  ritalinEditDialog.showModal();
}

editRitalinSaveBtn.addEventListener('click', () => {
  const newDate = editRitalinDateEl.value;
  const newTime = editRitalinTimeEl.value || '12:00';
  const newCount = Number(editRitalinCountEl.value) || 1;
  const updated = { ...editingRitalinEntry, date: newDate, timestamp: Temporal.PlainDateTime.from(`${newDate}T${newTime}:00`).toZonedDateTime(Temporal.Now.timeZoneId()).toInstant().toString(), count: newCount };
  ritalinEntries = updateEntry(ritalinEntries, updated);
  saveRitalinEntries(ritalinEntries);
  renderRitalinAll(ritalinEntries);
  ritalinEditDialog.close();
  toast('Entry updated');
});

editRitalinCancelBtn.addEventListener('click', () => ritalinEditDialog.close());

const BASE_PATH = '/codex/';

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    const swUrl = new URL('service-worker.js', new URL(BASE_PATH, window.location.origin));
    navigator.serviceWorker.register(swUrl, { scope: BASE_PATH }).catch(() => {});
  });
}

renderAll(entries);
