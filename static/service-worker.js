const CACHE_NAME = 'rahmen-cache-v3'; // Neue Version erzwingen

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

  // A) API & HTML: Erst Netzwerk, dann Cache
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

  // B) Bilder: Erst Cache, dann Netzwerk
  if (url.pathname.startsWith('/static/images/')) {
    event.respondWith(
      // ignoreSearch hilft manchmal, ist aber nicht zwingend
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