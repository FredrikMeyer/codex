import { backendUrl } from './config.js';

/**
 * @typedef {Object} ApiErrorContext
 * @property {string} operation
 * @property {string} endpoint
 * @property {string[]=} eventIds
 * @property {number=} eventCount
 */

/**
 * @param {Response} response
 * @param {ApiErrorContext} context
 * @returns {Promise<Error>}
 */
async function createApiError(response, context) {
  const body = await response.json().catch(() => ({}));
  const data = /** @type {any} */ (body);
  const details = [];

  details.push(`${context.operation} failed`);
  details.push(`${response.status} ${response.statusText || 'HTTP error'}`);

  if (typeof data.error === 'string') {
    details.push(data.error);
  }
  if (typeof data.field === 'string') {
    details.push(`field=${data.field}`);
  }
  if (typeof data.index === 'number') {
    details.push(`index=${data.index}`);
  }
  if (typeof data.id === 'string') {
    details.push(`id=${data.id}`);
  }
  if (context.eventCount !== undefined) {
    details.push(`events=${context.eventCount}`);
  }
  if (context.eventIds && context.eventIds.length > 0) {
    const suffix = context.eventIds.length < (context.eventCount || context.eventIds.length) ? ', ...' : '';
    details.push(`ids=${context.eventIds.join(', ')}${suffix}`);
  }

  return Object.assign(new Error(details.join(' | ')), {
    status: response.status,
    endpoint: context.endpoint,
    response: data
  });
}

/**
 * @param {Array<{ id: string }>} events
 * @returns {string[]}
 */
function sampleEventIds(events) {
  return events.slice(0, 3).map((event) => event.id);
}

/** @returns {Promise<{ code: string }>} */
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

/**
 * @param {string} code
 * @returns {Promise<{ token: string }>}
 */
export async function apiGenerateToken(code) {
  const response = await fetch(`${backendUrl}/generate-token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code })
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(/** @type {any} */ (errorData).error || 'Invalid code');
  }
  return response.json();
}

/**
 * @param {string} token
 * @returns {Promise<{ code: string }>}
 */
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

/**
 * @param {string} token
 * @param {UsageEvent[]} events
 * @returns {Promise<UploadResult>}
 */
export async function apiUploadEvents(token, events) {
  const cleanEvents = events.map(({ received_at: _received_at, ...eventData }) => eventData);
  const endpoint = '/events/batch';
  const response = await fetch(`${backendUrl}/events/batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ events: cleanEvents })
  });
  if (!response.ok) {
    throw await createApiError(response, {
      operation: 'Upload asthma events',
      endpoint,
      eventIds: sampleEventIds(cleanEvents),
      eventCount: cleanEvents.length
    });
  }
  const { saved } = await response.json();
  return { successCount: saved, errorCount: 0 };
}

/**
 * @param {string} token
 * @returns {Promise<{ events: UsageEvent[] }>}
 */
export async function apiDownloadEvents(token) {
  const endpoint = '/events';
  const response = await fetch(`${backendUrl}/events`, {
    method: 'GET',
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Token expired. Please reconnect.');
    }
    throw await createApiError(response, { operation: 'Download asthma events', endpoint });
  }
  return response.json();
}

/**
 * @param {string} token
 * @param {RitalinEvent[]} events
 * @returns {Promise<UploadResult>}
 */
export async function apiUploadRitalinEvents(token, events) {
  const cleanEvents = events.map(({ received_at: _received_at, ...eventData }) => eventData);
  const endpoint = '/ritalin-events/batch';
  const response = await fetch(`${backendUrl}/ritalin-events/batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ events: cleanEvents })
  });
  if (!response.ok) {
    throw await createApiError(response, {
      operation: 'Upload ritalin events',
      endpoint,
      eventIds: sampleEventIds(cleanEvents),
      eventCount: cleanEvents.length
    });
  }
  const { saved } = await response.json();
  return { successCount: saved, errorCount: 0 };
}

/**
 * @param {string} token
 * @param {string[]} ids
 * @returns {Promise<void>}
 */
export async function apiDeleteEvents(token, ids) {
  const endpoint = '/events';
  const response = await fetch(`${backendUrl}/events`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ ids })
  });
  if (!response.ok) {
    throw await createApiError(response, {
      operation: 'Delete asthma events',
      endpoint,
      eventIds: ids.slice(0, 3),
      eventCount: ids.length
    });
  }
}

/**
 * @param {string} token
 * @param {string[]} ids
 * @returns {Promise<void>}
 */
export async function apiDeleteRitalinEvents(token, ids) {
  const endpoint = '/ritalin-events';
  const response = await fetch(`${backendUrl}/ritalin-events`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ ids })
  });
  if (!response.ok) {
    throw await createApiError(response, {
      operation: 'Delete ritalin events',
      endpoint,
      eventIds: ids.slice(0, 3),
      eventCount: ids.length
    });
  }
}

/**
 * @param {string} token
 * @returns {Promise<{ events: RitalinEvent[] }>}
 */
export async function apiDownloadRitalinEvents(token) {
  const endpoint = '/ritalin-events';
  const response = await fetch(`${backendUrl}/ritalin-events`, {
    method: 'GET',
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Token expired. Please reconnect.');
    }
    throw await createApiError(response, { operation: 'Download ritalin events', endpoint });
  }
  return response.json();
}
