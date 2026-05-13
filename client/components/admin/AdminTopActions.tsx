import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, CheckCircle2, MessageCircle, PackageCheck, RefreshCw, Search, Truck, X } from "lucide-react";
import { ordersApi, type ApiOrder } from "@/lib/api";
import { chatbotAdminApi, type ChatbotConversation } from "@/lib/chatbotApi";
import { useAdminLayout } from "@/components/layout/AdminLayoutContext";

type AdminNotification = {
  id: string;
  title: string;
  description: string;
  time: string;
  href: string;
  icon: "new_order" | "ready" | "delivered" | "chat";
};

const NOTIFICATION_ORDER_STATUSES = new Set(["paid", "pago", "ready_for_pickup", "delivered"]);

function timeAgo(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 60_000);
  if (diff < 1) return "agora";
  if (diff < 60) return `${diff}min atras`;
  return `${Math.floor(diff / 60)}h atras`;
}

function orderCode(order: ApiOrder) {
  return order.order_code ? `#${order.order_code}` : `#${order.id.slice(0, 8).toUpperCase()}`;
}

function orderNotification(order: ApiOrder): AdminNotification | null {
  const time = order.updated_at || order.created_at;
  if (order.status === "paid" || order.status === "pago") {
    return {
      id: `order-paid:${order.id}:${time}`,
      title: "Novo pedido confirmado",
      description: `${orderCode(order)} - ${order.delivery_name} - R$ ${order.total.toFixed(2).replace(".", ",")}`,
      time,
      href: "/painel/orders",
      icon: "new_order",
    };
  }
  if (order.status === "ready_for_pickup") {
    return {
      id: `order-ready:${order.id}:${time}`,
      title: "Pedido pronto",
      description: `${orderCode(order)} pronto para retirada/entrega`,
      time,
      href: "/painel/orders",
      icon: "ready",
    };
  }
  if (order.status === "delivered") {
    return {
      id: `order-delivered:${order.id}:${time}`,
      title: "Pedido entregue",
      description: `${orderCode(order)} entregue para ${order.delivery_name}`,
      time,
      href: "/painel/orders",
      icon: "delivered",
    };
  }
  return null;
}

function chatNotification(conversation: ChatbotConversation): AdminNotification {
  const label = conversation.nome_cliente || conversation.session_id.slice(0, 8).toUpperCase();
  return {
    id: `chat:${conversation.id}:${conversation.status}:${conversation.iniciada_em}`,
    title: conversation.status === "em_humano" ? "Chat aguardando atendimento" : "Nova conversa no chat",
    description: label,
    time: conversation.iniciada_em,
    href: "/painel/chatbot",
    icon: "chat",
  };
}

function NotificationIcon({ icon }: { icon: AdminNotification["icon"] }) {
  const cls = "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg";
  if (icon === "ready") return <span className={`${cls} bg-blue-500/15 text-blue-300`}><PackageCheck size={14} /></span>;
  if (icon === "delivered") return <span className={`${cls} bg-green-500/15 text-green-300`}><Truck size={14} /></span>;
  if (icon === "chat") return <span className={`${cls} bg-violet-500/15 text-violet-300`}><MessageCircle size={14} /></span>;
  return <span className={`${cls} bg-gold/15 text-gold`}><CheckCircle2 size={14} /></span>;
}

