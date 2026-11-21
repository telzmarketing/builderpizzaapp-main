import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { ApiOrder, ApiProduct } from "@/lib/api";
import { amendmentFinancialAdjustment, amendmentPreviewTotal, buildAmendmentItems, OrderCard, newlyConfirmedOrders } from "./Orders";

function renderCard(order_code: string | null) {
  const order = {
    id: "order-d5-legacy-id", order_code, status: "preparing", items: [],
    delivery_name: "Cliente", total: 78.8, estimated_time: 20,
    created_at: "2026-10-27T08:20:00Z", updated_at: "2026-10-27T08:20:00Z",
  } as ApiOrder;
  const noop = () => {};
  return renderToStaticMarkup(<OrderCard order={order} updating={false}
    onAdvance={noop} onReconcilePayment={noop} onCancelRemotePayment={noop}
    onRefundPayment={noop} onPrint={noop} onLabels={noop} canDelete={false}
    onRequestDelete={noop} onDragStart={noop} onDragEnd={noop} />);
}

describe("orders card public number", () => {
  it("shows the same public code as the kitchen instead of the internal ID", () => {
    const html = renderCard("K5M4");
    expect(html).toContain(">#K5M4</h3>");
    expect(html).not.toContain("#ORDER-D5");
  });

  it("keeps the legacy ID fallback when there is no public code", () => {
    expect(renderCard(null)).toContain(">#ORDER-D5</h3>");
  });
});

describe("confirmed order print candidates", () => {
  const order = (id: string, status: ApiOrder["status"], extra: Partial<ApiOrder> = {}) =>
    ({ id, status, created_at: "2026-11-18T11:00:00Z", ...extra }) as ApiOrder;

  it("detects a paid order after the initial snapshot and skips an already alerted order", () => {
    const orders = [order("new", "paid"), order("old", "pago")];
    expect(newlyConfirmedOrders(orders, new Set(["old"]), new Set(["new"]), Date.parse("2026-11-18T12:00:00Z"))).toEqual([orders[0]]);
    expect(newlyConfirmedOrders(orders, new Set(), new Set(), Date.parse("2026-11-18T12:00:00Z"))).toEqual([]);
  });

  it("detects a quick transition from observed waiting to preparing with paid_at", () => {
    const orders = [
      order("fast", "preparing", { paid_at: "2026-11-18T12:00:00Z", payment_status: "approved" }),
      order("history", "preparing", { paid_at: "2026-11-18T11:00:00Z" }),
    ];
    expect(newlyConfirmedOrders(orders, new Set(), new Set(["fast"]), Date.parse("2026-11-18T12:00:00Z"))).toEqual([orders[0]]);
  });

  it("detects a newly created confirmed order that passed through paid between polls", () => {
    const baseline = Date.parse("2026-11-18T12:00:00Z");
    const orders = [
      order("new", "preparing", { created_at: "2026-11-18T12:00:01Z", paid_at: "2026-11-18T12:00:02Z" }),
      order("old", "preparing", { paid_at: "2026-11-18T12:00:02Z" }),
    ];
    expect(newlyConfirmedOrders(orders, new Set(), new Set(), baseline)).toEqual([orders[0]]);
    expect(newlyConfirmedOrders(orders, new Set(), new Set(), null)).toEqual([]);
  });

  it("does not print from payment_status alone or without confirmed paid_at", () => {
    const orders = [
      order("payment-only", "waiting_payment", { payment_status: "approved" }),
      order("no-confirmation", "preparing", { payment_status: "approved" }),
    ];
    expect(newlyConfirmedOrders(orders, new Set(), new Set(["payment-only", "no-confirmation"]), Date.parse("2026-11-18T10:00:00Z"))).toEqual([]);
  });

  it("keeps a failed candidate eligible until a successful print marks its ID", () => {
    const orders = [order("retry", "paid")];
    const alerted = new Set<string>();
    const waiting = new Set(["retry"]);
    expect(newlyConfirmedOrders(orders, alerted, waiting, null)).toEqual(orders);
    expect(newlyConfirmedOrders(orders, alerted, waiting, null)).toEqual(orders);
    alerted.add("retry");
    expect(newlyConfirmedOrders(orders, alerted, waiting, null)).toEqual([]);
  });
});

describe("order amendment composition", () => {
  const order = {
    id: "order-1",
    total: 30,
    composition_revision: 2,
    items: [{
      id: "line-1",
      product_id: "old-product",
      product_name: "Pizza antiga",
      quantity: 1,
      selected_size: "Grande",
      selected_size_id: null,
      flavor_division: 1,
      flavors: [{ product_id: "old-product", name: "Pizza antiga", price: 30, icon: "🍕" }],
      add_ons: [],
      selected_crust_type: null,
      selected_drink_variant: null,
      selected_border_id: null,
      selected_border_name: null,
      selected_drink_variant_id: null,
      notes: null,
      unit_price: 30,
      final_price: 30,
    }],
  } as ApiOrder;
  const replacement = { id: "new-product", name: "Pizza nova", price: 42, current_price: 40, icon: "🍕", active: true } as ApiProduct;

  it("sends a replacement product as a new composition line", () => {
    const items = buildAmendmentItems(order, { "line-1": { productId: replacement.id, quantity: 2 } }, [replacement]);
    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({ product_id: replacement.id, quantity: 2, final_price: 40, flavor_division: 1 });
  });

  it("previews replacement price while retaining the order-level total adjustment", () => {
    expect(amendmentPreviewTotal(order, { "line-1": { productId: replacement.id, quantity: 2 } }, [replacement])).toBe(80);
  });
});

describe("order amendment financial settlement", () => {
  const amendment = (delta: number) => ({
    id: `amendment-${delta}`,
    order_id: "order-1",
    revision: 3,
    actor_id: "admin-1",
    actor_name: "Operador",
    reason: "Ajuste solicitado",
    state: "applied",
    before_snapshot: {},
    after_snapshot: { financial_adjustment: { delta, previous_total: 50, new_total: 50 + delta } },
    created_at: "2026-11-21T12:00:00Z",
  });

  it("classifies a positive history delta as a charge", () => {
    expect(amendmentFinancialAdjustment(amendment(12.5))).toMatchObject({
      delta: 12.5, amount: 12.5, direction: "charge", previousTotal: 50, newTotal: 62.5,
    });
  });

  it("classifies a negative history delta as an abatement", () => {
    expect(amendmentFinancialAdjustment(amendment(-8))).toMatchObject({
      delta: -8, amount: 8, direction: "refund", previousTotal: 50, newTotal: 42,
    });
  });

  it("does not offer settlement for an unchanged total", () => {
    expect(amendmentFinancialAdjustment(amendment(0))).toMatchObject({
      delta: 0, amount: 0, direction: null,
    });
  });
});
