import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, Bell, CheckCircle2, MessageCircle, PackageCheck, RefreshCw, Search, Truck, X } from "lucide-react";
import { agenteWhatsAppApi, ordersApi, type ApiAgenteWhatsAppInternalAlert, type ApiOrder } from "@/lib/api";
import { chatbotAdminApi, type ChatbotConversation } from "@/lib/chatbotApi";
import { useAdminLayout } from "@/components/layout/AdminLayoutContext";

type AdminNotification = {
  id: string;
  title: string;
  description: string;
  time: string;
  href: string;
  icon: "new_order" | "ready" | "delivered" | "chat" | "agente_whatsapp";
  ackId?: string;
};

const NOTIFICATION_ORDER_STATUSES = new Set(["paid", "pago", "ready_for_pickup", "delivered"]);
const DISMISSED_NOTIFICATIONS_KEY = "admin.dismissed_notifications";
const MAX_DISMISSED_NOTIFICATIONS = 250;

function toText(value: unknown, fallback = ""): string {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) {
    const text = value.map((item) => toText(item)).filter(Boolean).join(", ");
    return text || fallback;
  }
  if (typeof value === "object") {
    const objectValue = value as Record<string, unknown>;
    const candidate =
      objectValue.message ?? objectValue.title ?? objectValue.description ?? objectValue.detail ?? objectValue.error ?? objectValue.name;
    if (candidate !== undefined && candidate !== value) return toText(candidate, fallback);
    try {
      return JSON.stringify(value);
    } catch {
      return fallback;
    }
  }
  return fallback;
}

function timeAgo(iso: string): string {
  const date = new Date(toText(iso));
  const timestamp = date.getTime();
  if (Number.isNaN(timestamp)) return "agora";
  const diff = Math.floor((Date.now() - timestamp) / 60_000);
  if (diff < 1) return "agora";
  if (diff < 60) return `${diff}min atras`;
  return `${Math.floor(diff / 60)}h atras`;
}

function orderCode(order: ApiOrder) {
  const id = toText(order.id);
  return order.order_code ? `#${toText(order.order_code)}` : `#${id.slice(0, 8).toUpperCase()}`;
}

function orderNotification(order: ApiOrder): AdminNotification | null {
  const time = toText(order.updated_at || order.created_at, new Date().toISOString());
  const total = typeof order.total === "number" ? order.total.toFixed(2).replace(".", ",") : toText(order.total, "0,00");
  const deliveryName = toText(order.delivery_name, "Cliente");
  if (order.status === "paid" || order.status === "pago") {
    return {
      id: `order-paid:${order.id}:${time}`,
      title: "Novo pedido confirmado",
      description: `${orderCode(order)} - ${deliveryName} - R$ ${total}`,
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
      description: `${orderCode(order)} entregue para ${deliveryName}`,
      time,
      href: "/painel/orders",
      icon: "delivered",
    };
  }
  return null;
}

function chatNotification(conversation: ChatbotConversation): AdminNotification {
  const sessionId = toText(conversation.session_id);
  const label = toText(conversation.nome_cliente, sessionId.slice(0, 8).toUpperCase() || "Conversa");
  return {
    id: `chat:${toText(conversation.id)}:${toText(conversation.status)}:${toText(conversation.iniciada_em)}`,
    title: conversation.status === "em_humano" ? "Chat aguardando atendimento" : "Nova conversa no chat",
    description: label,
    time: toText(conversation.iniciada_em, new Date().toISOString()),
    href: "/painel/chatbot",
    icon: "chat",
  };
}

function agenteWhatsAppNotification(alert: ApiAgenteWhatsAppInternalAlert): AdminNotification {
  const id = toText(alert.id);
  const time = toText(alert.last_seen_at || alert.updated_at || alert.created_at, new Date().toISOString());
  return {
    id: `agente-whatsapp:${id}:${time}`,
    title: toText(alert.title, "Alerta do agente WhatsApp"),
    description: toText(alert.message, "Verifique o agente WhatsApp."),
    time,
    href: "/painel/crm/agente-whatsapp",
    icon: "agente_whatsapp",
    ackId: id || undefined,
  };
}

function NotificationIcon({ icon }: { icon: AdminNotification["icon"] }) {
  const cls = "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg";
  if (icon === "agente_whatsapp") return <span className={`${cls} bg-red-500/15 text-red-300`}><AlertTriangle size={14} /></span>;
  if (icon === "ready") return <span className={`${cls} bg-blue-500/15 text-blue-300`}><PackageCheck size={14} /></span>;
  if (icon === "delivered") return <span className={`${cls} bg-green-500/15 text-green-300`}><Truck size={14} /></span>;
  if (icon === "chat") return <span className={`${cls} bg-violet-500/15 text-violet-300`}><MessageCircle size={14} /></span>;
  return <span className={`${cls} bg-gold/15 text-gold`}><CheckCircle2 size={14} /></span>;
}

