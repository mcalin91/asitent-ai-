self.addEventListener("install", (event) => {
  event.waitUntil(caches.open("medical-ai-v1").then((cache) => cache.addAll(["/", "/manifest.json", "/icon.svg"])));
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});
