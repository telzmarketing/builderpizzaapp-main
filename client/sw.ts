/// <reference lib="webworker" />

import { setCacheNameDetails } from "workbox-core";
import { precache, matchPrecache } from "workbox-precaching";

declare const self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: Array<{ url: string; revision?: string | null }>;
};

const LEGACY_MOTOBOY_CACHES = [
  "motoboy-static-v1",
  "motoboy-runtime-v1",
  "motoboy-media-v2",
  "motoboy-static-v2",
  "motoboy-media-v3",
];
const GLOBAL_FAVICON_URL = "/api/site-config/favicon?size=192";
const scopePath = new URL(self.registration.scope).pathname;

type PwaApp = {
  key: string;
  scope: string;
  cachePrefix: string;
};

const PWA_APPS: Record<string, PwaApp> = {
  "/motoboy/": { key: "motoboy", scope: "/motoboy/", cachePrefix: "telz-motoboy" },
  "/painel/bi-mobile/": { key: "bi-mobile", scope: "/painel/bi-mobile/", cachePrefix: "telz-bi-mobile" },
  "/app/kds/principal/": { key: "kds-principal", scope: "/app/kds/principal/", cachePrefix: "telz-kds-principal" },
  "/app/kds/pizzaiolo/": { key: "kds-pizzaiolo", scope: "/app/kds/pizzaiolo/", cachePrefix: "telz-kds-pizzaiolo" },
  "/app/kds/preparo/": { key: "kds-preparo", scope: "/app/kds/preparo/", cachePrefix: "telz-kds-preparo" },
  "/app/kds/expedicao/": { key: "kds-expedicao", scope: "/app/kds/expedicao/", cachePrefix: "telz-kds-expedicao" },
  "/app/kds/motoboys/": { key: "kds-motoboys", scope: "/app/kds/motoboys/", cachePrefix: "telz-kds-motoboys" },
  "/app/kds/pdv/": { key: "kds-pdv", scope: "/app/kds/pdv/", cachePrefix: "telz-kds-pdv" },
  "/app/kds/analitico/": { key: "kds-analitico", scope: "/app/kds/analitico/", cachePrefix: "telz-kds-analitico" },
};

const app = PWA_APPS[scopePath];
const scopedWorker = Boolean(app);
const legacyRootWorker = scopePath === "/";
const isMotoboy = (pathname: string) => pathname === "/motoboy" || pathname.startsWith("/motoboy/");
const isWithinApp = (pathname: string) => Boolean(app && (pathname === app.scope.slice(0, -1) || pathname.startsWith(app.scope)));

const SHARED_PRECACHE_PATTERNS = [
  /^\/index\.html(?:\?.*)?$/,
  /^\/motoboy-pwa-head\.js(?:\?.*)?$/,
  /^\/assets\/index-[^/]+\.(?:js|css)$/,
  /^\/assets\/admin-[^/]+\.css$/,
  /^\/assets\/[^/]+\.woff2$/,
  /^\/icons\/(?:[^/]+\.(?:png|svg|ico))$/,
];

