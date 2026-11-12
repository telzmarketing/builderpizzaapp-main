import { describe, expect, it } from "vitest";
import { getDedicatedConfigurationTab } from "./AdminConfiguracoes";

describe("AdminConfiguracoes route tabs", () => {
  it.each([
    ["/painel/comprovantes-pedidos", "comprovantes"],
    ["/painel/etiquetas-expedicao", "etiquetas-expedicao"],
    ["/painel/etiquetas-insumos", "etiquetas-insumos"],
    ["/painel/dominio", "dominio-https"],
    ["/painel/painel-tv-config", "painel-tv"],
    ["/painel/som", "som"],
    ["/painel/identificacao-parceiros", "identificacao-parceiros"],
  ])("limits %s to its own submodule tab", (pathname, expectedTab) => {
    expect(getDedicatedConfigurationTab(pathname)).toBe(expectedTab);
  });

  it("keeps all submodule tabs for the aggregate configuration route", () => {
    expect(getDedicatedConfigurationTab("/painel/configuracoes")).toBeNull();
  });
});
