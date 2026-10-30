import { beforeEach, describe, expect, it, vi } from "vitest";
import { ordersApi } from "./api";

describe("customer delivery location API", () => {
  beforeEach(() => {
    vi.stubGlobal("sessionStorage", {
      getItem: (key: string) => key === "customer_access_token" ? "customer-token" : null,
    });
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => key === "customer" ? JSON.stringify({ id: "customer-a" }) : null,
    });
  });

  it("uses the authenticated customer session and encoded order path", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => ({
        success: true,
        data: {
          order_id: "order/a",
          delivery_status: "on_the_way",
          available: false,
          latitude: null,
          longitude: null,
          captured_at: null,
          max_age_seconds: 120,
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await ordersApi.getDeliveryLocation("order/a");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/delivery/order/order%2Fa/location"),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer customer-token" }),
      }),
    );
  });
});
