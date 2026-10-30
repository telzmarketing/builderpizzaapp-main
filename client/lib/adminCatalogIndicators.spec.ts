import { describe, expect, it } from "vitest";
import { catalogProductsSummary, displayCatalogCount } from "./adminCatalogIndicators";

describe("admin catalog indicators", () => {
  it("hides counts while loading, after errors, and for empty lists", () => {
    expect(displayCatalogCount(8, false)).toBeNull();
    expect(displayCatalogCount(8, true)).toBe("8");
    expect(displayCatalogCount(0, true)).toBeNull();
  });

  it("uses an explicit non-numeric empty/loading summary", () => {
    expect(catalogProductsSummary(0, false)).toBe("Carregando produtos...");
    expect(catalogProductsSummary(0, true)).toBe("Nenhum produto nesta visualizacao");
    expect(catalogProductsSummary(1, true)).toBe("1 produto nesta visualizacao");
  });
});
