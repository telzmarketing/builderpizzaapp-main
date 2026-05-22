import { marketingTrackApi, paidTrafficApi, type CampaignPixelConfig } from "./api";

const STORAGE_KEY = "paid_traffic_tracking";
const PIXEL_STORAGE_KEY = "campaign_pixel_config";
const STORE_PIXEL_STORAGE_KEY = "store_pixel_configs";
const LOCATION_STORAGE_KEY = "visitor_location_permission_checked";
const INTERNAL_STAFF_PATHS = ["/painel", "/motoboy"];

// ─── Pixel helpers ────────────────────────────────────────────────────────────

declare global {
  interface Window {
    fbq?: (...args: unknown[]) => void;
    _fbq?: unknown;
    gtag?: (...args: unknown[]) => void;
    dataLayer?: unknown[];
    ttq?: { track: (event: string, data?: Record<string, unknown>) => void; load: (id: string) => void; page: () => void };
  }
}

function injectMetaPixel(pixelId: string): void {
  if (document.getElementById(`meta-pixel-${pixelId}`)) return;
  const script = document.createElement("script");
  script.id = `meta-pixel-${pixelId}`;
  script.innerHTML = `
    !function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?
    n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;
    n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;
    t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}
    (window,document,'script','https://connect.facebook.net/en_US/fbevents.js');
    fbq('init','${pixelId}');
  `;
  document.head.appendChild(script);
}

