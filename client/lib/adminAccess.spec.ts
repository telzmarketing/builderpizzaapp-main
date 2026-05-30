import { describe, expect, it } from "vitest";
import { findAdminNavigationGroup, findAdminNavigationItem } from "./adminAccess";

describe("admin navigation route matching", () => {
  it("uses the most specific route when module paths overlap", () => {
    expect(findAdminNavigationGroup("/painel/salao/pagina")?.label).toBe("Configuracoes");
    expect(findAdminNavigationItem("/painel/salao/pagina")?.label).toBe("Pagina Salao");
  });

  it("resolves navigation aliases to their canonical module", () => {
    expect(findAdminNavigationGroup("/painel/cupons")?.label).toBe("Marketing");
    expect(findAdminNavigationItem("/painel/marketing/ads")?.label).toBe("Trafego Pago");
  });
});
