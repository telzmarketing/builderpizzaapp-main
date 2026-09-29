import type { OrderBoardOrder, OrderBoardSnapshot } from "./api";

export const ORDER_BOARD_POLL_INTERVAL_MS = 5_000;
export const ORDER_BOARD_STALE_AFTER_MS = 15_000;

export type OrderBoardColumnId = "waiting" | "ready";

export type OrderBoardDeliveryOrder = OrderBoardOrder;

export const ORDER_BOARD_COLUMNS: Array<{
  id: OrderBoardColumnId;
  label: string;
  statuses: string[];
}> = [
  { id: "waiting", label: "Aguardando", statuses: ["preparing"] },
  { id: "ready", label: "Pronto para retirada", statuses: ["ready_for_pickup"] },
];

export function orderBoardColumn(status: string): OrderBoardColumnId | null {
  return ORDER_BOARD_COLUMNS.find((column) => column.statuses.includes(status))?.id ?? null;
}

export function normalizeBoardOrders(orders: OrderBoardDeliveryOrder[]): OrderBoardDeliveryOrder[] {
  const unique = new Map<string, OrderBoardDeliveryOrder>();
  for (const order of orders) unique.set(order.id, order);
  return [...unique.values()].sort((left, right) => {
    const leftDate = Date.parse(left.status_started_at || left.created_at);
    const rightDate = Date.parse(right.status_started_at || right.created_at);
    if (leftDate !== rightDate) return leftDate - rightDate;
    return left.id.localeCompare(right.id);
  });
}

export function groupBoardOrders(
  orders: OrderBoardDeliveryOrder[],
): Record<OrderBoardColumnId, OrderBoardDeliveryOrder[]> {
  const groups: Record<OrderBoardColumnId, OrderBoardDeliveryOrder[]> = {
    waiting: [],
    ready: [],
  };
  for (const order of normalizeBoardOrders(orders)) {
    const column = orderBoardColumn(order.status);
    if (column) groups[column].push(order);
  }
  return groups;
}

export function elapsedSeconds(startedAt: string | null | undefined, now = Date.now()): number {
  if (!startedAt) return 0;
  const parsed = Date.parse(startedAt);
  if (!Number.isFinite(parsed)) return 0;
  return Math.max(0, Math.floor((now - parsed) / 1_000));
}

export function formatBoardDuration(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(seconds / 3_600);
  const minutes = Math.floor((seconds % 3_600) / 60);
  const remainder = seconds % 60;
  return hours > 0
    ? `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`
    : `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

export function isBoardOrderLate(
  order: OrderBoardOrder,
  snapshot: OrderBoardSnapshot,
  now = Date.now(),
): boolean {
  const threshold = order.status === "preparing"
    ? snapshot.settings.production_sla_minutes
    : order.status === "ready_for_pickup"
      ? snapshot.settings.dispatch_sla_minutes
      : null;
  return threshold !== null && elapsedSeconds(order.status_started_at, now) >= threshold * 60;
}

export function visiblePage<T>(items: T[], page: number, pageSize: number): T[] {
  if (items.length <= pageSize) return items;
  const pages = Math.ceil(items.length / pageSize);
  const safePage = ((page % pages) + pages) % pages;
  return items.slice(safePage * pageSize, (safePage + 1) * pageSize);
}
