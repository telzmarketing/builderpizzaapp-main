export type PwaAppKey =
  | "motoboy" | "bi-mobile" | "kds-principal" | "kds-pizzaiolo" | "kds-preparo"
  | "kds-esfiha" | "kds-expedicao" | "kds-motoboys" | "kds-pdv" | "kds-analitico";

export type PwaAppDefinition = {
  key: PwaAppKey;
  scope: string;
  entryPath: string;
  aliasScope?: string;
  canonicalPaths: readonly string[];
  label: string;
};

export const PWA_APPS: readonly PwaAppDefinition[] = [
  { key: "motoboy", scope: "/motoboy/", entryPath: "/motoboy/", canonicalPaths: ["/motoboy"], label: "Motoboy" },
  { key: "bi-mobile", scope: "/painel/bi-mobile/", entryPath: "/painel/bi-mobile/", canonicalPaths: ["/painel/bi-mobile"], label: "BI Mobile" },
  { key: "kds-principal", scope: "/app/kds/principal/", entryPath: "/app/kds/principal/", aliasScope: "/painel/kds/", canonicalPaths: ["/painel/kds"], label: "KDS Principal" },
  { key: "kds-pizzaiolo", scope: "/app/kds/pizzaiolo/", entryPath: "/app/kds/pizzaiolo/", aliasScope: "/painel/cozinha/", canonicalPaths: ["/painel/cozinha"], label: "KDS Pizzaiolo" },
  { key: "kds-esfiha", scope: "/app/kds/esfiha/", entryPath: "/app/kds/esfiha/", aliasScope: "/painel/esfiha/", canonicalPaths: ["/painel/esfiha"], label: "KDS Esfiha" },
  { key: "kds-preparo", scope: "/app/kds/preparo/", entryPath: "/app/kds/preparo/", aliasScope: "/painel/preparo/", canonicalPaths: ["/painel/preparo"], label: "KDS Cozinha Preparo" },
  { key: "kds-expedicao", scope: "/app/kds/expedicao/", entryPath: "/app/kds/expedicao/", aliasScope: "/painel/expedicao/", canonicalPaths: ["/painel/expedicao"], label: "KDS Expedição" },
  { key: "kds-motoboys", scope: "/app/kds/motoboys/", entryPath: "/app/kds/motoboys/", aliasScope: "/tv/motoboys/", canonicalPaths: ["/tv/motoboys"], label: "KDS Motoboys" },
  { key: "kds-pdv", scope: "/app/kds/pdv/", entryPath: "/app/kds/pdv/", aliasScope: "/painel/kds/pdv/", canonicalPaths: ["/painel/kds/pdv"], label: "KDS PDV" },
  { key: "kds-analitico", scope: "/app/kds/analitico/", entryPath: "/app/kds/analitico/", aliasScope: "/painel/kds/analitico/", canonicalPaths: ["/painel/kds/analitico"], label: "KDS Analítico" },
];

export const KDS_PWA_KEYS = PWA_APPS.filter((app) => app.key.startsWith("kds-")).map((app) => app.key) as PwaAppKey[];
export const MOTOBOY_SCOPE = "/motoboy/";
export const BI_MOBILE_SCOPE = "/painel/bi-mobile/";

function matchesPath(pathname: string, app: PwaAppDefinition) {
  return pathname === app.scope.slice(0, -1) || pathname.startsWith(app.scope)
    || app.canonicalPaths.some((path) => pathname === path || pathname.startsWith(`${path}/`));
}

function matchesDedicatedEntry(pathname: string, app: PwaAppDefinition) {
  const entryRoot = app.entryPath.endsWith("/") ? app.entryPath.slice(0, -1) : app.entryPath;
  return pathname === entryRoot || pathname === app.entryPath || pathname.startsWith(app.scope)
    || app.canonicalPaths.some((path) => pathname === path || pathname.startsWith(`${path}/`));
}

export function getPwaApp(pathname: string): PwaAppDefinition | null {
  return [...PWA_APPS].sort((a, b) => Math.max(...b.canonicalPaths.map((path) => path.length)) - Math.max(...a.canonicalPaths.map((path) => path.length)))
    .find((app) => matchesPath(pathname, app)) ?? null;
}

