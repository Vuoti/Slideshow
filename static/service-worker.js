const CACHE_NAME = 'rahmen-cache-v2'; // Version hochgezählt!

const PRECACHE_URLS = [
  '/',
  '/static/manifest.json',
  '/static/icon.png'
];

self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(PRECACHE_URLS))
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // A) API: Network First, dann Cache
  if (url.pathname === '/' || url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          return caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, response.clone());
            return response;
          });
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // B) Bilder: Cache First
  // WICHTIG: Wir prüfen lockerer, ob es ein Bild ist
  if (url.pathname.startsWith('/static/images/')) {
    event.respondWith(
      caches.match(event.request, {ignoreSearch: true}).then(cachedResponse => {
        if (cachedResponse) {
          return cachedResponse;
        }
        return fetch(event.request).then(response => {
          return caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, response.clone());
            return response;
          });
        });
      })
    );
    return;
  }

  event.respondWith(fetch(event.request));
});