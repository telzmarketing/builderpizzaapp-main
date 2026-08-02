import { describe, expect, it } from "vitest";
import {
  activatePlatformSupportSession,
  isPlatformSupportPanelPathAllowed,
  isPlatformSupportSessionActive,
  platformRequestAccessToken,
  readPlatformSupportSession,
  restorePlatformMasterSession,
  shouldLoadRegularAdminPermissions,
} from "./platformSupportSession";

function memoryStorage(initial: Record<string, string> = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
    removeItem: (key: string) => { values.delete(key); },
  };
}

describe("platform support session", () => {
  it("swaps to the scoped token and restores the original Master credentials", () => {
    const local = memoryStorage({
      admin_token: "master-token",
      admin_user: "{\"name\":\"Master\"}",
      admin_permissions: "{\"is_master\":true}",
    });
    const session = memoryStorage();

    activatePlatformSupportSession({
      session_id: "support-1",
      tenant_id: "tenant-1",
      tenant_name: "Empresa Um",
      expires_at: "2030-01-01T00:00:00Z",
      access_token: "scoped-token",
    }, local, session);

    expect(local.getItem("admin_token")).toBe("master-token");
    expect(local.getItem("admin_permissions")).toBeNull();
    expect(readPlatformSupportSession(session)?.master_token).toBe("master-token");
    expect(readPlatformSupportSession(session)?.scoped_token).toBe("scoped-token");
    expect(platformRequestAccessToken(local, session)).toBe("scoped-token");
    expect(restorePlatformMasterSession(local, session)).toBe(true);
    expect(local.getItem("admin_token")).toBe("master-token");
    expect(platformRequestAccessToken(local, session)).toBe("master-token");
    expect(session.getItem("platform_support_session")).toBeNull();
  });

  it("checks expiration from the backend timestamp", () => {
    const state = {
      session_id: "support-1",
      tenant_id: "tenant-1",
      tenant_name: "Empresa Um",
      expires_at: "2030-01-01T00:00:00Z",
      scoped_token: "scoped-token",
      master_token: "master-token",
      master_user: null,
      master_permissions: null,
    };
    expect(isPlatformSupportSessionActive(state, Date.parse("2029-01-01T00:00:00Z"))).toBe(true);
    expect(isPlatformSupportSessionActive(state, Date.parse("2031-01-01T00:00:00Z"))).toBe(false);
  });

  it("allows only panel pages backed by the server support scope", () => {
    expect(isPlatformSupportPanelPathAllowed("/painel/gestao/financeiro")).toBe(true);
    expect(isPlatformSupportPanelPathAllowed("/painel/gestao/financeiro/transacoes")).toBe(true);
    expect(isPlatformSupportPanelPathAllowed("/painel/funcionamento")).toBe(true);
    expect(isPlatformSupportPanelPathAllowed("/painel/orders")).toBe(false);
    expect(isPlatformSupportPanelPathAllowed("/painel/gestao/estoque")).toBe(false);
    expect(isPlatformSupportPanelPathAllowed("/painel/salao")).toBe(false);
    expect(isPlatformSupportPanelPathAllowed("/painel/salao/pagina")).toBe(false);
    expect(isPlatformSupportPanelPathAllowed("/painel/logistica")).toBe(false);
    expect(isPlatformSupportPanelPathAllowed("/painel/whatsapp-gateway")).toBe(false);
    expect(isPlatformSupportPanelPathAllowed("/painel/products")).toBe(false);
    expect(isPlatformSupportPanelPathAllowed("/painel/plataforma")).toBe(false);
  });

  it("never loads the regular RBAC endpoint while a scoped support token is active", () => {
    expect(shouldLoadRegularAdminPermissions(null)).toBe(true);
    expect(shouldLoadRegularAdminPermissions({
      session_id: "support-1",
      tenant_id: "tenant-1",
      tenant_name: "Empresa Um",
      expires_at: "2030-01-01T00:00:00Z",
      scoped_token: "scoped-token",
      master_token: "master-token",
      master_user: null,
      master_permissions: null,
    })).toBe(false);
  });
});
