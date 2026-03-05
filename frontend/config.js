export const backendUrl = window.backendUrl || (window.location.hostname === 'localhost'
  ? 'http://localhost:5001'
  : 'https://asthma.fredrikmeyer.net');

export const storageKey = 'asthma-usage-entries';
export const lastTypeKey = 'asthma-last-medicine-type';
export const tokenKey = 'asthma-auth-token';
export const RITALIN_KEY = 'ritalin-usage-entries';
