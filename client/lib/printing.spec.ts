import { afterEach, describe, expect, it, vi } from "vitest";
import {
  DEFAULT_PRINTER_SETTINGS,
  buildPrintHtml,
  buildEntregaHtml,
  withReceiptBranding,
  openReceiptPreview,
  type PrinterSettings,
} from "./printing";
import type { ApiOrder } from "./api";

describe("receipt print readiness", () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });
  it("waits for the logo before requesting the browser print dialog", async () => {
    vi.useFakeTimers();
    const image = { complete: false, naturalWidth: 100, hidden: false, onload: null as null | (() => void), onerror: null as null | (() => void) };
    const target = { document: { open: vi.fn(), write: vi.fn(), close: vi.fn(), images: [image] }, focus: vi.fn(), print: vi.fn() };
    vi.stubGlobal("window", { open: vi.fn(() => target), setTimeout });
    expect(openReceiptPreview("<html>receipt</html>", true)).toBe(true);
    expect(target.print).not.toHaveBeenCalled();
    image.complete = true;
    image.onload?.();
    await vi.advanceTimersByTimeAsync(0);
    expect(target.print).toHaveBeenCalledOnce();
    expect(image.hidden).toBe(false);
  });
});

it("prints the persisted pending cash payment and calculated change on delivery receipts", () => {
  const order = { ...deliveryOrder(), payment_status: "pending" as const, pay_on_delivery: true, delivery_payment_method: "cash", cash_needs_change: true, cash_change_for: 100, cash_change_amount: 25.01 };
  const html = buildEntregaHtml(order, DEFAULT_PRINTER_SETTINGS);
  expect(html).toContain("Pagamento pendente");
  expect(html).toContain("25,01");
  expect(html).not.toContain("NÃO COBRAR");
});

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
  it("uses the tenant logo and server drink projection in all receipt templates", () => {
    const order = { ...deliveryOrder(), sales_channel: "counter", fulfillment_type: "pickup", drinks: [{ product_id: "combo-drink", product_name: "Kuat 2 L", quantity: 2, notes: "Gelado" }] };
    const settings = withReceiptBranding(DEFAULT_PRINTER_SETTINGS, { brand: { name: "Gran Torino", logo: "https://tenant.example/logo.png" } });
    for (const template of ["completo", "cozinha", "entrega"] as const) {
      const html = buildPrintHtml(order, template, settings);
      expect(html).toContain('class="receipt-logo"');
      expect(html).toContain('src="https://tenant.example/logo.png"');
      expect(html).toContain("filter:grayscale(1)");
      expect(html).toContain("ATENÇÃO — BEBIDAS");
      expect(html).toContain("2 × Kuat 2 L");
      expect(html).toContain("Gelado");
      expect(html).toContain("Origem: Balcão");
      expect(html).toContain("Modalidade: Retirada");
      expect(html).toContain("PAGAMENTO");
    }
  });

  it("classifies individual drinks only with structured facts and prints them in their own block", () => {
    const order = deliveryOrder();
    order.items.push({ ...order.items[0], id: "drink", product_id: "drink", product_name: "Água", product_type: "drink", quantity: 3 });
    const html = buildPrintHtml(order, "completo", DEFAULT_PRINTER_SETTINGS);
    expect(html).toContain("3 × Água");
    expect(html.split("Água")).toHaveLength(2);
    const ambiguous = { ...deliveryOrder(), items: [{ ...order.items[0], product_name: "Pizza refrigerante especial" }] };
    expect(buildPrintHtml(ambiguous, "completo", DEFAULT_PRINTER_SETTINGS)).not.toContain("ATENÇÃO — BEBIDAS");
  });

  it("keeps payment method separate from actual status and renders persisted cash change", () => {
    const order = { ...deliveryOrder(), payment_method: "credit_card" as const, payment_status: "pending" as const };
    const pending = buildPrintHtml(order, "completo", DEFAULT_PRINTER_SETTINGS);
    expect(pending).toContain("Cartão de crédito");
    expect(pending).toContain("Pagamento pendente");
    expect(pending).not.toContain("NÃO COBRAR");
    const online = buildPrintHtml({ ...order, payment_status: "approved", payment_provider: "pagarme" }, "entrega", DEFAULT_PRINTER_SETTINGS);
    expect(online).toContain("PAGO ONLINE — NÃO COBRAR");
  });

  it("escapes receipt content and rejects executable logo URLs", () => {
    const order = deliveryOrder();
    order.delivery_name = '<script>alert("customer")</script>';
    order.items[0].notes = '<img src=x onerror="alert(1)">';
    const html = buildPrintHtml(order, "completo", { ...DEFAULT_PRINTER_SETTINGS, storeLogoUrl: "javascript:alert(1)" });
    expect(html).not.toContain("<script>");
    expect(html).not.toContain("<img src=x");
    expect(html).not.toContain("javascript:");
    expect(html).toContain("&lt;img");
  });
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

  it("inclui o QR de pagamento oficial na nota quando o contrato fornece imagem", () => {
    const payment = {
      qr_code: "data:image/png;base64,QUJD",
      pix_qr_code: null,
      qr_code_text: "000201PIX",
      pix_payload: null,
    } as never;
    const html = buildPrintHtml(deliveryOrder(), "completo", DEFAULT_PRINTER_SETTINGS, payment);

    expect(html).toContain('class="receipt-qr"');
    expect(html).toContain('alt="QR Code para pagamento"');
    expect(html).toContain("000201PIX");
    expect(html).not.toContain("javascript:");
  });

  it("não renderiza QR quando o valor recebido não é uma imagem segura", () => {
    const payment = { qr_code: "javascript:alert(1)", pix_qr_code: null } as never;
    const html = buildPrintHtml(deliveryOrder(), "entrega", DEFAULT_PRINTER_SETTINGS, payment);

    expect(html).not.toContain('<section class="receipt-qr"');
    expect(html).not.toContain("javascript:");
  });
});
