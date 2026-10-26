export interface OperationalDrink {
  id?: string;
  product_id?: string;
  name?: string;
  product_name?: string;
  selected_drink_variant?: string | null;
  quantity: number;
  notes?: string | null;
}

type OperationalItem = { product_id: string; product_name: string; quantity: number; notes?: string | null; is_drink?: boolean; product_type?: string | null };

export function isOperationalDrink(item: { is_drink?: boolean; product_type?: string | null }) {
  return item.is_drink === true || item.product_type === "drink";
}

export function operationalDrinks(order: { drinks?: OperationalDrink[]; items: OperationalItem[] }): Array<OperationalDrink & { name: string }> {
  // Server projection includes combo components. Never guess from a product name.
  if (Array.isArray(order.drinks)) return order.drinks.map((drink) => ({ ...drink, name: [drink.name || drink.product_name || "Bebida", drink.selected_drink_variant].filter(Boolean).join(" · ") }));
  return order.items.filter(isOperationalDrink).map((item) => ({ product_id: item.product_id, name: item.product_name, quantity: item.quantity, notes: item.notes }));
}
