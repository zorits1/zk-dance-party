// ZK Dance Party – minimális service worker: a telepíthetőséghez (és a YouTube app „Megosztás” céljához) kell.
// Nem gyorsítótáraz: mindig a friss oldalt tölti a hálózatról.
// Régi (TV-)böngészőn és a legacy.html-nél egyáltalán nem nyúl a kérésekhez – ott a böngésző maga tölt.
var CH = +((self.navigator.userAgent.match(/Chrom(?:e|ium)\/(\d+)/) || [])[1] || 999);
self.addEventListener('install', function () { self.skipWaiting(); });
self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (k) { return Promise.all(k.map(function (c) { return caches.delete(c); })); }).then(function () { return self.clients.claim(); }));
});
self.addEventListener('fetch', function (e) {
  if (CH < 90) return;
  var u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin || /legacy\.html$/.test(u.pathname)) return;
  e.respondWith(fetch(e.request).catch(function () {
    return new Response('<meta name="viewport" content="width=device-width"><body style="background:#0b0614;color:#fff;font:20px sans-serif;text-align:center;padding-top:30vh">Nem sikerült betölteni – újrapróbálom…<script>setTimeout(function(){location.reload()},3000)</script>', { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
  }));
});
