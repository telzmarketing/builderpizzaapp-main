import { describe, expect, it } from "vitest";
import {
  firstAllowedPlatformPath,
  platformItemAllowed,
  platformItemMatchesPath,
  platformNavigationGroups,
} from "./platformNavigation";
import { getPlatformPageMeta } from "./platformPageMeta";

describe("platform master navigation", () => {
  it("exposes paths only for entries backed by real pages", () => {
    const items = platformNavigationGroups.flatMap((group) => group.items);

    expect(items.filter((item) => item.available).every((item) => !!item.path)).toBe(true);
    expect(items.filter((item) => !item.available).every((item) => !item.path)).toBe(true);
  });

  it("keeps company details inside the company navigation item", () => {
    const companies = platformNavigationGroups[0].items.find((item) => item.label === "Empresas");

    expect(companies).toBeDefined();
    expect(platformItemMatchesPath(companies!, "/painel/empresas/tenant-123")).toBe(true);
  });

  it("resolves dynamic company detail metadata", () => {
    const meta = getPlatformPageMeta("/painel/empresas/tenant-123");

    expect(meta.title).toBe("Detalhes da empresa");
    expect(meta.eyebrow).toContain("Empresas");
  });

  it("links billing navigation to the functional billing overview", () => {
    const billing = platformNavigationGroups[0].items.find((item) => item.label === "Cobrancas");

    expect(billing).toMatchObject({ available: true, path: "/painel/cobrancas" });
    expect(getPlatformPageMeta("/painel/cobrancas").title).toBe("Cobrancas");
  });

  it("links platform users to the dedicated read-only page", () => {
    const users = platformNavigationGroups[0].items.find(
      (item) => item.label === "Usuarios da plataforma",
    );

    expect(users).toMatchObject({
      available: true,
      path: "/painel/usuarios-plataforma",
    });
    expect(getPlatformPageMeta("/painel/usuarios-plataforma").title).toBe(
      "Usuarios da plataforma",
    );
  });

  it("links platform settings to the dedicated read-only page", () => {
    const settings = platformNavigationGroups[0].items.find(
      (item) => item.label === "Configuracoes",
    );

    expect(settings).toMatchObject({
      available: true,
      path: "/painel/configuracoes-plataforma",
    });
    expect(getPlatformPageMeta("/painel/configuracoes-plataforma").title).toBe(
      "Configuracoes",
    );
  });

  it("publishes every monitoring page with its backend capability", () => {
    const monitoring = platformNavigationGroups.find((group) => group.label === "Monitoramento");

    expect(monitoring?.items.map(({ label, path, permissionKey, available }) => ({
      label,
      path,
      permissionKey,
      available,
    }))).toEqual([
      { label: "Saude dos servicos", path: "/painel/saude-servicos", permissionKey: "monitoring.view", available: true },
      { label: "Integracoes", path: "/painel/integracoes-plataforma", permissionKey: "integrations.view", available: true },
      { label: "Filas e jobs", path: "/painel/filas-jobs", permissionKey: "jobs.view", available: true },
      { label: "WhatsApp Gateway", path: "/painel/whatsapp-gateway-plataforma", permissionKey: "gateway.view", available: true },
      { label: "Erros", path: "/painel/erros-plataforma", permissionKey: "errors.view", available: true },
      { label: "Armazenamento", path: "/painel/armazenamento-plataforma", permissionKey: "storage.view", available: true },
      { label: "Backups", path: "/painel/backups-plataforma", permissionKey: "backups.view", available: true },
    ]);
  });

  it("fails closed for routes whose backend capability is absent", () => {
    const allItems = platformNavigationGroups.flatMap((group) => group.items);
    const dashboard = allItems.find((item) => item.path === "/painel/plataforma")!;
    const health = allItems.find((item) => item.path === "/painel/saude-servicos")!;

    expect(platformItemAllowed(dashboard, [])).toBe(false);
    expect(platformItemAllowed(dashboard, ["tenants.view"])).toBe(true);
    expect(platformItemAllowed(health, [])).toBe(false);
    expect(platformItemAllowed(health, ["monitoring.view"])).toBe(true);
  });

  it("maps every published base page to the matching backend RBAC capability", () => {
    const platform = platformNavigationGroups.find((group) => group.label === "Plataforma")!;
    const permissionsByPath = Object.fromEntries(
      platform.items.map((item) => [item.path, item.permissionKey]),
    );

    expect(permissionsByPath).toMatchObject({
      "/painel/plataforma": "tenants.view",
      "/painel/empresas": "tenants.view",
      "/painel/planos": "tenants.view",
      "/painel/modulos": "tenants.view",
      "/painel/cobrancas": "tenants.view",
      "/painel/dominios": "tenants.view",
      "/painel/usuarios-plataforma": "platform_users.view",
      "/painel/suporte": "support.impersonate",
      "/painel/auditoria": "audit.view",
      "/painel/configuracoes-plataforma": "platform_settings.view",
    });
  });

  it("selects a permitted monitoring landing page for monitor-only operators", () => {
    expect(firstAllowedPlatformPath(["monitoring.view"])).toBe("/painel/saude-servicos");
    expect(firstAllowedPlatformPath(["errors.view"])).toBe("/painel/erros-plataforma");
    expect(firstAllowedPlatformPath([])).toBeUndefined();
  });

  it("does not expose storage or backups to the support capability set", () => {
    const supportCapabilities = [
      "monitoring.view",
      "integrations.view",
      "jobs.view",
      "gateway.view",
      "errors.view",
    ];
    const items = platformNavigationGroups.flatMap((group) => group.items);

    expect(platformItemAllowed(items.find((item) => item.label === "Erros")!, supportCapabilities)).toBe(true);
    expect(platformItemAllowed(items.find((item) => item.label === "Armazenamento")!, supportCapabilities)).toBe(false);
    expect(platformItemAllowed(items.find((item) => item.label === "Backups")!, supportCapabilities)).toBe(false);
  });

  it.each([
    ["/painel/saude-servicos", "Saude dos servicos"],
    ["/painel/integracoes-plataforma", "Integracoes"],
    ["/painel/filas-jobs", "Filas e jobs"],
    ["/painel/whatsapp-gateway-plataforma", "WhatsApp Gateway"],
    ["/painel/erros-plataforma", "Erros"],
    ["/painel/armazenamento-plataforma", "Armazenamento"],
    ["/painel/backups-plataforma", "Backups"],
  ])("resolves metadata for %s", (path, title) => {
    expect(getPlatformPageMeta(path).title).toBe(title);
  });
});
