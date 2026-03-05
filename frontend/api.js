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
  let successCount = 0;
  let errorCount = 0;
  for (const event of events) {
    try {
      const response = await fetch(`${backendUrl}/events`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ event })
      });
      if (response.ok) {
        successCount++;
      } else {
        errorCount++;
        console.error(`Failed to sync event ${event.id}:`, await response.text());
      }
    } catch (error) {
      errorCount++;
      console.error(`Network error syncing event ${event.id}:`, error);
    }
  }
  return { successCount, errorCount };
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
  let successCount = 0;
  let errorCount = 0;
  for (const event of events) {
    try {
      const response = await fetch(`${backendUrl}/ritalin-events`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ event })
      });
      if (response.ok) {
        successCount++;
      } else {
        errorCount++;
      }
    } catch (_) {
      errorCount++;
    }
  }
  return { successCount, errorCount };
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
