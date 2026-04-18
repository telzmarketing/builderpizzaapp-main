import { useNavigate, useLocation } from "react-router-dom";
import { Home, ShoppingCart, Bell, User, UtensilsCrossed } from "lucide-react";
import { useApp } from "@/context/AppContext";

export default function BottomNav() {
  const navigate = useNavigate();
  const location = useLocation();
  const { siteContent, cart } = useApp();
  const { nav } = siteContent;

  const active = (path: string) =>
    location.pathname === path ? "text-gold" : "text-stone hover:text-cream";

  return (
    <div className="fixed bottom-0 left-0 right-0 pb-4 px-4 z-50">
      <div className="bg-surface-02 rounded-full py-3 px-4 flex justify-around items-center shadow-2xl border border-surface-03">
        <button onClick={() => navigate("/")} className={`flex flex-col items-center gap-1 transition-colors ${active("/")}`}>
          <Home size={18} />
          <span className="text-[10px] font-medium">{nav.home}</span>
        </button>
        <button onClick={() => navigate("/cardapio")} className={`flex flex-col items-center gap-1 transition-colors ${active("/cardapio")}`}>
          <UtensilsCrossed size={18} />
          <span className="text-[10px] font-medium">Cardápio</span>
        </button>
        <button onClick={() => navigate("/cart")} className={`flex flex-col items-center gap-1 transition-colors relative ${active("/cart")}`}>
          <ShoppingCart size={18} />
          {cart.length > 0 && (
            <span className="absolute -top-1 right-0 bg-gold text-cream text-[10px] font-bold w-4 h-4 rounded-full flex items-center justify-center">
              {cart.length}
            </span>
          )}
          <span className="text-[10px] font-medium">{nav.cart}</span>
        </button>
        <button onClick={() => navigate("/pedidos")} className={`flex flex-col items-center gap-1 transition-colors ${active("/pedidos")}`}>
          <Bell size={18} />
          <span className="text-[10px] font-medium">{nav.orders}</span>
        </button>
        <button onClick={() => navigate("/conta")} className={`flex flex-col items-center gap-1 transition-colors ${active("/conta")}`}>
          <User size={18} />
          <span className="text-[10px] font-medium">{nav.account}</span>
        </button>
      </div>
    </div>
  );
}
