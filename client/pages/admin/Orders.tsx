import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle, CheckCircle2, ChevronRight, Clock3, Loader2,
  PackageCheck, Printer, RefreshCw, Route, ShoppingBag, Truck, Utensils, Volume2, VolumeX,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";
import { ordersApi, deliveryApi, type ApiOrder, type OrderStatus, type DeliveryPerson } from "@/lib/api";
import { printOrder } from "@/lib/printing";
import OrderTimer from "@/components/OrderTimer";
import { playOrderAlert, loadSoundType } from "@/lib/orderSound";

function playNewOrderAlert() {
  playOrderAlert(loadSoundType());
}

// ── Status labels ──────────────────────────────────────────────────────────────

const STATUS_LABELS: Record<string, string> = {
  pending: "Aguardando",
  waiting_payment: "Ag. pagamento",
  paid: "Pago",
  aguardando_pagamento: "Ag. pagamento",
  pago: "Pago",
  pagamento_recusado: "Pgto recusado",
  pagamento_expirado: "Pgto expirado",
  preparing: "Preparando",
  ready_for_pickup: "Pronto",
  on_the_way: "A caminho",
  delivered: "Entregue",
  cancelled: "Cancelado",
  refunded: "Reembolsado",
};

// ── Kanban columns ─────────────────────────────────────────────────────────────

type KanbanColumn = {
  id: string;
  title: string;
  description: string;
  statuses: OrderStatus[];
  icon: typeof Clock3;
  accent: string;
  targetStatus: OrderStatus | null; // status applied on drop
};

const KANBAN_COLUMNS: KanbanColumn[] = [
  {
    id: "waiting",
    title: "Aguardando pagamento",
    description: "Pedidos criados ou com pagamento em aberto",
    statuses: ["pending", "waiting_payment", "aguardando_pagamento"],
    icon: Clock3,
    accent: "text-orange-300 bg-orange-500/10 border-orange-500/20",
    targetStatus: "pending",
  },
  {
    id: "paid",
    title: "Pago",
    description: "Confirmados pelo fluxo de pagamento",
    statuses: ["paid", "pago"],
    icon: CheckCircle2,
    accent: "text-cyan-300 bg-cyan-500/10 border-cyan-500/20",
    targetStatus: "paid",
  },
  {
    id: "preparing",
    title: "Preparando",
    description: "Pedidos em produção",
    statuses: ["preparing"],
    icon: Utensils,
    accent: "text-gold bg-gold/10 border-gold/20",
    targetStatus: "preparing",
  },
  {
    id: "ready",
    title: "Pronto",
    description: "Aguardando retirada ou entrega",
    statuses: ["ready_for_pickup"],
    icon: PackageCheck,
    accent: "text-blue-300 bg-blue-500/10 border-blue-500/20",
    targetStatus: "ready_for_pickup",
  },
  {
    id: "delivery",
    title: "A caminho",
    description: "Saiu para entrega",
    statuses: ["on_the_way"],
    icon: Route,
    accent: "text-violet-300 bg-violet-500/10 border-violet-500/20",
    targetStatus: "on_the_way",
  },
  {
    id: "done",
    title: "Finalizados",
    description: "Entregues",
    statuses: ["delivered"],
    icon: ShoppingBag,
    accent: "text-green-300 bg-green-500/10 border-green-500/20",
    targetStatus: "delivered",
  },
  {
    id: "issues",
    title: "Problemas",
    description: "Recusados, expirados, cancelados ou reembolsados",
    statuses: ["pagamento_recusado", "pagamento_expirado", "cancelled", "refunded"],
    icon: AlertTriangle,
    accent: "text-red-300 bg-red-500/10 border-red-500/20",
    targetStatus: "cancelled",
  },
];

// Status → next status in the flow
const NEXT_STATUS: Partial<Record<string, OrderStatus>> = {
  pending: "paid",
  waiting_payment: "paid",
  aguardando_pagamento: "paid",
  paid: "preparing",
  pago: "preparing",
  preparing: "ready_for_pickup",
  ready_for_pickup: "on_the_way",
  on_the_way: "delivered",
};

