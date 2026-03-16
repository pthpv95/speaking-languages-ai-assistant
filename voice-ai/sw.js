const CACHE_NAME = "voice-ai-v2";
const PRECACHE = ["/", "/config", "/manifest.json"];

// ── Install: cache shell ────────────────────────────────────────────────────────
self.addEventListener("install", (e) => {
  console.log("[SW] install");
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE))
  );
  self.skipWaiting();
});

// ── Activate: clean old caches ──────────────────────────────────────────────────
self.addEventListener("activate", (e) => {
  console.log("[SW] activate");
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// ── Fetch: network-first for API, cache-first for shell ─────────────────────────
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  // API calls — always network
  if (
    url.pathname.startsWith("/transcribe") ||
    url.pathname.startsWith("/chat") ||
    url.pathname.startsWith("/language") ||
    url.pathname.startsWith("/history") ||
    url.pathname.startsWith("/health") ||
    url.pathname.startsWith("/subscribe") ||
    url.pathname.startsWith("/unsubscribe") ||
    url.pathname.startsWith("/send-push") ||
    url.pathname.startsWith("/vapid-public-key")
  ) {
    return;
  }

  // Shell — cache first, fallback to network
  e.respondWith(
    caches.match(e.request).then((cached) => {
      const fetched = fetch(e.request).then((response) => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(e.request, clone));
        return response;
      });
      return cached || fetched;
    })
  );
});

// ── Push notifications ──────────────────────────────────────────────────────────
self.addEventListener("push", (e) => {
  console.log("[SW] push event received!", e);
  let data = {};
  try {
    data = e.data ? e.data.json() : {};
    console.log("[SW] push data:", JSON.stringify(data));
  } catch (err) {
    console.error("[SW] push data parse error:", err);
    data = { title: "Voice AI Coach", body: e.data ? e.data.text() : "New message" };
  }
  const title = data.title || "Voice AI Coach";
  const options = {
    body: data.body || "Time to practice! Your language coach is ready.",
    icon: "/icon-192.png",
    badge: "/icon-192.png",
    tag: "practice-reminder",
    renotify: true,
    data: { url: "/" },
  };
  console.log("[SW] showing notification:", title, options);
  e.waitUntil(self.registration.showNotification(title, options));
});

// ── Notification click → open app ───────────────────────────────────────────────
self.addEventListener("notificationclick", (e) => {
  console.log("[SW] notification clicked");
  e.notification.close();
  e.waitUntil(
    clients.matchAll({ type: "window" }).then((windowClients) => {
      for (const client of windowClients) {
        if (client.url.includes("/") && "focus" in client) return client.focus();
      }
      return clients.openWindow("/");
    })
  );
});
