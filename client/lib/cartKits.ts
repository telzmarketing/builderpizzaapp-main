import type { CartItem } from "@/context/AppContext";

export type CartItemGroup =
  | { kind: "item"; key: string; item: CartItem }
  | { kind: "kit"; key: string; kit: NonNullable<CartItem["kit"]>; items: CartItem[] }
  | { kind: "strategic"; key: string; strategic: NonNullable<CartItem["strategicGroup"]>; items: CartItem[] };

export function getCartKitKey(item: CartItem): string | null {
  return item.kit?.instanceId ? `kit:${item.kit.instanceId}` : null;
}

export function groupCartItems(items: CartItem[]): CartItemGroup[] {
  const groups: CartItemGroup[] = [];
  const kitIndexes = new Map<string, number>();
  const strategicIndexes = new Map<string, number>();
  items.forEach((item) => {
    const strategicKey = item.strategicGroup?.instanceId
      ? `strategic:${item.strategicGroup.instanceId}`
      : null;
    if (strategicKey) {
      const existingIndex = strategicIndexes.get(strategicKey);
      if (existingIndex === undefined) {
        strategicIndexes.set(strategicKey, groups.length);
        groups.push({ kind: "strategic", key: strategicKey, strategic: item.strategicGroup!, items: [item] });
      } else {
        const group = groups[existingIndex];
        if (group.kind === "strategic") group.items.push(item);
      }
      return;
    }
    const key = getCartKitKey(item);
    if (!key) {
      groups.push({ kind: "item", key: item.cartItemId, item });
      return;
    }
    const existingIndex = kitIndexes.get(key);
    if (existingIndex === undefined) {
      kitIndexes.set(key, groups.length);
      groups.push({ kind: "kit", key, kit: item.kit!, items: [item] });
      return;
    }
    const group = groups[existingIndex];
    if (group.kind === "kit") group.items.push(item);
  });
  return groups;
}

export function cartItemIdsForRemoval(items: CartItem[], cartItemId: string): string[] {
  const target = items.find((item) => item.cartItemId === cartItemId);
  const kitInstanceId = target?.kit?.instanceId;
  const strategicInstanceId = target?.strategicGroup?.instanceId;
  return items
    .filter((item) => strategicInstanceId
      ? item.strategicGroup?.instanceId === strategicInstanceId
      : kitInstanceId
        ? item.kit?.instanceId === kitInstanceId
        : item.cartItemId === cartItemId)
    .map((item) => item.cartItemId);
}
