import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { pcpApi, type ApiEffectivePermissions } from "./api";
import { canManagePcp } from "@/components/admin/PcpWeeklyPanel";

describe("weekly PCP contracts", () => {
  beforeEach(() => {
    const storage = { getItem: (key: string) => key === "admin_token" ? "manager-token" : null, removeItem: vi.fn(), setItem: vi.fn() };
    vi.stubGlobal("localStorage", storage); vi.stubGlobal("sessionStorage", storage);
    vi.stubGlobal("window", { location: { pathname: "/painel/gestao/inventory", replace: vi.fn() } });
  });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it("consults and generates the canonical weekly forecast without client estimates", async () => {
    const fetchMock = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ data: { suggestions: [] } }), { headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await pcpApi.get("2026-10-26");
    await pcpApi.generate({ week_start: "2026-10-26", source_weeks: 4 });
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/api\/pcp\/weekly\/2026-10-26$/);
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ week_start: "2026-10-26", source_weeks: 4 });
    expect(new Headers(fetchMock.mock.calls[1][1].headers).get("Authorization")).toBe("Bearer manager-token");
  });

  it("approves only the actual loaded status and never posts stock/preparation movements", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ data: { status: "approved" } }), { headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await pcpApi.approve("2026-10-26", "draft");
    expect(fetchMock.mock.calls).toHaveLength(1);
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/pcp\/weekly\/2026-10-26\/approve$/);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ expected_status: "draft" });
  });

  it("does not offer manager actions to inventory viewers or editors", () => {
    expect(canManagePcp(null)).toBe(false);
    expect(canManagePcp({ modules: { inventory: { view: true, edit: true } } } as unknown as ApiEffectivePermissions)).toBe(false);
    expect(canManagePcp({ modules: { inventory: { manage: true } } } as unknown as ApiEffectivePermissions)).toBe(true);
  });
});
