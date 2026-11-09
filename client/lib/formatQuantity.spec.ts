import { describe, expect, it } from "vitest";
import { formatQuantity } from "./formatQuantity";

describe("formatQuantity", () => {
  it("removes trailing zeroes", () => {
    expect(formatQuantity("150.000000")).toBe("150");
  });

  it("preserves meaningful decimals", () => {
    expect(formatQuantity("1.250000")).toBe("1,25");
  });

  it("supports comma input", () => {
    expect(formatQuantity("0,125000")).toBe("0,125");
  });

  it("uses fallback for invalid values", () => {
    expect(formatQuantity("abc")).toBe("-");
  });
});
