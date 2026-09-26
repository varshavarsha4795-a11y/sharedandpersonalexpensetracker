// Expense Tracker - Service Worker
// Keeps the app installable + usable like a native app.
// It never caches logic/data - it only speeds up static files
// (css/js/icons) and lets pages/API calls always go to the network first,
// so nothing about the app's behaviour changes.

const CACHE_NAME = "expense-tracker-static-v1";

const STATIC_ASSETS = [
  "/static/style.css",
  "/static/dashboard.css",
  "/static/expense.css",
  "/static/income.css",
  "/static/profile.css",
  "/static/settings.css",
  "/static/settlement.css",
  "/static/reports.css",
  "/static/group_expense.css",
  "/static/group_expense.js",
  "/static/settlement.js",
  "/static/reports.js",
  "/static/profile.js",
  "/static/images/wallet.png",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/icons/icon-512-maskable.png",
  "/static/manifest.json"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      // Best-effort: don't fail install if one file is missing
      return Promise.all(
        STATIC_ASSETS.map((url) =>
          cache.add(url).catch(() => {})
        )
      );
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;

  // Never intercept anything but GET (forms/login/add-expense etc. must
  // always go straight to the server, untouched).
  if (request.method !== "GET") {
    return;
  }

  const url = new URL(request.url);

  const isStaticAsset =
    url.pathname.startsWith("/static/") ;

  if (isStaticAsset) {
    // Cache-first for static files - faster loads, works offline.
    event.respondWith(
      caches.match(request).then((cached) => {
        return (
          cached ||
          fetch(request).then((response) => {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
            return response;
          })
        );
      })
    );
    return;
  }

  // Every page (dashboard, expense, reports, etc.) - always try the
  // network first so data is always fresh; this also keeps the back
  // button behaving exactly like a normal website (real pages, real
  // browser history), it only falls back to a cached copy if the
  // network is unreachable.
  event.respondWith(
    fetch(request).catch(() => caches.match(request))
  );
});
