// Backend Configuration
// Allow override via window.backendUrl for testing
const backendUrl = window.backendUrl || (window.location.hostname === 'localhost'
  ? 'http://localhost:5001'  // Use 5001 to avoid macOS AirPlay on port 5000
  : 'https://asthma.fredrikmeyer.net');

// Storage keys
const storageKey = 'asthma-usage-entries';
const lastTypeKey = 'asthma-last-medicine-type';
const tokenKey = 'asthma-auth-token';

// Token management functions
function getToken() {
  return localStorage.getItem(tokenKey);
}

function setToken(token) {
  if (!token) {
    throw new Error('Token cannot be empty');
  }
  localStorage.setItem(tokenKey, token);
}

function clearToken() {
  localStorage.removeItem(tokenKey);
}

function hasToken() {
  const token = getToken();
  return token !== null && token !== '';
}

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
const entriesEl = document.getElementById('entries');
const toastEl = document.getElementById('toast');
const medicineTypeButtons = document.querySelectorAll('.medicine-type');
const preventiveBtn = document.getElementById('preventive-toggle');

const today = new Date();
usageDate.valueAsDate = today;

let selectedMedicineType = localStorage.getItem(lastTypeKey) || 'ventoline';
let preventive = false;

function generateId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).substring(2) + Date.now().toString(36);
}

function createTimestamp(dateValue) {
  const today = new Date().toISOString().slice(0, 10);
  return dateValue === today ? new Date().toISOString() : dateValue + 'T12:00:00.000Z';
}

function getEventsForDate(events, date) {
  return events.filter((e) => e.date === date);
}

function sumForType(events, date, type) {
  return getEventsForDate(events, date)
    .filter((e) => e.type === type)
    .reduce((sum, e) => sum + e.count, 0);
}

function loadEntries() {
  const raw = localStorage.getItem(storageKey);
  try {
    return raw ? JSON.parse(raw) : [];
  } catch (_) {
    return [];
  }
}

// One-time migration: convert old date-keyed format to flat event array
function migrateToEventLog(data) {
  const migrationKey = 'asthma-migrated-v2';
  if (localStorage.getItem(migrationKey)) {
    return data;
  }

  // Already an array means nothing to convert
  if (Array.isArray(data)) {
    localStorage.setItem(migrationKey, 'true');
    return data;
  }

  // Convert date-keyed object to event array
  const events = [];
  for (const [date, value] of Object.entries(data)) {
    let spray = 0;
    let ventoline = 0;
    if (typeof value === 'number') {
      ventoline = value;
    } else if (value && typeof value === 'object') {
      spray = value.spray || 0;
      ventoline = value.ventoline || 0;
    }
    if (spray > 0) {
      events.push({ id: generateId(), date, timestamp: date + 'T12:00:00.000Z', type: 'spray', count: spray, preventive: false });
    }
    if (ventoline > 0) {
      events.push({ id: generateId(), date, timestamp: date + 'T12:00:01.000Z', type: 'ventoline', count: ventoline, preventive: false });
    }
  }

  localStorage.setItem(migrationKey, 'true');
  return events;
}

function saveEntries(entries) {
  localStorage.setItem(storageKey, JSON.stringify(entries));
}

function render(events) {
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
    del.addEventListener('click', () => {
      entries = entries.filter((e) => e.date !== date);
      saveEntries(entries);
      render(entries);
      toast('Entry removed');
    });
    item.appendChild(del);
    entriesEl.appendChild(item);
  }
}

function toast(message) {
  toastEl.textContent = message;
  toastEl.classList.add('show');
  setTimeout(() => toastEl.classList.remove('show'), 1800);
}

function formatDate(value) {
  return new Date(value).toISOString().slice(0, 10);
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
entries = migrateToEventLog(entries);
saveEntries(entries); // Save migrated data

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
  render(entries);
  toast('Saved');
});

