const CACHE_NAME = 'rahmen-cache-v1';

// Diese Dateien sind Pflicht für die App-Hülle
const PRECACHE_URLS = [
  '/',
  '/static/manifest.json',
  '/static/icon.png',
  // Hier keine Bilder listen, das machen wir dynamisch!
];

// 1. Installieren
self.addEventListener('install', event => {
  self.skipWaiting(); // Sofort aktivieren, nicht warten
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(PRECACHE_URLS))
  );
});

// 2. Aktivieren
self.addEventListener('activate', event => {
  event.waitUntil(self.clients.claim()); // Sofort Kontrolle über alle Tabs übernehmen
});

// 3. Fetch (Der Türsteher)
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // A) API-Anfragen (Config & Bilderliste)
  // Strategie: Network First, Fallback to Cache
  if (url.pathname === '/' || url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request)
        .then(networkResponse => {
          // Wenn Netzwerk erfolgreich: Antwort klonen und in Cache legen
          return caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, networkResponse.clone());
            return networkResponse;
          });
        })
        .catch(() => {
          // Wenn Netzwerk tot: Aus Cache holen
          return caches.match(event.request);
        })
    );
    return;
  }

  // B) Bilder/Videos (aus /static/images/)
  // Strategie: Cache First, Fallback to Network
  if (url.pathname.startsWith('/static/images/')) {
    event.respondWith(
      caches.match(event.request).then(cachedResponse => {
        if (cachedResponse) {
          return cachedResponse; // Haben wir schon!
        }
        // Nicht im Cache? Versuchen zu holen
        return fetch(event.request).then(networkResponse => {
          return caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, networkResponse.clone());
            return networkResponse;
          });
        });
      })
    );
    return;
  }

  // C) Alles andere
  event.respondWith(fetch(event.request));
});