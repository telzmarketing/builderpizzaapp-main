/** Present the persisted public code; keep one fallback for legacy orders. */
export function orderDisplayCode(order: { id: string; order_code?: string | null }): string {
  return (order.order_code?.trim() || order.id.slice(0, 8)).toUpperCase();
}
