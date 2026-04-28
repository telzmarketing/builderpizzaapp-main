import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bell, BellOff, ChefHat, CheckCircle2, Clock3, Loader2,
  Maximize2, Minimize2, RefreshCw, UtensilsCrossed,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import { ordersApi, type ApiOrder, type ApiOrderItem, type OrderStatus } from "@/lib/api";

// ── Sound alert ────────────────────────────────────────────────────────────────

function playNewOrderAlert() {
  try {
    const ctx = new AudioContext();
    const beep = (freq: number, start: number, dur: number) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = freq;
      osc.type = "sine";
      gain.gain.setValueAtTime(0.35, ctx.currentTime + start);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + dur);
      osc.start(ctx.currentTime + start);
      osc.stop(ctx.currentTime + start + dur + 0.05);
    };
    beep(880, 0, 0.15);
    beep(1100, 0.2, 0.15);
    beep(880, 0.4, 0.25);
    setTimeout(() => {
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        const u = new SpeechSynthesisUtterance("Novo pedido!");
        u.lang = "pt-BR";
        u.rate = 0.95;
        u.pitch = 1.1;
        window.speechSynthesis.speak(u);
      }
    }, 700);
  } catch {
    // AudioContext pode falhar sem interação do usuário
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function elapsed(dateStr: string): string {
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (diff < 60) return `${diff}s`;
  if (diff < 3600) return `${Math.floor(diff / 60)}min`;
  return `${Math.floor(diff / 3600)}h ${Math.floor((diff % 3600) / 60)}min`;
}

function elapsedMinutes(dateStr: string): number {
  return Math.floor((Date.now() - new Date(dateStr).getTime()) / 60000);
}

function itemDescription(item: ApiOrderItem): string {
  const nameParts: string[] = [];
  if (item.flavors && item.flavors.length > 0) {
    nameParts.push(item.flavors.map((f) => f.name).join(" / "));
  } else {
    nameParts.push(item.product_name);
  }
  if (item.selected_size) nameParts.push(`(${item.selected_size})`);
  if (item.selected_crust_type) nameParts.push(`· ${item.selected_crust_type}`);
  if (item.selected_drink_variant) nameParts.push(`· ${item.selected_drink_variant}`);
  return nameParts.join(" ");
}

// ── Column config ──────────────────────────────────────────────────────────────

const KITCHEN_STATUSES: OrderStatus[] = ["paid", "pago", "preparing", "ready_for_pickup"];

type KitchenColumn = {
  id: string;
  label: string;
  statuses: OrderStatus[];
  accent: string;
  headerBorder: string;
  badge: string;
  actionLabel: string | null;
  actionStatus: OrderStatus | null;
  actionClass: string;
};

const COLUMNS: KitchenColumn[] = [
  {
    id: "fila",
    label: "Fila — Aguardando Preparo",
    statuses: ["paid", "pago"],
    accent: "text-amber-400",
    headerBorder: "border-amber-500/30",
    badge: "bg-amber-500/20 text-amber-300",
    actionLabel: "Iniciar Preparo",
    actionStatus: "preparing",
    actionClass: "bg-orange-500 hover:bg-orange-400 text-white",
  },
  {
    id: "preparing",
    label: "Em Preparo",
    statuses: ["preparing"],
    accent: "text-orange-400",
    headerBorder: "border-orange-500/30",
    badge: "bg-orange-500/20 text-orange-300",
    actionLabel: "Marcar como Pronto",
    actionStatus: "ready_for_pickup",
    actionClass: "bg-green-600 hover:bg-green-500 text-white",
  },
  {
    id: "ready",
    label: "Pronto — Aguardando Entrega",
    statuses: ["ready_for_pickup"],
    accent: "text-green-400",
    headerBorder: "border-green-500/30",
    badge: "bg-green-500/20 text-green-300",
    actionLabel: "Saiu para Entrega",
    actionStatus: "on_the_way",
    actionClass: "bg-blue-600 hover:bg-blue-500 text-white",
  },
];

function urgencyBorder(minutes: number): string {
  if (minutes >= 40) return "border-red-500/60 shadow-red-500/10 shadow-lg";
  if (minutes >= 25) return "border-amber-500/50";
  return "border-surface-03";
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function AdminCozinha() {
  const [orders, setOrders]       = useState<ApiOrder[]>([]);
  const [loading, setLoading]     = useState(true);
  const [updating, setUpdating]   = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState(new Date());
  const [soundOn, setSoundOn]     = useState(true);
  const [fullscreen, setFullscreen] = useState(false);
  const [, setTick]               = useState(0);

  const knownIds  = useRef<Set<string>>(new Set());
  const soundRef  = useRef(soundOn);
  soundRef.current = soundOn;

  const fetchOrders = useCallback(async (initial = false) => {
    try {
      const all = await ordersApi.list();
      const kitchen = all.filter((o) => KITCHEN_STATUSES.includes(o.status));

      if (!initial) {
        const fresh = kitchen.filter(
          (o) => (o.status === "paid" || o.status === "pago") && !knownIds.current.has(o.id),
        );
        if (fresh.length > 0 && soundRef.current) playNewOrderAlert();
      }

      kitchen.forEach((o) => knownIds.current.add(o.id));
      setOrders(kitchen);
      setLastRefresh(new Date());
    } catch {
      // mantém dados existentes em caso de erro
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchOrders(true); }, [fetchOrders]);

  // auto-refresh 30s
  useEffect(() => {
    const id = setInterval(() => fetchOrders(), 30_000);
    return () => clearInterval(id);
  }, [fetchOrders]);

  // timer tick para atualizar elapsed a cada 10s
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 10_000);
    return () => clearInterval(id);
  }, []);

  // fullscreen API
  useEffect(() => {
    if (fullscreen) {
      document.documentElement.requestFullscreen?.().catch(() => {});
    } else if (document.fullscreenElement) {
      document.exitFullscreen?.().catch(() => {});
    }
  }, [fullscreen]);

  useEffect(() => {
    const handler = () => setFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", handler);
    return () => document.removeEventListener("fullscreenchange", handler);
  }, []);

  const moveOrder = async (orderId: string, status: OrderStatus) => {
    setUpdating(orderId);
    try {
      await ordersApi.updateStatus(orderId, status);
      await fetchOrders();
    } finally {
      setUpdating(null);
    }
  };

  return (
    <div className="flex flex-col md:flex-row min-h-screen md:h-screen bg-surface-00 overflow-hidden">
      <AdminSidebar />

      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Header */}
        <div className="bg-surface-02 border-b border-surface-03 px-6 py-3 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3">
            <ChefHat size={22} className="text-gold" />
            <div>
              <h2 className="text-xl font-bold text-cream">Cozinha</h2>
              <p className="text-stone text-xs">
                Atualizado às{" "}
                {lastRefresh.toLocaleTimeString("pt-BR", {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                })}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setSoundOn((s) => !s)}
              title={soundOn ? "Silenciar alertas" : "Ativar alertas sonoros"}
              className={`p-2 rounded-lg border transition-colors ${
                soundOn
                  ? "border-gold/40 text-gold bg-gold/10"
                  : "border-surface-03 text-stone hover:text-cream"
              }`}
            >
              {soundOn ? <Bell size={16} /> : <BellOff size={16} />}
            </button>

            <button
              onClick={() => fetchOrders()}
              title="Atualizar agora"
              className="p-2 rounded-lg border border-surface-03 text-stone hover:text-cream transition-colors"
            >
              <RefreshCw size={16} />
            </button>

            <button
              onClick={() => setFullscreen((f) => !f)}
              title={fullscreen ? "Sair da tela cheia" : "Modo KDS — tela cheia"}
              className="p-2 rounded-lg border border-surface-03 text-stone hover:text-cream transition-colors"
            >
              {fullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
            </button>
          </div>
        </div>

        {/* Board */}
        {loading ? (
          <div className="flex-1 flex items-center justify-center text-stone gap-2">
            <Loader2 size={24} className="animate-spin" />
            Carregando pedidos...
          </div>
        ) : (
          <div className="flex-1 overflow-hidden flex">
            {COLUMNS.map((col) => {
              const colOrders = orders
                .filter((o) => col.statuses.includes(o.status))
                .sort(
                  (a, b) =>
                    new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
                );

              return (
                <div
                  key={col.id}
                  className="flex-1 flex flex-col border-r border-surface-03 last:border-r-0 overflow-hidden"
                >
                  {/* Column header */}
                  <div
                    className={`px-4 py-3 border-b ${col.headerBorder} bg-surface-02/60 flex-shrink-0 flex items-center justify-between`}
                  >
                    <span className={`font-bold text-sm ${col.accent}`}>{col.label}</span>
                    <span
                      className={`text-xs font-bold px-2.5 py-0.5 rounded-full ${col.badge}`}
                    >
                      {colOrders.length}
                    </span>
                  </div>

                  {/* Cards */}
                  <div className="flex-1 overflow-y-auto p-3 space-y-3">
                    {colOrders.length === 0 && (
                      <div className="flex flex-col items-center justify-center h-36 text-stone/40 text-sm gap-2 select-none">
                        <UtensilsCrossed size={28} />
                        <span>Nenhum pedido</span>
                      </div>
                    )}

                    {colOrders.map((order) => {
                      const mins       = elapsedMinutes(order.created_at);
                      const isUpdating = updating === order.id;

                      return (
                        <div
                          key={order.id}
                          className={`bg-surface-02 rounded-xl border p-4 space-y-3 transition-all ${urgencyBorder(mins)}`}
                        >
                          {/* Card header */}
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <p className="text-cream font-bold text-lg leading-tight tracking-wide">
                                #{order.id.slice(0, 8).toUpperCase()}
                              </p>
                              <p className="text-stone text-sm">{order.delivery_name}</p>
                            </div>
                            <div
                              className={`flex items-center gap-1 text-xs flex-shrink-0 font-semibold ${
                                mins >= 40
                                  ? "text-red-400"
                                  : mins >= 25
                                  ? "text-amber-400"
                                  : "text-stone"
                              }`}
                            >
                              <Clock3 size={12} />
                              {elapsed(order.created_at)}
                            </div>
                          </div>

                          {/* Items */}
                          <div className="space-y-2 border-t border-surface-03 pt-3">
                            {order.items.map((item) => (
                              <div key={item.id}>
                                <div className="flex items-baseline gap-2">
                                  <span className="text-gold font-extrabold text-lg min-w-[2rem] text-center leading-none">
                                    {item.quantity}×
                                  </span>
                                  <span className="text-cream font-semibold text-sm leading-snug">
                                    {itemDescription(item)}
                                  </span>
                                </div>
                                {item.notes && (
                                  <p className="ml-9 text-amber-300 text-xs mt-1 flex items-start gap-1">
                                    <span className="flex-shrink-0">⚠</span>
                                    {item.notes}
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>

                          {/* Action */}
                          {col.actionLabel && col.actionStatus && (
                            <button
                              onClick={() => moveOrder(order.id, col.actionStatus!)}
                              disabled={isUpdating}
                              className={`w-full py-2.5 rounded-lg text-sm font-bold transition-colors flex items-center justify-center gap-2 ${col.actionClass} disabled:opacity-50`}
                            >
                              {isUpdating ? (
                                <Loader2 size={14} className="animate-spin" />
                              ) : (
                                <CheckCircle2 size={14} />
                              )}
                              {col.actionLabel}
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
