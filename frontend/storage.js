import { storageKey, tokenKey, RITALIN_KEY } from './config.js';

export function loadEntries() {
  const raw = localStorage.getItem(storageKey);
  try {
    return raw ? JSON.parse(raw) : [];
  } catch (_) {
    return [];
  }
}

export function saveEntries(entries) {
  localStorage.setItem(storageKey, JSON.stringify(entries));
}

export function loadRitalinEntries() {
  const raw = localStorage.getItem(RITALIN_KEY);
  try {
    return raw ? JSON.parse(raw) : [];
  } catch (_) {
    return [];
  }
}

export function saveRitalinEntries(entries) {
  localStorage.setItem(RITALIN_KEY, JSON.stringify(entries));
}

export function getToken() {
  return localStorage.getItem(tokenKey);
}

export function setToken(token) {
  if (!token) {
    throw new Error('Token cannot be empty');
  }
  localStorage.setItem(tokenKey, token);
}

export function clearToken() {
  localStorage.removeItem(tokenKey);
}

export function hasToken() {
  const token = getToken();
  return token !== null && token !== '';
}
