import { describe, expect, it } from "vitest";
import {
  DEFAULT_PRINTER_SETTINGS,
  buildPrintHtml,
  buildEntregaHtml,
  type PrinterSettings,
} from "./printing";
import type { ApiOrder } from "./api";

function deliveryOrder(): ApiOrder {
  return {
    id: "abc12345-0000-0000-0000-000000000000",
    order_code: "10",
    customer_id: null,
    delivery_name: "Maria Silva Souza",
    delivery_phone: "(11) 98765-4321",
    delivery_street: "Rua Teste, 123",
    delivery_city: "Sao Paulo",
    delivery_complement: "Casa 2",
    status: "on_the_way",
    subtotal: 50,
    shipping_fee: 8,
    discount: 0,
    total: 58,
    estimated_time: 40,
    loyalty_points_earned: 0,
    coupon_id: null,
    payment_status: "approved",
    paid_at: null,
    preparation_started_at: null,
    out_for_delivery_at: null,
    delivered_at: null,
    target_delivery_minutes: 45,
    total_time_minutes: null,
    preparation_time_minutes: null,
    delivery_time_minutes: null,
    items: [
      {
        id: "item-1",
        product_id: "prod-1",
        product_name: "Pizza Calabresa",
        quantity: 1,
        selected_size: "Grande",
        selected_size_id: null,
        flavor_division: 1,
        selected_crust_type: null,
        selected_crust_type_id: null,
        selected_drink_variant: null,
        notes: null,
        flavors: [{ product_id: "prod-1", name: "Pizza Calabresa", price: 50, icon: "" }],
        add_ons: [],
        unit_price: 50,
        final_price: 50,
      },
    ],
    created_at: new Date("2026-05-12T12:00:00.000Z").toISOString(),
    updated_at: new Date("2026-05-12T12:00:00.000Z").toISOString(),
  };
}

describe("buildEntregaHtml", () => {
  it("mascara sobrenome e oculta telefone do cliente na via de entrega", () => {
    const settings: PrinterSettings = { ...DEFAULT_PRINTER_SETTINGS };
    const html = buildEntregaHtml(deliveryOrder(), settings);

    expect(html).toContain("Maria ********");
    expect(html).not.toContain("Silva");
    expect(html).not.toContain("Souza");
    expect(html).not.toContain("(11) 98765-4321");
    expect(html).not.toContain("Telefone");
  });

  it("mantem coluna de valores dentro dos tres tamanhos de papel", () => {
    const order = deliveryOrder();

    for (const paperWidth of ["58mm", "80mm", "a4"] as const) {
      const html = buildEntregaHtml(order, { ...DEFAULT_PRINTER_SETTINGS, paperWidth });

      expect(html).toContain("@page{size:");
      expect(html).toContain("table-layout:fixed");
      expect(html).toContain('class="b qty"');
      expect(html).toContain('class="price"');
    }
  });
});

describe("buildPrintHtml", () => {
  it("monta as vias de cozinha e recepcao/completo para o mesmo pedido", () => {
    const settings: PrinterSettings = { ...DEFAULT_PRINTER_SETTINGS };
    const order = deliveryOrder();

    const cozinha = buildPrintHtml(order, "cozinha", settings);
    const completo = buildPrintHtml(order, "completo", settings);

    expect(cozinha).toContain("COMANDA COZINHA");
    expect(completo).toContain("Pedido: ");
    expect(completo).toContain(order.delivery_phone);
  });

  it("usa medidas reais e colunas fixas para os tres tamanhos de nota", () => {
    const order = deliveryOrder();

    for (const paperWidth of ["58mm", "80mm", "a4"] as const) {
      const html = buildPrintHtml(order, "completo", { ...DEFAULT_PRINTER_SETTINGS, paperWidth });

      expect(html).toContain("@page{size:");
      expect(html).toContain("table-layout:fixed");
      expect(html).toContain('class="qty"');
      expect(html).toContain('class="price"');
      expect(html).toContain('class="totals"');
    }

    expect(buildPrintHtml(order, "completo", { ...DEFAULT_PRINTER_SETTINGS, paperWidth: "58mm" })).toContain("width:54mm");
    expect(buildPrintHtml(order, "completo", { ...DEFAULT_PRINTER_SETTINGS, paperWidth: "80mm" })).toContain("width:76mm");
    expect(buildPrintHtml(order, "completo", { ...DEFAULT_PRINTER_SETTINGS, paperWidth: "a4" })).toContain("width:190mm");
  });

  it("mantem textos pequenos fortes para impressao termica", () => {
    const html = buildPrintHtml(deliveryOrder(), "completo", DEFAULT_PRINTER_SETTINGS);

    expect(html).toContain(".s{font-size:var(--receipt-small);color:#000;font-weight:600}");
    expect(html).toContain("*{color:#000!important;text-shadow:none!important}");
    expect(html).not.toContain("color:#444");
  });
});
