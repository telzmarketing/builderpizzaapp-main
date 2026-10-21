import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { StaticRouter } from "react-router-dom/server";
import { Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useApp } from "@/context/AppContext";
import Product from "./Product";

vi.mock("@/context/AppContext", () => ({ useApp: vi.fn() }));

function renderProduct() {
  return renderToStaticMarkup(<StaticRouter location="/product/test-product"><Routes><Route path="/product/:id" element={<Product />} /></Routes></StaticRouter>);
}

describe("product page direct access", () => {
  beforeEach(() => {
    vi.mocked(useApp).mockReturnValue({ products: [], loading: true, productsLoaded: false, siteContent: { pages: { product: {} } }, multiFlavorsConfig: { pricingRule: "average", maxFlavors: 3 }, customer: null } as ReturnType<typeof useApp>);
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
});
