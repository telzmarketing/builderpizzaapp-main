import { afterEach, describe, expect, it, vi } from "vitest";
import { cartStorageKey, safeCheckoutReturnPath, tenantStorageScope } from "./AppContext";

describe("customer cart persistence scope", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("creates a tenant-safe cart key from the current host and tenant", () => {
    vi.stubGlobal("window", {
      location: { host: "loja.example.test", origin: "https://loja.example.test" },
    });
    vi.stubGlobal("sessionStorage", { getItem: () => null });

    expect(tenantStorageScope()).toBe("loja.example.test:public");
    expect(cartStorageKey()).toBe("telz:cart:v2:loja.example.test:public");
    expect(cartStorageKey("other.example.test:tenant-2")).toBe(
      "telz:cart:v2:other.example.test:tenant-2",
    );
  });

  it("keeps only same-origin return paths and preserves campaign query context", () => {
    vi.stubGlobal("window", {
      location: { origin: "https://loja.example.test" },
    });

    expect(safeCheckoutReturnPath("/checkout?campaign=black-friday&offer=1")).toBe(
      "/checkout?campaign=black-friday&offer=1",
    );
    expect(safeCheckoutReturnPath("https://loja.example.test/checkout?step=address")).toBe(
      "/checkout?step=address",
    );
    expect(safeCheckoutReturnPath("https://evil.example/steal")).toBeNull();
  });
});
