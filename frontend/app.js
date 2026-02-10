// Backend Configuration
const backendUrl = window.location.hostname === 'localhost'
  ? 'http://localhost:5000'
  : 'https://asthma.fredrikmeyer.net';

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
const entriesEl = document.getElementById('entries');
const toastEl = document.getElementById('toast');
const medicineTypeButtons = document.querySelectorAll('.medicine-type');

const today = new Date();
usageDate.valueAsDate = today;

let selectedMedicineType = localStorage.getItem(lastTypeKey) || 'ventoline';

function normalizeEntry(value) {
  if (typeof value === 'number') {
    // Old format: just a number → treat as ventoline (not spray)
    return { spray: 0, ventoline: value };
  }
  return { spray: value.spray || 0, ventoline: value.ventoline || 0 };
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
    const countText = breakdown.length > 0
      ? `${total} doses <span class="breakdown">(${breakdown.join(', ')})</span>`
      : `${total} doses`;
    item.innerHTML = `<div><div class="date">${date}</div><div class="count">${countText}</div></div>`;
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
  entries[dateKey] = { spray: 0, ventoline: 0 };
  updateCount(0);
  saveEntries(entries);
  render(entries);
  toast('Reset for day');
});

exportBtn.addEventListener('click', () => {
  const dates = Object.keys(entries).sort();
  const rows = [
    ['date', 'spray', 'ventoline', 'total'],
    ...dates.map((d) => {
      const normalized = normalizeEntry(entries[d]);
      const total = normalized.spray + normalized.ventoline;
      return [d, normalized.spray, normalized.ventoline, total];
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

const BASE_PATH = '/codex/';

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    const swUrl = new URL('service-worker.js', new URL(BASE_PATH, window.location.origin));
    navigator.serviceWorker.register(swUrl, { scope: BASE_PATH }).catch(() => {});
  });
}

render(entries);
