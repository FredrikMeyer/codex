import { backendUrl } from './config.js';

/** @param {string} value @returns {Uint8Array<ArrayBuffer>} */
function decode(value) {
  const binary = atob(value.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(value.length / 4) * 4, '='));
  return Uint8Array.from(binary, c => c.charCodeAt(0));
}

/** @param {ArrayBuffer} value @returns {string} */
function encode(value) {
  return btoa(Array.from(new Uint8Array(value), b => String.fromCharCode(b)).join(''))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/** @param {string} path @param {object} body @param {string | null} token */
async function post(path, body, token) {
  /** @type {Record<string, string>} */
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${backendUrl}${path}`, { method: 'POST', headers, body: JSON.stringify(body) });
  if (!response.ok) throw new Error('Could not complete passkey request. Please try again.');
  return response.json();
}

/** @returns {boolean} */
export function passkeysSupported() {
  return window.isSecureContext && typeof window.PublicKeyCredential !== 'undefined' && !!navigator.credentials;
}

/** @param {string} token @returns {Promise<void>} */
export async function registerPasskey(token) {
  const { challenge_id, options } = await post('/passkeys/register/options', {}, token);
  const publicKey = {
    ...options, challenge: decode(options.challenge),
    user: { ...options.user, id: decode(options.user.id) },
    excludeCredentials: (options.excludeCredentials || []).map((/** @type {any} */ item) => ({ ...item, id: decode(item.id) }))
  };
  const credential = /** @type {PublicKeyCredential | null} */ (await navigator.credentials.create({ publicKey }));
  if (!credential) throw new Error('Passkey creation cancelled.');
  const response = /** @type {AuthenticatorAttestationResponse} */ (credential.response);
  await post('/passkeys/register/verify', { challenge_id, credential: {
    id: credential.id, rawId: encode(credential.rawId), type: credential.type,
    response: { clientDataJSON: encode(response.clientDataJSON), attestationObject: encode(response.attestationObject),
      transports: typeof response.getTransports === 'function' ? response.getTransports() : [] }
  } }, token);
}

/** @returns {Promise<string>} */
export async function signInWithPasskey() {
  const { challenge_id, options } = await post('/passkeys/login/options', {}, null);
  const publicKey = { ...options, challenge: decode(options.challenge),
    allowCredentials: (options.allowCredentials || []).map((/** @type {any} */ item) => ({ ...item, id: decode(item.id) })) };
  const credential = /** @type {PublicKeyCredential | null} */ (await navigator.credentials.get({ publicKey }));
  if (!credential) throw new Error('Passkey sign-in cancelled.');
  const response = /** @type {AuthenticatorAssertionResponse} */ (credential.response);
  const data = await post('/passkeys/login/verify', { challenge_id, credential: {
    id: credential.id, rawId: encode(credential.rawId), type: credential.type,
    response: { clientDataJSON: encode(response.clientDataJSON), authenticatorData: encode(response.authenticatorData),
      signature: encode(response.signature), userHandle: response.userHandle ? encode(response.userHandle) : null }
  } }, null);
  return data.token;
}
