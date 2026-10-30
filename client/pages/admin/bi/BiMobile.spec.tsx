import { afterEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import BiMobile from "./BiMobile";

const query = vi.hoisted(() => ({
  data: null,
  loading: true,
  refreshing: false,
  error: null as string | null,
  refresh: vi.fn(),
}));
vi.mock("@/components/bi/useBiMobileAnalytics", () => ({
  useBiMobileAnalytics: () => query,
}));
vi.mock("@/context/AppContext", () => ({
  useApp: () => ({ siteContent: { brand: { name: "Pizzaria Teste", logo: "/uploads/pizzaria-logo.png" } } }),
}));

describe("BI mobile initial navigation and failure states", () => {
  afterEach(() => {
    query.loading = true;
    query.error = null;
    vi.useRealTimers();
  });

  it("opens Pedidos and keeps the four tabs immediately below the date filter", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-28T01:00:00Z"));
    const html = renderToStaticMarkup(<BiMobile />);
    expect(html).toContain('id="bi-mobile-date"');
    expect(html).toContain('max="2026-10-27"');
    expect(html).toContain('value="2026-10-27"');
    expect(html.match(/role="tab"/g)).toHaveLength(4);
    expect(html).toMatch(/id="bi-tab-orders"[^>]*aria-selected="true"/);
    for (const label of ["Pedidos", "Atendimento", "Evolução", "Geral"])
      expect(html).toContain(label);
    expect(html.indexOf('id="bi-mobile-date"')).toBeLessThan(
      html.indexOf('role="tablist"'),
    );
    expect(html).toContain('alt="Logo de Pizzaria Teste"');
    expect(html).toContain("Resumo operacional responsivo");
  });

  it("does not display zero metrics while the API is loading", () => {
    const html = renderToStaticMarkup(<BiMobile />);
    expect(html).toContain("Carregando indicadores reais...");
    expect(html).not.toContain("Pedidos do dia");
    expect(html).not.toContain("Receita confirmada / pedidos pagos");
  });

  it("shows the API failure and a retry action without zero sales", () => {
    query.loading = false;
    query.error = "Sem conexão com a API";
    const html = renderToStaticMarkup(<BiMobile />);
    expect(html).toContain('role="alert"');
    expect(html).toContain("Sem conexão com a API");
    expect(html).toContain("Tentar novamente");
    expect(html).not.toContain("Pedidos do dia");
  });
});
