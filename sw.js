// Change this version number (e.g., v3 to v4) EVERY TIME you make a big update!
const CACHE_NAME = 'srm-hub-v4'; 
const urlsToCache = [
  './index.html',
  './images/app-icon.svg'
];

self.addEventListener('install', event => {
  self.skipWaiting(); // Forces the new service worker to activate immediately
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

// This deletes old caches when a new version is detected
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  event.waitUntil(self.clients.claim());
});

// NETWORK-FIRST STRATEGY: Always fetch fresh code, fallback to cache if offline
self.addEventListener('fetch', event => {
  event.respondWith(
    fetch(event.request)
      .then(response => {
        // If we got a valid response, clone it and update the cache
        if (response && response.status === 200 && response.type === 'basic') {
            const responseToCache = response.clone();
            caches.open(CACHE_NAME).then(cache => {
                cache.put(event.request, responseToCache);
            });
        }
        return response;
      })
      .catch(() => {
        // If the internet is down, fallback to the cached version
        return caches.match(event.request);
      })
  );
});

// Listen for custom notifications
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SHOW_NOTIFICATION') {
        const options = {
            body: event.data.body,
            icon: 'images/app-icon.svg',
            badge: 'images/app-icon.svg',
            vibrate: [200, 100, 200],
            data: { url: '/' } 
        };
        event.waitUntil(
            self.registration.showNotification(event.data.title, options)
        );
    }
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    event.waitUntil(clients.openWindow(event.notification.data.url));
});
