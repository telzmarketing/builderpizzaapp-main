import { afterEach, describe, expect, it, vi } from "vitest";
import { deliveryApi } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("driver completion request", () => {
  it("posts completion without a confirmation code", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => "application/json" },
      json: async () => ({ success: true, data: { id: "delivery-1", status: "completed" } }),
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("localStorage", { getItem: () => "driver-token" });

    await deliveryApi.driverCompleteDelivery("delivery-1");

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/delivery/driver/deliveries/delivery-1/complete");
    expect(options.method).toBe("POST");
    expect(options.headers.Authorization).toBe("Bearer driver-token");
    expect(JSON.parse(options.body)).toEqual({ payment_received: false });
  });

  it("posts administrative completion with the supplied reason", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => "application/json" },
      json: async () => ({ success: true, data: { id: "delivery-1", status: "completed" } }),
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("localStorage", { getItem: () => null });
    vi.stubGlobal("sessionStorage", { getItem: () => null });

    await deliveryApi.adminComplete("delivery/1", "Corrida confirmada pelo painel.");

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/delivery/delivery%2F1/admin-complete");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({ reason: "Corrida confirmada pelo painel." });
  });
});
