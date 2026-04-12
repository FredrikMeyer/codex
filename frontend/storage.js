import { storageKey, tokenKey, RITALIN_KEY } from './config.js';

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
}

/** @returns {void} */
export function clearToken() {
  localStorage.removeItem(tokenKey);
}

/** @returns {boolean} */
export function hasToken() {
  const token = getToken();
  return token !== null && token !== '';
}
