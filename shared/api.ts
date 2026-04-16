/**
 * Tipos compartilhados entre client e server.
 * Os tipos do backend FastAPI estão em client/lib/api.ts.
 */

export interface DemoResponse {
  message: string;
}

/** Status possíveis de um pedido (espelho do backend) */
export type OrderStatus =
  | "pending"
  | "waiting_payment"
  | "paid"
  | "preparing"
  | "ready_for_pickup"
  | "on_the_way"
  | "delivered"
  | "cancelled"
  | "refunded";

/** Labels em português para exibição */
export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  pending: "Aguardando",
  waiting_payment: "Aguardando Pagamento",
  paid: "Pagamento Confirmado",
  preparing: "Preparando",
  ready_for_pickup: "Pronto para Retirada",
  on_the_way: "A caminho",
  delivered: "Entregue",
  cancelled: "Cancelado",
  refunded: "Reembolsado",
};
