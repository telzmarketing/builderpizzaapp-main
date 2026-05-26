import { Fragment, lazy, Suspense, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ChevronLeft, Plus, Minus, Trash2, UtensilsCrossed, ShoppingCart, Tag, Check, X } from "lucide-react";
import { useApp, CartItem } from "@/context/AppContext";
import { couponsApi, isAssetUrl, resolveOptimizedAssetUrl, storeOperationApi, type ApiCouponGift, type StoreOperationStatus } from "@/lib/api";
import { pizzaSizeLabel } from "@/lib/pizzaSizes";
import BottomNav from "@/components/BottomNav";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import StoreStatusBanner from "@/components/StoreStatusBanner";

const CheckoutUpsell = lazy(() => import("@/pages/checkout/CheckoutUpsell"));

function divisionLabel(d: number) {
  if (d === 2) return "Meio a Meio";
  if (d === 3) return "3 Sabores";
  return "Inteira";
}

function CartProductIcon({ icons }: { icons: string[] }) {
  const safeIcons = icons.filter(Boolean).slice(0, 3);
  const displayIcons = safeIcons.length > 0 ? safeIcons : ["🍕"];
  const isSingle = displayIcons.length === 1;

  return (
    <div className="w-16 h-16 rounded-xl bg-surface-03 flex-shrink-0 overflow-hidden">
      <div className={`w-full h-full ${isSingle ? "flex items-center justify-center" : "grid grid-cols-2 gap-0.5 p-1"}`}>
        {displayIcons.map((icon, index) => (
          <div key={`${icon}-${index}`} className="min-w-0 min-h-0 rounded-lg bg-surface-02 flex items-center justify-center overflow-hidden">
            {isAssetUrl(icon) ? (
              <img src={resolveOptimizedAssetUrl(icon, 160)} alt="" className="w-full h-full object-cover" />
            ) : (
              <span className={isSingle ? "text-2xl leading-none" : "text-lg leading-none"}>{icon}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function CartItemRow({ item, onRemove, onUpdate }: {
  item: CartItem;
  onRemove: () => void;
  onUpdate: (qty: number) => void;
}) {
  const isMulti = item.flavorDivision > 1;
  const displayIcons = isMulti ? item.flavors.map((f) => f.icon) : [item.productData.icon];
  const displayName = isMulti
    ? item.flavors.map((f) => f.name).join(" + ")
    : item.productData.name;

  return (
    <div className="bg-surface-02 rounded-2xl p-4 border border-surface-03">
      <div className="flex items-center gap-3">
        <CartProductIcon icons={displayIcons} />
        <div className="flex-1 min-w-0">
          <h3 className="text-cream font-semibold text-sm leading-tight">{displayName}</h3>
          <div className="flex flex-wrap gap-1 mt-1">
            <span className="text-xs text-stone">
              {SIZE_LABEL[item.selectedSize] ?? pizzaSizeLabel(item.selectedSize)}
              {isMulti && ` · ${divisionLabel(item.flavorDivision)}`}
              {item.selectedCrustType && ` · ${item.selectedCrustType.name}`}
              {item.selectedDrinkVariant && ` · ${item.selectedDrinkVariant.name}`}
            </span>
          </div>
          <p className="text-gold font-bold text-sm mt-1">
            R$ {item.finalPrice.toFixed(2)}
          </p>
          {item.promotionApplied && item.promotionName && (
            <p className="text-emerald-300 text-[11px] font-semibold mt-0.5">{item.promotionName} aplicada</p>
          )}
        </div>
        <div className="flex flex-col items-center gap-1 flex-shrink-0">
          <button onClick={() => onUpdate(item.quantity + 1)} className="w-7 h-7 rounded-full bg-surface-03 hover:bg-brand-mid text-gold-light flex items-center justify-center transition-colors">
            <Plus size={14} />
          </button>
          <div className="w-9 h-9 rounded-full bg-gold flex items-center justify-center">
            <span className="text-cream text-sm font-bold">{item.quantity}</span>
          </div>
          <button onClick={() => item.quantity === 1 ? onRemove() : onUpdate(item.quantity - 1)} className="w-7 h-7 rounded-full bg-surface-03 hover:bg-brand-mid text-stone hover:text-red-400 flex items-center justify-center transition-colors">
            <Minus size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}

const SIZE_LABEL: Record<string, string> = {
  Brotinho: "Pizza Broto",
  "Pizza Broto": "Pizza Broto",
  "Pizza Grande": "Pizza Grande",
  P: "Pequena",
  M: "Media",
  G: "Grande",
  GG: "Gigante",
  Small: "Small",
  Medium: "Medium",
  Large: "Large",
  Massive: "Massive",
};

export default function Cart() {
  const navigate = useNavigate();
  const { cart, removeFromCart, updateCartItem, cartSubtotal, cartDeliveryFee, cartTotal, siteContent, customer } = useApp();
  const { pages, nav } = siteContent;
  const c = pages.cart;

  const [couponCode, setCouponCode] = useState("");
  const [couponDiscount, setCouponDiscount] = useState(0);
  const [couponFreeShipping, setCouponFreeShipping] = useState(false);
  const [couponGift, setCouponGift] = useState<ApiCouponGift | null>(null);
  const [couponMsg, setCouponMsg] = useState("");
  const [couponApplied, setCouponApplied] = useState(false);
  const [couponLoading, setCouponLoading] = useState(false);
  const [storeStatus, setStoreStatus] = useState<StoreOperationStatus | null>(null);

  useEffect(() => {
    storeOperationApi.status().then(setStoreStatus).catch(() => setStoreStatus(null));
  }, []);

  const selectedItemsCount = cart.reduce((total, item) => total + item.quantity, 0);
  const selectedItemsTitle = selectedItemsCount === 1 ? "Item escolhido" : "Itens escolhidos";

  const promotionBlocksCoupons = cart.some((item) => item.promotionApplied && item.promotionBlocksOtherCoupons);
  const promotionFreeShipping = cart.some((item) => item.promotionApplied && item.promotionFreeShipping);
  const promotionGiftByCartItemId = useMemo(() => {
    const gifts = new Map<string, ApiCouponGift>();
    cart.forEach((item) => {
      if (!item.promotionApplied || !item.promotionGiftEnabled || !item.promotionGiftProductId || !item.promotionGiftName) return;
      const quantity = Math.max(1, item.promotionGiftQuantity ?? 1) * item.quantity;
      gifts.set(item.cartItemId, {
        product_id: item.promotionGiftProductId,
        name: item.promotionGiftName,
        icon: item.promotionGiftIcon ?? "🎁",
        quantity,
        unit_price: 0,
        original_price: 0,
        is_gift: true,
        gift_reason: "product_promotion",
        promotion_id: item.promotionId ?? null,
        promotion_name: item.promotionName ?? null,
      });
    });
    return gifts;
  }, [cart]);

  useEffect(() => {
    if (!promotionBlocksCoupons || !couponApplied) return;
    setCouponCode("");
    setCouponDiscount(0);
    setCouponFreeShipping(false);
    setCouponGift(null);
    setCouponApplied(false);
    setCouponMsg("Este carrinho tem produto em promocao que bloqueia outros cupons.");
  }, [promotionBlocksCoupons, couponApplied]);

  const handleApplyCoupon = async () => {
    if (!couponCode.trim()) return;
    if (promotionBlocksCoupons) {
      setCouponMsg("Este carrinho tem produto em promocao que bloqueia outros cupons.");
      return;
    }
    setCouponLoading(true);
    setCouponMsg("");
    try {
      const result = await couponsApi.apply(
        couponCode.trim(),
        cartSubtotal,
        customer?.id,
        customer?.phone ?? undefined,
        cartDeliveryFee,
      );
      if (result.valid) {
        setCouponDiscount(result.discount_amount);
        setCouponFreeShipping(result.free_shipping_applied);
        setCouponGift(result.gift);
        setCouponApplied(true);
        setCouponMsg(result.message);
      } else {
        setCouponDiscount(0);
        setCouponFreeShipping(false);
        setCouponGift(null);
        setCouponApplied(false);
        setCouponMsg(result.message);
      }
    } catch {
      setCouponMsg("Erro ao validar cupom.");
    } finally {
      setCouponLoading(false);
    }
  };

  const handleRemoveCoupon = () => {
    setCouponCode("");
    setCouponDiscount(0);
    setCouponFreeShipping(false);
    setCouponGift(null);
    setCouponApplied(false);
    setCouponMsg("");
  };

  const deliveryFeeFinal = couponFreeShipping || promotionFreeShipping ? 0 : cartDeliveryFee;
  const finalTotal = cartSubtotal + deliveryFeeFinal - couponDiscount;

  if (cart.length === 0) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00 flex flex-col">
        <div className="bg-brand-dark px-4 py-3 flex justify-between items-center sticky top-0 z-30">
          <button onClick={() => navigate(-1)} className="text-parchment hover:text-cream transition-colors">
            <ChevronLeft size={24} />
          </button>
          <button onClick={() => navigate("/")} aria-label="Ir para a home da loja">
            <MoschettieriLogo className="text-cream text-base scale-[1.14] origin-center" />
          </button>
          <div className="w-6"></div>
        </div>
        <div className="px-4 pt-6">
          <h1 className="text-2xl font-bold text-cream">Carrinho de Compra</h1>
        </div>
        <div className="flex-1 flex items-center justify-center px-4 py-16 pb-32">
          <div className="text-center">
            <div className="text-6xl mb-4">🛒</div>
            <h2 className="text-2xl font-bold text-cream mb-2">{c.emptyTitle}</h2>
            <p className="text-stone mb-6">{c.emptySubtitle}</p>
            <Link to="/" className="inline-block bg-gold hover:bg-gold/90 text-cream font-bold py-3 px-6 rounded-full transition-colors">
              {c.menuButton}
            </Link>
          </div>
        </div>
        <BottomNav />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00">

      {/* Header */}
      <div className="bg-brand-dark px-4 py-3 flex justify-between items-center sticky top-0 z-30">
        <button onClick={() => navigate(-1)} className="text-parchment hover:text-cream transition-colors">
          <ChevronLeft size={24} />
        </button>
        <button onClick={() => navigate("/")} aria-label="Ir para a home da loja">
          <MoschettieriLogo className="text-cream text-base scale-[1.14] origin-center" />
        </button>
        <div className="w-6"></div>
      </div>

      {/* Content */}
      <div className="px-4 pt-6 pb-36">
        <div className="mb-5">
          <h1 className="text-2xl font-bold text-cream">Carrinho de Compra</h1>
        </div>

        <div className="space-y-3">
          <h2 className="text-sm font-bold uppercase tracking-wide text-gold-light">
            {selectedItemsTitle}
          </h2>
          {cart.map((item) => {
            const promotionGift = promotionGiftByCartItemId.get(item.cartItemId);
            return (
              <Fragment key={item.cartItemId}>
                <CartItemRow
                  item={item}
                  onRemove={() => removeFromCart(item.cartItemId)}
                  onUpdate={(qty) => updateCartItem(item.cartItemId, qty, item.selectedSize, item.selectedAddOns)}
                />
                {promotionGift && (
                  <div className="bg-green-500/10 rounded-2xl p-4 border border-green-500/30">
                    <div className="flex items-center gap-3">
                      <CartProductIcon icons={[promotionGift.icon || "🎁"]} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="text-cream font-semibold text-sm leading-tight truncate">{promotionGift.name}</h3>
                          <span className="rounded-full bg-green-500/20 px-2 py-0.5 text-[10px] font-bold text-green-300">Brinde</span>
                        </div>
                        <p className="text-stone text-xs mt-1">{promotionGift.quantity}x - Promocao {promotionGift.promotion_name}</p>
                        <p className="text-green-400 font-bold text-sm mt-1">R$ 0,00</p>
                      </div>
                    </div>
                  </div>
                )}
              </Fragment>
            );
          })}
          {couponGift && (
            <div className="bg-green-500/10 rounded-2xl p-4 border border-green-500/30">
              <div className="flex items-center gap-3">
                <CartProductIcon icons={[couponGift.icon || "🎁"]} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="text-cream font-semibold text-sm leading-tight truncate">{couponGift.name}</h3>
                    <span className="rounded-full bg-green-500/20 px-2 py-0.5 text-[10px] font-bold text-green-300">Brinde</span>
                  </div>
                  <p className="text-stone text-xs mt-1">{couponGift.quantity}x - Cupom {couponGift.coupon_code}</p>
                  <p className="text-green-400 font-bold text-sm mt-1">R$ 0,00</p>
                </div>
              </div>
            </div>
          )}
          <Suspense fallback={null}>
            <CheckoutUpsell isLocked={false} />
          </Suspense>
        </div>

        {/* Action Buttons */}
        <div className="mt-6 space-y-3">
          <button
            onClick={() => navigate("/cardapio")}
            className="w-full py-3 rounded-full border-2 border-surface-03 hover:border-gold/50 text-parchment hover:text-cream flex items-center justify-center gap-2 transition-colors text-sm font-medium"
          >
            <UtensilsCrossed size={16} className="text-gold" />
            Adicionar outro item
          </button>
          <button
            onClick={() => navigate("/cardapio")}
            className="w-full py-3 rounded-full border-2 border-surface-03 hover:border-gold/50 text-parchment hover:text-cream flex items-center justify-center gap-2 transition-colors text-sm font-medium"
          >
            <span className="text-base">🥤</span>
            Adicionar bebidas
          </button>
        </div>

        {/* Coupon Field */}
        <div className="bg-surface-02 rounded-xl p-4 mt-4 border border-surface-03">
          <p className="text-parchment text-sm font-medium mb-2 flex items-center gap-2">
            <Tag size={14} className="text-gold" />
            Cupom de desconto
          </p>
          {couponApplied ? (
            <div className="flex items-center gap-2 bg-green-500/10 border border-green-500/30 rounded-lg px-3 py-2">
              <Check size={16} className="text-green-400 flex-shrink-0" />
              <span className="text-green-400 text-sm flex-1">{couponMsg}</span>
              <button onClick={handleRemoveCoupon} className="text-stone hover:text-red-400 transition-colors">
                <X size={14} />
              </button>
            </div>
          ) : (
            <>
              {promotionBlocksCoupons && (
                <p className="text-amber-300 text-xs mb-2">Produto em promocao neste carrinho bloqueia outros cupons.</p>
              )}
              <div className="flex gap-2">
                <input
                  type="text"
                  value={couponCode}
                  onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
                  onKeyDown={(e) => e.key === "Enter" && handleApplyCoupon()}
                  placeholder="Digite o código"
                  disabled={promotionBlocksCoupons}
                  className="flex-1 bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream placeholder-stone text-sm focus:outline-none focus:border-gold font-mono uppercase"
                />
                <button
                  onClick={handleApplyCoupon}
                  disabled={promotionBlocksCoupons || couponLoading || !couponCode.trim()}
                  className="bg-gold hover:bg-gold/90 disabled:opacity-50 text-cream font-bold px-4 py-2 rounded-lg text-sm transition-colors"
                >
                  {couponLoading ? "..." : "Aplicar"}
                </button>
              </div>
              {couponMsg && (
                <p className="text-red-400 text-xs mt-1">{couponMsg}</p>
              )}
            </>
          )}
        </div>

        <div className="bg-surface-02 rounded-xl p-4 mt-4 space-y-3 border border-surface-03">
          <div className="flex justify-between text-parchment text-sm">
            <span>Subtotal dos itens:</span>
            <span>R$ {cartSubtotal.toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-parchment text-sm">
            <span>Taxa de entrega:</span>
            <span>{couponFreeShipping || promotionFreeShipping ? "Gratis" : `R$ ${cartDeliveryFee.toFixed(2)}`}</span>
          </div>
          {promotionFreeShipping && (
            <div className="flex justify-between text-sm">
              <span className="text-green-400">Frete gratis da promocao:</span>
              <span className="text-green-400">Aplicado</span>
            </div>
          )}
          {couponDiscount > 0 && (
            <div className="flex justify-between text-sm">
              <span className="text-green-400">Desconto do cupom:</span>
              <span className="text-green-400">- R$ {couponDiscount.toFixed(2)}</span>
            </div>
          )}
          <div className="border-t border-surface-03 pt-3 flex justify-between">
            <span className="text-cream font-bold">Total:</span>
            <span className="text-gold font-bold text-lg">R$ {finalTotal.toFixed(2)}</span>
          </div>
        </div>

      </div>

      {/* Finalizar Pedido */}
      <div className="px-4 mb-24">
        <StoreStatusBanner compact />
      </div>

      <div className="fixed bottom-20 left-0 right-0 px-4">
        <button
          onClick={() => {
            if (storeStatus && !storeStatus.is_open && !storeStatus.allow_scheduled_orders) return;
            if (!customer) { navigate("/conta?redirect=/checkout"); return; }
            navigate("/checkout");
          }}
          disabled={!!storeStatus && !storeStatus.is_open && !storeStatus.allow_scheduled_orders}
          className={`w-full font-bold py-4 px-4 rounded-full text-center transition-colors text-base active:scale-95 shadow-lg flex items-center justify-center gap-2 ${
            storeStatus && !storeStatus.is_open && !storeStatus.allow_scheduled_orders
              ? "bg-surface-03 text-stone cursor-not-allowed shadow-none"
              : "bg-gold hover:bg-gold/90 text-cream shadow-gold/30"
          }`}
        >
          <ShoppingCart size={18} />
          {storeStatus && !storeStatus.is_open && !storeStatus.allow_scheduled_orders
            ? "Loja fechada"
            : `Finalizar pedido · R$ ${finalTotal.toFixed(2)}`}
        </button>
      </div>
      <BottomNav />
    </div>
  );
}
