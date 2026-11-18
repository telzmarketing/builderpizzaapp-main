import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { DeliveryRecord } from "@/lib/api";
import { DeliveryCard } from "./Motoboy";

const delivery: DeliveryRecord = {
  id: "delivery-1",
  order_id: "order-1",
  status: "on_the_way",
  estimated_minutes: 40,
  created_at: "2026-11-18T12:00:00Z",
  updated_at: "2026-11-18T12:00:00Z",
  order: { id: "order-1", payment: { status: "paid", pay_on_delivery: false } },
};

function card(record: DeliveryRecord) {
  return renderToStaticMarkup(
    <DeliveryCard
      delivery={record}
      currentLocation={null}
      busy={false}
      onStart={vi.fn()}
      onConfirmPayment={vi.fn()}
      onComplete={vi.fn()}
      onProblem={vi.fn()}
      onView={vi.fn()}
    />,
  );
}

describe("Motoboy delivery completion", () => {
  it("offers one completion button without a confirmation code field", () => {
    const markup = card(delivery);
    expect(markup.match(/Finalizar entrega/g)).toHaveLength(1);
    expect(markup).not.toContain("<input");
  });

  it("requires payment receipt before offering completion for pay-on-delivery", () => {
    const markup = card({
      ...delivery,
      order: { id: "order-1", payment: { status: "pending", pay_on_delivery: true } },
    });
    expect(markup).toContain("Confirmar recebimento do pagamento");
    expect(markup).not.toContain("Finalizar entrega");
  });
});
