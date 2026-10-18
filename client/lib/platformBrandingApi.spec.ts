import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { platformBrandingApi } from "./api";

function storage() {
  return { getItem: () => null, removeItem: vi.fn(), setItem: vi.fn() };
}

describe("platform manager branding API", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", storage());
    vi.stubGlobal("sessionStorage", storage());
    vi.stubGlobal("window", { location: { pathname: "/painel/configuracoes-plataforma", replace: vi.fn() } });
  });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it("persists manager logo and favicon using the platform endpoint", async () => {
    const branding = { logo_url: "/api/platform/branding/assets/logo.png", favicon_url: "" };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true, data: branding }), { headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await platformBrandingApi.save(branding)).toEqual(branding);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/api\/admin\/platform\/settings\/branding$/);
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body as string)).toEqual(branding);
  });

  it("uploads multipart content to the dedicated manager route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ data: { url: "/api/platform/branding/assets/new.png" } }), { headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["image"], "logo.png", { type: "image/png" });
    expect(await platformBrandingApi.upload(file)).toBe("/api/platform/branding/assets/new.png");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/api\/admin\/platform\/settings\/branding\/upload$/);
    expect(init.method).toBe("POST");
    expect((init.body as FormData).get("file")).toBeInstanceOf(File);
    expect(new Headers(init.headers).has("Content-Type")).toBe(false);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("preserves forbidden upload errors without retrying a mutation", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Sem permissao para gerenciar a plataforma." }), { status: 403 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(platformBrandingApi.upload(new File(["image"], "logo.png"))).rejects.toMatchObject({ status: 403, message: "Sem permissao para gerenciar a plataforma." });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not report save success or retry on a rejected manager asset", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Imagem nao pertence ao gestor." }), { status: 422 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(platformBrandingApi.save({ logo_url: "/uploads/company.png", favicon_url: "" })).rejects.toMatchObject({ status: 422, message: "Imagem nao pertence ao gestor." });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
