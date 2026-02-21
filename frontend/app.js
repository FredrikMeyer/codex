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

const today = new Date();
usageDate.valueAsDate = today;

let selectedMedicineType = localStorage.getItem(lastTypeKey) || 'ventoline';

function normalizeEntry(value) {
  if (typeof value === 'number') {
    // Old format: just a number → treat as ventoline (not spray)
    return { spray: 0, ventoline: value, preventive: false };
  }
  return { spray: value.spray || 0, ventoline: value.ventoline || 0, preventive: value.preventive || false };
}

function loadEntries() {
  const raw = localStorage.getItem(storageKey);
  try {
    return raw ? JSON.parse(raw) : {};
  } catch (_) {
    return {};
  }
}

// One-time migration: flip old entries from spray→ventoline
function migrateOldData(entries) {
  const migrationKey = 'asthma-migrated-v1';
  if (localStorage.getItem(migrationKey)) {
    return entries; // Already migrated
  }

  const migrated = {};
  for (const [date, value] of Object.entries(entries)) {
    const normalized = normalizeEntry(value);
    // If entry has ONLY spray (no ventoline), flip it
    if (normalized.spray > 0 && normalized.ventoline === 0) {
      migrated[date] = { spray: 0, ventoline: normalized.spray };
    } else {
      migrated[date] = normalized;
    }
  }

  localStorage.setItem(migrationKey, 'true');
  return migrated;
}

function getEntryForDate(entries, date) {
  const entry = entries[date];
  return entry ? normalizeEntry(entry) : { spray: 0, ventoline: 0 };
}

function saveEntries(entries) {
  localStorage.setItem(storageKey, JSON.stringify(entries));
}

function render(entries) {
  entriesEl.innerHTML = '';
  const dates = Object.keys(entries).sort((a, b) => new Date(b) - new Date(a));
  if (!dates.length) {
    entriesEl.innerHTML = '<div class="hint">No history yet. Save your first day.</div>';
    return;
  }
  for (const date of dates) {
    const item = document.createElement('div');
    item.className = 'entry';
    const normalized = normalizeEntry(entries[date]);
    const total = normalized.spray + normalized.ventoline;
    const breakdown = [];
    if (normalized.spray > 0) breakdown.push(`Spray: ${normalized.spray}`);
    if (normalized.ventoline > 0) breakdown.push(`Ventoline: ${normalized.ventoline}`);
    if (normalized.preventive) breakdown.push('Exercise');
    const countText = breakdown.length > 0
      ? `${total} doses <span class="breakdown">(${breakdown.join(', ')})</span>`
      : `${total} doses`;
    item.innerHTML = `<div><div class="date">${date}</div><div class="count">${countText}</div></div>`;
    const preventiveBtn = document.createElement('button');
    preventiveBtn.textContent = normalized.preventive ? 'Exercise ✓' : 'Exercise';
    preventiveBtn.className = 'ghost';
    preventiveBtn.addEventListener('click', () => {
      const current = normalizeEntry(entries[date]);
      current.preventive = !current.preventive;
      entries[date] = current;
      saveEntries(entries);
      render(entries);
    });
    item.appendChild(preventiveBtn);
    const del = document.createElement('button');
    del.textContent = 'Delete';
    del.className = 'ghost';
    del.addEventListener('click', () => {
      delete entries[date];
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
  const entry = getEntryForDate(entries, dateKey);
  updateCount(entry[selectedMedicineType]);
}

let entries = loadEntries();
entries = migrateOldData(entries);
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
  updateCountForCurrentSelection();
});

saveBtn.addEventListener('click', () => {
  const dateKey = formatDate(usageDate.value);
  const entry = getEntryForDate(entries, dateKey);
  entry[selectedMedicineType] = Number(countEl.textContent) || 0;
  entries[dateKey] = entry;
  saveEntries(entries);
  localStorage.setItem(lastTypeKey, selectedMedicineType);
  render(entries);
  toast('Saved');
});

resetBtn.addEventListener('click', () => {
  const dateKey = formatDate(usageDate.value);
  entries[dateKey] = { spray: 0, ventoline: 0, preventive: false };
  updateCount(0);
  saveEntries(entries);
  render(entries);
  toast('Reset for day');
});

exportBtn.addEventListener('click', () => {
  const dates = Object.keys(entries).sort();
  const rows = [
    ['date', 'spray', 'ventoline', 'total', 'preventive'],
    ...dates.map((d) => {
      const normalized = normalizeEntry(entries[d]);
      const total = normalized.spray + normalized.ventoline;
      return [d, normalized.spray, normalized.ventoline, total, normalized.preventive ? 'true' : 'false'];
    })
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

  const dates = Object.keys(entries);
  if (dates.length === 0) {
    toast('No entries to sync');
    return;
  }

  try {
    syncToCloudBtn.disabled = true;
    syncToCloudBtn.textContent = 'Syncing...';

    let successCount = 0;
    let errorCount = 0;

    // Send each entry to the backend
    for (const date of dates) {
      const entry = normalizeEntry(entries[date]);

      try {
        const response = await fetch(`${backendUrl}/logs`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({
            log: {
              date: date,
              spray: entry.spray,
              ventoline: entry.ventoline,
              preventive: entry.preventive || false
            }
          })
        });

        if (response.ok) {
          successCount++;
        } else {
          errorCount++;
          console.error(`Failed to sync entry for ${date}:`, await response.text());
        }
      } catch (error) {
        errorCount++;
        console.error(`Network error syncing entry for ${date}:`, error);
      }
    }

    // Show result
    if (errorCount === 0) {
      toast(`✓ Synced ${successCount} ${successCount === 1 ? 'entry' : 'entries'} to cloud`);
    } else if (successCount > 0) {
      toast(`⚠ Synced ${successCount} entries, ${errorCount} failed`);
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

    const response = await fetch(`${backendUrl}/logs`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Token expired. Please reconnect.');
      }
      throw new Error('Failed to fetch logs from cloud');
    }

    const data = await response.json();
    const cloudLogs = data.logs;

    if (cloudLogs.length === 0) {
      toast('No data on cloud yet');
      return;
    }

    // Merge with local entries
    let newEntries = 0;
    let updatedEntries = 0;

    for (const cloudLog of cloudLogs) {
      const { date, spray, ventoline, preventive } = cloudLog;
      const localEntry = entries[date];

      if (!localEntry) {
        // New entry from cloud
        entries[date] = { spray, ventoline, preventive: preventive || false };
        newEntries++;
      } else {
        // Entry exists locally
        // Strategy: Prefer cloud (has timestamp, is persistent)
        const localSpray = localEntry.spray || 0;
        const localVentoline = localEntry.ventoline || 0;

        if (localSpray !== spray || localVentoline !== ventoline || (localEntry.preventive || false) !== (preventive || false)) {
          entries[date] = { spray, ventoline, preventive: preventive || false };
          updatedEntries++;
        }
      }
    }

    if (newEntries === 0 && updatedEntries === 0) {
      toast('Already in sync');
    } else {
      saveEntries(entries);
      render(entries);

      const parts = [];
      if (newEntries > 0) parts.push(`${newEntries} new`);
      if (updatedEntries > 0) parts.push(`${updatedEntries} updated`);
      toast(`✓ Synced ${parts.join(', ')} from cloud`);
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
