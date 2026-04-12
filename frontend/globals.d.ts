export {};

declare global {
  const Temporal: typeof import('@js-temporal/polyfill').Temporal;
}
