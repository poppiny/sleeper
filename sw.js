// Offline cache: precache the app, then serve from cache and refresh in the background (web font included).
const CACHE = 'sleeper-v2';
const IDS = ['egg', 'baby', 'moko', 'bosa', 'tsuki', 'hidamari', 'kumo', 'neguse', 'obake', 'kujira', 'unicorn'];
const FILES = ['./', 'app.js', 'game.js', 'manifest.webmanifest', 'assets/bg_day.png', 'assets/bg_night.png',
  'assets/icon-192.png', 'assets/apple-touch-icon.png', ...IDS.map(i => `assets/${i}.png`), ...IDS.slice(1).map(i => `assets/${i}_sleep.png`)];

self.addEventListener('install', e => e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES)).then(() => self.skipWaiting())));
self.addEventListener('activate', e => e.waitUntil(
  caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  e.respondWith(caches.open(CACHE).then(async c => {
    const hit = await c.match(e.request, { ignoreSearch: e.request.url.startsWith(self.location.origin) });
    const net = fetch(e.request).then(r => { if (r.ok || r.type === 'opaque') c.put(e.request, r.clone()); return r; });
    if (!hit) return net;
    net.catch(() => {});
    return hit;
  }));
});
