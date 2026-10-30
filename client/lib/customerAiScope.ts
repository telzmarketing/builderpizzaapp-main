export const CUSTOMER_AI_ALLOWED_AREAS = [
  "Catálogo",
  "Promoções",
  "FAQs",
  "Frete",
  "Pedidos",
] as const;

export const CUSTOMER_AI_SCOPE_GUARDRAIL =
  "Escopo obrigatório da IA do cliente: responder somente sobre catálogo, promoções, FAQs, frete e pedidos. Não acessar nem expor CRM, Memória Comercial, estoque, financeiro, fiscal, configurações internas, Gestor IA ou dados de outros clientes. Fora desse escopo, orientar o cliente a falar com um atendente.";

export function ensureCustomerAiScope(value: string): string {
  const base = value.trim();
  if (base.includes(CUSTOMER_AI_SCOPE_GUARDRAIL)) return base;
  return [base, CUSTOMER_AI_SCOPE_GUARDRAIL].filter(Boolean).join("\n\n");
}
