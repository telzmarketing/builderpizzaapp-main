import { apiFetch } from "./api";
import { getTrackingData, isPublicSalesPath } from "./tracking";

export const PRESENCE_HEARTBEAT_MS = 30_000;

export function startStorefrontPresence(pathname: string): () => void {
  if (!isPublicSalesPath(pathname)) return () => {};
  const tabId = crypto.randomUUID();
  const tracking = getTrackingData();
  let active = false;
  let sequence = 0;
  function send(present: boolean) {
    if (!present && !active) return;
    active = present;
    void apiFetch("/marketing/track", {
      method: "POST", keepalive: !present,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fingerprint: tracking.session_id, session_id: tracking.session_id,
        event_type: present ? "store_presence" : "store_presence_leave", page: pathname,
        metadata: { tab_id: tabId, sequence: ++sequence } }),
    }).catch(() => {});
  }
  function heartbeat() { send(document.visibilityState !== "hidden"); }
  function leave() { send(false); }
  heartbeat();
  const timer = window.setInterval(heartbeat, PRESENCE_HEARTBEAT_MS);
  document.addEventListener("visibilitychange", heartbeat);
  window.addEventListener("pagehide", leave);
  window.addEventListener("pageshow", heartbeat);
  return () => {
    window.clearInterval(timer);
    document.removeEventListener("visibilitychange", heartbeat);
    window.removeEventListener("pagehide", leave);
    window.removeEventListener("pageshow", heartbeat);
    leave();
  };
}
