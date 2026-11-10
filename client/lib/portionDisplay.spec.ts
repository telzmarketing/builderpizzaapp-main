import { describe, expect, it } from "vitest";
import { formatPortionIngredient, formatPortionTitle, formatRequestedPortions } from "./portionDisplay";

describe("portion display labels", () => {
  const config = { source_item_name: "Brócolis", portion_weight: 80, unit_symbol: "GR", size: "Grande" };

  it("shows the configured weight instead of the converted source fraction", () => {
    expect(formatPortionTitle(config, "Brócolis - porção 8E+1 GR - Grande")).toBe("Brócolis - porção 80 GR - Grande");
    expect(formatPortionIngredient({ portion_weight: 80, unit_symbol: "GR" }, "0.16", "CBÇ")).toBe("80 GR");
  });

  it("labels the requested quantity as portions", () => {
    expect(formatRequestedPortions("20")).toBe("20 porções");
  });
});
