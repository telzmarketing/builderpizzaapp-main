import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import ProductRecipeEditor, { RecipeCompositionResult } from "./ProductRecipeEditor";
import type { ApiProduct, RecipeCompositionPreview } from "@/lib/api";

const ingredient = { inventory_item_id: "cheese", name: "Mucarela", quantity: "0.100001", unit_id: "kg", unit_symbol: "kg", component_role: "flavor", position: 0, waste_percent: "0" };
const composition: RecipeCompositionPreview = {
  product_id: "pizza", quantity: 1, complete: false, missing: ["product:other"], recipe_version_ids: ["v1"],
  common_components: [{ ...ingredient, inventory_item_id: "box", name: "Caixa", quantity: "1.000000", unit_symbol: "un", component_role: "packaging" }],
  flavors: [{ product_id: "pizza", name: "Mucarela", fraction: "0.5", ingredients: [ingredient] }], ingredients: [ingredient],
  removed_ingredients: [{ ...ingredient, inventory_item_id: "onion", name: "Cebola" }], substitutions: [], methods: [{ recipe_version_id: "v1", instructions: "Aplicar conforme a ficha", preparation_steps: ["Separar", "Montar"], reference_image_url: null }], notes: null,
};

describe("recipe editor feedback", () => {
  it("renders a protected loading state without showing an empty editor as loaded", () => {
    const product = { id: "pizza", name: "Mucarela" } as ApiProduct;
    const html = renderToStaticMarkup(<ProductRecipeEditor product={product} catalog={[product]} onClose={() => {}} />);
    expect(html).toContain("Carregando fichas, insumos e unidades");
    expect(html).not.toContain("Publicar nova versao");
    expect(html).toContain('aria-modal="true"');
  });
  it("marks partial composition explicitly and preserves backend Decimal output and steps", () => {
    const html = renderToStaticMarkup(<RecipeCompositionResult result={composition} />);
    expect(html).toContain("Composicao incompleta");
    expect(html).toContain("product:other");
    expect(html).toContain("0.100001");
    expect(html).toContain("Componentes comuns");
    expect(html).toContain("Ingredientes removidos");
    expect(html).toContain("Separar");
    expect(html).toContain("Montar");
  });
  it("renders optional missing images and an empty recipe without crashing", () => {
    const html = renderToStaticMarkup(<RecipeCompositionResult result={{ ...composition, complete: true, missing: [], methods: [], common_components: [], flavors: [], ingredients: [], removed_ingredients: [] }} />);
    expect(html).toContain("Composicao completa");
    expect(html).not.toContain("<img");
  });
});
