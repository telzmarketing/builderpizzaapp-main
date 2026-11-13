import { describe, expect, it } from "vitest";
import { adminPreloadRoutes } from "./adminRoutePreload";

describe("admin route preload coverage", () => {
  it("preloads every AdminConfiguracoes consumer route", () => {
    expect(adminPreloadRoutes).toEqual(expect.arrayContaining([
      "/painel/comprovantes-pedidos",
      "/painel/etiquetas-expedicao",
      "/painel/etiquetas-insumos",
      "/painel/dominio",
      "/painel/painel-tv-config",
      "/painel/som",
      "/painel/identificacao-parceiros",
      "/painel/configuracoes/ia-central",
      "/painel/configuracoes",
    ]));
  });
});
