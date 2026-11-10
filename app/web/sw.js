/* Guarda las pantallas de la app para abrirla sin conexión.
   Red primero: con conexión se sirve siempre la última versión publicada. */
const CACHE = "orduenliturgia-app-v1";
const PANTALLAS = ["./", "index.html", "style.css", "app.js"];
const AMBITO = new URL("./", self.location).pathname;

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(PANTALLAS)));
  self.skipWaiting();
});
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin || !u.pathname.startsWith(AMBITO)) return;
  e.respondWith(
    fetch(e.request, { cache: "no-cache" }).then(r => {
      if (r.ok) { const copia = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copia)); }
      return r;
    }).catch(() => caches.match(e.request, { ignoreSearch: true }).then(r => r || caches.match("index.html")))
  );
});
