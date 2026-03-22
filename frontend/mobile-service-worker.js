const MOBILE_CACHE = "mobile-shell-v20260316-02";
const SHELL_ASSETS = [
  "/mobile",
  "/assets/manifest.webmanifest",
  "/assets/css/mobile-dashboard.css?v=20260316_mobileapp11",
  "/assets/js/state/mobile-state.js?v=20260316_mobileapp11",
  "/assets/js/pages/mobile-dashboard-page.js?v=20260316_mobileapp11",
  "/assets/js/mobile-dashboard.js?v=20260316_mobileapp11",
  "/assets/icons/trading-assistant-192.png",
  "/assets/icons/trading-assistant-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(MOBILE_CACHE).then((cache) => cache.addAll(SHELL_ASSETS)).catch(() => undefined)
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.map((key) => {
          if (key !== MOBILE_CACHE) {
            return caches.delete(key);
          }
          return Promise.resolve(false);
        })
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") {
    return;
  }
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) {
    return;
  }
  if (!url.pathname.startsWith("/mobile") && !url.pathname.startsWith("/assets/")) {
    return;
  }
  event.respondWith(
    fetch(request)
      .then((response) => {
        const cloned = response.clone();
        caches.open(MOBILE_CACHE).then((cache) => cache.put(request, cloned)).catch(() => undefined);
        return response;
      })
      .catch(() => caches.match(request).then((cached) => cached || Response.error()))
  );
});
