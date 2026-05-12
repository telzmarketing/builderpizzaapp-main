import { describe, expect, it } from "vitest";
import {
  DEFAULT_PRINTER_SETTINGS,
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
});
