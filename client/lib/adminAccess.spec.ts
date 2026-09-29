import { describe, expect, it } from "vitest";
import { filterAdminNavigation, findAdminNavigationGroup, findAdminNavigationItem, firstAllowedAdminPath } from "./adminAccess";
import type { ApiEffectivePermissions } from "./api";

describe("admin navigation route matching", () => {
  it("uses the most specific route when module paths overlap", () => {
    expect(findAdminNavigationGroup("/painel/salao/pagina")?.label).toBe("Configuracoes");
    expect(findAdminNavigationItem("/painel/salao/pagina")?.label).toBe("Pagina Salao");
  });

  it("resolves navigation aliases to their canonical module", () => {
    expect(findAdminNavigationGroup("/painel/cupons")?.label).toBe("Marketing");
    expect(findAdminNavigationItem("/painel/marketing/ads")?.label).toBe("Trafego Pago");
  });

  it.each([
    ["cozinha", "/painel/cozinha", "KDS Cozinha"],
    ["expedicao", "/painel/expedicao", "KDS Expedição"],
  ])("keeps the %s KDS profile on its only allowed screen", (moduleKey, path, label) => {
    const permissions: ApiEffectivePermissions = {
      is_master: false,
      modules: { [moduleKey]: { view: true, edit: true } },
    };
    expect(firstAllowedAdminPath(permissions)).toBe(path);
    expect(filterAdminNavigation(permissions).flatMap((group) => group.children.map((item) => item.label)))
      .toEqual([label]);
  });

  it("keeps the KDS overview and motoboy room under the orders permission", () => {
    const permissions: ApiEffectivePermissions = {
      is_master: false,
      modules: { pedidos: { view: true, edit: false } },
    };

    const kdsItems = filterAdminNavigation(permissions)
      .find((group) => group.label === "KDS")
      ?.children.map((item) => item.path);

    expect(kdsItems).toEqual(["/painel/kds", "/painel/kds/sala-motoboy"]);
  });
});
