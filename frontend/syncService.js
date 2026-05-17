import { smartMerge } from './tracker.js';
import { saveEntries, saveRitalinEntries, getToken, setToken, clearToken, hasToken } from './storage.js';
import { apiGenerateCode, apiGenerateToken, apiFetchCode, apiUploadEvents, apiDownloadEvents, apiUploadRitalinEvents, apiDownloadRitalinEvents, apiDeleteEvents, apiDeleteRitalinEvents } from './api.js';
import { toast, updateSyncStatus as renderSyncStatus } from './ui.js';

// DOM elements
const syncStatusText = document.getElementById('sync-status-text');
const syncStatusDot = document.querySelector('.status-dot');
const syncSetupSection = document.getElementById('sync-setup');
const syncConfiguredSection = document.getElementById('sync-configured');
const generateCodeBtn = /** @type {HTMLButtonElement} */ (document.getElementById('generate-code'));
const generatedCodeDisplay = /** @type {HTMLElement} */ (document.getElementById('generated-code'));
const codeInput = /** @type {HTMLInputElement} */ (document.getElementById('code-input'));
const completeSetupBtn = /** @type {HTMLButtonElement} */ (document.getElementById('complete-setup'));
const disconnectBtn = /** @type {HTMLButtonElement} */ (document.getElementById('disconnect-sync'));
const clearLocalDataBtn = /** @type {HTMLButtonElement} */ (document.getElementById('clear-local-data'));
const tokenInput = /** @type {HTMLInputElement} */ (document.getElementById('token-input'));
const enterTokenBtn = /** @type {HTMLButtonElement} */ (document.getElementById('enter-token'));
const showCodeBtn = /** @type {HTMLButtonElement} */ (document.getElementById('show-code'));
const syncFromCloudBtn = /** @type {HTMLButtonElement} */ (document.getElementById('sync-from-cloud'));
const syncToCloudBtn = /** @type {HTMLButtonElement} */ (document.getElementById('sync-to-cloud'));
const syncSetupCollapse = /** @type {HTMLDetailsElement | null} */ (document.querySelector('.sync-setup-collapse'));
if (syncSetupCollapse) {
  const mobile = window.matchMedia('(max-width: 600px)');
  const applyCollapse = () => { syncSetupCollapse.open = !mobile.matches; };
  applyCollapse();
  mobile.addEventListener('change', applyCollapse);
}

/** @type {(() => UsageEvent[]) | undefined} */
let _getEntries;
/** @type {((entries: UsageEvent[]) => void) | undefined} */
let _setEntries;
/** @type {(() => RitalinEvent[]) | undefined} */
let _getRitalinEntries;
/** @type {((entries: RitalinEvent[]) => void) | undefined} */
let _setRitalinEntries;
/** @type {((entries: UsageEvent[]) => void) | undefined} */
let _onSynced;
/** @type {((entries: RitalinEvent[]) => void) | undefined} */
let _onRitalinSynced;
/** @type {(() => void) | undefined} */
let _onLocalDataCleared;

/** @returns {void} */
function updateSyncStatus() {
  renderSyncStatus(hasToken(), {
    syncStatusText, syncStatusDot, syncSetupSection, syncConfiguredSection,
    syncFromCloudBtn, syncToCloudBtn
  });
}

/** @returns {Promise<void>} */
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

/** @returns {Promise<void>} */
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

    codeInput.value = '';
    generatedCodeDisplay.textContent = '';
    generatedCodeDisplay.classList.remove('show');

    updateSyncStatus();
    toast('Cloud sync connected!');
  } catch (error) {
    toast(/** @type {Error} */ (error).message || 'Failed to connect. Please try again.');
    console.error('Complete setup error:', error);
  } finally {
    completeSetupBtn.disabled = false;
    completeSetupBtn.textContent = 'Complete Setup';
  }
}

/** @returns {void} */
function clearLocalData() {
  if (confirm('Clear all local data on this device? Your cloud data is unaffected. You can sync it back afterwards.')) {
    if (_setEntries) _setEntries([]);
    saveEntries([]);
    if (_onLocalDataCleared) _onLocalDataCleared();
    toast('Local data cleared');
  }
}

/** @returns {void} */
function disconnectSync() {
  if (confirm('Are you sure you want to disconnect cloud sync? Your local data will remain safe.')) {
    clearToken();
    updateSyncStatus();
    toast('Cloud sync disconnected');
  }
}

/** @returns {Promise<void>} */
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
    if (/** @type {any} */ (error).status === 401) {
      toast('Session expired. Please reconnect.');
      clearToken();
      updateSyncStatus();
      return;
    }
    toast('Failed to retrieve code. Check your connection.');
    console.error('Show code error:', error);
  }
}

/**
 * @param {number} asthma
 * @param {number} ritalin
 * @returns {string}
 */
function describeCombinedCount(asthma, ritalin) {
  const parts = [];
  if (asthma > 0) parts.push(`${asthma} asthma`);
  if (ritalin > 0) parts.push(`${ritalin} ritalin`);
  const noun = (asthma + ritalin) === 1 ? 'event' : 'events';
  return `${parts.join(' + ')} ${noun}`;
}

