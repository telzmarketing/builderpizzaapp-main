import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { gestorApi } from "./api";

function storage() {
  const values = new Map<string, string>();
  return { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value), removeItem: (key: string) => values.delete(key) };
}

describe("Gestor IA API", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", storage());
    vi.stubGlobal("sessionStorage", storage());
    vi.stubGlobal("window", { location: { pathname: "/painel/gestor", replace: vi.fn() } });
  });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it("loads the administrative dashboard from the dedicated Gestor endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ metrics: { conversations_open: 2 } }), { headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await gestorApi.dashboard();
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/api\/gestor\/dashboard$/);
    expect(fetchMock.mock.calls[0][0]).not.toMatch(/agente-whatsapp/);
  });

  it("keeps AI settings and channel mutations on the dedicated Gestor routes", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "ai-1" }), { headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "channel-1" }), { headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await gestorApi.updateAISettings({ provider: "internal", writes_enabled: false });
    await gestorApi.updateChannel({ enabled: true, app_secret_ref: "env:GESTOR_META_APP_SECRET_PROD" });
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/api\/gestor\/ai\/settings$/);
    expect(fetchMock.mock.calls[1][0]).toMatch(/\/api\/gestor\/whatsapp\/channel$/);
    expect(JSON.parse(String(fetchMock.mock.calls[1][1].body))).not.toHaveProperty("secret");
  });
});
