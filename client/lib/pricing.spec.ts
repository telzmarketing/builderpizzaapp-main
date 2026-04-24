import { describe, expect, it } from "vitest";
import { normalizeCrustPriceAddition } from "./pricing";

describe("normalizeCrustPriceAddition", () => {
  it("treats empty and zero crust additions as zero", () => {
    expect(normalizeCrustPriceAddition(undefined, 95)).toBe(0);
    expect(normalizeCrustPriceAddition(null, 95)).toBe(0);
    expect(normalizeCrustPriceAddition(0, 95)).toBe(0);
  });

  it("keeps real crust additions", () => {
    expect(normalizeCrustPriceAddition(5, 95)).toBe(5);
    expect(normalizeCrustPriceAddition(12.5, 95)).toBe(12.5);
  });

  it("treats legacy crust values equal to the product base price as no addition", () => {
    expect(normalizeCrustPriceAddition(95, 95)).toBe(0);
    expect(normalizeCrustPriceAddition(95.001, 95)).toBe(0);
  });
});
