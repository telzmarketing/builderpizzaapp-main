export interface PromotionalKitItemDraft {
  id?: string;
  product_id: string;
  quantity: number;
}

export function kitItemDraftsFromItems(
  items: Array<{ id: string; product_id: string; quantity: number }>,
): PromotionalKitItemDraft[] {
  return items.map(({ id, product_id, quantity }) => ({ id, product_id, quantity }));
}

export function addKitItemDraft(
  items: PromotionalKitItemDraft[],
  productId: string,
  quantity: number,
): PromotionalKitItemDraft[] {
  const safeQuantity = Math.max(1, Math.floor(quantity) || 1);
  const existing = items.find((item) => item.product_id === productId);
  if (existing) {
    return items.map((item) => item.product_id === productId
      ? { ...item, quantity: item.quantity + safeQuantity }
      : item);
  }
  return [...items, { product_id: productId, quantity: safeQuantity }];
}

export function removeKitItemDraft(items: PromotionalKitItemDraft[], index: number): PromotionalKitItemDraft[] {
  return items.filter((_, itemIndex) => itemIndex !== index);
}
