const CACHE = "daymark-app-__DAYMARK_BUILD__";

function publicAsset(url) {
  return url.origin === self.location.origin && (url.pathname === "/" || url.pathname === "/index.html" || url.pathname === "/manifest.webmanifest" || /^\/icon(?:-(?:192|512)\.png|\.svg)$/.test(url.pathname) || url.pathname === "/@vite/client" || url.pathname === "/@react-refresh" || /^\/(assets|src|node_modules\/\.vite)\//.test(url.pathname)) && !["google_connected", "google_error", "outlook_connected", "outlook_error"].some(key => url.searchParams.has(key));
}

self.addEventListener("notificationclick", event => {
  event.notification.close();
  event.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(windows => {
    const existing = windows.find(client => client.url.startsWith(self.location.origin + "/"));
    return existing ? existing.focus() : self.clients.openWindow("/");
  }));
});

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(["/", "/manifest.webmanifest", "/icon.svg", "/icon-192.png", "/icon-512.png"])).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key.startsWith("daymark-app-") && key !== CACHE).map((key) => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener("message", (event) => {
  if (event.data?.type !== "CACHE_APP_ASSETS" || !Array.isArray(event.data.urls)) return;
  event.waitUntil(caches.open(CACHE).then((cache) => Promise.allSettled(event.data.urls.slice(0, 150).filter((value) => { try { return publicAsset(new URL(value)); } catch { return false; } }).map((url) => cache.add(url)))));
});
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || !publicAsset(url)) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    try {
      const response = await fetch(event.request);
      if (response.ok && response.type !== "opaque") await cache.put(event.request, response.clone());
      return response;
    } catch {
      const cached = await cache.match(event.request);
      if (cached) return cached;
      if (event.request.mode === "navigate") return await cache.match("/") || Response.error();
      return Response.error();
    }
  })());
});
