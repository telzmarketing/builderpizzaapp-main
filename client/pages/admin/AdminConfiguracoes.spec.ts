import { describe, expect, it } from "vitest";
import { isDomainOnlyConfigurationRoute } from "./AdminConfiguracoes";

describe("AdminConfiguracoes domain route", () => {
  it("limits the submodule tabs to Domain and HTTPS", () => {
    expect(isDomainOnlyConfigurationRoute("/painel/dominio")).toBe(true);
  });

  it("keeps the shared tabs for the other configuration routes", () => {
    expect(isDomainOnlyConfigurationRoute("/painel/comprovantes-pedidos")).toBe(false);
  });
});
