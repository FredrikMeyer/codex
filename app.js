const storageKey = 'asthma-usage-entries';
const usageDate = document.getElementById('usage-date');
const countEl = document.getElementById('count');
const incBtn = document.getElementById('increment');
const decBtn = document.getElementById('decrement');
const saveBtn = document.getElementById('save');
const resetBtn = document.getElementById('reset-day');
const exportBtn = document.getElementById('export');
const entriesEl = document.getElementById('entries');
const toastEl = document.getElementById('toast');

const today = new Date();
usageDate.valueAsDate = today;

function loadEntries() {
  const raw = localStorage.getItem(storageKey);
  try {
    return raw ? JSON.parse(raw) : {};
  } catch (_) {
    return {};
  }
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
    item.innerHTML = `<div><div class="date">${date}</div><div class="count">${entries[date]} doses</div></div>`;
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

const entries = loadEntries();
const defaultDate = formatDate(usageDate.value);
updateCount(entries[defaultDate] || 0);

incBtn.addEventListener('click', () => {
  const current = Number(countEl.textContent) || 0;
  updateCount(current + 1);
});

decBtn.addEventListener('click', () => {
  const current = Number(countEl.textContent) || 0;
  updateCount(Math.max(0, current - 1));
});

usageDate.addEventListener('change', (e) => {
  const dateKey = formatDate(e.target.value);
  updateCount(entries[dateKey] || 0);
});

saveBtn.addEventListener('click', () => {
  const dateKey = formatDate(usageDate.value);
  entries[dateKey] = Number(countEl.textContent) || 0;
  saveEntries(entries);
  render(entries);
  toast('Saved');
});

resetBtn.addEventListener('click', () => {
  const dateKey = formatDate(usageDate.value);
  entries[dateKey] = 0;
  updateCount(0);
  saveEntries(entries);
  render(entries);
  toast('Reset for day');
});

exportBtn.addEventListener('click', () => {
  const dates = Object.keys(entries).sort();
  const rows = [['date', 'doses'], ...dates.map((d) => [d, entries[d]])];
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
