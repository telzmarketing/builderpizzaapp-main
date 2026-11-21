import type { ProductConfiguratorProps } from "@/pages/Product";
import type { CartPromotionMeta } from "@/context/AppContext";
import type {
  ApiEffectivePermissions,
  ApiProduct,
  CheckoutItemIn,
} from "./api";

export interface ManualCartLine {
  id: string;
  name: string;
  item: CheckoutItemIn;
  promotion?: CartPromotionMeta;
}

export function configuredManualLine(
  args: Parameters<NonNullable<ProductConfiguratorProps["onAdd"]>>,
  id: string,
): ManualCartLine {
  const [
    product,
    quantity,
    size,
    addOns,
    flavors,
    division,
    unitPrice,
    notes,
    crust,
    drink,
    sizeId,
    promotion,
    border,
    selectedOptions,
  ] = args;
  return {
    id,
    name: product.name,
    promotion,
    item: {
      product_id: product.id,
      quantity,
      selected_size: size,
      selected_size_id: sizeId,
      flavor_division: division,
      flavors: flavors.map((flavor) => ({
        product_id: flavor.productId,
        name: flavor.name,
        price: flavor.price,
        icon: flavor.icon,
      })),
      final_price: unitPrice,
      add_ons: addOns,
      notes: notes || null,
      option_selections:
        selectedOptions?.map((option) => ({
          group_id: option.groupId,
          group_name: option.groupName,
          option_id: option.optionId,
          label: option.label,
          quantity: option.quantity ?? 1,
          price_addition: option.priceAddition,
        })) ?? [],
      selected_crust_type_id: crust?.id ?? null,
      selected_crust_type_name: crust?.name ?? null,
      selected_border_id: border?.id ?? null,
      selected_border_name: border?.name ?? null,
      selected_drink_variant_id: drink?.id ?? null,
      selected_drink_variant_name: drink?.name ?? null,
    },
  };
}

export function simpleManualLine(
  product: ApiProduct,
  id: string,
  quantity = 1,
): ManualCartLine {
  const price = product.current_price ?? product.price;
  const promotion = product.promotion_applied
    ? {
        applied: true,
        id: product.promotion_id,
        name: product.promotion_name,
        discount: product.promotion_discount,
        freeShipping: product.promotion_free_shipping,
        giftEnabled: product.promotion_gift_enabled,
        giftProductId: product.promotion_gift_product_id,
        giftQuantity: product.promotion_gift_quantity,
        giftName: product.promotion_gift_name,
        giftIcon: product.promotion_gift_icon,
        blocksOtherCoupons: product.promotion_blocks_other_coupons,
      }
    : undefined;
  return {
    id,
    name: product.name,
    promotion,
    item: {
      product_id: product.id,
      quantity: Math.max(1, Math.floor(quantity)),
      selected_size: "",
      selected_size_id: null,
      flavor_division: 1,
      flavors: [
        {
          product_id: product.id,
          name: product.name,
          price,
          icon: product.icon || "🍕",
        },
      ],
      final_price: price,
      add_ons: [],
      notes: null,
      option_selections: [],
      selected_crust_type_id: null,
      selected_crust_type_name: null,
      selected_border_id: null,
      selected_border_name: null,
      selected_drink_variant_id: null,
      selected_drink_variant_name: null,
    },
  };
}

export function canCreateManualOrder(
  permissions: ApiEffectivePermissions | null,
): boolean {
  return (
    !!permissions &&
    (permissions.is_master || permissions.modules.pedidos?.create === true)
  );
}

export function newManualOrderKey() {
  return `manual:${crypto.randomUUID()}`;
}
