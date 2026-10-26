import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PRESENCE_HEARTBEAT_MS, startStorefrontPresence } from "./storefrontPresence";
import { apiFetch } from "./api";

vi.mock("./api", () => ({ apiFetch: vi.fn().mockResolvedValue({ ok: true }) }));
vi.mock("./tracking", () => ({ getTrackingData: () => ({ session_id: "shared-browser-session" }), isPublicSalesPath: (path: string) => ["/", "/checkout"].includes(path) }));

describe("storefront tab presence lifecycle", () => {
  let visibility: string;
  let events: EventTarget;
  beforeEach(() => {
    vi.useFakeTimers(); vi.clearAllMocks(); visibility = "visible"; events = new EventTarget();
    vi.stubGlobal("document", { get visibilityState() { return visibility; }, addEventListener: events.addEventListener.bind(events), removeEventListener: events.removeEventListener.bind(events) });
    vi.stubGlobal("window", { setInterval, clearInterval, addEventListener: events.addEventListener.bind(events), removeEventListener: events.removeEventListener.bind(events) });
  });
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });
  const payloads = () => vi.mocked(apiFetch).mock.calls.map((call) => JSON.parse(String(call[1]?.body)));
  it("does not heartbeat for internal routes", () => {
    startStorefrontPresence("/painel")(); startStorefrontPresence("/motoboy")();
    expect(apiFetch).not.toHaveBeenCalled();
  });
  it("renews while visible, sends leave on hide and cleanup, and resumes", () => {
    const stop = startStorefrontPresence("/");
    vi.advanceTimersByTime(PRESENCE_HEARTBEAT_MS);
    expect(payloads().map((value) => value.event_type)).toEqual(["store_presence", "store_presence"]);
    visibility = "hidden"; events.dispatchEvent(new Event("visibilitychange"));
    vi.advanceTimersByTime(PRESENCE_HEARTBEAT_MS * 2);
    expect(payloads().at(-1).event_type).toBe("store_presence_leave");
    expect(apiFetch).toHaveBeenCalledTimes(3);
    visibility = "visible"; events.dispatchEvent(new Event("visibilitychange")); stop();
    expect(payloads().at(-1).metadata.sequence).toBe(5);
    vi.advanceTimersByTime(PRESENCE_HEARTBEAT_MS * 2);
    expect(apiFetch).toHaveBeenCalledTimes(5);
  });
  it("keeps one browser identity across tabs with independently closable tab identifiers", () => {
    const first = startStorefrontPresence("/"); const second = startStorefrontPresence("/checkout");
    const values = payloads();
    expect(values[0].fingerprint).toBe(values[1].fingerprint);
    expect(values[0].metadata.tab_id).not.toBe(values[1].metadata.tab_id);
    first(); second();
  });
});
