// Offline cache: precache everything, then serve from cache and refresh in the background.
const CACHE = 'sleeper-v1';
const IDS = ['egg', 'baby', 'moko', 'bosa', 'tsuki', 'hidamari', 'kumo', 'neguse', 'obake', 'kujira', 'unicorn'];
const FILES = ['./', 'app.js', 'game.js', 'manifest.webmanifest', 'assets/bg_day.webp', 'assets/bg_night.webp',
  'assets/icon-192.png', 'assets/apple-touch-icon.png', ...IDS.map(i => `assets/${i}.webp`), ...IDS.slice(1).map(i => `assets/${i}_sleep.webp`)];

self.addEventListener('install', e => e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES)).then(() => self.skipWaiting())));
self.addEventListener('activate', e => e.waitUntil(
  caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET' || !e.request.url.startsWith(self.location.origin)) return;
  e.respondWith(caches.open(CACHE).then(async c => {
    const hit = await c.match(e.request, { ignoreSearch: true });
    const net = fetch(e.request).then(r => { if (r.ok) c.put(e.request, r.clone()); return r; });
    if (!hit) return net;
    net.catch(() => {});
    return hit;
  }));
});
