import { describe, expect, it } from "vitest";
import {
  platformLicenseActionNeedsDays,
  platformLicenseActionsForStatus,
} from "./platformLicense";

describe("platform license actions", () => {
  it("offers only transitions accepted by each backend state", () => {
    expect(platformLicenseActionsForStatus("trial")).toContain("convert");
    expect(platformLicenseActionsForStatus("trial")).not.toContain("start_trial");
    expect(platformLicenseActionsForStatus("active")).toContain("grace");
    expect(platformLicenseActionsForStatus("expired")).toContain("start_trial");
    expect(platformLicenseActionsForStatus("cancelled")).toEqual(["renew", "start_trial", "courtesy"]);
    expect(platformLicenseActionsForStatus("blocked")).toContain("reactivate");
  });

  it("requires days for duration actions and expired reactivation", () => {
    expect(platformLicenseActionNeedsDays("extend", { expires_at: null })).toBe(true);
    expect(platformLicenseActionNeedsDays("convert", { expires_at: null })).toBe(false);
    expect(platformLicenseActionNeedsDays(
      "reactivate",
      { expires_at: "2025-01-01T00:00:00Z" },
      Date.parse("2026-01-01T00:00:00Z"),
    )).toBe(true);
    expect(platformLicenseActionNeedsDays(
      "reactivate",
      { expires_at: "2027-01-01T00:00:00Z" },
      Date.parse("2026-01-01T00:00:00Z"),
    )).toBe(false);
  });
});
