import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { ApiOrder } from "@/lib/api";
import { OrderCard } from "./Orders";

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