function injectGooglePixel(pixelId: string): void {
  if (document.getElementById(`gtag-pixel-${pixelId}`)) return;
  const script = document.createElement("script");
  script.id = `gtag-pixel-${pixelId}`;
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${pixelId}`;
  document.head.appendChild(script);
  window.dataLayer = window.dataLayer ?? [];
  window.gtag = function (...args) { window.dataLayer!.push(args); };
  window.gtag("js", new Date());
  window.gtag("config", pixelId);
}

function injectTikTokPixel(pixelId: string): void {
  if (document.getElementById(`ttq-pixel-${pixelId}`)) return;
  const script = document.createElement("script");
  script.id = `ttq-pixel-${pixelId}`;
  script.innerHTML = `
    !function(w,d,t){w.TiktokAnalyticsObject=t;var ttq=w[t]=w[t]||[];ttq.methods=
    ["page","track","identify","instances","debug","on","off","once","ready","alias",
    "group","enableCookie","disableCookie"];ttq.setAndDefer=function(t,e){t[e]=function(){
    t.push([e].concat(Array.prototype.slice.call(arguments,0)))}};
    for(var i=0;i<ttq.methods.length;i++)ttq.setAndDefer(ttq,ttq.methods[i]);
    ttq.instance=function(t){for(var e=ttq._i[t]||[],n=0;n<ttq.methods.length;n++)
    ttq.setAndDefer(e,ttq.methods[n]);return e};ttq.load=function(e,n){var i=
    "https://analytics.tiktok.com/i18n/pixel/events.js";ttq._i=ttq._i||{};
    ttq._i[e]=[];ttq._i[e]._u=i;ttq._t=ttq._t||{};ttq._t[e]=+new Date;
    ttq._o=ttq._o||{};ttq._o[e]=n||{};var o=document.createElement("script");
    o.type="text/javascript";o.async=!0;o.src=i+"?sdkid="+e+"&lib="+t;
    var a=document.getElementsByTagName("script")[0];a.parentNode.insertBefore(o,a)};
    ttq.load('${pixelId}');ttq.page()}(window,document,'ttq');
  `;
  document.head.appendChild(script);
}

export function firePixelEvent(
  event: string,
  data?: { value?: number; currency?: string; content_name?: string; order_id?: string }
): void {
  const configs = readPixelConfigs();
  if (configs.length === 0) return;
  try {
    for (const config of configs) {
      if (!config.events.includes(event)) continue;

      const currency = data?.currency ?? "BRL";
      const value = data?.value ?? 0;

      if (config.platform === "meta" && typeof window.fbq === "function") {
        if (event === "Purchase") {
          window.fbq("trackSingle", config.pixel_id, "Purchase", { value, currency, content_name: data?.content_name });
        } else if (event === "InitiateCheckout") {
          window.fbq("trackSingle", config.pixel_id, "InitiateCheckout", { value, currency });
        } else if (event === "AddToCart") {
          window.fbq("trackSingle", config.pixel_id, "AddToCart", { value, currency, content_name: data?.content_name });
        } else if (event === "Lead") {
          window.fbq("trackSingle", config.pixel_id, "Lead");
        } else {
          window.fbq("trackSingle", config.pixel_id, event);
        }
      }

      if (config.platform === "google" && typeof window.gtag === "function") {
        if (event === "Purchase") {
          window.gtag("event", "purchase", { value, currency, transaction_id: data?.order_id });
        } else if (event === "InitiateCheckout") {
          window.gtag("event", "begin_checkout", { value, currency });
        } else if (event === "AddToCart") {
          window.gtag("event", "add_to_cart", { value, currency, item_name: data?.content_name });
        } else if (event === "ViewContent") {
          window.gtag("event", "view_item", { value, currency, item_name: data?.content_name });
        } else if (event === "Lead") {
          window.gtag("event", "generate_lead");
        } else {
          window.gtag("event", event.toLowerCase().replace(/\s+/g, "_"));
        }
      }

      if (config.platform === "tiktok" && window.ttq) {
        if (event === "Purchase") {
          window.ttq.track("PlaceAnOrder", { value, currency });
        } else if (event === "InitiateCheckout") {
          window.ttq.track("InitiateCheckout", { value, currency });
        } else if (event === "Lead") {
          window.ttq.track("SubmitForm");
        } else {
          window.ttq.track(event);
        }
      }
    }
  } catch {
    // pixel errors never block the customer experience
  }
}

function readPixelConfigs(): CampaignPixelConfig[] {
  const configsByKey = new Map<string, CampaignPixelConfig>();
  const add = (config: CampaignPixelConfig | null | undefined) => {
    if (!config?.platform || !config.pixel_id) return;
    const key = `${config.platform}:${config.pixel_id}`;
    const existing = configsByKey.get(key);
    if (existing) {
      existing.events = Array.from(new Set([...existing.events, ...config.events]));
      return;
    }
    configsByKey.set(key, { ...config, events: [...config.events] });
  };

  try {
    const rawStore = sessionStorage.getItem(STORE_PIXEL_STORAGE_KEY);
    const storeConfigs = rawStore ? JSON.parse(rawStore) as CampaignPixelConfig[] : [];
    storeConfigs.forEach(add);
  } catch {
    /* ignore invalid cached config */
  }

  try {
    const rawCampaign = sessionStorage.getItem(PIXEL_STORAGE_KEY);
    add(rawCampaign ? JSON.parse(rawCampaign) as CampaignPixelConfig : null);
  } catch {
    /* ignore invalid cached config */
  }

  return Array.from(configsByKey.values());
}

function injectPixelConfig(config: CampaignPixelConfig): void {
  if (config.platform === "meta") injectMetaPixel(config.pixel_id);
  else if (config.platform === "google") injectGooglePixel(config.pixel_id);
  else if (config.platform === "tiktok") injectTikTokPixel(config.pixel_id);
}

export async function initStorePixels(): Promise<void> {
  try {
    const configs = await paidTrafficApi.storePixelConfig();
    sessionStorage.setItem(STORE_PIXEL_STORAGE_KEY, JSON.stringify(configs));
    configs.forEach(injectPixelConfig);
  } catch {
    // pixel init errors never block the customer experience
  }
}

export async function initCampaignPixel(campaignId: string | null | undefined): Promise<void> {
  if (!campaignId) return;
  try {
    const config = await paidTrafficApi.campaignPixelConfig(campaignId);
    if (!config) return;
    sessionStorage.setItem(PIXEL_STORAGE_KEY, JSON.stringify(config));
    injectPixelConfig(config);
  } catch {
    // pixel init errors never block the customer experience
  }
}

export type TrackingData = {
  session_id: string;
  campaign_id?: string | null;
  utm_source?: string | null;
  utm_medium?: string | null;
  utm_campaign?: string | null;
  utm_content?: string | null;
  utm_term?: string | null;
  landing_page?: string | null;
  referrer?: string | null;
};

export function isInternalStaffPath(path?: string | null): boolean {
  const rawPath = path ?? (typeof window !== "undefined" ? window.location.pathname : "");
  if (!rawPath) return false;
  let pathname = rawPath;
  try {
    if (/^https?:\/\//i.test(rawPath)) pathname = new URL(rawPath).pathname;
  } catch {
    pathname = rawPath;
  }
  return INTERNAL_STAFF_PATHS.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

function newSessionId(): string {
  if (crypto?.randomUUID) return crypto.randomUUID();
  return `sess-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function getTrackingData(): TrackingData {
  const existing = localStorage.getItem(STORAGE_KEY);
  if (existing) {
    try {
      const parsed = JSON.parse(existing) as TrackingData;
      if (parsed.session_id) return parsed;
    } catch {
      /* ignore */
    }
  }
  const data: TrackingData = {
    session_id: newSessionId(),
    landing_page: window.location.href,
    referrer: document.referrer || null,
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  return data;
}

export function captureTrackingFromUrl(): TrackingData {
  const current = getTrackingData();
  const params = new URLSearchParams(window.location.search);
  const next: TrackingData = {
    ...current,
    campaign_id: params.get("campaign_id") || current.campaign_id || null,
    utm_source: params.get("utm_source") || current.utm_source || null,
    utm_medium: params.get("utm_medium") || current.utm_medium || null,
    utm_campaign: params.get("utm_campaign") || current.utm_campaign || null,
    utm_content: params.get("utm_content") || current.utm_content || null,
    utm_term: params.get("utm_term") || current.utm_term || null,
    landing_page: current.landing_page || window.location.href,
    referrer: current.referrer || document.referrer || null,
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  return next;
}

export function checkoutTrackingPayload(): Partial<TrackingData> {
  return getTrackingData();
}

type VisitorLocation = {
  latitude: number;
  longitude: number;
  location_accuracy_m?: number | null;
};

export function trackEvent(
  event_type: string,
  value?: number,
  metadata?: Record<string, unknown>,
  location?: VisitorLocation
) {
  if (isInternalStaffPath()) return;
  const data = getTrackingData();
  marketingTrackApi.track({
    fingerprint: data.session_id,
    session_id: data.session_id,
    event_type,
    page: window.location.pathname,
    product_id: typeof metadata?.product_id === "string" ? metadata.product_id : undefined,
    metadata,
    utm_source: data.utm_source,
    utm_medium: data.utm_medium,
    utm_campaign: data.utm_campaign,
    utm_content: data.utm_content,
    utm_term: data.utm_term,
    referrer: data.referrer,
    latitude: location?.latitude,
    longitude: location?.longitude,
    location_accuracy_m: location?.location_accuracy_m,
  }).catch(() => { /* Tracking must never break the customer experience. */ });
}

export function requestVisitorLocation(): void {
  if (isInternalStaffPath()) return;
  if (!("geolocation" in navigator)) return;
  if (sessionStorage.getItem(LOCATION_STORAGE_KEY)) return;
  sessionStorage.setItem(LOCATION_STORAGE_KEY, "1");

  navigator.geolocation.getCurrentPosition(
    (position) => {
      trackEvent("location_update", undefined, { source: "browser_geolocation" }, {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        location_accuracy_m: position.coords.accuracy,
      });
    },
    () => { /* Cliente negou ou navegador nao entregou localizacao. */ },
    { enableHighAccuracy: false, timeout: 8000, maximumAge: 10 * 60 * 1000 },
  );
}
