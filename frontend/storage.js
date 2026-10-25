import { storageKey, tokenKey, RITALIN_KEY, ASTHMA_SYNCED_IDS_KEY, RITALIN_SYNCED_IDS_KEY } from './config.js';

/** @returns {UsageEvent[]} */
export function loadEntries() {
  const raw = localStorage.getItem(storageKey);
  try {
    return raw ? JSON.parse(raw) : [];
  } catch (_) {
    return [];
  }
}

/** @param {UsageEvent[]} entries @returns {void} */
export function saveEntries(entries) {
  localStorage.setItem(storageKey, JSON.stringify(entries));
}

/** @returns {RitalinEvent[]} */
export function loadRitalinEntries() {
  const raw = localStorage.getItem(RITALIN_KEY);
  try {
    return raw ? JSON.parse(raw) : [];
  } catch (_) {
    return [];
  }
}

/** @param {RitalinEvent[]} entries @returns {void} */
export function saveRitalinEntries(entries) {
  localStorage.setItem(RITALIN_KEY, JSON.stringify(entries));
}

/** @returns {string | null} */
export function getToken() {
  return localStorage.getItem(tokenKey);
}

/** @param {string} token @returns {void} */
export function setToken(token) {
  if (!token) {
    throw new Error('Token cannot be empty');
  }
  localStorage.setItem(tokenKey, token);
  clearSyncedIds();
}

/** @returns {void} */
export function clearToken() {
  localStorage.removeItem(tokenKey);
  clearSyncedIds();
}

/** @param {string} key @returns {Set<string>} */
function loadIdSet(key) {
  try {
    return new Set(JSON.parse(localStorage.getItem(key) || '[]'));
  } catch (_) {
    return new Set();
  }
}

/** @returns {Set<string>} */
export function loadAsthmaSyncedIds() {
  return loadIdSet(ASTHMA_SYNCED_IDS_KEY);
}

/** @param {Set<string>} ids @returns {void} */
export function saveAsthmaSyncedIds(ids) {
  localStorage.setItem(ASTHMA_SYNCED_IDS_KEY, JSON.stringify([...ids]));
}

/** @returns {Set<string>} */
export function loadRitalinSyncedIds() {
  return loadIdSet(RITALIN_SYNCED_IDS_KEY);
}

/** @param {Set<string>} ids @returns {void} */
export function saveRitalinSyncedIds(ids) {
  localStorage.setItem(RITALIN_SYNCED_IDS_KEY, JSON.stringify([...ids]));
}

/** Synced IDs belong to one cloud account, so they are reset when the token changes. @returns {void} */
function clearSyncedIds() {
  localStorage.removeItem(ASTHMA_SYNCED_IDS_KEY);
  localStorage.removeItem(RITALIN_SYNCED_IDS_KEY);
}

/** @returns {boolean} */
export function hasToken() {
  const token = getToken();
  return token !== null && token !== '';
}
