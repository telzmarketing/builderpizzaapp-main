/**
 * CheckoutUpsell — camada de upsell plugada no checkout.
 *
 * Regras de negócio implementadas aqui:
 * - Só aparece antes da geração de pagamento (isLocked = false)
 * - Não mostra produto já presente no carrinho
 * - Não repete upsell já exibido na mesma sessão (sessionStorage)
 * - Adiciona item ao carrinho existente via addToCart do AppContext
 * - Registra eventos (viewed / accepted / rejected) na UpsellEngine
 *
 * NÃO altera:
 * - Fluxo de checkout, cupons, frete, Mercado Pago
 * - Lógica de preço, promoções, pedidos
 */
import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, Loader2, ShoppingBag, Sparkles, X } from "lucide-react";
import { useApp } from "@/context/AppContext";
import {
  isAssetUrl,
  resolveAssetUrl,
  upsellsApi,
  type ApiUpsell,
  type ApiUpsellProduct,
} from "@/lib/api";

const SESSION_KEY = "mo_seen_upsells";

function getSeenIds(): Set<string> {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    return new Set(raw ? (JSON.parse(raw) as string[]) : []);
  } catch {
    return new Set();
  }
}

function markSeen(id: string) {
  try {
    const seen = getSeenIds();
    seen.add(id);
    sessionStorage.setItem(SESSION_KEY, JSON.stringify([...seen]));
  } catch {}
}

function defaultSizeInfo(product: ApiUpsellProduct): { label: string; id?: string; price: number } {
  if (!product.sizes || product.sizes.length === 0) {
    return { label: "U", price: product.price };
  }
  const def = product.sizes.find((s) => s.is_default && s.active) ?? product.sizes.find((s) => s.active);
  if (!def) return { label: "U", price: product.price };
  return { label: def.label, id: def.id, price: def.price };
}

interface UpsellCardProps {
  upsell: ApiUpsell;
  onAccept: () => void;
  onReject: () => void;
}

function UpsellCard({ upsell, onAccept, onReject }: UpsellCardProps) {
  const { product } = upsell;
  if (!product) return null;

  const price = upsell.promotional_price ?? product.price;
  const originalPrice = product.price;
  const hasDiscount = upsell.promotional_price !== null && upsell.promotional_price < originalPrice;

  const iconSrc = upsell.image_url || product.icon;
  const hasImage = isAssetUrl(iconSrc);

  return (
    <div className="bg-surface-02 rounded-2xl border border-surface-03 overflow-hidden">
      <div className="flex items-center gap-4 p-4">
        {/* Product image/icon */}
        <div className="w-16 h-16 rounded-xl bg-surface-03 flex-shrink-0 flex items-center justify-center text-2xl overflow-hidden">
          {hasImage
            ? <img src={resolveAssetUrl(iconSrc)} alt={product.name} className="w-full h-full object-cover" />
            : <span>{iconSrc || "🍕"}</span>
          }
        </div>

        {/* Text */}
        <div className="flex-1 min-w-0">
          <p className="text-cream font-bold text-sm leading-snug">{upsell.main_text}</p>
          {upsell.secondary_text && (
            <p className="text-stone text-xs mt-0.5 leading-snug">{upsell.secondary_text}</p>
          )}
          <div className="flex items-baseline gap-2 mt-1.5">
            <span className="text-gold font-bold text-base">R$ {price.toFixed(2)}</span>
            {hasDiscount && (
              <span className="text-stone text-xs line-through">R$ {originalPrice.toFixed(2)}</span>
            )}
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="grid grid-cols-2 border-t border-surface-03">
        <button
          type="button"
          onClick={onReject}
          className="flex items-center justify-center gap-2 py-3 text-stone text-sm font-medium hover:text-cream hover:bg-surface-03 transition-colors"
        >
          <X size={15} />
          Não, obrigado
        </button>
        <button
          type="button"
          onClick={onAccept}
          className="flex items-center justify-center gap-2 py-3 text-gold text-sm font-bold hover:bg-gold/10 border-l border-surface-03 transition-colors"
        >
          <ShoppingBag size={15} />
          Adicionar
        </button>
      </div>
    </div>
  );
}

interface Props {
  isLocked: boolean;
}

export default function CheckoutUpsell({ isLocked }: Props) {
  const { cart, cartSubtotal, addToCart } = useApp();
  const [upsells, setUpsells] = useState<ApiUpsell[]>([]);
  const [loading, setLoading] = useState(false);
  const [acceptedIds, setAcceptedIds] = useState<Set<string>>(new Set());
  const fetchedRef = useRef(false);

  useEffect(() => {
    if (isLocked || cart.length === 0) return;
    // Only fetch once per checkout session to avoid repeated requests
    if (fetchedRef.current) return;
    fetchedRef.current = true;

    const seen = getSeenIds();
    setLoading(true);

    upsellsApi
      .eligible({
        cart_items: cart.map((item) => ({
          product_id: item.productId,
          category: item.productData.category ?? undefined,
          quantity: item.quantity,
        })),
        cart_total: cartSubtotal,
      })
      .then((data) => {
        // Filter already seen in this session
        const fresh = data.filter((u) => !seen.has(u.id) && !acceptedIds.has(u.id));
        setUpsells(fresh);

        // Mark all as viewed and log events
        fresh.forEach((u) => {
          markSeen(u.id);
          upsellsApi.event({ upsell_id: u.id, event_type: "viewed" }).catch(() => {});
        });
      })
      .catch(() => {})
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLocked]);

  const handleAccept = (upsell: ApiUpsell) => {
    const product = upsell.product;
    if (!product) return;

    const price = upsell.promotional_price ?? product.price;
    const { label: sizeLabel, id: sizeId, price: sizePrice } = defaultSizeInfo(product);
    const finalPrice = upsell.promotional_price ?? sizePrice;

    // Add to existing cart via AppContext — does not create new checkout step
    addToCart(
      product as Parameters<typeof addToCart>[0],
      1,
      sizeLabel,
      [],
      [{ productId: product.id, name: product.name, price: finalPrice, icon: product.icon ?? "🍕" }],
      1,
      finalPrice,
      undefined,
      null,
      null,
      sizeId,
    );

    upsellsApi.event({ upsell_id: upsell.id, event_type: "accepted", revenue: price }).catch(() => {});

    setAcceptedIds((prev) => new Set([...prev, upsell.id]));
    setUpsells((prev) => prev.filter((u) => u.id !== upsell.id));
  };

  const handleReject = (upsell: ApiUpsell) => {
    upsellsApi.event({ upsell_id: upsell.id, event_type: "rejected" }).catch(() => {});
    setUpsells((prev) => prev.filter((u) => u.id !== upsell.id));
  };

  // Don't render anything when locked (after payment generated) or empty
  if (isLocked || (upsells.length === 0 && !loading)) return null;

  return (
    <section>
      <h2 className="text-cream font-bold text-lg mb-3 flex items-center gap-2">
        <Sparkles size={20} className="text-gold" />
        Adicione ao seu pedido
      </h2>

      {loading ? (
        <div className="flex items-center justify-center py-6 text-stone gap-2">
          <Loader2 size={18} className="animate-spin" />
          <span className="text-sm">Buscando sugestoes...</span>
        </div>
      ) : (
        <div className="space-y-3">
          {upsells.map((upsell) => (
            <UpsellCard
              key={upsell.id}
              upsell={upsell}
              onAccept={() => handleAccept(upsell)}
              onReject={() => handleReject(upsell)}
            />
          ))}
        </div>
      )}
    </section>
  );
}