/** Returns an app only when the current path is an installable PWA entry/scope. */
export function getPwaEntryApp(pathname: string): PwaAppDefinition | null {
  return [...PWA_APPS].sort((a, b) => Math.max(...b.canonicalPaths.map((path) => path.length)) - Math.max(...a.canonicalPaths.map((path) => path.length)))
    .find((app) => matchesDedicatedEntry(pathname, app)) ?? null;
}

export function isPwaEntryPath(pathname: string) {
  return getPwaEntryApp(pathname) !== null;
}

export function pwaScopeForPath(pathname: string, app = getPwaApp(pathname)) {
  if (!app) return null;
  // KDS manifests use the operational alias as their installation boundary.
  // Register that boundary even when a saved /app/kds link opened the screen;
  // the installed app must control its manifest start_url.
  if (app.aliasScope && app.key.startsWith("kds-")) return app.aliasScope;
  return app.scope;
}

export function manifestUrl(appKey: PwaAppKey) {
  return `/api/site-config/manifest.webmanifest?app=${encodeURIComponent(appKey)}`;
}

export function isMotoboyPath(pathname: string) { return getPwaApp(pathname)?.key === "motoboy"; }
export function isBiMobilePath(pathname: string) { return getPwaApp(pathname)?.key === "bi-mobile"; }
export function isKdsPwaPath(pathname: string) { return getPwaApp(pathname)?.key.startsWith("kds-") === true; }

export function isLegacyMotoboyWorker(registration: ServiceWorkerRegistration, origin: string) {
  const worker = registration.active || registration.waiting || registration.installing;
  return registration.scope === `${origin}/` && worker?.scriptURL === `${origin}/sw.js`;
}

async function retireLegacyWorker(registration: ServiceWorkerRegistration) {
  const subscription = await registration.pushManager?.getSubscription();
  if (subscription) return;
  await registration.unregister();
}

export async function configurePwaWorker(pathname: string, container: ServiceWorkerContainer, origin: string) {
  const app = getPwaApp(pathname);
  const entryApp = getPwaEntryApp(pathname);
  const registrations = await container.getRegistrations();
  const legacy = registrations.filter((registration) => isLegacyMotoboyWorker(registration, origin));
  const canRegister = app && (entryApp?.key === app.key || app.key === "motoboy" || app.key === "bi-mobile");
  if (!canRegister) {
    await Promise.all(legacy.map(async (registration) => { await registration.update(); await retireLegacyWorker(registration); }));
    return null;
  }
  await container.register("/sw.js", { scope: pwaScopeForPath(pathname, app)!, updateViaCache: "none" });
  await Promise.all(legacy.map(async (registration) => { await registration.update(); await retireLegacyWorker(registration); }));
  return app;
}

// Compatibility aliases retained for existing Motoboy/BI callers.
export async function configureMotoboyWorker(pathname: string, container: ServiceWorkerContainer, origin: string) {
  return configurePwaWorker(pathname, container, origin);
}
export async function configureBiMobileWorker(pathname: string, container: ServiceWorkerContainer) {
  if (!isBiMobilePath(pathname)) return null;
  return container.register("/sw.js", { scope: pwaScopeForPath(pathname) ?? BI_MOBILE_SCOPE, updateViaCache: "none" });
}
export function syncMotoboyPwaHead(pathname: string) {
  const update = (window as Window & { updateMotoboyPwaHead?: (path: string) => void }).updateMotoboyPwaHead;
  update?.(pathname);
  const app = getPwaApp(pathname);
  if (!app || typeof document === "undefined") return;
  // Keep newly added app keys compatible with the static pre-React head bridge
  // until that bridge is regenerated. Existing entries remain owned by it.
  const hasManifest = Boolean(document.querySelector("link[data-telz-pwa][rel='manifest']"));
  if (hasManifest) return;
  const add = (tag: string, attributes: Record<string, string>) => {
    const node = document.createElement(tag);
    node.setAttribute("data-telz-pwa", "true");
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
    document.head.appendChild(node);
  };
  add("link", { rel: "manifest", href: manifestUrl(app.key) });
  add("meta", { name: "mobile-web-app-capable", content: "yes" });
  add("meta", { name: "apple-mobile-web-app-capable", content: "yes" });
  add("meta", { name: "apple-mobile-web-app-title", content: app.label });
}
