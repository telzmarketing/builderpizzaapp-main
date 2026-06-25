/// <reference lib="webworker" />

import { clientsClaim } from "workbox-core";
import { ExpirationPlugin } from "workbox-expiration";
import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from "workbox-precaching";
import { NavigationRoute, registerRoute } from "workbox-routing";
import { CacheFirst, StaleWhileRevalidate } from "workbox-strategies";

declare const self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: Array<{ url: string; revision?: string | null }>;
};

const LEGACY_RUNTIME_CACHES = ["motoboy-static-v1", "motoboy-runtime-v1"];
const RUNTIME_STATIC_CACHE = "motoboy-static-v2";
const RUNTIME_MEDIA_CACHE = "motoboy-media-v2";
const GLOBAL_FAVICON_URL = "/api/site-config/favicon?size=192";

type PushPayload = {
  title: string;
  body: string;
  url: string;
  icon?: string;
  badge?: string;
};

precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

self.skipWaiting();
clientsClaim();

self.addEventListener("activate", (event) => {
  event.waitUntil(Promise.all(LEGACY_RUNTIME_CACHES.map((cacheName) => caches.delete(cacheName))));
});

registerRoute(
  new NavigationRoute(createHandlerBoundToURL("/index.html"), {
    allowlist: [/^\/motoboy(?:\/.*)?$/],
  }),
);

registerRoute(
  ({ request, url }) =>
    request.method === "GET" &&
    url.origin === self.location.origin &&
    url.pathname.startsWith("/icons/"),
  new CacheFirst({
    cacheName: RUNTIME_STATIC_CACHE,
    plugins: [
      new ExpirationPlugin({
        maxEntries: 80,
        maxAgeSeconds: 30 * 24 * 60 * 60,
      }),
    ],
  }),
);

registerRoute(
  ({ request }) =>
    request.method === "GET" &&
    ["font", "image"].includes(request.destination),
  new StaleWhileRevalidate({
    cacheName: RUNTIME_MEDIA_CACHE,
    plugins: [
      new ExpirationPlugin({
        maxEntries: 60,
        maxAgeSeconds: 7 * 24 * 60 * 60,
      }),
    ],
  }),
);

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
  const url = payload.url || fallback.url;

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

  const targetUrl = new URL(event.notification.data?.url || "/motoboy", self.location.origin).href;

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ("focus" in client && client.url.startsWith(self.location.origin)) {
          void client.focus();
          return;
        }
      }

      if (self.clients.openWindow) return self.clients.openWindow(targetUrl);
    }),
  );
});
