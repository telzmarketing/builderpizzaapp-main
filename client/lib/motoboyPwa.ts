import { isPublicSalesPath } from "./tracking";

export type PwaAppKey =
  | "storefront" | "motoboy" | "bi-mobile" | "kds-principal" | "kds-pizzaiolo" | "kds-preparo"
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
  { key: "storefront", scope: "/", entryPath: "/", canonicalPaths: ["/"], label: "Loja" },
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
export const PWA_CONTEXT_STORAGE_KEY = "telz:pwa-context";

export type PwaContext = {
  appKey: PwaAppKey;
  pathname: string;
  search: string;
  hash: string;
};

type StorageReader = Pick<Storage, "getItem">;
type StorageWriter = Pick<Storage, "setItem">;

function isKdsPwaKey(value: unknown): value is PwaAppKey {
  return typeof value === "string" && KDS_PWA_KEYS.includes(value as PwaAppKey);
}

function suffix(value: string | undefined, prefix: "?" | "#") {
  return value?.startsWith(prefix) ? value : "";
}

function pwaTarget(context: PwaContext) {
  return `${context.pathname}${context.search}${context.hash}`;
}

/**
 * Saves only an internal KDS route. This survives the login redirect and a
 * full reload, but cannot be used as an arbitrary external redirect.
 */
export function rememberPwaContext(
  pathname: string,
  search = "",
  hash = "",
  storage: StorageWriter = localStorage,
): string | null {
  const app = getPwaApp(pathname);
  if (!app || !isKdsPwaKey(app.key)) return null;

  const context: PwaContext = {
    appKey: app.key,
    pathname,
    search: suffix(search, "?"),
    hash: suffix(hash, "#"),
  };
  try {
    storage.setItem(PWA_CONTEXT_STORAGE_KEY, JSON.stringify(context));
  } catch {
    // Storage can be unavailable in private browsing or embedded webviews.
  }
  return pwaTarget(context);
}

export function readPwaContext(storage: StorageReader = localStorage): PwaContext | null {
  try {
    const raw = storage.getItem(PWA_CONTEXT_STORAGE_KEY);
    if (!raw) return null;
    const context = JSON.parse(raw) as Partial<PwaContext>;
    if (!isKdsPwaKey(context.appKey) || typeof context.pathname !== "string") return null;
    if (getPwaApp(context.pathname)?.key !== context.appKey) return null;
    return {
      appKey: context.appKey,
      pathname: context.pathname,
      search: suffix(context.search, "?"),
      hash: suffix(context.hash, "#"),
    };
  } catch {
    return null;
  }
}

export function consumePwaContextTarget(
  storage: StorageReader & Pick<Storage, "removeItem"> = localStorage,
): string | null {
  const context = readPwaContext(storage);
  try {
    storage.removeItem(PWA_CONTEXT_STORAGE_KEY);
  } catch {
    // Ignore storage failures; the login flow can still use its normal target.
  }
  return context ? pwaTarget(context) : null;
}

export function clearPwaContext(storage: Pick<Storage, "removeItem"> = localStorage) {
  try {
    storage.removeItem(PWA_CONTEXT_STORAGE_KEY);
  } catch {
    // Ignore storage failures.
  }
}

function matchesPath(pathname: string, app: PwaAppDefinition) {
  if (app.key === "storefront") return isPublicSalesPath(pathname);
  return pathname === app.scope.slice(0, -1) || pathname.startsWith(app.scope)
    || app.canonicalPaths.some((path) => pathname === path || pathname.startsWith(`${path}/`));
}

function matchesDedicatedEntry(pathname: string, app: PwaAppDefinition) {
  if (app.key === "storefront") return isPublicSalesPath(pathname);
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
  const canRegister = app && (entryApp?.key === app.key || app.key === "storefront" || app.key === "motoboy" || app.key === "bi-mobile");
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
