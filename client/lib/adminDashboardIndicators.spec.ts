import { describe, expect, it } from "vitest";
import { dashboardRevenueData, hasDashboardRevenueData } from "./adminDashboardIndicators";

describe("admin dashboard indicators", () => {
  it("does not create a chart when the API has no daily revenue", () => {
    expect(hasDashboardRevenueData([])).toBe(false);
    expect(hasDashboardRevenueData([{ day: "2026-10-29", revenue: 125 }])).toBe(true);
    expect(dashboardRevenueData([])).toEqual([]);
    expect(dashboardRevenueData([{ day: "2026-10-29", revenue: 125 }])).toHaveLength(7);
  });
});
