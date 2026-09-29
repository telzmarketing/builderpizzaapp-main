import { describe, expect, it } from "vitest";
import {
  elapsedSeconds, formatBoardDuration, groupBoardOrders, isBoardOrderLate,
  normalizeBoardOrders, visiblePage, type OrderBoardDeliveryOrder,
} from "./orderBoard";
import type { OrderBoardSnapshot } from "./api";

const order = (id: string, status: string, started = "2026-09-27T12:00:00Z"): OrderBoardDeliveryOrder => ({
  id,
  code: id,
  order_code: id,
  status,
  created_at: started,
  status_started_at: started,
  delivery: {
    provider_key: "own",
    provider_label: "Motoboy Próprio",
    driver_name: "Carlos Silva",
  },
});

describe("order board domain helpers", () => {
  it("derives exactly the two TV columns from official statuses", () => {
    const grouped = groupBoardOrders([
      order("1", "paid"),
      order("1", "preparing"),
      order("2", "ready_for_pickup"),
      order("3", "on_the_way"),
      order("4", "cancelled"),
    ]);
    expect(grouped.waiting.map((item) => item.id)).toEqual(["1"]);
    expect(grouped.ready.map((item) => item.id)).toEqual(["2"]);
  });

  it("deduplicates and sorts the oldest status transition first", () => {
    expect(normalizeBoardOrders([
      order("2", "preparing", "2026-09-27T12:01:00Z"),
      order("1", "preparing"),
      order("1", "preparing"),
    ]).map((item) => item.id)).toEqual(["1", "2"]);
    expect(elapsedSeconds("2026-09-27T12:00:00Z", Date.parse("2026-09-27T12:07:32Z"))).toBe(452);
    expect(formatBoardDuration(452)).toBe("07:32");
    expect(formatBoardDuration(3_661)).toBe("01:01:01");
  });

  it("uses server settings for late state and stable automatic pages", () => {
    const snapshot = { settings: { production_sla_minutes: 20, dispatch_sla_minutes: 5 } } as OrderBoardSnapshot;
    expect(isBoardOrderLate(order("1", "preparing"), snapshot, Date.parse("2026-09-27T12:21:00Z"))).toBe(true);
    expect(isBoardOrderLate(order("2", "ready_for_pickup"), snapshot, Date.parse("2026-09-27T12:04:59Z"))).toBe(false);
    expect(visiblePage([1, 2, 3, 4, 5], 1, 2)).toEqual([3, 4]);
    expect(visiblePage([1, 2, 3, 4, 5], 3, 2)).toEqual([1, 2]);
  });
});
