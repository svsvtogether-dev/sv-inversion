// Service Worker para PWA SV Inversión
const CACHE_NAME = 'sv-inversion-v1';

self.addEventListener('install', (e) => {
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(clients.claim());
});

self.addEventListener('fetch', (e) => {
  // Solo interceptar peticiones GET estáticas
  if (e.request.method === 'GET' && e.request.url.includes('/static/')) {
    e.respondWith(
      caches.match(e.request).then((cached) => {
        return cached || fetch(e.request).then((resp) => {
          if (resp.status === 200) {
            const copy = resp.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(e.request, copy));
          }
          return resp;
        });
      }).catch(() => fetch(e.request))
    );
  }
});