function AdminTopActionsContent() {
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState<AdminNotification[]>([]);
  const [bellOpen, setBellOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const bellRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const fetchNotifications = async () => {
      try {
        const [orders, conversations] = await Promise.all([
          ordersApi.list({ limit: 50 }),
          chatbotAdminApi.listConversations(undefined, 1).catch(() => ({ items: [] })),
        ]);
        const orderNotifications = (orders ?? [])
          .filter((order) => NOTIFICATION_ORDER_STATUSES.has(order.status))
          .map(orderNotification)
          .filter((item): item is AdminNotification => Boolean(item));
        const chatNotifications = (conversations.items ?? [])
          .filter((conversation) => conversation.status === "aberta" || conversation.status === "em_humano")
          .map(chatNotification);
        setNotifications([...orderNotifications, ...chatNotifications]
          .sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime())
          .slice(0, 30));
      } catch {
        /* keep previous notifications */
      }
    };
    fetchNotifications();
    const id = window.setInterval(fetchNotifications, 30_000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    if (searchOpen) searchRef.current?.focus();
  }, [searchOpen]);

  useEffect(() => {
    if (!bellOpen) return;
    const handler = (e: MouseEvent) => {
      if (bellRef.current && !bellRef.current.contains(e.target as Node)) setBellOpen(false);
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

  const count = notifications.length;

  return (
    <div className="flex items-center gap-1.5 flex-shrink-0 rounded-xl border border-surface-03 bg-surface-01/70 p-1 shadow-sm">
      {searchOpen ? (
        <form
          onSubmit={handleSearch}
          className="flex items-center gap-1.5 rounded-lg bg-surface-02 border border-surface-03 px-3 py-1.5"
        >
          <Search size={14} className="text-stone flex-shrink-0" />
          <input
            ref={searchRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar pedido..."
            className="bg-transparent text-cream text-sm w-32 sm:w-40 outline-none placeholder:text-stone/50"
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

      <button
        onClick={() => { setRefreshing(true); setTimeout(() => window.location.reload(), 200); }}
        disabled={refreshing}
        className="flex items-center justify-center w-8 h-8 rounded-lg text-stone hover:text-cream hover:bg-surface-03 transition-colors disabled:opacity-50"
        title="Atualizar pagina"
      >
        <RefreshCw size={15} className={refreshing ? "animate-spin" : ""} />
      </button>

      <div ref={bellRef} className="relative">
        <button
          onClick={() => setBellOpen((v) => !v)}
          className="relative flex items-center justify-center w-8 h-8 rounded-lg text-stone hover:text-cream hover:bg-surface-03 transition-colors"
          title="Notificacoes"
        >
          <Bell size={15} />
          {count > 0 && (
            <span className="absolute -top-1 -right-1 min-w-[16px] h-4 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center px-1 leading-none">
              {count > 99 ? "99+" : count}
            </span>
          )}
        </button>

        {bellOpen && (
          <div className="absolute top-10 right-0 z-50 w-80 overflow-hidden rounded-2xl border border-surface-03 bg-surface-02 shadow-2xl">
            <div className="flex items-center justify-between border-b border-surface-03 px-4 py-3">
              <p className="text-cream font-bold text-sm">Notificacoes</p>
              <span className="text-[11px] text-stone">{count} ativa{count !== 1 ? "s" : ""}</span>
            </div>
            <div className="max-h-72 overflow-y-auto">
              {notifications.length === 0 ? (
                <div className="flex flex-col items-center py-8 text-center px-4">
                  <Bell size={28} className="text-stone mb-2" />
                  <p className="text-stone text-sm">Nenhuma notificacao ativa</p>
                </div>
              ) : (
                notifications.map((notification) => (
                  <button
                    key={notification.id}
                    onClick={() => { navigate(notification.href); setBellOpen(false); }}
                    className="flex w-full gap-3 border-b border-surface-03/40 px-4 py-3 text-left transition-colors last:border-0 hover:bg-surface-03/50"
                  >
                    <NotificationIcon icon={notification.icon} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-xs font-bold text-cream">{notification.title}</span>
                        <span className="shrink-0 text-[10px] text-stone">{timeAgo(notification.time)}</span>
                      </div>
                      <p className="mt-0.5 truncate text-[11px] text-stone">{notification.description}</p>
                    </div>
                  </button>
                ))
              )}
            </div>
            {notifications.length > 0 && (
              <div className="border-t border-surface-03 px-4 py-2.5">
                <button
                  onClick={() => { navigate("/painel/orders"); setBellOpen(false); }}
                  className="w-full text-center text-gold text-xs font-bold hover:text-gold/80 transition-colors"
                >
                  Ver painel de pedidos
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function AdminTopActions({ force = false }: { force?: boolean }) {
  const insideGlobalLayout = useAdminLayout();

  if (insideGlobalLayout && !force) {
    return <span data-admin-top-actions-placeholder className="hidden" />;
  }

  return <AdminTopActionsContent />;
}
