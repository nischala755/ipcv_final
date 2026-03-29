const CACHE_NAME = "authlab-cache-v1";
const ASSETS = ["/", "/index.html", "/manifest.webmanifest"];
const RUNTIME_CACHE = "authlab-runtime-v1";
const OFFLINE_OPENCV_URL = "https://docs.opencv.org/4.10.0/opencv.js";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(ASSETS))
      .then(() => caches.open(RUNTIME_CACHE))
      .then((cache) => cache.add(OFFLINE_OPENCV_URL).catch(() => null))
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME && k !== RUNTIME_CACHE).map((k) => caches.delete(k)))
    )
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request)
        .then((response) => {
          const copy = response.clone();
          const cacheName = event.request.url.includes("opencv.js") ? RUNTIME_CACHE : CACHE_NAME;
          caches.open(cacheName).then((cache) => cache.put(event.request, copy));
          return response;
        })
        .catch(() => {
          if (event.request.mode === "navigate") {
            return caches.match("/index.html");
          }
          return caches.match(event.request);
        });
    })
  );
});
