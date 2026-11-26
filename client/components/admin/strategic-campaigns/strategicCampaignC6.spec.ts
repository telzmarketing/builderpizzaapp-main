import { describe, expect, it } from "vitest";
import {
  availableCapacity,
  canConfirmReservation,
  canReleaseReservation,
  validateReservationAmounts,
} from "./strategicCampaignC6";

describe("strategic campaign C6 helpers", () => {
  it("calculates available capacity without returning a negative value", () => {
    expect(availableCapacity({ capacity_total: 12, capacity_used: 5 })).toBe(7);
    expect(availableCapacity({ capacity_total: 3, capacity_used: 4 })).toBe(0);
  });

  it("allows only supported reservation transitions", () => {
    expect(canConfirmReservation({ status: "held" })).toBe(true);
    expect(canConfirmReservation({ status: "confirmed" })).toBe(false);
    expect(canReleaseReservation({ status: "held" })).toBe(true);
    expect(canReleaseReservation({ status: "confirmed" })).toBe(true);
    expect(canReleaseReservation({ status: "expired" })).toBe(false);
  });

  it("validates each payment mode before sending the request", () => {
    expect(validateReservationAmounts("no_payment", 100, 0)).toBeNull();
    expect(validateReservationAmounts("partial", 100, 40)).toBeNull();
    expect(validateReservationAmounts("full", 100, 100)).toBeNull();
    expect(validateReservationAmounts("no_payment", 100, 1)).toContain("igual a zero");
    expect(validateReservationAmounts("partial", 100, 100)).toContain("menor que o total");
    expect(validateReservationAmounts("full", 100, 90)).toContain("igual ao valor total");
  });
});
