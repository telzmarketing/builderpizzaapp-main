import { afterEach, describe, expect, it, vi } from "vitest";
import { crustApi } from "./api";

afterEach(() => vi.unstubAllGlobals());

function mockApi(data: unknown = []) {
  vi.stubGlobal("localStorage", { getItem: () => null });
  vi.stubGlobal("sessionStorage", { getItem: () => null });
  const fetchMock = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ data }), {
    headers: { "Content-Type": "application/json" },
  }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("massas e bordas no contrato de catálogo", () => {
  it("preserva a consulta pública sem filtro para carregar ambos os tipos", async () => {
    const fetchMock = mockApi();
    await crustApi.list("pizza");
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/products\/pizza\/crusts$/);
  });

  it.each(["dough", "border"] as const)("filtra o painel por %s e inclui inativos", async (kind) => {
    const fetchMock = mockApi();
    await crustApi.list("pizza", false, kind);
    const url = new URL(fetchMock.mock.calls[0][0], "https://example.test");
    expect(url.searchParams.get("active_only")).toBe("false");
    expect(url.searchParams.get("option_kind")).toBe(kind);
  });

  it("permite filtrar bordas ativas na consulta pública", async () => {
    const fetchMock = mockApi();
    await crustApi.list("pizza", true, "border");
    const url = new URL(fetchMock.mock.calls[0][0], "https://example.test");
    expect(url.searchParams.get("option_kind")).toBe("border");
    expect(url.searchParams.has("active_only")).toBe(false);
  });

  it.each(["dough", "border"] as const)("envia e preserva %s ao cadastrar e editar", async (kind) => {
    const input = { name: "Opção", option_kind: kind, price_addition: 14, active: true, sort_order: 0 };
    const saved = { ...input, id: "option", product_id: "pizza", created_at: "2026-10-30" };
    const fetchMock = mockApi(saved);
    expect(await crustApi.create("pizza", input)).toEqual(saved);
    expect(await crustApi.update("pizza", "option", { option_kind: kind, price_addition: 15 })).toEqual(saved);
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual(input);
    expect(fetchMock.mock.calls[1][1].method).toBe("PUT");
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ option_kind: kind, price_addition: 15 });
  });
});
