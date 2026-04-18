import { useNavigate, useLocation } from "react-router-dom";
import { Home, ShoppingCart, Bell, User } from "lucide-react";
import { useApp } from "@/context/AppContext";

export default function BottomNav() {
  const navigate = useNavigate();
  const location = useLocation();
  const { siteContent, cart } = useApp();
  const { nav } = siteContent;

  const active = (path: string) =>
    location.pathname === path ? "text-orange-500" : "text-slate-400 hover:text-white";

  return (
    <div className="fixed bottom-0 left-0 right-0 pb-4 px-4 z-50">
      <div className="bg-slate-800 rounded-full py-3 px-6 flex justify-around items-center shadow-2xl border border-slate-700">
        <button onClick={() => navigate("/")} className={`flex flex-col items-center gap-1 transition-colors ${active("/")}`}>
          <Home size={20} />
          <span className="text-xs font-medium">{nav.home}</span>
        </button>
        <button onClick={() => navigate("/cart")} className={`flex flex-col items-center gap-1 transition-colors relative ${active("/cart")}`}>
          <ShoppingCart size={20} />
          {cart.length > 0 && (
            <span className="absolute -top-1 -right-2 bg-orange-500 text-white text-[10px] font-bold w-4 h-4 rounded-full flex items-center justify-center">
              {cart.length}
            </span>
          )}
          <span className="text-xs font-medium">{nav.cart}</span>
        </button>
        <button onClick={() => navigate("/pedidos")} className={`flex flex-col items-center gap-1 transition-colors ${active("/pedidos")}`}>
          <Bell size={20} />
          <span className="text-xs font-medium">{nav.orders}</span>
        </button>
        <button onClick={() => navigate("/conta")} className={`flex flex-col items-center gap-1 transition-colors ${active("/conta")}`}>
          <User size={20} />
          <span className="text-xs font-medium">{nav.account}</span>
        </button>
      </div>
    </div>
  );
}
