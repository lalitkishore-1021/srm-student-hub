// Change this version number every time you want to force phones to update!
const CACHE_NAME = 'srm-hub-v12-speed-sync'; 

const ASSETS_TO_CACHE = [
    '/',
    '/index.html',
    '/manifest.json',
    '/images/app-icon.svg'
];

// 1. INSTALL EVENT: Cache the core files and force the update immediately
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('Opened cache');
            return cache.addAll(ASSETS_TO_CACHE);
        })
    );
    // Force the waiting service worker to become active immediately
    self.skipWaiting(); 
});

// 2. ACTIVATE EVENT: Destroy old caches so your phone doesn't get stuck on old code
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('Clearing old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    // Take control of the page immediately without requiring a refresh
    self.clients.claim(); 
});

// 3. FETCH EVENT: Stale-While-Revalidate (Instant Load, Background Update)
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // 🚨 CRITICAL BYPASS: Never cache API requests
    if (url.pathname.startsWith('/api/')) {
        return; 
    }

    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            const fetchPromise = fetch(event.request).then((networkResponse) => {
                if (networkResponse && networkResponse.status === 200 && networkResponse.type === 'basic') {
                    const responseToCache = networkResponse.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseToCache);
                    });
                }
                return networkResponse;
            }).catch(() => {
                // Network failed, do nothing, the cached response is already returned.
            });

            // Return cached response immediately if available, otherwise wait for network
            return cachedResponse || fetchPromise;
        })
    );
});

// 4. MESSAGE EVENT: Catch the signals from index.html and show the Mobile Notifications!
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SHOW_NOTIFICATION') {
        const title = event.data.title;
        const options = {
            body: event.data.body,
            icon: '/images/app-icon.svg',
            badge: '/images/app-icon.svg',
            vibrate: [200, 100, 200],
            requireInteraction: false
        };
        
        self.registration.showNotification(title, options);
    }
});

// 5. PERIODIC SYNC: Offline Background Notifications without opening the app!
self.addEventListener('periodicsync', (event) => {
    if (event.tag === 'check-notifications') {
        event.waitUntil(checkAndTriggerBackgroundNotifications());
    }
});

async function checkAndTriggerBackgroundNotifications() {
    // This runs strictly in the background via Service Worker!
    const now = new Date();
    const hours = now.getHours();
    const minutes = now.getMinutes();
    const timeFloat = hours + (minutes / 60);

    // Hardcoded mess timings for offline fallback
    if (timeFloat >= 7.0 && timeFloat < 7.5) {
        self.registration.showNotification("Good Morning! ☀️", { body: "Breakfast is being served right now in the mess!", icon: '/images/app-icon.svg' });
    } else if (timeFloat >= 12.0 && timeFloat < 12.5) {
        self.registration.showNotification("Lunch Time Approaching! 🍛", { body: "Time to grab some lunch!", icon: '/images/app-icon.svg' });
    } else if (timeFloat >= 19.0 && timeFloat < 19.5) {
        self.registration.showNotification("Dinner Time! 🍽️", { body: "Dinner is ready in the mess.", icon: '/images/app-icon.svg' });
    }
}