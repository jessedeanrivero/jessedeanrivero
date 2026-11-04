// Judah's Star Jar service worker: keeps the app shell available offline.
// Star data (/api/judahstars) is never cached so the jar is always live.
const CACHE = "judahstars-v1";
const SHELL = [
  "/judahstars",
  "/judahstars/manifest.webmanifest",
  "/judahstars/icon-192.png",
  "/judahstars/icon-512.png",
  "/judahstars/apple-touch-icon.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("judahstars-") && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (!url.pathname.startsWith("/judahstars")) return;

  // Page: network first so updates show up, cached copy when offline.
  if (e.request.mode === "navigate") {
    e.respondWith(
      fetch(e.request)
        .then((res) => { const copy = res.clone(); caches.open(CACHE).then((c) => c.put("/judahstars", copy)); return res; })
        .catch(() => caches.match("/judahstars"))
    );
    return;
  }

  // Icons and manifest: cache first.
  e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request)));
});
