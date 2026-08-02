import { describe, expect, it } from "vitest";
import {
  adminLandingPath,
  isPlatformHostname,
  parsePlatformHostnames,
} from "./platformHost";

describe("platform host routing", () => {
  it("normalizes configured hostnames", () => {
    const hosts = parsePlatformHostnames(" ERP.TELZ.COM.BR.,admin.telz.com.br ");

    expect(isPlatformHostname("erp.telz.com.br", hosts)).toBe(true);
    expect(isPlatformHostname("ADMIN.TELZ.COM.BR.", hosts)).toBe(true);
    expect(isPlatformHostname("loja.telz.com.br", hosts)).toBe(false);
  });

  it("lands platform sessions in company administration", () => {
    expect(adminLandingPath("erp.telz.com.br")).toBe("/painel/plataforma");
    expect(adminLandingPath("loja.exemplo.com.br")).toBe("/painel");
  });
});
