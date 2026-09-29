import { describe, expect, it } from "vitest";
import type { KdsDispatchOrder, KdsKitchenOrder, KdsOverviewOrder } from "./api";
import { activeKitchenOrders, clearAssignedDriverSelections, groupKdsOverviewOrders, replaceDispatchOrder } from "./kds";

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
    delivery: null,
    items: [],
  };
}

describe("KDS state", () => {
  it("moves every ready order out of the kitchen, including pickup", () => {
    expect(activeKitchenOrders([
      order("waiting", "paid"),
      order("cooking", "preparing"),
      order("delivery-ready", "ready_for_pickup"),
      order("pickup-ready", "ready_for_pickup", "pickup"),
    ]).map((item) => item.id)).toEqual(["waiting", "cooking"]);
  });

  it("clears a newly busy driver from every dispatch card", () => {
    expect(clearAssignedDriverSelections({ first: "driver-a", second: "driver-a", third: "driver-b" }, "driver-a"))
      .toEqual({ third: "driver-b" });
  });

  it("keeps an assigned order visible with its updated dispatch state", () => {
    const before = { ...order("dispatch", "ready_for_pickup"), can_assign_driver: true } as KdsDispatchOrder;
    const after = {
      ...before,
      can_assign_driver: false,
      delivery: { id: "delivery-1", status: "assigned", delivery_person_name: "Maria" },
    };

    expect(replaceDispatchOrder([before], after)).toEqual([after]);
  });

  it("groups the general panel orders by the backend stage", () => {
    const overviewOrders = [
      { id: "a", stage: "waiting_kitchen" },
      { id: "b", stage: "in_route" },
      { id: "c", stage: "waiting_kitchen" },
    ] as KdsOverviewOrder[];

    const grouped = groupKdsOverviewOrders(overviewOrders);
    expect(grouped.waiting_kitchen.map((item) => item.id)).toEqual(["a", "c"]);
    expect(grouped.in_route.map((item) => item.id)).toEqual(["b"]);
    expect(grouped.preparing).toEqual([]);
  });
});
