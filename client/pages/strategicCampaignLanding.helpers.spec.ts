import { describe, expect, it } from "vitest";
import { immediateChoiceEnabled, shouldKeepAvailabilityStep } from "./strategicCampaignLanding.helpers";

describe("strategic campaign landing availability", () => {
  it("disables immediate sales while the store is closed or status is loading", () => {
    expect(immediateChoiceEnabled("immediate", { is_open: false }, false)).toBe(false);
    expect(immediateChoiceEnabled("hybrid", { is_open: false }, false)).toBe(false);
    expect(immediateChoiceEnabled("immediate", { is_open: true }, true)).toBe(false);
    expect(immediateChoiceEnabled("immediate", { is_open: true }, false)).toBe(true);
  });

  it("keeps the availability step for closed stores and scheduled modes", () => {
    expect(shouldKeepAvailabilityStep("immediate", false, false)).toBe(true);
    expect(shouldKeepAvailabilityStep("immediate", true, false)).toBe(false);
    expect(shouldKeepAvailabilityStep("preorder", true, false)).toBe(true);
    expect(shouldKeepAvailabilityStep("hybrid", true, false)).toBe(true);
    expect(shouldKeepAvailabilityStep("immediate", true, true)).toBe(true);
  });
});
