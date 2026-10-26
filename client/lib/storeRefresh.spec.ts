import { describe, expect, it } from "vitest";
import { getStoreRefreshPlan } from "./storeRefresh";
import { optionalMetric } from "./marketingMetrics";

describe("storefront synchronization", () => {
  it("refreshes pricing configuration together with the product being configured", () => {
    expect(getStoreRefreshPlan("/product/pizza-1")).toEqual({ products: true, campaignBanners: false, multiFlavorsConfig: true });
  });
  it.each(["/", "/menu", "/cardapio"])("refreshes the live catalog on %s", (path) => {
    expect(getStoreRefreshPlan(path).products).toBe(true);
  });
  it.each(["/painel", "/painel/products", "/motoboy", "/tv/motoboys"])("does not load public catalog on %s", (path) => {
    expect(Object.values(getStoreRefreshPlan(path)).some(Boolean)).toBe(false);
  });
});

describe("unavailable marketing metrics", () => {
  it("distinguishes metrics absent from the API from an observed zero", () => {
    expect(optionalMetric(undefined)).toBe("Indisponível");
    expect(optionalMetric(null, true)).toBe("Indisponível");
    expect(optionalMetric(0)).toBe("0");
    expect(optionalMetric(0, true)).toBe("0.0%");
    expect(optionalMetric(0.25, true)).toBe("25.0%");
  });
});
