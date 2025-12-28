const CACHE = 'asthma-tracker-v2';
const ASSET_PATHS = [
  '.',
  'index.html',
  'styles.css',
  'app.js',
  'manifest.webmanifest'
];
const BASE_URL = self.location.href.replace(/service-worker\\.js(?:\\?.*)?$/, '');
const ASSETS = ASSET_PATHS.map((path) => new URL(path, BASE_URL).toString());

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(ASSETS))
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE).map((k) => caches.delete(k)))
    )
  );
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});
