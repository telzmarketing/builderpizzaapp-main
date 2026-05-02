import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, RefreshCw, Search, X, ShoppingBag } from "lucide-react";
import { ordersApi, type ApiOrder } from "@/lib/api";

function timeAgo(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 60_000);
  if (diff < 1) return "agora";
  if (diff < 60) return `${diff}min atrás`;
  return `${Math.floor(diff / 60)}h atrás`;
}

const ACTIVE_STATUSES = new Set(["pending", "confirmed", "preparing", "ready_for_pickup"]);

export default function AdminTopActions() {
  const navigate = useNavigate();

  const [pendingOrders, setPendingOrders] = useState<ApiOrder[]>([]);
  const [bellOpen, setBellOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const bellRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const fetch = () =>
      ordersApi
        .list({ limit: 20 })
        .then((orders) =>
          setPendingOrders((orders ?? []).filter((o) => ACTIVE_STATUSES.has(o.status)))
        )
        .catch(() => {});
    fetch();
    const id = window.setInterval(fetch, 30_000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    if (searchOpen) searchRef.current?.focus();
  }, [searchOpen]);

  useEffect(() => {
    if (!bellOpen) return;
    const handler = (e: MouseEvent) => {
      if (bellRef.current && !bellRef.current.contains(e.target as Node))
        setBellOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [bellOpen]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    navigate(`/painel/orders?q=${encodeURIComponent(query.trim())}`);
    setQuery("");
    setSearchOpen(false);
  };

  const count = pendingOrders.length;

  return (
    <div className="flex items-center gap-1.5 flex-shrink-0">
      {/* Search */}
      {searchOpen ? (
        <form
          onSubmit={handleSearch}
          className="flex items-center gap-1.5 bg-surface-01 border border-surface-03 rounded-xl px-3 py-1.5"
        >
          <Search size={14} className="text-stone flex-shrink-0" />
          <input
            ref={searchRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar pedido..."
            className="bg-transparent text-cream text-sm w-40 outline-none placeholder:text-stone/50"
          />
          <button
            type="button"
            onClick={() => { setSearchOpen(false); setQuery(""); }}
            className="text-stone hover:text-cream transition-colors"
          >
            <X size={13} />
          </button>
        </form>
      ) : (
        <button
          onClick={() => setSearchOpen(true)}
          className="flex items-center justify-center w-8 h-8 rounded-lg text-stone hover:text-cream hover:bg-surface-03 transition-colors"
          title="Buscar pedido"
        >
          <Search size={15} />
        </button>
      )}

      {/* Refresh */}
      <button
        onClick={() => { setRefreshing(true); setTimeout(() => window.location.reload(), 200); }}
        disabled={refreshing}
        className="flex items-center justify-center w-8 h-8 rounded-lg text-stone hover:text-cream hover:bg-surface-03 transition-colors disabled:opacity-50"
        title="Atualizar página"
      >
        <RefreshCw size={15} className={refreshing ? "animate-spin" : ""} />
      </button>

      {/* Bell */}
      <div ref={bellRef} className="relative">
        <button
          onClick={() => setBellOpen((v) => !v)}
          className="relative flex items-center justify-center w-8 h-8 rounded-lg text-stone hover:text-cream hover:bg-surface-03 transition-colors"
          title="Notificações"
        >
          <Bell size={15} />
          {count > 0 && (
            <span className="absolute -top-1 -right-1 min-w-[16px] h-4 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center px-1 leading-none">
              {count > 99 ? "99+" : count}
            </span>
          )}
        </button>

        {bellOpen && (
          <div className="absolute top-10 right-0 w-80 bg-surface-02 border border-surface-03 rounded-2xl shadow-2xl overflow-hidden z-50">
            <div className="px-4 py-3 border-b border-surface-03 flex items-center justify-between">
              <p className="text-cream font-bold text-sm">Pedidos ativos</p>
              <span className="text-[11px] text-stone">
                {count} pendente{count !== 1 ? "s" : ""}
              </span>
            </div>
            <div className="max-h-72 overflow-y-auto">
              {pendingOrders.length === 0 ? (
                <div className="flex flex-col items-center py-8 text-center px-4">
                  <ShoppingBag size={28} className="text-stone mb-2" />
                  <p className="text-stone text-sm">Nenhum pedido ativo</p>
                </div>
              ) : (
                pendingOrders.map((order) => (
                  <button
                    key={order.id}
                    onClick={() => { navigate("/painel/orders"); setBellOpen(false); }}
                    className="w-full text-left px-4 py-3 hover:bg-surface-03/50 transition-colors border-b border-surface-03/40 last:border-0"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-cream text-xs font-bold font-mono">
                        #{order.id.slice(0, 8).toUpperCase()}
                      </span>
                      <span className="text-stone text-[10px]">{timeAgo(order.created_at)}</span>
                    </div>
                    <p className="text-stone text-[11px] mt-0.5 truncate">{order.delivery_name}</p>
                    <p className="text-gold text-[11px] font-bold">
                      R$ {order.total.toFixed(2).replace(".", ",")}
                    </p>
                  </button>
                ))
              )}
            </div>
            {pendingOrders.length > 0 && (
              <div className="px-4 py-2.5 border-t border-surface-03">
                <button
                  onClick={() => { navigate("/painel/orders"); setBellOpen(false); }}
                  className="w-full text-center text-gold text-xs font-bold hover:text-gold/80 transition-colors"
                >
                  Ver todos os pedidos →
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
