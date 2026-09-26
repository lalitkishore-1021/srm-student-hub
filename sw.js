// Change this version number every time you want to force phones to update!
const CACHE_NAME = 'srm-hub-v55-clean-ui-push'; 

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

// 3. FETCH EVENT: Network First (Ensures you always get the latest code)
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // CRITICAL BYPASS: Never cache API requests
    if (url.pathname.startsWith('/api/')) {
        return; 
    }

    event.respondWith(
        fetch(event.request).then((networkResponse) => {
            if (networkResponse && networkResponse.status === 200 && networkResponse.type === 'basic') {
                const responseToCache = networkResponse.clone();
                caches.open(CACHE_NAME).then((cache) => {
                    cache.put(event.request, responseToCache);
                });
            }
            return networkResponse;
        }).catch(() => {
            // Network failed, fallback to cache
            return caches.match(event.request);
        })
    );
});

// 4. MESSAGE EVENT: Catch the signals from index.html and show the Mobile Notifications!
self.addEventListener('message', (event) => {
    if (!event.data) return;

    if (event.data.type === 'SHOW_NOTIFICATION') {
        const title = event.data.title;
        const options = {
            body: event.data.body,
            icon: '/images/app-icon.svg',
            badge: '/images/app-icon.svg',
            vibrate: [200, 100, 200],
            requireInteraction: false,
            data: { url: event.data.url || '/' }
        };
        self.registration.showNotification(title, options);
    } else if (event.data.type === 'SCHEDULE_DELAYED_NOTIFICATION') {
        const delay = event.data.delayMs || 4000;
        const title = event.data.title || 'SRM Student Hub';
        const body = event.data.body || 'Background notifications active. You will receive timetable and mess reminders without opening the app.';
        const url = event.data.url || '/';
        setTimeout(() => {
            self.registration.showNotification(title, {
                body: body,
                icon: '/images/app-icon.svg',
                badge: '/images/app-icon.svg',
                tag: 'srm-bg-test',
                renotify: true,
                vibrate: [200, 100, 200],
                data: { url: url }
            });
        }, delay);
    } else if (event.data.type === 'UPDATE_SCHEDULE_CACHE') {
        caches.open('srm-offline-data').then(cache => {
            const dataToStore = {
                timetable: event.data.timetable || {},
                attendance: event.data.attendance || [],
                profile: event.data.profile || {},
                updatedAt: Date.now()
            };
            const response = new Response(JSON.stringify(dataToStore), {
                headers: { 'Content-Type': 'application/json' }
            });
            cache.put('/offline-schedule-data.json', response);
        }).catch(err => console.warn('Cache schedule err:', err));
    }
});

// 5. NATIVE PUSH EVENT: Wakes up the Service Worker in the background even when app is closed!
self.addEventListener('push', (event) => {
    let data = {};
    if (event.data) {
        try {
            data = event.data.json();
        } catch(e) {
            data = { title: 'SRM Student Hub', body: event.data.text() };
        }
    } else {
        data = { title: 'SRM Student Hub', body: 'You have a new campus update.' };
    }

    const title = data.title || 'SRM Student Hub';
    const options = {
        body: data.body || 'New notification received.',
        icon: data.icon || '/images/app-icon.svg',
        badge: '/images/app-icon.svg',
        vibrate: [200, 100, 200],
        tag: data.tag || 'srm-push-' + Date.now(),
        renotify: true,
        data: { url: data.url || '/' }
    };

    event.waitUntil(self.registration.showNotification(title, options));
});

// 6. NOTIFICATION CLICK: Focus or open the app on click
self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    const targetUrl = (event.notification.data && event.notification.data.url) || '/';
    
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
            for (let client of windowClients) {
                if (client.url.includes(self.location.origin) && 'focus' in client) {
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(targetUrl);
            }
        })
    );
});

// 7. PERIODIC SYNC: Offline Background Notifications without opening the app!
self.addEventListener('periodicsync', (event) => {
    if (event.tag === 'check-notifications') {
        event.waitUntil(checkAndTriggerBackgroundNotifications());
    }
});

async function checkAndTriggerBackgroundNotifications() {
    // This runs strictly in the background via Service Worker even when the app is completely closed!
    const now = new Date();
    const hours = now.getHours();
    const minutes = now.getMinutes();
    const timeFloat = hours + (minutes / 60);

    // 1. Check cached timetable data for upcoming classes
    try {
        const cache = await caches.open('srm-offline-data');
        const cachedRes = await cache.match('/offline-schedule-data.json');
        if (cachedRes) {
            const data = await cachedRes.json();
            const tt = data.timetable || {};
            const currentDayNum = (now.getDay() || 7).toString();
            const classes = tt[currentDayNum] || [];
            const nowMins = hours * 60 + minutes;

            classes.forEach(c => {
                if (!c.time && !c.time_from) return;
                const startTimeStr = c.time_from || (c.time.split('-')[0] || '').trim();
                const parts = startTimeStr.split(':');
                if (parts.length >= 2) {
                    let ch = parseInt(parts[0]);
                    const cm = parseInt(parts[1]);
                    // If times are in 12-hour format like 01:25 PM
                    if (ch < 8 && ch >= 1) ch += 12;
                    const classMins = ch * 60 + cm;
                    const diff = classMins - nowMins;

                    // Trigger notification 15 mins before class
                    if (diff >= 5 && diff <= 18) {
                        self.registration.showNotification(`Class in ${diff}m: ${c.subject || c.code}`, {
                            body: `Room ${c.room || 'TBA'} • ${startTimeStr} - ${c.faculty || 'SRM Faculty'}`,
                            icon: '/images/app-icon.svg',
                            badge: '/images/app-icon.svg',
                            tag: 'class-alert-' + (c.code || startTimeStr),
                            renotify: true,
                            vibrate: [200, 100, 200],
                            data: { url: '/#timetable-view' }
                        });
                    }
                }
            });
        }
    } catch(e) {
        console.warn('Background TT check error:', e);
    }

    // 2. Mess timings notification
    if (timeFloat >= 7.3 && timeFloat < 7.7) {
        self.registration.showNotification("Breakfast Time - SRM Mess", {
            body: "Breakfast is being served right now in the mess.",
            icon: '/images/app-icon.svg',
            tag: 'mess-breakfast',
            data: { url: '/#mess-view' }
        });
    } else if (timeFloat >= 12.3 && timeFloat < 12.8) {
        self.registration.showNotification("Lunch Time - SRM Mess", {
            body: "Lunch is being served right now in the hostel mess.",
            icon: '/images/app-icon.svg',
            tag: 'mess-lunch',
            data: { url: '/#mess-view' }
        });
    } else if (timeFloat >= 19.3 && timeFloat < 19.8) {
        self.registration.showNotification("Dinner Time - SRM Mess", {
            body: "Dinner is now being served in the hostel mess.",
            icon: '/images/app-icon.svg',
            tag: 'mess-dinner',
            data: { url: '/#mess-view' }
        });
    }
}
