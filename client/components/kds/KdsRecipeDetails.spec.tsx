import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import KdsRecipeDetails from "./KdsRecipeDetails";
import type { RecipeCompositionPreview } from "@/lib/api";

const recipe: RecipeCompositionPreview = {
  product_id: "pizza", quantity: 1, complete: true, missing: [], recipe_version_ids: ["v1"],
  common_components: [{ inventory_item_id: "dough", name: "Massa", quantity: "0.250000", unit_id: "kg", unit_symbol: "kg", component_role: "base", position: 0, waste_percent: "0" }],
  flavors: [{ product_id: "margherita", name: "Margherita", fraction: "1", ingredients: [{ inventory_item_id: "cheese", name: "Mucarela", quantity: "0.150000", unit_id: "kg", unit_symbol: "kg", component_role: "flavor", position: 1, waste_percent: "0" }] }],
  ingredients: [], removed_ingredients: [], substitutions: [],
  methods: [{ recipe_version_id: "v1", instructions: "Distribuir uniformemente.", preparation_steps: ["Abrir a massa", "Montar o recheio"], reference_image_url: null }], notes: null,
};

describe("KDS recipe details", () => {
  it("renders server quantities, flavors and assembly steps", () => {
    const html = renderToStaticMarkup(<KdsRecipeDetails recipe={recipe} />);
    expect(html).toContain("0.250000");
    expect(html).toContain("Margherita");
    expect(html).toContain("Distribuir uniformemente.");
    expect(html).toContain("Abrir a massa");
  });

  it("keeps missing recipe state explicit", () => {
    const html = renderToStaticMarkup(<KdsRecipeDetails recipe={null} />);
    expect(html).toContain("Ficha técnica ainda não disponível");
  });
});
