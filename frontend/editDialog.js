import { updateEntry } from './tracker.js';
import { saveEntries, saveRitalinEntries } from './storage.js';
import { toast } from './ui.js';

// --- Asthma edit dialog ---
const asthmaEditDialog = /** @type {HTMLDialogElement} */ (document.getElementById('asthma-edit-dialog'));
const editAsthmaDateEl = /** @type {HTMLInputElement} */ (document.getElementById('edit-asthma-date'));
const editAsthmaTimeEl = /** @type {HTMLInputElement} */ (document.getElementById('edit-asthma-time'));
const editAsthmaCountEl = /** @type {HTMLInputElement} */ (document.getElementById('edit-asthma-count'));
const editAsthmaPreventiveBtn = /** @type {HTMLButtonElement} */ (document.getElementById('edit-asthma-preventive'));
const editAsthmaTypeButtons = /** @type {NodeListOf<HTMLButtonElement>} */ (document.querySelectorAll('.edit-asthma-type'));
const editAsthmaSaveBtn = /** @type {HTMLButtonElement} */ (document.getElementById('edit-asthma-save'));
const editAsthmaCancelBtn = /** @type {HTMLButtonElement} */ (document.getElementById('edit-asthma-cancel'));

/** @type {UsageEvent | null} */
let editingAsthmaEntry = null;
let editingAsthmaPreventive = false;
/** @type {MedicineType} */
let editingAsthmaType = 'ventoline';

/** @type {(() => UsageEvent[]) | undefined} */
let _getAsthmaEntries;
/** @type {((entries: UsageEvent[]) => void) | undefined} */
let _setAsthmaEntries;
/** @type {((entries: UsageEvent[]) => void) | undefined} */
let _onAsthmaSaved;

/**
 * @param {() => UsageEvent[]} getEntries
 * @param {(entries: UsageEvent[]) => void} setEntries
 * @param {(entries: UsageEvent[]) => void} onSaved
 * @returns {void}
 */
export function initAsthmaEditDialog(getEntries, setEntries, onSaved) {
  _getAsthmaEntries = getEntries;
  _setAsthmaEntries = setEntries;
  _onAsthmaSaved = onSaved;

  editAsthmaTypeButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      editingAsthmaType = /** @type {MedicineType} */ (btn.dataset['type'] || 'ventoline');
      editAsthmaTypeButtons.forEach((b) => b.classList.toggle('active', b === btn));
    });
  });

  editAsthmaPreventiveBtn.addEventListener('click', () => {
    editingAsthmaPreventive = !editingAsthmaPreventive;
    editAsthmaPreventiveBtn.classList.toggle('active', editingAsthmaPreventive);
  });

  editAsthmaSaveBtn.addEventListener('click', () => {
    if (!editingAsthmaEntry || !_getAsthmaEntries || !_setAsthmaEntries || !_onAsthmaSaved) return;
    const newDate = editAsthmaDateEl.value;
    const newTime = editAsthmaTimeEl.value || '12:00';
    const newCount = Number(editAsthmaCountEl.value) || 1;
    /** @type {UsageEvent} */
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

/**
 * @param {UsageEvent} entry
 * @returns {void}
 */
export function openAsthmaEditDialog(entry) {
  editingAsthmaEntry = entry;
  editingAsthmaPreventive = entry.preventive;
  editingAsthmaType = entry.type;
  const localTime = Temporal.Instant.from(entry.timestamp)
    .toZonedDateTimeISO(Temporal.Now.timeZoneId())
    .toPlainTime();
  editAsthmaDateEl.value = entry.date;
  editAsthmaTimeEl.value = localTime.toString().slice(0, 5);
  editAsthmaCountEl.value = String(entry.count);
  editAsthmaTypeButtons.forEach((btn) => btn.classList.toggle('active', btn.dataset['type'] === editingAsthmaType));
  editAsthmaPreventiveBtn.classList.toggle('active', editingAsthmaPreventive);
  asthmaEditDialog.showModal();
}

// --- Ritalin edit dialog ---
const ritalinEditDialog = /** @type {HTMLDialogElement} */ (document.getElementById('ritalin-edit-dialog'));
const editRitalinDateEl = /** @type {HTMLInputElement} */ (document.getElementById('edit-ritalin-date'));
const editRitalinTimeEl = /** @type {HTMLInputElement} */ (document.getElementById('edit-ritalin-time'));
const editRitalinCountEl = /** @type {HTMLInputElement} */ (document.getElementById('edit-ritalin-count'));
const editRitalinSaveBtn = /** @type {HTMLButtonElement} */ (document.getElementById('edit-ritalin-save'));
const editRitalinCancelBtn = /** @type {HTMLButtonElement} */ (document.getElementById('edit-ritalin-cancel'));

/** @type {RitalinEvent | null} */
let editingRitalinEntry = null;

/** @type {(() => RitalinEvent[]) | undefined} */
let _getRitalinEntries;
/** @type {((entries: RitalinEvent[]) => void) | undefined} */
let _setRitalinEntries;
/** @type {((entries: RitalinEvent[]) => void) | undefined} */
let _onRitalinSaved;

/**
 * @param {() => RitalinEvent[]} getEntries
 * @param {(entries: RitalinEvent[]) => void} setEntries
 * @param {(entries: RitalinEvent[]) => void} onSaved
 * @returns {void}
 */
export function initRitalinEditDialog(getEntries, setEntries, onSaved) {
  _getRitalinEntries = getEntries;
  _setRitalinEntries = setEntries;
  _onRitalinSaved = onSaved;

  editRitalinSaveBtn.addEventListener('click', () => {
    if (!editingRitalinEntry || !_getRitalinEntries || !_setRitalinEntries || !_onRitalinSaved) return;
    const newDate = editRitalinDateEl.value;
    const newTime = editRitalinTimeEl.value || '12:00';
    const newCount = Number(editRitalinCountEl.value) || 1;
    /** @type {RitalinEvent} */
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

/**
 * @param {RitalinEvent} entry
 * @returns {void}
 */
export function openRitalinEditDialog(entry) {
  editingRitalinEntry = entry;
  const localTime = Temporal.Instant.from(entry.timestamp)
    .toZonedDateTimeISO(Temporal.Now.timeZoneId())
    .toPlainTime();
  editRitalinDateEl.value = entry.date;
  editRitalinTimeEl.value = localTime.toString().slice(0, 5);
  editRitalinCountEl.value = String(entry.count);
  ritalinEditDialog.showModal();
}