resetBtn.addEventListener('click', () => {
  const dateKey = formatDate(usageDate.value);
  entries = entries.filter((e) => e.date !== dateKey);
  updateCount(0);
  saveEntries(entries);
  render(entries);
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
const showCodeBtn = document.getElementById('show-code');

// Update sync status UI
function updateSyncStatus() {
  const isConfigured = hasToken();
  if (isConfigured) {
    syncStatusText.textContent = 'Connected';
    syncStatusDot.classList.add('connected');
    syncSetupSection.style.display = 'none';
    syncConfiguredSection.style.display = 'block';
    syncFromCloudBtn.style.display = 'block';
    syncToCloudBtn.style.display = 'block';
  } else {
    syncStatusText.textContent = 'Not configured';
    syncStatusDot.classList.remove('connected');
    syncSetupSection.style.display = 'block';
    syncConfiguredSection.style.display = 'none';
    syncFromCloudBtn.style.display = 'none';
    syncToCloudBtn.style.display = 'none';
  }
}

// Generate setup code from backend
async function generateCode() {
  try {
    generateCodeBtn.disabled = true;
    generateCodeBtn.textContent = 'Generating...';

    const response = await fetch(`${backendUrl}/generate-code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });

    if (!response.ok) {
      throw new Error('Failed to generate code');
    }

    const data = await response.json();
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

    const response = await fetch(`${backendUrl}/generate-token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code })
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || 'Invalid code');
    }

    const data = await response.json();
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
    const response = await fetch(`${backendUrl}/code`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });

    if (!response.ok) {
      if (response.status === 401) {
        toast('Session expired. Please reconnect.');
        clearToken();
        updateSyncStatus();
        return;
      }
      throw new Error('Failed to retrieve code');
    }

    const data = await response.json();
    const code = data.code;

    // Try to copy to clipboard
    if (navigator.clipboard) {
      try {
        await navigator.clipboard.writeText(code);
        toast(`Your code: ${code} (copied to clipboard!)`);
      } catch (clipboardError) {
        // Fallback if clipboard fails
        toast(`Your code: ${code}`);
      }
    } else {
      // Fallback for browsers without clipboard API
      toast(`Your code: ${code}`);
    }
  } catch (error) {
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

    let successCount = 0;
    let errorCount = 0;

    for (const event of entries) {
      try {
        const response = await fetch(`${backendUrl}/events`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ event })
        });

        if (response.ok) {
          successCount++;
        } else {
          errorCount++;
          console.error(`Failed to sync event ${event.id}:`, await response.text());
        }
      } catch (error) {
        errorCount++;
        console.error(`Network error syncing event ${event.id}:`, error);
      }
    }

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

    const response = await fetch(`${backendUrl}/events`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Token expired. Please reconnect.');
      }
      throw new Error('Failed to fetch events from cloud');
    }

    const data = await response.json();
    const cloudEvents = data.events;

    if (cloudEvents.length === 0) {
      toast('No data on cloud yet');
      return;
    }

    const localIds = new Set(entries.map((e) => e.id));
    const unmatched = cloudEvents.filter((e) => !localIds.has(e.id));

    if (unmatched.length === 0) {
      toast('Already in sync');
      return;
    }

    // For each unmatched cloud event, check if a functionally equivalent
    // local event exists (same date/type/count/preventive but different ID).
    // If so, update the local ID to the cloud ID to align future syncs.
    // Otherwise treat it as genuinely new.
    const matchedLocalIndices = new Set();
    const trulyNew = [];

    for (const cloudEvent of unmatched) {
      const localIdx = entries.findIndex(
        (e, i) => !matchedLocalIndices.has(i) &&
                   e.date === cloudEvent.date &&
                   e.type === cloudEvent.type &&
                   e.count === cloudEvent.count &&
                   Boolean(e.preventive) === Boolean(cloudEvent.preventive)
      );
      if (localIdx !== -1) {
        matchedLocalIndices.add(localIdx);
        entries[localIdx] = { ...entries[localIdx], id: cloudEvent.id };
      } else {
        trulyNew.push(cloudEvent);
      }
    }

    entries = [...entries, ...trulyNew];
    saveEntries(entries);
    render(entries);

    if (trulyNew.length > 0) {
      toast(`✓ Synced ${trulyNew.length} new ${trulyNew.length === 1 ? 'event' : 'events'} from cloud`);
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
showCodeBtn.addEventListener('click', showCode);
syncFromCloudBtn.addEventListener('click', syncFromCloud);
syncToCloudBtn.addEventListener('click', syncToCloud);

// Handle Enter key in code input
codeInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') {
    completeSetup();
  }
});

// Initialize sync status on page load
updateSyncStatus();

const BASE_PATH = '/codex/';

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    const swUrl = new URL('service-worker.js', new URL(BASE_PATH, window.location.origin));
    navigator.serviceWorker.register(swUrl, { scope: BASE_PATH }).catch(() => {});
  });
}

render(entries);
