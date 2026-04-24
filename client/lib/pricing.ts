const PRICE_EPSILON = 0.01;

export function normalizeCrustPriceAddition(priceAddition: number | null | undefined, productBasePrice: number | null | undefined): number {
  const addition = Number(priceAddition ?? 0);
  if (!Number.isFinite(addition) || addition <= 0) return 0;

  const basePrice = Number(productBasePrice ?? 0);
  if (Number.isFinite(basePrice) && basePrice > 0 && Math.abs(addition - basePrice) <= PRICE_EPSILON) {
    return 0;
  }

  return addition;
}

export function formatCrustAddition(priceAddition: number): string {
  return priceAddition > 0 ? `+ R$ ${priceAddition.toFixed(2)}` : "Sem adicional";
}
