type PaymentFacts = {
  payment_status?: string | null;
  payment_method?: string | null;
  payment_provider?: string | null;
  pay_on_delivery?: boolean;
  delivery_payment_method?: string | null;
  cash_needs_change?: boolean | null;
  cash_change_for?: number | null;
  cash_change_amount?: number | null;
  fulfillment_type?: string | null;
};

const methods: Record<string, string> = { cash: "Dinheiro", card: "Cartão", credit_card: "Cartão de crédito", debit_card: "Cartão de débito", pix: "Pix" };
const statuses: Record<string, string> = { pending: "Pagamento pendente", approved: "Pagamento confirmado", paid: "Pagamento confirmado", rejected: "Pagamento recusado", failed: "Falha no pagamento", expired: "Pagamento expirado", cancelled: "Pagamento cancelado", refunded: "Pagamento reembolsado" };
const onlineProviders = new Set(["mercado_pago", "mercadopago", "pagarme", "pagar_me", "pagar.me", "asaas"]);
const money = (value: number) => value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export function operationalPaymentLines(order: PaymentFacts): string[] {
  const confirmed = order.payment_status === "approved" || order.payment_status === "paid";
  const online = confirmed && !order.pay_on_delivery && onlineProviders.has(order.payment_provider || "");
  const method = order.pay_on_delivery ? order.delivery_payment_method : order.payment_method;
  const lines = [online ? "PAGO ONLINE — NÃO COBRAR" : confirmed ? "PAGAMENTO CONFIRMADO — NÃO COBRAR" : statuses[order.payment_status || ""] || "Pagamento não informado — verificar antes de cobrar"];
  lines.push(`Forma: ${methods[method || ""] || "Não informada"}`);
  if (order.payment_provider) lines.push(`Provedor: ${order.payment_provider}`);
  if (order.pay_on_delivery && !confirmed) lines.push(order.fulfillment_type === "pickup" ? "Pagamento na retirada" : "Pagamento na entrega");
  if (!confirmed && method === "cash" && order.cash_needs_change && order.cash_change_for != null) {
    lines.push(`Receber: ${money(order.cash_change_for)}`);
    lines.push(order.cash_change_amount != null ? `TROCO: ${money(order.cash_change_amount)}` : "Troco não informado — verificar");
  }
  return lines;
}

export function operationalPaymentHtml(order: PaymentFacts): string {
  const escape = (text: string) => text.replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]!);
  return `<section><p class="b">PAGAMENTO</p>${operationalPaymentLines(order).map((line) => `<p class="b">${escape(line)}</p>`).join("")}</section>`;
}
