import type { ProductConfiguratorProps } from "@/pages/Product";
import type { ApiEffectivePermissions, CheckoutItemIn } from "./api";

export interface ManualCartLine { id: string; name: string; item: CheckoutItemIn }

export function configuredManualLine(args: Parameters<NonNullable<ProductConfiguratorProps["onAdd"]>>, id: string): ManualCartLine {
  const [product, quantity, size, addOns, flavors, division, unitPrice, notes, crust, drink, sizeId, , border] = args;
  return { id, name: product.name, item: {
    product_id: product.id, quantity, selected_size: size, selected_size_id: sizeId,
    flavor_division: division, flavors: flavors.map((flavor) => ({ product_id: flavor.productId, name: flavor.name, price: flavor.price, icon: flavor.icon })),
    final_price: unitPrice, add_ons: addOns, notes: notes || null,
    selected_crust_type_id: crust?.id ?? null, selected_crust_type_name: crust?.name ?? null,
    selected_border_id: border?.id ?? null, selected_border_name: border?.name ?? null,
    selected_drink_variant_id: drink?.id ?? null, selected_drink_variant_name: drink?.name ?? null,
  } };
}

export function canCreateManualOrder(permissions: ApiEffectivePermissions | null): boolean {
  return !!permissions && (permissions.is_master || permissions.modules.pedidos?.create === true);
}

export function newManualOrderKey() {
  return `manual:${crypto.randomUUID()}`;
}