function loadDismissedNotificationIds(): string[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(DISMISSED_NOTIFICATIONS_KEY) || "[]");
    return Array.isArray(parsed) ? parsed.filter((id): id is string => typeof id === "string") : [];
  } catch {
    return [];
  }
}

function saveDismissedNotificationIds(ids: string[]) {
  localStorage.setItem(DISMISSED_NOTIFICATIONS_KEY, JSON.stringify(ids.slice(-MAX_DISMISSED_NOTIFICATIONS)));
}

function AdminTopActionsContent({ hideSearch = false }: { hideSearch?: boolean }) {
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState<AdminNotification[]>([]);
  const [bellOpen, setBellOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const bellRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const dismissedRef = useRef<Set<string>>(new Set(loadDismissedNotificationIds()));

  const fetchNotifications = useCallback(async () => {
    try {
      const [orders, conversations, agenteAlerts] = await Promise.all([
        ordersApi.list({ limit: 50 }),
        chatbotAdminApi.listConversations(undefined, 1).catch(() => ({ items: [] })),
        agenteWhatsAppApi.listInternalAlerts({ status: "active", limit: 10 }).catch(() => []),
      ]);
      const orderNotifications = (orders ?? [])
        .filter((order) => NOTIFICATION_ORDER_STATUSES.has(order.status))
        .map(orderNotification)
        .filter((item): item is AdminNotification => Boolean(item));
      const chatNotifications = (conversations.items ?? [])
        .filter((conversation) => conversation.status === "aberta" || conversation.status === "em_humano")
        .map(chatNotification);
      const agenteNotifications = (agenteAlerts ?? []).map(agenteWhatsAppNotification);
      setNotifications([...agenteNotifications, ...orderNotifications, ...chatNotifications]
        .filter((notification) => !dismissedRef.current.has(notification.id))
        .sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime())
        .slice(0, 30));
    } catch {
      /* keep previous notifications */
    }
  }, []);

  useEffect(() => {
    fetchNotifications();
    const id = window.setInterval(fetchNotifications, 30_000);
    return () => window.clearInterval(id);
  }, [fetchNotifications]);

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

  const handleClearNotifications = () => {
    const nextDismissed = new Set([...dismissedRef.current, ...notifications.map((notification) => notification.id)]);
    dismissedRef.current = nextDismissed;
    saveDismissedNotificationIds([...nextDismissed]);
    notifications
      .filter((notification) => notification.ackId)
      .forEach((notification) => agenteWhatsAppApi.acknowledgeInternalAlert(notification.ackId!).catch(() => {}));
    setNotifications([]);
  };

  return (
    <div className="flex items-center gap-1.5 flex-shrink-0 rounded-xl border border-surface-03 bg-surface-01/70 p-1 shadow-sm">
      {!hideSearch && (searchOpen ? (
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
      ))}

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
              <div>
                <p className="text-cream font-bold text-sm">Notificacoes</p>
                <span className="text-[11px] text-stone">{count} ativa{count !== 1 ? "s" : ""}</span>
              </div>
              {notifications.length > 0 && (
                <button
                  type="button"
                  onClick={handleClearNotifications}
                  className="inline-flex items-center gap-1 rounded-lg border border-surface-03 px-2 py-1 text-[11px] font-bold text-stone transition-colors hover:border-gold/50 hover:text-gold"
                  title="Limpar notificacoes"
                >
                  <X size={12} />
                  Limpar
                </button>
              )}
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
                    onClick={() => {
                      if (notification.ackId) agenteWhatsAppApi.acknowledgeInternalAlert(notification.ackId).catch(() => {});
                      navigate(notification.href);
                      setBellOpen(false);
                    }}
                    className="flex w-full gap-3 border-b border-surface-03/40 px-4 py-3 text-left transition-colors last:border-0 hover:bg-surface-03/50"
                  >
                    <NotificationIcon icon={notification.icon} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-xs font-bold text-cream">{toText(notification.title)}</span>
                        <span className="shrink-0 text-[10px] text-stone">{timeAgo(notification.time)}</span>
                      </div>
                      <p className="mt-0.5 truncate text-[11px] text-stone">{toText(notification.description)}</p>
                    </div>
                  </button>
                ))
              )}
            </div>
            {notifications.length > 0 && (
              <div className="border-t border-surface-03 px-4 py-2.5">
                <button
                  onClick={() => { navigate(notifications[0]?.href || "/painel/orders"); setBellOpen(false); }}
                  className="w-full text-center text-gold text-xs font-bold hover:text-gold/80 transition-colors"
                >
                  Abrir notificacao mais recente
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function AdminTopActions({ force = false, hideSearch = false }: { force?: boolean; hideSearch?: boolean }) {
  const insideGlobalLayout = useAdminLayout();

  if (insideGlobalLayout && !force) {
    return <span data-admin-top-actions-placeholder className="hidden" />;
  }

  return <AdminTopActionsContent hideSearch={hideSearch} />;
}
