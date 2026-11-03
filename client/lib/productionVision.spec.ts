import { describe, expect, it } from "vitest";
import { normalizeProductionVisionDashboard } from "./productionVision";

describe("normalizeProductionVisionDashboard", () => {
  it("accepts the API envelope and protects missing collections", () => {
    const result = normalizeProductionVisionDashboard({ data: { cameras: [{ id: "cam-1", name: "Montagem" }], metrics: { monitored_orders: 3 } } });
    expect(result.cameras).toHaveLength(1);
    expect(result.metrics?.monitored_orders).toBe(3);
    expect(result.stations).toEqual([]);
    expect(result.history).toEqual([]);
  });
});
