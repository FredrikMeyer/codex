import { updateEntry } from './tracker.js';
import { saveEntries, saveRitalinEntries } from './storage.js';
import { toast } from './ui.js';

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

let _getAsthmaEntries;
let _setAsthmaEntries;
let _onAsthmaSaved;

export function initAsthmaEditDialog(getEntries, setEntries, onSaved) {
  _getAsthmaEntries = getEntries;
  _setAsthmaEntries = setEntries;
  _onAsthmaSaved = onSaved;

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
    const updated = {
      ...editingAsthmaEntry,
      date: newDate,
      timestamp: Temporal.PlainDateTime.from(`${newDate}T${newTime}:00`)
        .toZonedDateTime(Temporal.Now.timeZoneId())
        .toInstant()
        .toString(),
      type: editingAsthmaType,
      count: newCount,
      preventive: editingAsthmaPreventive
    };
    const newEntries = updateEntry(_getAsthmaEntries(), updated);
    _setAsthmaEntries(newEntries);
    saveEntries(newEntries);
    _onAsthmaSaved(newEntries);
    asthmaEditDialog.close();
    toast('Entry updated');
  });

  editAsthmaCancelBtn.addEventListener('click', () => asthmaEditDialog.close());
}

export function openAsthmaEditDialog(entry) {
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

// --- Ritalin edit dialog ---
const ritalinEditDialog = document.getElementById('ritalin-edit-dialog');
const editRitalinDateEl = document.getElementById('edit-ritalin-date');
const editRitalinTimeEl = document.getElementById('edit-ritalin-time');
const editRitalinCountEl = document.getElementById('edit-ritalin-count');
const editRitalinSaveBtn = document.getElementById('edit-ritalin-save');
const editRitalinCancelBtn = document.getElementById('edit-ritalin-cancel');

let editingRitalinEntry = null;

let _getRitalinEntries;
let _setRitalinEntries;
let _onRitalinSaved;

export function initRitalinEditDialog(getEntries, setEntries, onSaved) {
  _getRitalinEntries = getEntries;
  _setRitalinEntries = setEntries;
  _onRitalinSaved = onSaved;

  editRitalinSaveBtn.addEventListener('click', () => {
    const newDate = editRitalinDateEl.value;
    const newTime = editRitalinTimeEl.value || '12:00';
    const newCount = Number(editRitalinCountEl.value) || 1;
    const updated = {
      ...editingRitalinEntry,
      date: newDate,
      timestamp: Temporal.PlainDateTime.from(`${newDate}T${newTime}:00`)
        .toZonedDateTime(Temporal.Now.timeZoneId())
        .toInstant()
        .toString(),
      count: newCount
    };
    const newEntries = updateEntry(_getRitalinEntries(), updated);
    _setRitalinEntries(newEntries);
    saveRitalinEntries(newEntries);
    _onRitalinSaved(newEntries);
    ritalinEditDialog.close();
    toast('Entry updated');
  });

  editRitalinCancelBtn.addEventListener('click', () => ritalinEditDialog.close());
}

export function openRitalinEditDialog(entry) {
  editingRitalinEntry = entry;
  const localTime = Temporal.Instant.from(entry.timestamp)
    .toZonedDateTimeISO(Temporal.Now.timeZoneId())
    .toPlainTime();
  editRitalinDateEl.value = entry.date;
  editRitalinTimeEl.value = localTime.toString().slice(0, 5);
  editRitalinCountEl.value = entry.count;
  ritalinEditDialog.showModal();
}
