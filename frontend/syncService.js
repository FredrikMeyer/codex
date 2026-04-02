import { smartMerge } from './tracker.js';
import { saveEntries, saveRitalinEntries, getToken, setToken, clearToken, hasToken } from './storage.js';
import { apiGenerateCode, apiGenerateToken, apiFetchCode, apiUploadEvents, apiDownloadEvents, apiUploadRitalinEvents, apiDownloadRitalinEvents, apiDeleteEvents, apiDeleteRitalinEvents } from './api.js';
import { toast, updateSyncStatus as renderSyncStatus } from './ui.js';

// DOM elements
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
const syncFromCloudBtn = document.getElementById('sync-from-cloud');
const syncToCloudBtn = document.getElementById('sync-to-cloud');
const ritalinSyncFromCloudBtn = document.getElementById('ritalin-sync-from-cloud');
const ritalinSyncToCloudBtn = document.getElementById('ritalin-sync-to-cloud');

let _getEntries;
let _setEntries;
let _getRitalinEntries;
let _setRitalinEntries;
let _onSynced;
let _onRitalinSynced;
let _onLocalDataCleared;

function updateSyncStatus() {
  renderSyncStatus(hasToken(), {
    syncStatusText, syncStatusDot, syncSetupSection, syncConfiguredSection,
    syncFromCloudBtn, syncToCloudBtn, ritalinSyncFromCloudBtn, ritalinSyncToCloudBtn
  });
}

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
    toast(error.message || 'Failed to connect. Please try again.');
    console.error('Complete setup error:', error);
  } finally {
    completeSetupBtn.disabled = false;
    completeSetupBtn.textContent = 'Complete Setup';
  }
}

function clearLocalData() {
  if (confirm('Clear all local data on this device? Your cloud data is unaffected. You can sync it back afterwards.')) {
    _setEntries([]);
    saveEntries([]);
    _onLocalDataCleared();
    toast('Local data cleared');
  }
}

function disconnectSync() {
  if (confirm('Are you sure you want to disconnect cloud sync? Your local data will remain safe.')) {
    clearToken();
    updateSyncStatus();
    toast('Cloud sync disconnected');
  }
}

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

async function syncToCloud() {
  const token = getToken();
  if (!token) {
    toast('Please set up cloud sync first');
    return;
  }

  const entries = _getEntries();
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

    const { entries: merged, newCount, idUpdates } = smartMerge(_getEntries(), cloudEvents);

    if (newCount === 0 && idUpdates === 0) {
      toast('Already in sync');
      return;
    }

    _setEntries(merged);
    saveEntries(merged);
    _onSynced(merged);

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

async function syncRitalinToCloud() {
  const token = getToken();
  if (!token) { toast('Please set up cloud sync first'); return; }
  const ritalinEntries = _getRitalinEntries();
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

    const ritalinEntries = _getRitalinEntries();
    const localIds = new Set(ritalinEntries.map((e) => e.id));
    const newEvents = cloudEvents.filter((e) => !localIds.has(e.id));

    if (newEvents.length === 0) { toast('Already in sync'); return; }

    const merged = [...ritalinEntries, ...newEvents];
    _setRitalinEntries(merged);
    saveRitalinEntries(merged);
    _onRitalinSynced(merged);
    toast(`✓ Synced ${newEvents.length} new ${newEvents.length === 1 ? 'event' : 'events'} from cloud`);
  } catch (error) {
    toast(error.message || 'Sync failed. Check your connection.');
  } finally {
    ritalinSyncFromCloudBtn.disabled = false;
    ritalinSyncFromCloudBtn.textContent = 'Sync from Cloud';
  }
}

export async function deleteEventsFromCloud(ids) {
  const token = getToken();
  if (!token || ids.length === 0) return;
  try {
    await apiDeleteEvents(token, ids);
  } catch (error) {
    console.error('Failed to delete events from cloud:', error);
  }
}

export async function deleteRitalinEventsFromCloud(ids) {
  const token = getToken();
  if (!token || ids.length === 0) return;
  try {
    await apiDeleteRitalinEvents(token, ids);
  } catch (error) {
    console.error('Failed to delete ritalin events from cloud:', error);
  }
}

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
  disconnectBtn.addEventListener('click', disconnectSync);
  clearLocalDataBtn.addEventListener('click', clearLocalData);
  showCodeBtn.addEventListener('click', showCode);
  syncFromCloudBtn.addEventListener('click', syncFromCloud);
  syncToCloudBtn.addEventListener('click', syncToCloud);
  ritalinSyncToCloudBtn.addEventListener('click', syncRitalinToCloud);
  ritalinSyncFromCloudBtn.addEventListener('click', syncRitalinFromCloud);

  codeInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      completeSetup();
    }
  });

  updateSyncStatus();
}
