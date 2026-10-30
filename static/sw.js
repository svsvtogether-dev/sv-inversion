// Service Worker para PWA SV Inversión - Estrategia Network First (Actualizaciones Inmediatas)
const CACHE_NAME = 'sv-inversion-v4';

self.addEventListener('install', (e) => {
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  // Borra cachés viejas automáticamente
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    }).then(() => clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  // Las llamadas a la API nunca se cachean
  if (e.request.url.includes('/api/')) {
    return;
  }

  // Network-First: Busca siempre la versión más reciente en la red
  e.respondWith(
    fetch(e.request)
      .then((resp) => {
        if (resp && resp.status === 200) {
          const copy = resp.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(e.request, copy));
        }
        return resp;
      })
      .catch(() => caches.match(e.request))
  );
});
