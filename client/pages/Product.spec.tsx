import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { StaticRouter } from "react-router-dom/server";
import { Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useApp } from "@/context/AppContext";
import Product, { filterFlavorCandidates, getFlavorSubcategories } from "./Product";

vi.mock("@/context/AppContext", () => ({ useApp: vi.fn() }));

function renderProduct() {
  return renderToStaticMarkup(<StaticRouter location="/product/test-product"><Routes><Route path="/product/:id" element={<Product />} /></Routes></StaticRouter>);
}

describe("product page direct access", () => {
  beforeEach(() => {
    vi.mocked(useApp).mockReturnValue({ products: [], loading: true, productsLoaded: false, siteContent: { pages: { product: {} } }, multiFlavorsConfig: { pricingRule: "average", maxFlavors: 3 }, customer: null } as ReturnType<typeof useApp>);
  });

  it("keeps flavor subcategories in catalog order and filters by search or subcategory", () => {
    const candidates = [
      { id: "classic-1", name: "Margherita", description: "Molho e queijo", category: "Pizzas", subcategory: "Clássicas" },
      { id: "special-1", name: "Baiana", description: "Calabresa picante", category: "Pizzas", subcategory: "Especiais" },
      { id: "classic-2", name: "Quatro Queijos", description: "Queijo cremoso", category: "Pizzas", subcategory: "Clássicas" },
    ] as unknown as Parameters<typeof getFlavorSubcategories>[0];

    expect(getFlavorSubcategories(candidates)).toEqual(["Clássicas", "Especiais"]);
    expect(filterFlavorCandidates(candidates, "picante").map((candidate) => candidate.id)).toEqual(["special-1"]);
    expect(filterFlavorCandidates(candidates, "", "Clássicas").map((candidate) => candidate.id)).toEqual(["classic-1", "classic-2"]);
  });

  it("renders loading before any products arrive without crashing", () => {
    expect(renderProduct()).toContain("Carregando produto");
  });

  it("renders an absent product after loading without crashing", () => {
    vi.mocked(useApp).mockReturnValue({ ...useApp(), loading: false } as ReturnType<typeof useApp>);
    expect(renderProduct()).toContain("Produto não encontrado");
  });

  it("waits for validated options and quote before enabling purchase", () => {
    vi.mocked(useApp).mockReturnValue({ ...useApp(), loading: false, products: [{ id: "test-product", name: "Agua", description: "Agua mineral", product_type: "drink", price: 5, icon: "💧", active: true, inventory_available: true }] } as ReturnType<typeof useApp>);
    const html = renderProduct();
    expect(html).toContain("Carregando opcoes");
    expect(html).toMatch(/disabled=""/);
  });

  it("reuses configuration inside operator flow without public navigation", () => {
    const product = { id: "operator-product", name: "Agua", description: "Agua mineral", product_type: "drink", price: 5, icon: "💧", active: true };
    const html = renderToStaticMarkup(<StaticRouter location="/operacoes/novo-pedido"><Product productId="operator-product" catalog={[product as never]} embedded onBack={() => {}} onAdd={() => {}} /></StaticRouter>);
    expect(html).toContain("Configurar produto");
    expect(html).toContain("Voltar ao catálogo");
    expect(html).not.toContain("Ir para a home da loja");
    expect(html).not.toContain('href="/cart"');
  });
});
