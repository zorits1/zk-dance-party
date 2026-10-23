// ZK Dance Party – service worker: telepíthetőség (YouTube app „Megosztás” célja) + gyorsítótár.
// A 3D karakterek (avatars/) ritkán változnak: gyorsítótárból jönnek (gyors indulás, kevesebb adat).
// A mozdulatadat (data/) a gyorsítótárból azonnal, közben a háttérben frissül. Minden más: előbb hálózat, ha nincs, gyorsítótár.
const CACHE = 'zk-assets-v1';
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', e => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin) return;
  const p = url.pathname;
  if (/\/avatars\//.test(p)) {
    e.respondWith(caches.open(CACHE).then(async c => (await c.match(req)) || fetch(req).then(r => { if (r.ok) c.put(req, r.clone()); return r })));
  } else if (/\/data\//.test(p)) {
    e.respondWith(caches.open(CACHE).then(async c => {
      const hit = await c.match(req, {ignoreSearch: true});
      const net = fetch(req).then(r => { if (r.ok) c.put(req, r.clone()); return r }).catch(() => hit);
      return hit || net;
    }));
  } else {
    e.respondWith(fetch(req).then(r => { if (r.ok && /\.(html|js|json|png|jpg|webmanifest)$|\/$/.test(p)) caches.open(CACHE).then(c => c.put(req, r.clone())); return r })
      .catch(async () => (await caches.match(req)) || new Response('<h1>Nincs internet</h1>', {headers: {'Content-Type': 'text/html; charset=utf-8'}})));
  }
});
