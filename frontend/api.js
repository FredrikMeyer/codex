import { backendUrl } from './config.js';

export async function apiGenerateCode() {
  const response = await fetch(`${backendUrl}/generate-code`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  });
  if (!response.ok) {
    throw new Error('Failed to generate code');
  }
  return response.json();
}

export async function apiGenerateToken(code) {
  const response = await fetch(`${backendUrl}/generate-token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code })
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error || 'Invalid code');
  }
  return response.json();
}

export async function apiFetchCode(token) {
  const response = await fetch(`${backendUrl}/code`, {
    method: 'GET',
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!response.ok) {
    if (response.status === 401) {
      throw Object.assign(new Error('Session expired. Please reconnect.'), { status: 401 });
    }
    throw new Error('Failed to retrieve code');
  }
  return response.json();
}

export async function apiUploadEvents(token, events) {
  const cleanEvents = events.map(({ received_at: _received_at, ...eventData }) => eventData);
  const response = await fetch(`${backendUrl}/events/batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ events: cleanEvents })
  });
  if (!response.ok) {
    throw new Error(`Failed to upload events: ${response.status}`);
  }
  const { saved } = await response.json();
  return { successCount: saved, errorCount: 0 };
}

export async function apiDownloadEvents(token) {
  const response = await fetch(`${backendUrl}/events`, {
    method: 'GET',
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Token expired. Please reconnect.');
    }
    throw new Error('Failed to fetch events from cloud');
  }
  return response.json();
}

export async function apiUploadRitalinEvents(token, events) {
  const cleanEvents = events.map(({ received_at: _received_at, ...eventData }) => eventData);
  const response = await fetch(`${backendUrl}/ritalin-events/batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ events: cleanEvents })
  });
  if (!response.ok) {
    throw new Error(`Failed to upload ritalin events: ${response.status}`);
  }
  const { saved } = await response.json();
  return { successCount: saved, errorCount: 0 };
}

export async function apiDeleteEvents(token, ids) {
  const response = await fetch(`${backendUrl}/events`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ ids })
  });
  if (!response.ok) {
    throw new Error(`Failed to delete events: ${response.status}`);
  }
}

export async function apiDeleteRitalinEvents(token, ids) {
  const response = await fetch(`${backendUrl}/ritalin-events`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ ids })
  });
  if (!response.ok) {
    throw new Error(`Failed to delete ritalin events: ${response.status}`);
  }
}

export async function apiDownloadRitalinEvents(token) {
  const response = await fetch(`${backendUrl}/ritalin-events`, {
    method: 'GET',
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Token expired. Please reconnect.');
    }
    throw new Error('Failed to fetch events from cloud');
  }
  return response.json();
}
