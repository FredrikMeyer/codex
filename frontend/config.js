export const backendUrl = window.backendUrl || (window.location.hostname === 'localhost'
  ? 'http://localhost:5001'
  : 'https://asthma.fredrikmeyer.net');

export const storageKey = 'asthma-usage-entries';
export const lastTypeKey = 'asthma-last-medicine-type';
export const tokenKey = 'asthma-auth-token';
export const RITALIN_KEY = 'ritalin-usage-entries';
export const ASTHMA_SYNCED_IDS_KEY = 'asthma-synced-ids';
export const RITALIN_SYNCED_IDS_KEY = 'ritalin-synced-ids';
