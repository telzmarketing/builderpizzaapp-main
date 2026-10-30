import { describe, expect, it } from "vitest";
import { toggleAdminTheme } from "./adminTheme";

describe("admin theme", () => {
  it("toggles only between the two panel themes", () => {
    expect(toggleAdminTheme("dark")).toBe("light");
    expect(toggleAdminTheme("light")).toBe("dark");
  });
});