const APP_PRECACHE_PATTERNS: Record<string, RegExp[]> = {
  motoboy: [/^\/assets\/Motoboy-[^/]+\.js$/],
  "bi-mobile": [/^\/assets\/Bi(?:Mobile|Dashboard)-[^/]+\.js$/],
  "kds-principal": [
    /^\/assets\/KdsOverview-[^/]+\.js$/,
    /^\/assets\/(?:KdsBrandLogo|KdsSessionActions|kds)-[^/]+\.js$/,
  ],
  "kds-pizzaiolo": [
    /^\/assets\/Cozinha-[^/]+\.js$/,
    /^\/assets\/(?:KdsBrandLogo|KdsSessionActions|kds)-[^/]+\.js$/,
  ],
  "kds-preparo": [
    /^\/assets\/Preparation-[^/]+\.js$/,
    /^\/assets\/PreparationOperationsPanel-[^/]+\.js$/,
    /^\/assets\/(?:KdsBrandLogo|KdsSessionActions|kds)-[^/]+\.js$/,
  ],
  "kds-expedicao": [
    /^\/assets\/Expedicao-[^/]+\.(?:js|css)$/,
    /^\/assets\/(?:KdsBrandLogo|KdsSessionActions|kds)-[^/]+\.js$/,
  ],
  "kds-motoboys": [
    /^\/assets\/OrderBoardTv-[^/]+\.js$/,
    /^\/assets\/(?:KdsBrandLogo|KdsSessionActions|kds)-[^/]+\.js$/,
  ],
  "kds-pdv": [
    /^\/assets\/KdsPdv-[^/]+\.js$/,
    /^\/assets\/(?:KdsBrandLogo|KdsSessionActions|kds)-[^/]+\.js$/,
  ],
  "kds-analitico": [
    /^\/assets\/KdsAnalytics-[^/]+\.js$/,
    /^\/assets\/(?:KdsBrandLogo|KdsSessionActions|kds)-[^/]+\.js$/,
  ],
};

const isAllowedPrecacheUrl = (url: string, appKey: string) => {
  const pathname = new URL(url, self.location.origin).pathname;
  return SHARED_PRECACHE_PATTERNS.some((pattern) => pattern.test(pathname))
    || (APP_PRECACHE_PATTERNS[appKey] ?? []).some((pattern) => pattern.test(pathname));
};

const manifestForApp = (manifest: Array<{ url: string; revision?: string | null }>, appKey: string) =>
  manifest.filter((entry) => isAllowedPrecacheUrl(entry.url, appKey));

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
  setCacheNameDetails({ prefix: app.cachePrefix, suffix: "v1" });
  // The build emits one manifest for every app. Keep only the shared shell and
  // the explicitly identified chunks for this registration's app. Unknown
  // chunks stay network-first and are never placed in another app's precache.
  precache(manifestForApp(self.__WB_MANIFEST, app.key));
}

self.skipWaiting();

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    if (scopedWorker) {
      await self.clients.claim();
    } else if (legacyRootWorker) {
      // The root worker is only a legacy Motoboy push bridge. It may clean its
      // own known historical caches, but must never remove another app cache.
      await Promise.all(LEGACY_MOTOBOY_CACHES.map((cacheName) => caches.delete(cacheName)));
      if (!(await self.registration.pushManager?.getSubscription())) await self.registration.unregister();
    }
  })());
});

if (scopedWorker) self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;
  event.respondWith((async () => {
    const client = event.clientId ? await self.clients.get(event.clientId) : null;
    const clientPath = client ? new URL(client.url).pathname : "";
    const path = event.request.mode === "navigate" ? url.pathname : clientPath;
    // Shared assets are only handled when requested by a page inside this app's
    // scope. This prevents a KDS worker from serving another PWA's assets.
    if (!isWithinApp(path)) return fetch(event.request);
    if (event.request.mode === "navigate") {
      try { return await fetch(event.request); }
      catch { return (await matchPrecache("/index.html")) || Response.error(); }
    }
    const precached = await matchPrecache(event.request.url);
    if (precached) return precached;
    if (!url.pathname.startsWith("/assets/") && !url.pathname.startsWith("/icons/")) return fetch(event.request);
    const runtime = await caches.open(`${app.cachePrefix}-runtime-v1`);
    const cached = await runtime.match(event.request);
    if (cached) return cached;
    const response = await fetch(event.request);
    if (response.ok && response.type === "basic") await runtime.put(event.request, response.clone());
    return response;
  })());
});

if (legacyRootWorker || app?.key === "motoboy") self.addEventListener("push", (event) => {
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

if (legacyRootWorker || app?.key === "motoboy") self.addEventListener("notificationclick", (event) => {
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
