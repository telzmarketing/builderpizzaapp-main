import { describe, expect, it } from "vitest";
import type { KdsKitchenOrder } from "./api";
import { activeKitchenOrders, clearAssignedDriverSelections } from "./kds";

function order(
  id: string,
  status: KdsKitchenOrder["status"],
  fulfillmentType: KdsKitchenOrder["fulfillment_type"] = "delivery",
): KdsKitchenOrder {
  return {
    id,
    status,
    fulfillment_type: fulfillmentType,
    total: 0,
    estimated_time: 0,
    created_at: "2026-09-22T12:00:00Z",
    updated_at: "2026-09-22T12:00:00Z",
    items: [],
  };
}

describe("KDS state", () => {
  it("moves delivery orders to dispatch and retains pickup orders for completion", () => {
    expect(activeKitchenOrders([
      order("waiting", "paid"),
      order("cooking", "preparing"),
      order("delivery-ready", "ready_for_pickup"),
      order("pickup-ready", "ready_for_pickup", "pickup"),
    ]).map((item) => item.id)).toEqual(["waiting", "cooking", "pickup-ready"]);
  });

  it("clears a newly busy driver from every dispatch card", () => {
    expect(clearAssignedDriverSelections({ first: "driver-a", second: "driver-a", third: "driver-b" }, "driver-a"))
      .toEqual({ third: "driver-b" });
  });
});
