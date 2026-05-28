const CACHE = "goova-v8";
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

self.addEventListener("push", e => {
  const data = e.data ? e.data.json() : {};
  const title = data.title || "Goova";
  const body = data.body || "Vous avez une nouvelle notification";
  e.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: "/icon-192.png",
      badge: "/icon-192.png",
      vibrate: [200, 100, 200],
    })
  );
});

self.addEventListener("notificationclick", e => {
  e.notification.close();
  e.waitUntil(clients.matchAll({ type: "window" }).then(cs => {
    if (cs.length) { cs[0].focus(); return; }
    clients.openWindow("/");
  }));
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);

  // API calls → réseau uniquement, jamais de cache
  if (url.pathname.startsWith("/api/")) return;

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
