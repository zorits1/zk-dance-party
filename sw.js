// ZK Dance Party – minimális service worker: a telepíthetőséghez (és a YouTube app „Megosztás” céljához) kell.
// Nem gyorsítótáraz: mindig a friss oldalt tölti a hálózatról.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(caches.keys().then(k => Promise.all(k.map(c => caches.delete(c)))).then(() => self.clients.claim())));
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET' || new URL(e.request.url).origin !== location.origin) return;
  e.respondWith(fetch(e.request).catch(() => new Response('<h1>Nincs internet</h1>', {headers: {'Content-Type': 'text/html; charset=utf-8'}})));
});
