import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { ChevronLeft, Loader2, ShoppingBag } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { ordersApi, type ApiOrder } from "@/lib/api";
import BottomNav from "@/components/BottomNav";
import MoschettieriLogo from "@/components/MoschettieriLogo";

const statusStyle: Record<string, string> = {
  pending: "bg-slate-500/20 text-stone",
  waiting_payment: "bg-yellow-500/20 text-yellow-400",
  paid: "bg-cyan-500/20 text-cyan-400",
  preparing: "bg-gold/20 text-gold-light",
  ready_for_pickup: "bg-purple-500/20 text-purple-400",
  on_the_way: "bg-blue-500/20 text-blue-400",
  delivered: "bg-green-500/20 text-green-400",
  cancelled: "bg-red-500/20 text-red-400",
  refunded: "bg-slate-500/20 text-stone",
};

export default function Pedidos() {
  const navigate = useNavigate();
  const { siteContent, customer } = useApp();
  const { pages, nav } = siteContent;
  const c = pages.pedidos;
  const statusLabels = pages.tracking.statusLabels;

  const [orders, setOrders] = useState<ApiOrder[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!customer) return;
    setLoading(true);
    ordersApi.list({ customer_id: customer.id, limit: 50 })
      .then((data) => setOrders([...data].reverse()))
      .catch(() => {/* show empty state */})
      .finally(() => setLoading(false));
  }, [customer]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00">

      {/* Header */}
      <div className="bg-brand-dark px-4 py-3 flex justify-between items-center sticky top-0 z-30">
        <button onClick={() => navigate(-1)} className="text-parchment hover:text-cream transition-colors">
          <ChevronLeft size={24} />
        </button>
        <MoschettieriLogo className="text-cream text-base" />
        <div className="w-6" />
      </div>

      <div className="px-4 pt-6 pb-32">
        {!customer ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <ShoppingBag size={64} className="text-slate-600 mb-4" />
            <h2 className="text-cream font-bold text-xl mb-2">Faça login para ver seus pedidos</h2>
            <p className="text-stone text-sm mb-6">Entre na sua conta para acompanhar o histórico de pedidos.</p>
            <button onClick={() => navigate("/conta")} className="bg-gold hover:bg-gold/90 text-cream font-bold py-3 px-8 rounded-full transition-colors">
              Entrar
            </button>
          </div>
        ) : loading ? (
          <div className="flex items-center justify-center py-24">
            <Loader2 size={40} className="animate-spin text-gold" />
          </div>
        ) : orders.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <ShoppingBag size={64} className="text-slate-600 mb-4" />
            <h2 className="text-cream font-bold text-xl mb-2">{c.emptyTitle}</h2>
            <p className="text-stone text-sm mb-6">{c.emptySubtitle}</p>
            <Link to="/" className="bg-gold hover:bg-gold/90 text-cream font-bold py-3 px-8 rounded-full transition-colors">
              {c.orderButton}
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {orders.map((order) => (
              <div key={order.id} className="bg-surface-02 rounded-2xl border border-surface-03 overflow-hidden">
                {/* Order Header */}
                <div className="flex items-center justify-between px-4 py-3 border-b border-surface-03">
                  <div>
                    <p className="text-cream font-bold text-sm font-mono">
                      #{order.id.slice(0, 8).toUpperCase()}
                    </p>
                    <p className="text-stone text-xs">
                      {new Date(order.created_at).toLocaleDateString("pt-BR", {
                        day: "2-digit",
                        month: "short",
                        year: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  </div>
                  <span className={`text-xs font-bold px-3 py-1 rounded-full ${statusStyle[order.status] ?? "bg-slate-500/20 text-stone"}`}>
                    {statusLabels[order.status] ?? order.status}
                  </span>
                </div>

                {/* Items */}
                <div className="px-4 py-3 space-y-2">
                  {order.items.map((item) => {
                    const isMulti = item.flavor_division > 1;
                    const displayIcons = item.flavors.map((f) => f.icon).join("");
                    const displayName = isMulti
                      ? item.flavors.map((f) => f.name).join(" + ")
                      : item.product_name;
                    return (
                      <div key={item.id} className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-full bg-surface-03 flex items-center justify-center text-sm flex-shrink-0">
                          {displayIcons || "🍕"}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-cream text-sm truncate">{displayName}</p>
                          <p className="text-stone text-xs">
                            x{item.quantity} · {item.selected_size}
                            {isMulti && ` · ${item.flavor_division === 2 ? "Meio a Meio" : "3 Sabores"}`}
                          </p>
                        </div>
                        <p className="text-parchment text-sm flex-shrink-0">
                          R$ {(item.final_price * item.quantity).toFixed(2)}
                        </p>
                      </div>
                    );
                  })}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between px-4 py-3 bg-brand-dark/50 border-t border-surface-03">
                  <div>
                    <p className="text-stone text-xs">Total pago</p>
                    <p className="text-gold font-bold">R$ {order.total.toFixed(2)}</p>
                  </div>
                  <button
                    onClick={() => navigate(`/order-tracking?orderId=${order.id}`)}
                    className="text-xs text-gold-light border border-gold/40 px-4 py-2 rounded-full hover:bg-gold/10 transition-colors"
                  >
                    Ver detalhes
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <BottomNav />
    </div>
  );
}
