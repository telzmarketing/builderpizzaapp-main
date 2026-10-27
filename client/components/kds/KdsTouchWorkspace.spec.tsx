import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { KdsKitchenOrder } from "@/lib/api";
import KdsTouchWorkspace from "./KdsTouchWorkspace";

const order: KdsKitchenOrder = {
  id: "order-d5-legacy-id",
  order_code: "K5M4",
  status: "preparing",
  fulfillment_type: "delivery",
  total: 78.8,
  estimated_time: 20,
  created_at: "2026-10-27T08:20:00Z",
  updated_at: "2026-10-27T08:20:00Z",
  delivery: null,
  items: [
    {
      id: "item-1",
      product_id: "pizza",
      product_name: "Pizza Peperoni",
      quantity: 1,
      flavors: [],
    },
  ],
};

const noop = async () => {};
function renderOrder(value: KdsKitchenOrder) {
  return renderToStaticMarkup(
    <KdsTouchWorkspace
      queue={null}
      loading={false}
      refreshing={false}
      error={null}
      busy={null}
      selected={[]}
      targetOperator=""
      setSelected={() => {}}
      setTargetOperator={() => {}}
      load={noop}
      updatePresence={noop}
      command={noop}
      redistribute={noop}
      orders={[value]}
      ordersLoading={false}
      updating={null}
      startOrder={noop}
      finishOrder={noop}
    />,
  );
}

describe("KDS order identity", () => {
  it("shows the canonical code in the queue, preparation and summary", () => {
    const markup = renderOrder(order);
    expect(markup.match(/#K5M4/g)).toHaveLength(3);
    expect(markup).not.toContain("#ORDER-D5");
  });

  it("uses the same legacy fallback across the three panels", () => {
    const markup = renderOrder({ ...order, order_code: null });
    expect(markup.match(/#ORDER-D5/g)).toHaveLength(3);
  });
});
