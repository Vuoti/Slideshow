const CACHE_NAME = 'rahmen-cache-v1';

// Dateien, die sofort beim Start gespeichert werden sollen (die "App-Hülle")
const PRECACHE_URLS = [
  '/',
  '/static/manifest.json',
  '/static/icon.png' 
  // index.html wird implizit durch '/' gecacht
];

// 1. Installieren: Grundgerüst cachen
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

// 2. Aktivieren: Alte Caches aufräumen (falls wir Version v2 machen)
self.addEventListener('activate', event => {
  event.waitUntil(self.clients.claim());
});

// 3. Fetch: Jeder Netzwerkaufruf geht hier durch
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // A) Ist es ein Bild oder Video aus unserem Static-Ordner?
  // Strategie: Cache First, falling back to Network
  if (url.pathname.startsWith('/static/images/')) {
    event.respondWith(
      caches.match(event.request).then(cachedResponse => {
        if (cachedResponse) {
          return cachedResponse; // Super! Haben wir schon.
        }
        // Nicht im Cache? Holen, dann speichern.
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

  // B) Ist es die API oder die Hauptseite?
  // Strategie: Network First (wir wollen ja wissen, ob es neue Bilder gibt), falling back to Cache
  if (url.pathname === '/' || url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request)
        .then(networkResponse => {
          return caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, networkResponse.clone());
            return networkResponse;
          });
        })
        .catch(() => {
          // Internet weg? Dann nimm das alte Zeug aus dem Cache
          return caches.match(event.request);
        })
    );
    return;
  }

  // C) Alles andere (z.B. Admin Panel) -> Einfach durchlassen
  event.respondWith(fetch(event.request));
});