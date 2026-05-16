const CACHE = "goova-v1";
const SHELL = [
  "/",
  "/index.html",
  "/manifest.json",
  "/icon-192.png",
  "/icon-512.png",
  "/apple-touch-icon.png",
];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);

  // API calls → réseau uniquement, pas de cache
  if (url.hostname.includes("onrender.com")) return;

  // Ressources externes (CDN) → réseau d'abord
  if (!url.hostname.includes("vercel.app") && url.hostname !== self.location.hostname && url.hostname !== "localhost") {
    return;
  }

  // App shell → cache d'abord, réseau en fallback
  e.respondWith(
    caches.match(e.request).then(cached => {
      const network = fetch(e.request).then(res => {
        if (res.ok && e.request.method === "GET") {
          caches.open(CACHE).then(c => c.put(e.request, res.clone()));
        }
        return res;
      }).catch(() => null);
      return cached || network || caches.match("/");
    })
  );
});
