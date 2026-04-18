import { Link, useNavigate } from "react-router-dom";
import { ChevronLeft, Plus, Minus, Trash2 } from "lucide-react";
import { useApp, CartItem } from "@/context/AppContext";

function divisionLabel(d: number) {
  if (d === 2) return "Meio a Meio";
  if (d === 3) return "3 Sabores";
  return "Inteira";
}

function CartItemRow({ item, onRemove, onUpdate }: {
  item: CartItem;
  onRemove: () => void;
  onUpdate: (qty: number) => void;
}) {
  const isMulti = item.flavorDivision > 1;
  const displayIcons = item.flavors.map((f) => f.icon).join("");
  const displayName = isMulti
    ? item.flavors.map((f) => f.name).join(" + ")
    : item.productData.name;

  return (
    <div className="bg-slate-800 rounded-2xl p-4 border border-slate-700">
      <div className="flex items-center gap-3">
        <div className="w-16 h-16 rounded-xl bg-slate-700 flex-shrink-0 flex items-center justify-center text-2xl leading-none">
          {displayIcons || item.productData.icon}
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-white font-semibold text-sm leading-tight">{displayName}</h3>
          <div className="flex flex-wrap gap-1 mt-1">
            <span className="text-xs text-slate-400">
              {SIZE_LABEL[item.selectedSize] ?? item.selectedSize}
              {isMulti && ` · ${divisionLabel(item.flavorDivision)}`}
            </span>
          </div>
          <p className="text-orange-500 font-bold text-sm mt-1">
            R$ {item.finalPrice.toFixed(2)}
          </p>
        </div>
        <div className="flex flex-col items-center gap-1 flex-shrink-0">
          <button onClick={() => onUpdate(item.quantity + 1)} className="w-7 h-7 rounded-full bg-slate-700 hover:bg-slate-600 text-orange-400 flex items-center justify-center transition-colors">
            <Plus size={14} />
          </button>
          <div className="w-9 h-9 rounded-full bg-orange-500 flex items-center justify-center">
            <span className="text-white text-sm font-bold">{item.quantity}</span>
          </div>
          <button onClick={() => item.quantity === 1 ? onRemove() : onUpdate(item.quantity - 1)} className="w-7 h-7 rounded-full bg-slate-700 hover:bg-slate-600 text-slate-400 hover:text-red-400 flex items-center justify-center transition-colors">
            <Minus size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}

const SIZE_LABEL: Record<string, string> = { P: "Pequena", M: "Média", G: "Grande", GG: "Gigante", Small: "Small", Medium: "Medium", Large: "Large", Massive: "Massive" };

export default function Cart() {
  const navigate = useNavigate();
  const { cart, removeFromCart, updateCartItem, cartSubtotal, cartDeliveryFee, cartTotal, siteContent } = useApp();
  const { pages, nav } = siteContent;
  const c = pages.cart;

  if (cart.length === 0) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-950">
        <div className="bg-slate-900 px-4 py-4 flex justify-between items-center sticky top-0 z-30">
          <button onClick={() => navigate(-1)} className="text-slate-300 hover:text-white transition-colors">
            <ChevronLeft size={24} />
          </button>
          <h1 className="text-white font-bold flex-1 text-center">{c.title}</h1>
          <div className="w-6"></div>
        </div>
        <div className="flex-1 flex items-center justify-center px-4 py-16">
          <div className="text-center">
            <div className="text-6xl mb-4">🛒</div>
            <h2 className="text-2xl font-bold text-white mb-2">{c.emptyTitle}</h2>
            <p className="text-slate-400 mb-6">{c.emptySubtitle}</p>
            <Link to="/" className="inline-block bg-orange-500 hover:bg-orange-600 text-white font-bold py-3 px-6 rounded-full transition-colors">
              {c.menuButton}
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-950">

      {/* Header */}
      <div className="bg-slate-900 px-4 py-4 flex justify-between items-center sticky top-0 z-30">
        <button onClick={() => navigate(-1)} className="text-slate-300 hover:text-white transition-colors">
          <ChevronLeft size={24} />
        </button>
        <h1 className="text-white font-bold flex-1 text-center">
          {c.title} <span className="text-orange-500 text-sm font-normal">({cart.length} {cart.length === 1 ? "item" : "itens"})</span>
        </h1>
        <div className="w-6"></div>
      </div>

      {/* Content */}
      <div className="px-4 pt-6 pb-36">
        <div className="space-y-3">
          {cart.map((item) => (
            <CartItemRow
              key={item.cartItemId}
              item={item}
              onRemove={() => removeFromCart(item.cartItemId)}
              onUpdate={(qty) => updateCartItem(item.cartItemId, qty, item.selectedSize, item.selectedAddOns)}
            />
          ))}
        </div>

        <div className="bg-slate-800 rounded-xl p-4 mt-6 space-y-3 border border-slate-700">
          <div className="flex justify-between text-slate-300 text-sm">
            <span>Subtotal dos itens:</span>
            <span>R$ {cartSubtotal.toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-slate-300 text-sm">
            <span>Taxa de entrega:</span>
            <span>R$ {cartDeliveryFee.toFixed(2)}</span>
          </div>
          <div className="border-t border-slate-700 pt-3 flex justify-between">
            <span className="text-white font-bold">Total:</span>
            <span className="text-orange-500 font-bold text-lg">R$ {cartTotal.toFixed(2)}</span>
          </div>
        </div>
      </div>

      {/* Checkout Button */}
      <div className="fixed bottom-0 left-0 right-0 bg-slate-950/95 border-t border-slate-800 px-4 py-4 backdrop-blur-sm">
        <button
          onClick={() => navigate("/checkout")}
          className="w-full bg-orange-500 hover:bg-orange-600 text-white font-bold py-4 px-4 rounded-full text-center transition-colors text-base active:scale-95 shadow-lg shadow-orange-500/30"
        >
          {c.checkoutButton} · R$ {cartTotal.toFixed(2)}
        </button>
      </div>
    </div>
  );
}
