import { marketingTrackApi, paidTrafficApi, type CampaignPixelConfig } from "./api";

const STORAGE_KEY = "paid_traffic_tracking";
const PIXEL_STORAGE_KEY = "campaign_pixel_config";

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
    fbq('init','${pixelId}');fbq('track','PageView');
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
  const raw = sessionStorage.getItem(PIXEL_STORAGE_KEY);
  if (!raw) return;
  try {
    const config = JSON.parse(raw) as CampaignPixelConfig;
    if (!config.events.includes(event)) return;

    const currency = data?.currency ?? "BRL";
    const value = data?.value ?? 0;

    if (config.platform === "meta" && typeof window.fbq === "function") {
      if (event === "Purchase") {
        window.fbq("track", "Purchase", { value, currency, content_name: data?.content_name });
      } else if (event === "InitiateCheckout") {
        window.fbq("track", "InitiateCheckout", { value, currency });
      } else if (event === "AddToCart") {
        window.fbq("track", "AddToCart", { value, currency, content_name: data?.content_name });
      } else if (event === "Lead") {
        window.fbq("track", "Lead");
      } else {
        window.fbq("track", event);
      }
    }

    if (config.platform === "google" && typeof window.gtag === "function") {
      if (event === "Purchase") {
        window.gtag("event", "purchase", { value, currency, transaction_id: data?.order_id });
      } else if (event === "InitiateCheckout") {
        window.gtag("event", "begin_checkout", { value, currency });
      } else {
        window.gtag("event", event.toLowerCase().replace(/\s+/g, "_"));
      }
    }

    if (config.platform === "tiktok" && window.ttq) {
      if (event === "Purchase") {
        window.ttq.track("PlaceAnOrder", { value, currency });
      } else if (event === "InitiateCheckout") {
        window.ttq.track("InitiateCheckout", { value, currency });
      } else {
        window.ttq.track(event);
      }
    }
  } catch {
    // pixel errors never block the customer experience
  }
}

export async function initCampaignPixel(campaignId: string | null | undefined): Promise<void> {
  if (!campaignId) return;
  try {
    const config = await paidTrafficApi.campaignPixelConfig(campaignId);
    if (!config) return;
    sessionStorage.setItem(PIXEL_STORAGE_KEY, JSON.stringify(config));

    if (config.platform === "meta") injectMetaPixel(config.pixel_id);
    else if (config.platform === "google") injectGooglePixel(config.pixel_id);
    else if (config.platform === "tiktok") injectTikTokPixel(config.pixel_id);
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

export function trackEvent(event_type: string, value?: number, metadata?: Record<string, unknown>) {
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
  }).catch(() => { /* Tracking must never break the customer experience. */ });
}
