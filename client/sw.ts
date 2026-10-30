/// <reference lib="webworker" />

import { setCacheNameDetails } from "workbox-core";
import { precache, matchPrecache } from "workbox-precaching";

declare const self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: Array<{ url: string; revision?: string | null }>;
};

const LEGACY_RUNTIME_CACHES = ["motoboy-static-v1", "motoboy-runtime-v1", "motoboy-media-v2"];
const GLOBAL_FAVICON_URL = "/api/site-config/favicon?size=192";
const scopePath = new URL(self.registration.scope).pathname;
const scopedWorker = scopePath === "/motoboy/" || scopePath === "/painel/bi-mobile/";
const scopedBi = scopePath === "/painel/bi-mobile/";
const isMotoboy = (pathname: string) => pathname === "/motoboy" || pathname.startsWith("/motoboy/");
const isBiMobile = (pathname: string) => pathname === "/painel/bi-mobile" || pathname.startsWith("/painel/bi-mobile/");

type PushPayload = {
  title: string;
  body: string;
  url: string;
  icon?: string;
  badge?: string;
};

// The same script updates the old root registration into a push-only bridge.
// Never install a root fetch handler or cache public/admin requests.
if (scopedWorker) {
  setCacheNameDetails({ prefix: scopedBi ? "telz-bi-mobile" : "telz-motoboy", suffix: "v4" });
  precache(self.__WB_MANIFEST);
}

self.skipWaiting();

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    await Promise.all([...LEGACY_RUNTIME_CACHES, "motoboy-static-v2", "motoboy-media-v3"].map((cacheName) => caches.delete(cacheName)));
    if (scopedWorker) {
      await self.clients.claim();
    } else {
      // Exact known former cache only; leave other apps and push endpoints alone.
      await caches.delete(`workbox-precache-v2-${self.registration.scope}`);
      if (!(await self.registration.pushManager?.getSubscription())) await self.registration.unregister();
    }
  })());
});

if (scopedWorker) self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;
  event.respondWith((async () => {
    const client = event.clientId ? await self.clients.get(event.clientId) : null;
    const path = event.request.mode === "navigate" ? url.pathname : client ? new URL(client.url).pathname : "";
    // A scoped document can navigate via SPA into the store. Do not cache there.
    if (!isMotoboy(path) && !isBiMobile(path)) return fetch(event.request);
    if (event.request.mode === "navigate") {
      try { return await fetch(event.request); }
      catch { return (await matchPrecache("/index.html")) || Response.error(); }
    }
    const precached = await matchPrecache(event.request.url);
    if (precached) return precached;
    if (!url.pathname.startsWith("/assets/") && !url.pathname.startsWith("/icons/")) return fetch(event.request);
    const runtime = await caches.open(scopedBi ? "telz-bi-mobile-runtime-v4" : "telz-motoboy-runtime-v4");
    const cached = await runtime.match(event.request);
    if (cached) return cached;
    const response = await fetch(event.request);
    if (response.ok && response.type === "basic") await runtime.put(event.request, response.clone());
    return response;
  })());
});

self.addEventListener("push", (event) => {
  const fallback: PushPayload = {
    title: "Motoboy Delivery",
    body: "Nova atualizacao no painel do entregador.",
    url: "/motoboy",
  };

  let payload: PushPayload = fallback;
  try {
    payload = event.data ? event.data.json() : fallback;
  } catch {
    payload = { ...fallback, body: event.data?.text() || fallback.body };
  }
  const title = payload.title || fallback.title;
  const requested = new URL(payload.url || fallback.url, self.location.origin);
  const url = requested.origin === self.location.origin && isMotoboy(requested.pathname) ? requested.href : `${self.location.origin}/motoboy/`;

  event.waitUntil(
    self.registration.showNotification(title, {
      body: payload.body || fallback.body,
      icon: payload.icon || GLOBAL_FAVICON_URL,
      badge: payload.badge || payload.icon || GLOBAL_FAVICON_URL,
      data: { url },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  const requested = new URL(event.notification.data?.url || "/motoboy/", self.location.origin);
  const targetUrl = requested.origin === self.location.origin && isMotoboy(requested.pathname) ? requested.href : `${self.location.origin}/motoboy/`;

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        const clientUrl = new URL(client.url);
        if ("focus" in client && clientUrl.origin === self.location.origin && isMotoboy(clientUrl.pathname)) {
          void client.focus();
          return;
        }
      }

      if (self.clients.openWindow) return self.clients.openWindow(targetUrl);
    }),
  );
});
