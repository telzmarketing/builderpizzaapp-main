import { trackingApi } from "./api";

const STORAGE_KEY = "paid_traffic_tracking";

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
  trackingApi.event({
    ...data,
    event_type,
    value,
    path: window.location.pathname,
    metadata,
  }).catch(() => {
    /* Tracking must never break the customer experience. */
  });
}
