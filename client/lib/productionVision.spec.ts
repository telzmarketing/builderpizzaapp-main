import { describe, expect, it } from "vitest";
import { normalizeProductionVisionDashboard, normalizeProductionVisionList } from "./productionVision";

describe("normalizeProductionVisionDashboard", () => {
  it("accepts the API envelope and protects missing collections", () => {
    const result = normalizeProductionVisionDashboard({ data: { cameras: [{ id: "cam-1", name: "Montagem" }], metrics: { monitored_orders: 3 } } });
    expect(result.cameras).toHaveLength(1);
    expect(result.metrics?.monitored_orders).toBe(3);
    expect(result.stations).toEqual([]);
    expect(result.history).toEqual([]);
  });

  it("normalizes backend metric names used by the dashboard", () => {
    const result = normalizeProductionVisionDashboard({
      cameras_online: 2,
      sessions_complete: 4,
      sessions_partial: 1,
      photos_captured: 9,
    });
    expect(result.metrics).toMatchObject({
      cameras_online: 2,
      completed_sessions: 4,
      partial_sessions: 1,
      photos_captured: 9,
    });
  });

  it("accepts list responses both wrapped and unwrapped", () => {
    expect(normalizeProductionVisionList<{ id: string }>({ data: [{ id: "camera-1" }] })).toEqual([{ id: "camera-1" }]);
    expect(normalizeProductionVisionList<{ id: string }>(null)).toEqual([]);
  });
});
