import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import {
  BiMetrics,
  SalesTooltip,
  biMoney,
  biNumber,
  biPercent,
} from "./BiMobileComponents";

describe("BI mobile presentation of actual and unavailable data", () => {
  it("distinguishes missing information from a measured zero", () => {
    expect(biMoney(null)).toBe("Indisponível");
    expect(biNumber(undefined)).toBe("Indisponível");
    expect(biNumber(0)).toBe("0");
    expect(biMoney(0)).toContain("0,00");
    expect(biPercent(null)).toBe("Sem base comparável");
    expect(biPercent(0)).toBe("0%");
  });

  it("shows both historical metrics and differences in a touch tooltip", () => {
    const html = renderToStaticMarkup(
      <SalesTooltip
        active
        metric="revenue"
        payload={[
          {
            payload: {
              label: "20:00",
              date: "2026-10-27 20",
              previous_date: "2026-09-27 20",
              orders: 8,
              revenue: 400,
              pizzas: 10,
              previous_orders: 4,
              previous_revenue: 200,
              previous_pizzas: 5,
              comparison: {
                orders: { difference: 4, percent: 100 },
                revenue: { difference: 200, percent: 100 },
              },
            },
          },
        ]}
      />,
    );
    expect(html).toContain("20:00");
    expect(html).toContain("27/10/2026");
    expect(html).toContain("27/09/2026");
    expect(html).toContain("Pedidos anteriores:");
    expect(html).toContain("Diferença de pedidos pagos:");
    expect(html).toContain("Diferença de receita confirmada:");
    expect(html).toContain("+100%");
  });

  it("does not fabricate a comparison when there is no historical base", () => {
    const html = renderToStaticMarkup(
      <SalesTooltip
        active
        metric="orders"
        payload={[
          {
            payload: { label: "10:00", orders: 0, revenue: 0, pizzas: 0 },
          },
        ]}
      />,
    );
    expect(html).not.toContain("Anterior:");
    expect(html).not.toContain("Diferença");
    expect(
      renderToStaticMarkup(<SalesTooltip active={false} metric="orders" />),
    ).toBe("");
  });

  it("escapes content received from backend and preserves metric helper text", () => {
    const html = renderToStaticMarkup(
      <BiMetrics
        items={[
          {
            label: "<script>bad</script>",
            value: "Indisponível",
            helper: "Sem presença comprovada",
          },
        ]}
      />,
    );
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
    expect(html).toContain("Sem presença comprovada");
  });
});
