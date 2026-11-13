import { describe, expect, it } from "vitest";
import { isLocalPrintOrderHomologationPath } from "./localPrintOrderHomologation";

describe("local Print Pedido homologation route", () => {
  const base = {
    dev: true,
    hostname: "localhost",
    pathname: "/operacoes/print-pedido",
  };

  it("allows the exact local development route", () => {
    expect(isLocalPrintOrderHomologationPath(base)).toBe(true);
    expect(isLocalPrintOrderHomologationPath({ ...base, pathname: "/operacoes/print-pedido/" })).toBe(true);
    expect(isLocalPrintOrderHomologationPath({ ...base, pathname: "/painel/crm/agente-whatsapp" })).toBe(true);
    expect(isLocalPrintOrderHomologationPath({ ...base, pathname: "/painel/crm/agente-whatsapp/" })).toBe(true);
  });

  it("does not allow production builds or other hosts", () => {
    expect(isLocalPrintOrderHomologationPath({ ...base, dev: false })).toBe(false);
    expect(isLocalPrintOrderHomologationPath({ ...base, hostname: "127.0.0.1" })).toBe(true);
    expect(isLocalPrintOrderHomologationPath({ ...base, hostname: "erp.example.com" })).toBe(false);
  });

  it("does not broaden the exception to other paths", () => {
    expect(isLocalPrintOrderHomologationPath({ ...base, pathname: "/painel/plataforma" })).toBe(false);
    expect(isLocalPrintOrderHomologationPath({ ...base, pathname: "/operacoes/novo-pedido" })).toBe(false);
    expect(isLocalPrintOrderHomologationPath({ ...base, pathname: "/painel/crm/agente-whatsapp/sessoes" })).toBe(false);
  });
});
