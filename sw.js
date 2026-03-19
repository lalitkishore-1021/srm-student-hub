// Change this version number every time you want to force phones to update!
const CACHE_NAME = 'srm-hub-v10-profile-sync'; 

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

// 3. FETCH EVENT: The "Bouncer"
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // 🚨 CRITICAL BYPASS: Never, ever cache the Python API requests!
    if (url.pathname.startsWith('/api/')) {
        return; // Let the request pass straight to the Render server
    }

    // NETWORK-FIRST STRATEGY: Always try to get the freshest code from the internet.
    // If the internet is down (offline mode), fallback to the cached version.
    event.respondWith(
        fetch(event.request).then((response) => {
            // If the network fetch is successful, save a copy in the cache for later
            if (response && response.status === 200 && response.type === 'basic') {
                const responseClone = response.clone();
                caches.open(CACHE_NAME).then((cache) => {
                    cache.put(event.request, responseClone);
                });
            }
            return response;
        }).catch(() => {
            // If the network fails (offline), pull it from the cache
            return caches.match(event.request);
        })
    );
});

// 4. MESSAGE EVENT: Catch the signals from index.html and show the Mobile Notifications!
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SHOW_NOTIFICATION') {
        const title = event.data.title;
        const options = {
            body: event.data.body,
            icon: '/images/app-icon.svg', // Shows your SRM Hub logo in the notification!
            badge: '/images/app-icon.svg',
            vibrate: [200, 100, 200],     // Vibrate pattern for phones
            requireInteraction: false
        };
        
        self.registration.showNotification(title, options);
    }
});