const NEXT_LABEL: Partial<Record<string, string>> = {
  pending: "Confirmar Pago",
  waiting_payment: "Confirmar Pago",
  aguardando_pagamento: "Confirmar Pago",
  paid: "Preparando",
  pago: "Preparando",
  preparing: "Pronto",
  ready_for_pickup: "A caminho",
  on_the_way: "Entregue",
};

// ── Helpers ────────────────────────────────────────────────────────────────────

const statusColor = (status: string) => {
  if (status === "delivered") return "bg-green-500/15 text-green-300";
  if (status === "on_the_way" || status === "ready_for_pickup") return "bg-blue-500/15 text-blue-300";
  if (["cancelled", "refunded", "pagamento_recusado", "pagamento_expirado"].includes(status))
    return "bg-red-500/15 text-red-300";
  if (status === "paid" || status === "pago") return "bg-cyan-500/15 text-cyan-300";
  if (status === "preparing") return "bg-gold/15 text-gold";
  return "bg-stone/20 text-stone";
};

const formatCurrency = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const formatDateTime = (v: string) =>
  new Date(v).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

function orderTimeLabel(order: ApiOrder) {
  const diff = Date.now() - new Date(order.created_at).getTime();
  const minutes = Math.max(0, Math.floor(diff / 60000));
  if (minutes < 1) return "Agora";
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}min`;
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function AdminOrders() {
  const [orders, setOrders] = useState<ApiOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [newOrderFlash, setNewOrderFlash] = useState(false);

  // Motoboy assignment modal
  const [assignModal, setAssignModal] = useState<{ order: ApiOrder } | null>(null);
  const [availablePersons, setAvailablePersons] = useState<DeliveryPerson[]>([]);
  const [selectedPersonId, setSelectedPersonId] = useState("");
  const [estimatedMinutes, setEstimatedMinutes] = useState(40);
  const [assigning, setAssigning] = useState(false);

  // paidIds tracks orders already alerted — fires sound only once per order when it first becomes paid
  const paidIds = useRef<Set<string>>(new Set());
  const isFirstFetch = useRef(true);

  // Drag state — ref avoids triggering re-renders during drag
  const draggedId = useRef<string | null>(null);
  const [dragOverColumn, setDragOverColumn] = useState<string | null>(null);

  const fetchOrders = useCallback(async (silent = false) => {
    if (silent) setRefreshing(true);
    else setLoading(true);
    setError("");
    try {
      const data = await ordersApi.list({ limit: 150 });
      const sorted = [...data].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

      if (!isFirstFetch.current) {
        // Alert fires only when an order ENTERS paid/pago status for the first time
        const newlyPaid = sorted.filter(
          (o) => (o.status === "paid" || o.status === "pago") && !paidIds.current.has(o.id),
        );
        if (newlyPaid.length > 0 && soundEnabled) {
          playNewOrderAlert();
          setNewOrderFlash(true);
          setTimeout(() => setNewOrderFlash(false), 2000);
        }
      }
      isFirstFetch.current = false;
      // Mark all currently-paid orders so subsequent polls don't re-alert
      sorted
        .filter((o) => o.status === "paid" || o.status === "pago")
        .forEach((o) => paidIds.current.add(o.id));

      setOrders(sorted);
      setLastUpdated(new Date());
    } catch {
      setError("Não foi possível carregar os pedidos.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [soundEnabled]);

  useEffect(() => {
    fetchOrders();
    const id = window.setInterval(() => fetchOrders(true), 15_000);
    return () => window.clearInterval(id);
  }, [fetchOrders]);

  const handleStatusChange = useCallback(async (orderId: string, newStatus: OrderStatus) => {
    setUpdatingId(orderId);
    try {
      const updated = await ordersApi.updateStatus(orderId, newStatus);
      setOrders((prev) => prev.map((o) => (o.id === orderId ? updated : o)));
    } catch {
      alert("Erro ao atualizar status.");
    } finally {
      setUpdatingId(null);
    }
  }, []);

  // Drag handlers
  const handleDragStart = useCallback((orderId: string) => {
    draggedId.current = orderId;
  }, []);

  const handleDragEnd = useCallback(() => {
    draggedId.current = null;
    setDragOverColumn(null);
  }, []);

  const handleDrop = useCallback((column: KanbanColumn) => {
    const id = draggedId.current;
    if (!id || !column.targetStatus) return;
    const order = orders.find((o) => o.id === id);
    if (!order || order.status === column.targetStatus) return;
    handleStatusChange(id, column.targetStatus);
    setDragOverColumn(null);
  }, [orders, handleStatusChange]);

  const openAssignModal = useCallback(async (order: ApiOrder) => {
    setSelectedPersonId("");
    setEstimatedMinutes(40);
    setAssignModal({ order });
    try {
      const persons = await deliveryApi.listPersons(true);
      setAvailablePersons(persons ?? []);
    } catch {
      setAvailablePersons([]);
    }
  }, []);

  const handleAssign = useCallback(async () => {
    if (!assignModal || !selectedPersonId) return;
    setAssigning(true);
    try {
      await deliveryApi.assign(assignModal.order.id, selectedPersonId, estimatedMinutes);
      setAssignModal(null);
      setSelectedPersonId("");
      await fetchOrders(true);
    } catch {
      alert("Erro ao atribuir motoboy. Verifique se o motoboy está disponível.");
    } finally {
      setAssigning(false);
    }
  }, [assignModal, selectedPersonId, estimatedMinutes, fetchOrders]);

  const groupedOrders = useMemo(() => {
    const grouped = new Map<string, ApiOrder[]>();
    KANBAN_COLUMNS.forEach((col) => grouped.set(col.id, []));
    orders.forEach((order) => {
      const col = KANBAN_COLUMNS.find((c) => c.statuses.includes(order.status));
      grouped.get(col?.id ?? "waiting")?.push(order);
    });
    return grouped;
  }, [orders]);

  const activeOrders = orders.filter((o) => !["delivered", "cancelled", "refunded"].includes(o.status)).length;

  return (
    <div className="min-h-screen bg-surface-00 flex flex-col md:flex-row md:h-screen overflow-hidden">
      <AdminSidebar />

      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="bg-surface-02 border-b border-surface-03 px-4 md:px-8 py-4 flex flex-col xl:flex-row xl:items-center xl:justify-between gap-4">
          <div>
            <p className="text-gold text-xs font-bold uppercase tracking-[0.24em]">Kanban operacional</p>
            <h1 className="text-cream text-2xl font-black mt-1">Pedidos</h1>
            <p className="text-stone text-sm mt-1">
              Arraste os cards entre colunas ou use os botões para avançar o status.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className={`rounded-xl border px-3 py-2 transition-colors ${newOrderFlash ? "border-gold bg-gold/20" : "border-surface-03 bg-surface-03/60"}`}>
              <p className="text-stone text-[11px] uppercase tracking-widest">Ativos</p>
              <p className="text-cream text-sm font-black">{activeOrders}</p>
            </div>
            <div className="rounded-xl border border-surface-03 bg-surface-03/60 px-3 py-2">
              <p className="text-stone text-[11px] uppercase tracking-widest">Total carregado</p>
              <p className="text-cream text-sm font-black">{orders.length}</p>
            </div>
            <button
              onClick={() => setSoundEnabled((v) => !v)}
              title={soundEnabled ? "Desativar alerta sonoro" : "Ativar alerta sonoro"}
              className={`inline-flex items-center gap-2 rounded-xl border px-3 py-2.5 text-sm font-bold transition-colors ${soundEnabled ? "border-gold/40 bg-gold/10 text-gold hover:bg-gold/20" : "border-surface-03 bg-surface-03/60 text-stone hover:text-cream"}`}
            >
              {soundEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
            </button>
            <button
              onClick={() => fetchOrders(true)}
              disabled={loading || refreshing}
              className="inline-flex items-center gap-2 rounded-xl bg-gold px-4 py-2.5 text-sm font-bold text-cream transition hover:bg-gold/90 disabled:opacity-60"
            >
              <RefreshCw size={16} className={loading || refreshing ? "animate-spin" : ""} />
              Atualizar
            </button>
            <AdminTopActions />
          </div>
        </header>

        {/* Sub-header */}
        <section className="border-b border-surface-03 bg-surface-00 px-4 md:px-8 py-2 flex items-center justify-between gap-2">
          <p className="text-stone text-xs">Atualização automática a cada 15s · Arraste ou clique <ChevronRight size={11} className="inline" /> para avançar status</p>
          {lastUpdated && (
            <p className="text-stone text-xs">
              {lastUpdated.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
            </p>
          )}
        </section>

        {/* Body */}
        <div className="flex-1 overflow-hidden">
          {error && (
            <div className="mx-4 md:mx-8 mt-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex h-full items-center justify-center">
              <Loader2 size={40} className="animate-spin text-gold" />
            </div>
          ) : orders.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center px-6 text-center">
              <ShoppingBag size={54} className="mb-4 text-gold" />
              <p className="text-cream text-xl font-bold">Nenhum pedido ainda</p>
              <p className="text-stone text-sm mt-2">Os pedidos aparecem aqui automaticamente.</p>
            </div>
          ) : (
            <div className="h-full overflow-x-auto overflow-y-hidden p-4 md:p-6">
              <div className="flex h-full gap-4 min-w-max">
                {KANBAN_COLUMNS.map((column) => {
                  const Icon = column.icon;
                  const columnOrders = groupedOrders.get(column.id) ?? [];
                  const isDragOver = dragOverColumn === column.id;
                  return (
                    <section
                      key={column.id}
                      className={`flex h-full w-[300px] flex-col rounded-2xl border transition-colors ${
                        isDragOver
                          ? "border-gold bg-gold/5"
                          : "border-surface-03 bg-surface-02"
                      }`}
                      onDragOver={(e) => { e.preventDefault(); setDragOverColumn(column.id); }}
                      onDragLeave={(e) => {
                        if (!e.currentTarget.contains(e.relatedTarget as Node)) {
                          setDragOverColumn(null);
                        }
                      }}
                      onDrop={() => handleDrop(column)}
                    >
                      {/* Column header */}
                      <header className="border-b border-surface-03 p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <span className={`inline-flex h-8 w-8 items-center justify-center rounded-xl border ${column.accent}`}>
                                <Icon size={16} />
                              </span>
                              <h2 className="text-cream text-sm font-black truncate">{column.title}</h2>
                            </div>
                            <p className="text-stone text-xs mt-2 leading-snug">{column.description}</p>
                          </div>
                          <span className="rounded-full bg-surface-03 px-2.5 py-1 text-xs font-bold text-parchment flex-shrink-0">
                            {columnOrders.length}
                          </span>
                        </div>
                      </header>

                      {/* Cards */}
                      <div className="flex-1 overflow-y-auto p-3 space-y-3">
                        {columnOrders.length === 0 ? (
                          <div className={`rounded-xl border border-dashed p-6 text-center text-xs text-stone transition-colors ${isDragOver ? "border-gold/50 bg-gold/5 text-gold" : "border-surface-03"}`}>
                            {isDragOver ? "Soltar aqui" : "Sem pedidos"}
                          </div>
                        ) : (
                          columnOrders.map((order) => (
                            <OrderCard
                              key={order.id}
                              order={order}
                              updating={updatingId === order.id}
                              onAdvance={() => {
                                const next = NEXT_STATUS[order.status];
                                if (next) handleStatusChange(order.id, next);
                              }}
                              onAssignMotoboy={() => openAssignModal(order)}
                              onPrint={() => printOrder(order)}
                              onDragStart={() => handleDragStart(order.id)}
                              onDragEnd={handleDragEnd}
                            />
                          ))
                        )}
                      </div>
                    </section>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Motoboy assignment modal */}
      {assignModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-surface-02 rounded-2xl border border-surface-03 p-6 w-full max-w-md">
            <h3 className="text-cream font-bold text-lg mb-1">Atribuir Motoboy</h3>
            <p className="text-stone text-sm mb-5">
              Pedido #{assignModal.order.id.slice(0, 8).toUpperCase()} · {assignModal.order.delivery_name}
            </p>

            {availablePersons.length === 0 ? (
              <div className="rounded-xl border border-dashed border-surface-03 p-6 text-center mb-5">
                <Truck size={28} className="text-stone mx-auto mb-2" />
                <p className="text-stone text-sm">Nenhum motoboy disponível no momento.</p>
                <p className="text-stone/70 text-xs mt-1">Aguarde um motoboy ficar disponível.</p>
              </div>
            ) : (
              <div className="space-y-2 mb-5 max-h-56 overflow-y-auto pr-1">
                {availablePersons.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => setSelectedPersonId(p.id)}
                    className={`w-full text-left px-4 py-3 rounded-xl border transition-colors ${
                      selectedPersonId === p.id
                        ? "border-gold bg-gold/10 text-cream"
                        : "border-surface-03 bg-surface-03/40 text-parchment hover:border-gold/50"
                    }`}
                  >
                    <p className="font-bold text-sm">{p.name}</p>
                    <p className="text-xs text-stone mt-0.5">
                      {p.phone} · {p.vehicle_type} · {p.total_deliveries} entregas · ⭐ {p.average_rating.toFixed(1)}
                    </p>
                  </button>
                ))}
              </div>
            )}

            <label className="flex flex-col gap-1.5 mb-5">
              <span className="text-stone text-xs font-medium">Tempo estimado de entrega</span>
              <div className="flex items-center gap-3">
                <input
                  type="range" min={10} max={120} step={5}
                  value={estimatedMinutes}
                  onChange={(e) => setEstimatedMinutes(Number(e.target.value))}
                  className="flex-1 accent-gold"
                />
                <span className="text-gold font-bold text-sm w-14 text-right">{estimatedMinutes} min</span>
              </div>
            </label>

            <div className="flex gap-3">
              <button
                onClick={() => setAssignModal(null)}
                className="flex-1 rounded-xl border border-surface-03 py-2.5 text-stone text-sm hover:text-cream transition-colors"
              >
                Cancelar
              </button>
              <button
                disabled={!selectedPersonId || assigning}
                onClick={handleAssign}
                className="flex-1 flex items-center justify-center gap-2 rounded-xl bg-gold py-2.5 text-cream text-sm font-bold hover:bg-gold/90 disabled:opacity-50 transition-colors"
              >
                {assigning && <Loader2 size={14} className="animate-spin" />}
                {assigning ? "Atribuindo..." : "Atribuir"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Order Card ─────────────────────────────────────────────────────────────────

interface OrderCardProps {
  order: ApiOrder;
  updating: boolean;
  onAdvance: () => void;
  onAssignMotoboy?: () => void;
  onPrint: () => void;
  onDragStart: () => void;
  onDragEnd: () => void;
}

function OrderCard({ order, updating, onAdvance, onAssignMotoboy, onPrint, onDragStart, onDragEnd }: OrderCardProps) {
  const isReadyForPickup = order.status === "ready_for_pickup";
  const nextLabel = isReadyForPickup ? null : NEXT_LABEL[order.status];

  const itemSummary = order.items.slice(0, 2).map((item) => {
    const isMulti = item.flavor_division > 1;
    const name = isMulti ? item.flavors.map((f) => f.name).join(" + ") : item.product_name;
    return `${item.quantity}x ${name}`;
  });
  const remaining = Math.max(order.items.length - 2, 0);

  return (
    <article
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      className={`rounded-2xl border border-surface-03 bg-surface-03/45 p-4 shadow-sm select-none transition-opacity cursor-grab active:cursor-grabbing ${updating ? "opacity-50 pointer-events-none" : ""}`}
    >
      {/* Top row: ID + status badge */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-cream font-mono text-sm font-black">#{order.id.slice(0, 8).toUpperCase()}</h3>
          <p className="text-stone text-xs mt-1">{formatDateTime(order.created_at)} · {orderTimeLabel(order)}</p>
        </div>
        <span className={`rounded-full px-2 py-1 text-[10px] font-bold whitespace-nowrap flex-shrink-0 ${statusColor(order.status)}`}>
          {STATUS_LABELS[order.status] ?? order.status}
        </span>
      </div>

      {/* Customer */}
      <div className="mt-3">
        <p className="text-cream text-sm font-bold truncate">{order.delivery_name}</p>
        <p className="text-stone text-xs mt-0.5 truncate">{order.delivery_phone}</p>
        <p className="text-stone/80 text-xs mt-0.5 line-clamp-2">
          {order.delivery_street}
          {order.delivery_complement ? ` — ${order.delivery_complement}` : ""}
          {`, ${order.delivery_city}`}
        </p>
      </div>

      {/* Items */}
      <div className="mt-3 rounded-xl bg-surface-02/80 p-3">
        <p className="text-parchment text-xs font-bold mb-1.5">Itens</p>
        <div className="space-y-0.5">
          {itemSummary.map((item, i) => (
            <p key={i} className="text-stone text-xs line-clamp-1">{item}</p>
          ))}
          {remaining > 0 && <p className="text-gold text-xs font-semibold">+ {remaining} item(ns)</p>}
        </div>
      </div>

      {/* Total */}
      <div className="mt-3 flex items-center justify-between border-t border-surface-03 pt-3">
        <div>
          <p className="text-stone text-[10px] uppercase tracking-widest">Total</p>
          <p className="text-gold text-base font-black">{formatCurrency(order.total)}</p>
        </div>
        <div className="text-right">
          <p className="text-stone text-[10px] uppercase tracking-widest">Entrega</p>
          <p className="text-parchment text-xs font-semibold">{order.estimated_time} min</p>
        </div>
      </div>

      {/* Operational timer — só aparece após pagamento confirmado */}
      {order.paid_at && (
        <OrderTimer
          paidAt={order.paid_at}
          deliveredAt={order.delivered_at}
          targetMinutes={order.target_delivery_minutes ?? 45}
          status={order.status}
        />
      )}

      {/* Action buttons */}
      <div className="mt-3 flex gap-2">
        {/* Assign motoboy — for ready_for_pickup orders */}
        {isReadyForPickup && (
          <button
            onClick={onAssignMotoboy}
            disabled={updating}
            className="flex-1 flex items-center justify-center gap-1.5 rounded-lg bg-blue-500/15 hover:bg-blue-500/25 text-blue-300 text-xs font-bold py-2 px-3 transition-colors disabled:opacity-50"
          >
            <Truck size={13} />
            Atribuir Motoboy
          </button>
        )}

        {/* Advance status */}
        {nextLabel && (
          <button
            onClick={onAdvance}
            disabled={updating}
            className="flex-1 flex items-center justify-center gap-1.5 rounded-lg bg-gold/15 hover:bg-gold/25 text-gold text-xs font-bold py-2 px-3 transition-colors disabled:opacity-50"
          >
            {updating ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <ChevronRight size={13} />
            )}
            {nextLabel}
          </button>
        )}

        {/* Print */}
        <button
          onClick={onPrint}
          title="Imprimir pedido"
          className="flex items-center justify-center rounded-lg bg-surface-02 hover:bg-surface-03 text-parchment p-2 transition-colors"
        >
          <Printer size={14} />
        </button>
      </div>
    </article>
  );
}
