import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { KdsKitchenOrder } from "@/lib/api";
import KdsTouchWorkspace from "./KdsTouchWorkspace";

const order: KdsKitchenOrder = {
  id: "order-d5-legacy-id",
  order_code: "K5M4",
  status: "paid",
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
const command = async () => true;
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
      command={command}
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

  it("removes a started order from the waiting queue while keeping it in preparation", () => {
    const markup = renderOrder({ ...order, status: "preparing" });
    expect(markup).toContain("Pedido em preparo");
    expect(markup).toContain("Nenhum pedido na cozinha.");
  });

  it("renders an active stock-check task and its countdown after the waiting queue is empty", () => {
    const markup = renderToStaticMarkup(
      <KdsTouchWorkspace
        queue={{
          generated_at: "2026-11-15T14:00:01Z",
          presence: {
            operator_id: "operator-1",
            operator_name: "Pizzaiolo",
            state: "available",
            station_id: "pizza",
            queue_count: 0,
            active_task_id: "task-1",
            updated_at: "2026-11-15T14:00:01Z",
            version: 1,
          },
          tasks: [
            {
              id: "task-1",
              order_id: "order-d5-legacy-id",
              order_code: "K5M4",
              order_item_id: "item-1",
              unit_index: 1,
              state: "checking_stock",
              version: 2,
              priority: 0,
              created_at: "2026-11-15T14:00:00Z",
              started_at: "2026-11-15T14:00:01Z",
              stock_check_after: "2026-11-15T14:00:06Z",
              server_time: "2026-11-15T14:00:01Z",
              product_name: "Pizza Peperoni",
            },
          ],
        }}
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
        command={command}
        redistribute={noop}
        orders={[{
          ...order,
          status: "preparing",
          production_units: [{
            id: "unit-1",
            order_item_id: "item-1",
            unit_index: 1,
            task_id: "task-1",
            state: "checking_stock",
            version: 2,
            product_name: "Pizza Peperoni",
          }],
        }]}
        ordersLoading={false}
        updating={null}
        startOrder={noop}
        finishOrder={noop}
      />,
    );

    expect(markup).toContain("Conferindo estoque");
    expect(markup).toContain("Nenhuma baixa durante a contagem.");
  });
});