/** @returns {Promise<void>} */
async function syncToCloud() {
  const token = getToken();
  if (!token) {
    toast('Please set up cloud sync first');
    return;
  }

  const asthmaEntries = _getEntries ? _getEntries() : [];
  const ritalinEntries = _getRitalinEntries ? _getRitalinEntries() : [];

  if (asthmaEntries.length === 0 && ritalinEntries.length === 0) {
    toast('No entries to sync');
    return;
  }

  try {
    syncToCloudBtn.disabled = true;
    syncToCloudBtn.textContent = 'Syncing...';

    const asthmaUpload = asthmaEntries.length > 0
      ? apiUploadEvents(token, asthmaEntries)
      : Promise.resolve({ successCount: 0, errorCount: 0 });
    const ritalinUpload = ritalinEntries.length > 0
      ? apiUploadRitalinEvents(token, ritalinEntries)
      : Promise.resolve({ successCount: 0, errorCount: 0 });

    const [asthmaResult, ritalinResult] = await Promise.all([asthmaUpload, ritalinUpload]);

    const totalErrors = asthmaResult.errorCount + ritalinResult.errorCount;
    const totalSuccess = asthmaResult.successCount + ritalinResult.successCount;

    if (totalErrors === 0) {
      toast(`✓ Synced ${describeCombinedCount(asthmaResult.successCount, ritalinResult.successCount)} to cloud`);
    } else if (totalSuccess > 0) {
      toast(`⚠ Synced ${totalSuccess} events, ${totalErrors} failed`);
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

/** @returns {Promise<void>} */
async function syncFromCloud() {
  const token = getToken();
  if (!token) {
    toast('Please set up cloud sync first');
    return;
  }

  try {
    syncFromCloudBtn.disabled = true;
    syncFromCloudBtn.textContent = 'Syncing...';

    const [asthmaData, ritalinData] = await Promise.all([
      apiDownloadEvents(token),
      apiDownloadRitalinEvents(token)
    ]);

    const localAsthma = _getEntries ? _getEntries() : [];
    const { entries: mergedAsthma, newCount: newAsthmaCount, idUpdates } =
      smartMerge(localAsthma, asthmaData.events);

    if (newAsthmaCount > 0 || idUpdates > 0) {
      if (_setEntries) _setEntries(mergedAsthma);
      saveEntries(mergedAsthma);
      if (_onSynced) _onSynced(mergedAsthma);
    }

    const localRitalin = _getRitalinEntries ? _getRitalinEntries() : [];
    const localRitalinIds = new Set(localRitalin.map((e) => e.id));
    const newRitalinEvents = ritalinData.events.filter((e) => !localRitalinIds.has(e.id));

    if (newRitalinEvents.length > 0) {
      const mergedRitalin = [...localRitalin, ...newRitalinEvents];
      if (_setRitalinEntries) _setRitalinEntries(mergedRitalin);
      saveRitalinEntries(mergedRitalin);
      if (_onRitalinSynced) _onRitalinSynced(mergedRitalin);
    }

    if (newAsthmaCount === 0 && newRitalinEvents.length === 0) {
      toast('Already in sync');
    } else {
      toast(`✓ Synced ${describeCombinedCount(newAsthmaCount, newRitalinEvents.length)} from cloud`);
    }
  } catch (error) {
    toast(/** @type {Error} */ (error).message || 'Sync failed. Check your connection.');
    console.error('Sync from cloud error:', error);
  } finally {
    syncFromCloudBtn.disabled = false;
    syncFromCloudBtn.textContent = 'Sync from Cloud';
  }
}

/**
 * @param {string[]} ids
 * @returns {Promise<void>}
 */
export async function deleteEventsFromCloud(ids) {
  const token = getToken();
  if (!token || ids.length === 0) return;
  try {
    await apiDeleteEvents(token, ids);
  } catch (error) {
    toast('Deleted locally, but cloud delete failed. Sync may restore this event.');
    console.error('Failed to delete events from cloud:', { ids, error });
  }
}

/**
 * @param {string[]} ids
 * @returns {Promise<void>}
 */
export async function deleteRitalinEventsFromCloud(ids) {
  const token = getToken();
  if (!token || ids.length === 0) return;
  try {
    await apiDeleteRitalinEvents(token, ids);
  } catch (error) {
    toast('Deleted locally, but cloud delete failed. Sync may restore this event.');
    console.error('Failed to delete ritalin events from cloud:', { ids, error });
  }
}

/**
 * @typedef {Object} SyncServiceOptions
 * @property {() => UsageEvent[]} getEntries
 * @property {(entries: UsageEvent[]) => void} setEntries
 * @property {() => RitalinEvent[]} getRitalinEntries
 * @property {(entries: RitalinEvent[]) => void} setRitalinEntries
 * @property {(entries: UsageEvent[]) => void} onSynced
 * @property {(entries: RitalinEvent[]) => void} onRitalinSynced
 * @property {() => void} onLocalDataCleared
 */

/**
 * @param {SyncServiceOptions} options
 * @returns {void}
 */
export function initSyncService({ getEntries, setEntries, getRitalinEntries, setRitalinEntries, onSynced, onRitalinSynced, onLocalDataCleared }) {
  _getEntries = getEntries;
  _setEntries = setEntries;
  _getRitalinEntries = getRitalinEntries;
  _setRitalinEntries = setRitalinEntries;
  _onSynced = onSynced;
  _onRitalinSynced = onRitalinSynced;
  _onLocalDataCleared = onLocalDataCleared;

  generateCodeBtn.addEventListener('click', generateCode);
  completeSetupBtn.addEventListener('click', completeSetup);
  enterTokenBtn.addEventListener('click', () => {
    const token = tokenInput.value.trim();
    if (!token) {
      toast('Please paste a token');
      return;
    }
    setToken(token);
    tokenInput.value = '';
    updateSyncStatus();
    toast('Cloud sync connected!');
  });
  disconnectBtn.addEventListener('click', disconnectSync);
  clearLocalDataBtn.addEventListener('click', clearLocalData);
  showCodeBtn.addEventListener('click', showCode);
  syncFromCloudBtn.addEventListener('click', syncFromCloud);
  syncToCloudBtn.addEventListener('click', syncToCloud);

  codeInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      completeSetup();
    }
  });

  updateSyncStatus();
}
