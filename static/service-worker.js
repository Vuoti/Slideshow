// WICHTIG: Hier muss derselbe Name stehen wie in der index.html!
const CACHE_NAME = 'rahmen-cache-v3';

const PRECACHE_URLS = [
  '/',
  '/static/manifest.json',
  '/static/icon.png'
];

self.addEventListener('install', event => {
  self.skipWaiting(); // Sofort aktivieren
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(PRECACHE_URLS))
  );
});

// Alte Caches löschen (Aufräumen)
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('Lösche alten Cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // A) API & HTML (Config, Liste)
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

  // B) Bilder
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