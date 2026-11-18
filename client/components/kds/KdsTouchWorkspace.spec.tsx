import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { KdsKitchenOrder } from "@/lib/api";
import KdsTouchWorkspace, {
  pendingUnitMessage,
  productionUnitSummary,
} from "./KdsTouchWorkspace";

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
        orders={[
          {
            ...order,
            status: "preparing",
            production_units: [
              {
                id: "unit-1",
                order_item_id: "item-1",
                unit_index: 1,
                task_id: "task-1",
                state: "checking_stock",
                version: 2,
                product_name: "Pizza Peperoni",
              },
            ],
          },
        ]}
        ordersLoading={false}
        updating={null}
        startOrder={noop}
        finishOrder={noop}
      />,
    );

    expect(markup).toContain("Conferindo estoque");
    expect(markup).toContain("Nenhuma baixa durante a contagem.");
  });

  it("keeps oven units out of the pizzaiolo task list but shows an actionable dispatch status", () => {
    const ovenUnit = {
      id: "unit-oven",
      order_item_id: "item-1",
      unit_index: 1,
      task_id: "task-oven",
      state: "baking",
      version: 3,
      product_name: "Pizza Peperoni",
    };
    const summary = productionUnitSummary(ovenUnit);
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
            active_task_id: null,
            updated_at: "2026-11-15T14:00:01Z",
            version: 1,
          },
          tasks: [],
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
        orders={[
          { ...order, status: "preparing", production_units: [ovenUnit] },
        ]}
        ordersLoading={false}
        updating={null}
        startOrder={noop}
        finishOrder={noop}
      />,
    );

    expect(summary.label).toBe("No forno — aguardando Expedição");
    expect(summary.detail).toBe(
      "Próxima ação: retirar e conferir no KDS Expedição",
    );
    expect(summary.actionable).toBe(false);
    expect(markup).toContain("No forno — aguardando Expedição");
    expect(markup).toContain(
      "Próxima ação: retirar e conferir no KDS Expedição",
    );
    expect(markup).toContain("Pendências:");
    expect(markup).toContain("lg:grid-rows-[minmax(0,1fr)_auto_auto]");
  });

  it("distinguishes missing task from an oven unit", () => {
    const withoutTask = productionUnitSummary({
      id: "unit-missing",
      order_item_id: "item-1",
      unit_index: 2,
      task_id: null,
      state: "assembling",
      version: 1,
    });
    const absentTask = productionUnitSummary({
      id: "unit-absent",
      order_item_id: "item-1",
      unit_index: 3,
      task_id: "task-absent",
      state: "assembling",
      version: 1,
    });

    expect(withoutTask.label).toBe("Sem tarefa atribuída");
    expect(absentTask.label).toBe("Tarefa ausente da fila");
  });

  it("lists each pending unit with its product and next action", () => {
    const message = pendingUnitMessage(
      [
        {
          id: "unit-oven",
          order_item_id: "item-1",
          unit_index: 1,
          task_id: "task-oven",
          state: "baking",
          version: 3,
          product_name: "Pizza Peperoni",
        },
        {
          id: "unit-missing",
          order_item_id: "item-1",
          unit_index: 2,
          task_id: null,
          state: "assembling",
          version: 1,
          product_name: "Pizza Peperoni",
        },
      ],
      [],
    );

    expect(message).toContain(
      "Unidade 1 — Pizza Peperoni: No forno — aguardando Expedição",
    );
    expect(message).toContain(
      "Unidade 2 — Pizza Peperoni: Sem tarefa atribuída",
    );
    expect(message).toContain(
      "retirar e conferir as unidades no KDS Expedição",
    );
  });
});
