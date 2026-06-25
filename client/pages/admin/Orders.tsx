import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  AlertTriangle, Bell, BellOff, CalendarDays, CheckCircle2, ChevronLeft, ChevronRight, Clock3, Loader2,
  PackageCheck, Printer, RefreshCw, Route, ShoppingBag, Trash2, Truck,
  UserCheck, Users, Utensils,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";
import {
  ordersApi, paymentsApi, deliveryApi, marketingVisitorsApi,
  type ApiEffectivePermissions, type ApiOrder, type OrderStatus, type DeliveryPerson,
} from "@/lib/api";
import { loadPrinterSettings, printConfirmedOrder, printOrder, type PrintTemplate } from "@/lib/printing";
import OrderTimer from "@/components/OrderTimer";
import { playOrderAlert, loadSoundType } from "@/lib/orderSound";

function playNewOrderAlert() {
  playOrderAlert(loadSoundType());
}

// ── Status labels ──────────────────────────────────────────────────────────────

const STATUS_LABELS: Record<string, string> = {
  pending: "Aguardando",
  waiting_payment: "Ag. pagamento",
  paid: "Pedido confirmado",
  aguardando_pagamento: "Ag. pagamento",
  pago: "Pedido confirmado",
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
    title: "Pedido Confirmado",
    description: "Pedidos confirmados para preparo",
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
  pending: "Aprovar pagamento",
  waiting_payment: "Aprovar pagamento",
  aguardando_pagamento: "Aprovar pagamento",
  paid: "Preparando",
  pago: "Preparando",
  preparing: "Pronto",
  ready_for_pickup: "A caminho",
  on_the_way: "Entregue",
};

const WAITING_PAYMENT_STATUSES = new Set(["pending", "waiting_payment", "aguardando_pagamento"]);
const CONFIRMED_PAYMENT_STATUSES = new Set(["paid", "pago"]);
const CONFIRMED_PAYMENT_VALUES = new Set(["approved", "paid"]);
const AUTO_PRINTED_CONFIRMED_ORDERS_KEY = "moschettieri_auto_printed_confirmed_orders";
const DELETE_CONFIRMATION_TEXT = "excluir";

function loadStoredAdminPermissions(): ApiEffectivePermissions | null {
  try {
    const raw = localStorage.getItem("admin_permissions");
    return raw ? JSON.parse(raw) as ApiEffectivePermissions : null;
  } catch {
    return null;
  }
}

function canDeleteOrdersFromPermissions(permissions: ApiEffectivePermissions | null) {
  if (!permissions) return false;
  if (permissions.is_master) return true;
  const roleName = (permissions.role_name ?? "").trim().toLowerCase();
  const roleId = (permissions.role_id ?? "").trim().toLowerCase();
  return (
    roleName === "administrador" ||
    roleName === "administrativo" ||
    roleId === "administrador" ||
    roleId === "administrativo"
  );
}

function loadAutoPrintedConfirmedOrderIds() {
  try {
    const raw = localStorage.getItem(AUTO_PRINTED_CONFIRMED_ORDERS_KEY);
    const ids = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(ids) ? ids.filter((id) => typeof id === "string") : []);
  } catch {
    return new Set<string>();
  }
}

function rememberAutoPrintedConfirmedOrder(orderId: string) {
  try {
    const ids = Array.from(loadAutoPrintedConfirmedOrderIds());
    const next = [orderId, ...ids.filter((id) => id !== orderId)].slice(0, 200);
    localStorage.setItem(AUTO_PRINTED_CONFIRMED_ORDERS_KEY, JSON.stringify(next));
  } catch {
    /* ignore storage errors */
  }
}

function printConfirmedOrderOnce(order: ApiOrder) {
  if (!CONFIRMED_PAYMENT_STATUSES.has(order.status)) return true;
  if (!loadPrinterSettings().autoPrintConfirmedOrders) return true;
  if (loadAutoPrintedConfirmedOrderIds().has(order.id)) return true;

  const opened = printConfirmedOrder(order);
  if (opened) rememberAutoPrintedConfirmedOrder(order.id);
  return opened;
}

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

const toDateInputValue = (date: Date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const todayInputValue = () => toDateInputValue(new Date());

const inputDateToLocalDate = (value: string) => {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
};

const dayRangeIso = (value: string) => {
  const start = inputDateToLocalDate(value);
  const end = inputDateToLocalDate(value);
  end.setHours(23, 59, 59, 999);
  return {
    date_from: start.toISOString(),
    date_to: end.toISOString(),
  };
};

const shiftDateInput = (value: string, days: number) => {
  const date = inputDateToLocalDate(value);
  date.setDate(date.getDate() + days);
  return toDateInputValue(date);
};

const formatDayLabel = (value: string) =>
  inputDateToLocalDate(value).toLocaleDateString("pt-BR", {
    weekday: "long",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });

function orderTimeLabel(order: ApiOrder) {
  const diff = Date.now() - new Date(order.created_at).getTime();
  const minutes = Math.max(0, Math.floor(diff / 60000));
  if (minutes < 1) return "Agora";
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}min`;
}

// ── Main component ─────────────────────────────────────────────────────────────

function paymentInfoLabel(order: ApiOrder) {
  if (order.pay_on_delivery) return "Pagamento na entrega";
  if (order.payment_status === "approved" || order.payment_status === "paid") return "Pagamento online efetuado";
  return null;
}

function isEffectiveRevenueOrder(order: ApiOrder) {
  return (
    CONFIRMED_PAYMENT_VALUES.has(order.payment_status ?? "") &&
    !["cancelled", "refunded"].includes(order.status)
  );
}

export default function AdminOrders() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [orders, setOrders] = useState<ApiOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [newOrderFlash, setNewOrderFlash] = useState(false);
  const [selectedDate, setSelectedDate] = useState(() => todayInputValue());
  const [onlineStats, setOnlineStats] = useState({ visitors: 0, registeredCustomers: 0 });
  const [deleteModal, setDeleteModal] = useState<{ order: ApiOrder; confirmation: string } | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const adminPermissions = useMemo(() => loadStoredAdminPermissions(), []);
  const canDeleteOrders = useMemo(() => canDeleteOrdersFromPermissions(adminPermissions), [adminPermissions]);
  const orderSearchQuery = searchParams.get("q")?.trim().toLowerCase() ?? "";

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
      const data = await ordersApi.list({ ...dayRangeIso(selectedDate), limit: 500 });
      const sorted = [...data].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

      if (!isFirstFetch.current && selectedDate === todayInputValue()) {
        // Alert fires only when an order ENTERS paid/pago status for the first time
        const newlyPaid = sorted.filter(
          (o) => (o.status === "paid" || o.status === "pago") && !paidIds.current.has(o.id),
        );
        const blockedPrint = newlyPaid.some((order) => !printConfirmedOrderOnce(order));
        if (blockedPrint) {
          setError("O navegador bloqueou a impressao automatica. Habilite pop-ups para imprimir cozinha e recepcao.");
        }
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
  }, [selectedDate, soundEnabled]);

  const fetchOnlineStats = useCallback(async () => {
    try {
      const data = await marketingVisitorsApi.list("today");
      setOnlineStats({
        visitors: data.online_visitors ?? 0,
        registeredCustomers: data.online_registered_customers ?? 0,
      });
    } catch {
      setOnlineStats({ visitors: 0, registeredCustomers: 0 });
    }
  }, []);

  useEffect(() => {
    fetchOrders();
    fetchOnlineStats();
    const id = window.setInterval(() => fetchOrders(true), 15_000);
    const onlineId = window.setInterval(fetchOnlineStats, 15_000);
    return () => {
      window.clearInterval(id);
      window.clearInterval(onlineId);
    };
  }, [fetchOrders, fetchOnlineStats]);

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

  const handleApprovePayment = useCallback(async (orderId: string) => {
    setUpdatingId(orderId);
    try {
      await paymentsApi.approve(orderId);
      const updated = await ordersApi.get(orderId);
      setOrders((prev) => prev.map((o) => (o.id === orderId ? updated : o)));
    } catch {
      alert("Erro ao aprovar pagamento.");
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
    if (WAITING_PAYMENT_STATUSES.has(order.status)) {
      setDragOverColumn(null);
      return;
    }
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

  const handleDeleteOrder = useCallback(async () => {
    if (!deleteModal || deleteModal.confirmation.trim().toLowerCase() !== DELETE_CONFIRMATION_TEXT) return;
    setDeletingId(deleteModal.order.id);
    setError("");
    try {
      await ordersApi.remove(deleteModal.order.id);
      setOrders((prev) => prev.filter((order) => order.id !== deleteModal.order.id));
      setDeleteModal(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel excluir o pedido.");
    } finally {
      setDeletingId(null);
    }
  }, [deleteModal]);

  const filteredOrders = useMemo(() => {
    if (!orderSearchQuery) return orders;
    return orders.filter((order) =>
      [order.id, order.order_code, order.delivery_name, order.delivery_phone]
        .filter(Boolean)
        .some((value) => value!.toLowerCase().includes(orderSearchQuery)),
    );
  }, [orderSearchQuery, orders]);

  const groupedOrders = useMemo(() => {
    const grouped = new Map<string, ApiOrder[]>();
    KANBAN_COLUMNS.forEach((col) => grouped.set(col.id, []));
    filteredOrders.forEach((order) => {
      const col = KANBAN_COLUMNS.find((c) => c.statuses.includes(order.status));
      grouped.get(col?.id ?? "waiting")?.push(order);
    });
    return grouped;
  }, [filteredOrders]);

  const activeOrders = orders.filter((o) => !["delivered", "cancelled", "refunded"].includes(o.status)).length;
  const estimatedDayRevenue = useMemo(() => orders.reduce((sum, order) => sum + order.total, 0), [orders]);
  const effectiveDayRevenue = useMemo(
    () => orders.reduce((sum, order) => sum + (isEffectiveRevenueOrder(order) ? order.total : 0), 0),
    [orders],
  );
  const selectedDateLabel = useMemo(() => formatDayLabel(selectedDate), [selectedDate]);
  const isToday = selectedDate === todayInputValue();

  return (
    <div className="min-h-screen bg-surface-00 flex flex-col md:flex-row md:h-screen overflow-hidden">
      <AdminSidebar />

      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="bg-surface-02 border-b border-surface-03 px-4 md:px-8 py-4 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl border border-gold/25 bg-gold/10 text-gold">
              <ShoppingBag size={20} />
            </div>
            <div>
              <p className="text-gold text-[11px] font-bold uppercase tracking-[0.22em] mb-1">
                Operacao
              </p>
              <h2 className="text-xl md:text-2xl font-black leading-tight text-cream">Pedidos</h2>
              <p className="text-stone text-xs md:text-sm mt-1 leading-snug">
                {lastUpdated
                  ? `Atualizado as ${lastUpdated.toLocaleTimeString("pt-BR", {
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                    })} - ${selectedDateLabel}`
                  : "Carregando pedidos..."}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 lg:justify-end">
            <AdminTopActions />
          </div>
        </header>

        {/* Body */}
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          {error && (
            <div className="mx-4 md:mx-8 mt-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}
          {orderSearchQuery && (
            <div className="mx-4 mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-gold/25 bg-gold/10 px-4 py-3 text-sm text-cream md:mx-8">
              <span>
                Busca por pedido: <strong>{searchParams.get("q")}</strong> ({filteredOrders.length} resultado{filteredOrders.length === 1 ? "" : "s"})
              </span>
              <button
                type="button"
                onClick={() => {
                  const next = new URLSearchParams(searchParams);
                  next.delete("q");
                  setSearchParams(next, { replace: true });
                }}
                className="rounded-lg border border-gold/30 px-3 py-1.5 text-xs font-bold text-gold transition-colors hover:bg-gold/10"
              >
                Limpar busca
              </button>
            </div>
          )}

          <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
            <div className="relative z-20 flex w-full flex-shrink-0 flex-wrap items-center gap-2 border-b border-surface-03 bg-surface-01/95 px-4 py-3 md:px-6">
              <div className="flex h-10 min-w-[14rem] shrink-0 items-center justify-between gap-3 rounded-xl border border-surface-03 bg-surface-02 px-4">
                <span className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-widest text-stone">
                  <Users size={15} className="text-green-400" />
                  Visitantes online
                </span>
                <span className="text-sm font-black text-cream">{onlineStats.visitors}</span>
              </div>
              <div className="flex h-10 min-w-[17rem] shrink-0 items-center justify-between gap-3 rounded-xl border border-surface-03 bg-surface-02 px-4">
                <span className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-widest text-stone">
                  <UserCheck size={15} className="text-blue-400" />
                  Clientes cadastrados online
                </span>
                <span className="text-sm font-black text-cream">{onlineStats.registeredCustomers}</span>
              </div>
            </div>
            <div className="relative z-20 flex w-full flex-shrink-0 flex-wrap items-center gap-2 border-b border-surface-03 bg-surface-01/95 px-4 py-4 md:px-6">
              <div className="flex h-11 shrink-0 items-center overflow-hidden rounded-xl border border-surface-03 bg-surface-02">
                <button
                  onClick={() => setSelectedDate((value) => shiftDateInput(value, -1))}
                  title="Dia anterior"
                  className="flex h-full w-10 items-center justify-center text-stone transition-colors hover:text-cream"
                >
                  <ChevronLeft size={16} />
                </button>
                <label className="flex h-full items-center gap-2 border-x border-surface-03 px-3 text-sm font-semibold text-parchment">
                  <CalendarDays size={16} className="text-gold" />
                  <input
                    type="date"
                    value={selectedDate}
                    onChange={(event) => setSelectedDate(event.target.value || todayInputValue())}
                    className="w-[8.5rem] bg-transparent text-sm font-semibold text-parchment outline-none [color-scheme:dark]"
                  />
                </label>
                <button
                  onClick={() => setSelectedDate((value) => shiftDateInput(value, 1))}
                  title="Proximo dia"
                  className="flex h-full w-10 items-center justify-center text-stone transition-colors hover:text-cream"
                >
                  <ChevronRight size={16} />
                </button>
              </div>
              <button
                onClick={() => setSelectedDate(todayInputValue())}
                disabled={isToday}
                className="flex h-11 shrink-0 items-center justify-center rounded-xl border border-surface-03 bg-surface-02 px-4 text-sm font-semibold text-stone transition-colors hover:text-cream disabled:opacity-50"
              >
                Hoje
              </button>
              <div className={`flex h-11 shrink-0 items-center gap-2 rounded-xl border px-4 transition-colors ${newOrderFlash ? "border-gold bg-gold/20" : "border-surface-03 bg-surface-02"}`}>
                <span className="text-stone text-[10px] uppercase tracking-widest">Ativos</span>
                <span className="text-cream text-sm font-black">{activeOrders}</span>
              </div>
              <div className="flex h-11 shrink-0 items-center gap-2 rounded-xl border border-surface-03 bg-surface-02 px-4">
                <span className="text-stone text-[10px] uppercase tracking-widest">No dia</span>
                <span className="text-cream text-sm font-black">{orders.length}</span>
              </div>
              <div className="flex h-11 shrink-0 items-center gap-2 rounded-xl border border-surface-03 bg-surface-02 px-4">
                <span className="text-stone text-[10px] uppercase tracking-widest">Receita estimada</span>
                <span className="text-cream text-sm font-black">{formatCurrency(estimatedDayRevenue)}</span>
              </div>
              <div className="flex h-11 shrink-0 items-center gap-2 rounded-xl border border-surface-03 bg-surface-02 px-4">
                <span className="text-stone text-[10px] uppercase tracking-widest">Receita efetivada</span>
                <span className="text-cream text-sm font-black">{formatCurrency(effectiveDayRevenue)}</span>
              </div>
              <button
                onClick={() => setSoundEnabled((v) => !v)}
                title={soundEnabled ? "Silenciar alertas de novo pedido" : "Ativar alertas de novo pedido"}
                className={`flex h-11 shrink-0 items-center justify-center gap-2 rounded-xl border px-4 text-sm font-semibold transition-colors ${
                  soundEnabled
                    ? "border-gold/40 text-gold bg-gold/10"
                    : "border-surface-03 bg-surface-02 text-stone hover:text-cream"
                }`}
              >
                {soundEnabled ? <Bell size={16} /> : <BellOff size={16} />}
                Alertas
              </button>
              <button
                onClick={() => fetchOrders(true)}
                disabled={loading || refreshing}
                title="Atualizar agora"
                className="flex h-11 shrink-0 items-center justify-center gap-2 rounded-xl border border-surface-03 bg-surface-02 px-4 text-sm font-semibold text-stone transition-colors hover:text-cream disabled:opacity-60"
              >
                <RefreshCw size={16} className={loading || refreshing ? "animate-spin" : ""} />
                Atualizar
              </button>
              <p className="ml-auto min-w-[10rem] truncate text-right text-[11px] text-stone">
                {lastUpdated
                  ? `Atualizado as ${lastUpdated.toLocaleTimeString("pt-BR", {
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                    })}`
                  : "Carregando pedidos..."}
              </p>
            </div>

            {loading ? (
              <div className="flex h-full flex-1 items-center justify-center">
                <Loader2 size={40} className="animate-spin text-gold" />
              </div>
            ) : orders.length === 0 ? (
              <div className="flex h-full flex-1 flex-col items-center justify-center px-6 text-center">
                <ShoppingBag size={54} className="mb-4 text-gold" />
                <p className="text-cream text-xl font-bold">Nenhum pedido neste dia</p>
                <p className="text-stone text-sm mt-2">Os pedidos de {selectedDateLabel} aparecem aqui automaticamente.</p>
              </div>
            ) : (
              <div className="w-full min-w-0 flex-1 overflow-y-auto px-3 pb-4 pt-3 md:px-4 md:pb-4">
                <div className="grid min-h-full grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7 xl:gap-2">
                  {KANBAN_COLUMNS.map((column) => {
                    const Icon = column.icon;
                    const columnOrders = groupedOrders.get(column.id) ?? [];
                    const isDragOver = dragOverColumn === column.id;
                    return (
                      <section
                        key={column.id}
                        className={`flex min-h-[18rem] min-w-0 flex-col rounded-xl border transition-colors xl:h-full ${
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
                        <header className="border-b border-surface-03 p-3 xl:p-2.5">
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0">
                              <div className="flex items-center gap-1.5">
                                <span className={`inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border ${column.accent}`}>
                                  <Icon size={14} />
                                </span>
                                <h2 className="truncate text-xs font-black text-cream" title={column.title}>{column.title}</h2>
                              </div>
                              <p className="mt-1.5 hidden text-[11px] leading-snug text-stone 2xl:block">{column.description}</p>
                            </div>
                            <span className="shrink-0 rounded-full bg-surface-03 px-2 py-1 text-[10px] font-bold text-parchment">
                              {columnOrders.length}
                            </span>
                          </div>
                        </header>

                        {/* Cards */}
                        <div className="flex-1 space-y-2 overflow-y-auto p-2">
                          {columnOrders.length === 0 ? (
                            <div className={`rounded-lg border border-dashed p-4 text-center text-[11px] text-stone transition-colors ${isDragOver ? "border-gold/50 bg-gold/5 text-gold" : "border-surface-03"}`}>
                              {isDragOver ? "Soltar aqui" : "Sem pedidos"}
                            </div>
                          ) : (
                            columnOrders.map((order) => (
                              <OrderCard
                                key={order.id}
                                order={order}
                                updating={updatingId === order.id || deletingId === order.id}
                                onAdvance={() => {
                                  const next = NEXT_STATUS[order.status];
                                  if (WAITING_PAYMENT_STATUSES.has(order.status)) {
                                    handleApprovePayment(order.id);
                                  } else if (next) {
                                    handleStatusChange(order.id, next);
                                  }
                                }}
                                onAssignMotoboy={() => openAssignModal(order)}
                                onPrint={(tpl) => printOrder(order, tpl)}
                                canDelete={canDeleteOrders}
                                onRequestDelete={() => setDeleteModal({ order, confirmation: "" })}
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
        </div>
      </main>

      {deleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-2xl border border-red-500/30 bg-surface-02 p-6 shadow-xl">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-red-500/30 bg-red-500/10 text-red-300">
                <Trash2 size={18} />
              </div>
              <div className="min-w-0">
                <h3 className="text-lg font-bold text-cream">Excluir pedido</h3>
                <p className="mt-1 text-sm text-stone">
                  Pedido #{deleteModal.order.id.slice(0, 8).toUpperCase()} de {deleteModal.order.delivery_name}
                </p>
              </div>
            </div>

            <div className="mt-5 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3">
              <p className="text-sm font-semibold text-red-100">
                Esta acao remove o pedido da tela administrativa e nao deve ser usada no lugar de cancelar pedido.
              </p>
            </div>

            <label className="mt-5 flex flex-col gap-2">
              <span className="text-xs font-bold uppercase tracking-widest text-stone">
                Digite excluir para confirmar
              </span>
              <input
                value={deleteModal.confirmation}
                onChange={(event) => setDeleteModal((current) => (
                  current ? { ...current, confirmation: event.target.value } : current
                ))}
                autoFocus
                className="h-11 rounded-xl border border-surface-03 bg-surface-03 px-3 text-sm font-semibold text-cream outline-none transition-colors placeholder:text-stone focus:border-red-400"
                placeholder="excluir"
              />
            </label>

            <div className="mt-6 flex gap-3">
              <button
                onClick={() => setDeleteModal(null)}
                disabled={deletingId === deleteModal.order.id}
                className="flex-1 rounded-xl border border-surface-03 py-2.5 text-sm text-stone transition-colors hover:text-cream disabled:opacity-50"
              >
                Cancelar
              </button>
              <button
                onClick={handleDeleteOrder}
                disabled={
                  deletingId === deleteModal.order.id ||
                  deleteModal.confirmation.trim().toLowerCase() !== DELETE_CONFIRMATION_TEXT
                }
                className="flex-1 flex items-center justify-center gap-2 rounded-xl bg-red-500 py-2.5 text-sm font-bold text-white transition-colors hover:bg-red-500/90 disabled:opacity-50"
              >
                {deletingId === deleteModal.order.id && <Loader2 size={14} className="animate-spin" />}
                Excluir
              </button>
            </div>
          </div>
        </div>
      )}

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
  onPrint: (template: PrintTemplate) => void;
  canDelete: boolean;
  onRequestDelete: () => void;
  onDragStart: () => void;
  onDragEnd: () => void;
}

function OrderCard({
  order,
  updating,
  onAdvance,
  onAssignMotoboy,
  onPrint,
  canDelete,
  onRequestDelete,
  onDragStart,
  onDragEnd,
}: OrderCardProps) {
  const [printMenuOpen, setPrintMenuOpen] = useState(false);
  const isReadyForPickup = order.status === "ready_for_pickup";
  const isWaitingPayment = WAITING_PAYMENT_STATUSES.has(order.status);
  const nextLabel = isReadyForPickup ? null : NEXT_LABEL[order.status];
  const unresolvedDeliveryProblem = Boolean(order.delivery?.problem_report && !order.delivery.problem_resolved_at);
  const payOnDeliveryPaymentProblem = Boolean(
    order.pay_on_delivery &&
    (order.payment_status === "failed" || order.payment_status === "rejected" || unresolvedDeliveryProblem),
  );
  const paymentInfo = paymentInfoLabel(order);

  const itemSummary = order.items.slice(0, 2).map((item) => {
    const isMulti = item.flavor_division > 1;
    const name = isMulti ? item.flavors.map((f) => f.name).join(" + ") : item.product_name;
    return `${item.quantity}x ${item.is_gift ? "[BRINDE] " : ""}${name}`;
  });
  const remaining = Math.max(order.items.length - 2, 0);

  return (
    <article
      draggable={!isWaitingPayment}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      className={`cursor-grab select-none rounded-xl border border-surface-03 bg-surface-03/45 p-3 shadow-sm transition-opacity active:cursor-grabbing xl:p-2.5 ${updating ? "opacity-50 pointer-events-none" : ""}`}
    >
      {/* Top row: ID + status badge */}
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="font-mono text-xs font-black text-cream">#{order.id.slice(0, 8).toUpperCase()}</h3>
          <p className="mt-1 text-[10px] text-stone">{formatDateTime(order.created_at)} · {orderTimeLabel(order)}</p>
        </div>
        <span className={`max-w-full shrink-0 truncate rounded-full px-1.5 py-1 text-[9px] font-bold ${statusColor(order.status)}`}>
          {STATUS_LABELS[order.status] ?? order.status}
        </span>
      </div>

      {/* Customer */}
      <div className="mt-2">
        <p className="truncate text-xs font-bold text-cream">{order.delivery_name}</p>
        <p className="mt-0.5 truncate text-[11px] text-stone">{order.delivery_phone}</p>
        <p className="mt-0.5 line-clamp-2 text-[11px] text-stone/80">
          {order.delivery_street}
          {order.delivery_complement ? ` — ${order.delivery_complement}` : ""}
          {`, ${order.delivery_city}`}
        </p>
      </div>

      {/* Items */}
      <div className="mt-2 rounded-lg bg-surface-02/80 p-2">
        <p className="mb-1 text-[11px] font-bold text-parchment">Itens</p>
        <div className="space-y-0.5">
          {itemSummary.map((item, i) => (
            <p key={i} className="break-words text-[11px] leading-snug text-stone">{item}</p>
          ))}
          {remaining > 0 && <p className="text-[11px] font-semibold text-gold">+ {remaining} item(ns)</p>}
        </div>
      </div>

      {/* Total */}
      <div className="mt-2 flex items-center justify-between border-t border-surface-03 pt-2">
        <div>
          <p className="text-[9px] uppercase tracking-widest text-stone">Total</p>
          <p className="text-sm font-black text-gold">{formatCurrency(order.total)}</p>
        </div>
        <div className="text-right">
          <p className="text-[9px] uppercase tracking-widest text-stone">Entrega</p>
          <p className="text-[11px] font-semibold text-parchment">{order.estimated_time} min</p>
        </div>
      </div>

      {paymentInfo && (
        <div className="mt-2 rounded-lg border border-gold/25 bg-gold/10 px-2 py-1.5">
          <p className="text-[11px] font-bold text-gold">{paymentInfo}</p>
        </div>
      )}

      {payOnDeliveryPaymentProblem && (
        <div className="mt-2 rounded-lg border border-red-500/40 bg-red-500/10 px-2 py-1.5">
          <p className="text-[10px] font-bold uppercase tracking-widest text-red-300">Problema no pagamento na entrega</p>
          <p className="mt-1 text-xs font-semibold text-red-100">
            Este pedido nao entra na receita efetivada enquanto o pagamento nao for confirmado.
          </p>
          {order.delivery?.problem_report && (
            <p className="mt-1 line-clamp-2 text-xs text-parchment">{order.delivery.problem_report}</p>
          )}
        </div>
      )}

      {/* Quem cancelou — aparece apenas em pedidos cancelados */}
      {order.status === "cancelled" && order.cancelled_by && (
        <div className="mt-2 rounded-lg border border-red-500/20 bg-red-500/10 px-2 py-1.5">
          <p className="text-[10px] font-bold uppercase tracking-widest text-red-300 mb-1">Cancelamento</p>
          <p className="text-xs text-red-200 font-semibold">
            {order.cancelled_by === "customer" && "Cancelado pelo cliente"}
            {order.cancelled_by === "admin" && "Cancelado pelo administrador"}
            {order.cancelled_by === "system" && "Cancelado pelo sistema (PIX não pago)"}
          </p>
          {order.cancellation_reason && (
            <p className="text-[11px] text-stone mt-0.5">{order.cancellation_reason}</p>
          )}
          {order.cancelled_at && (
            <p className="text-[10px] text-stone/70 mt-0.5">{formatDateTime(order.cancelled_at)}</p>
          )}
        </div>
      )}

      {/* Operational timer — só aparece após pagamento confirmado */}
      {order.paid_at && (
        <OrderTimer
          paidAt={order.paid_at}
          deliveredAt={order.delivered_at}
          targetMinutes={order.target_delivery_minutes ?? 45}
          status={order.status}
        />
      )}

      {order.delivery && (
        <div className="mt-2 rounded-lg border border-blue-500/20 bg-blue-500/10 p-2">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-widest text-blue-200">Motoboy</p>
              <p className="mt-1 truncate text-sm font-black text-cream">
                {order.delivery.delivery_person_name || "Atribuido"}
              </p>
              {order.delivery.assigned_at && (
                <p className="mt-0.5 text-xs text-stone">Atribuido em {formatDateTime(order.delivery.assigned_at)}</p>
              )}
            </div>
            <span className="shrink-0 rounded-full border border-blue-500/30 bg-blue-500/15 px-2 py-1 text-[10px] font-bold text-blue-200">
              {STATUS_LABELS[order.delivery.status] ?? order.delivery.status}
            </span>
          </div>
        </div>
      )}

      {unresolvedDeliveryProblem && (
        <div className="mt-2 rounded-lg border border-red-500/40 bg-red-500/10 p-2">
          <div className="flex items-start gap-2">
            <AlertTriangle size={15} className="mt-0.5 shrink-0 text-red-300" />
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-widest text-red-300">
                Problema na entrega
              </p>
              <p className="mt-1 text-xs font-semibold text-red-100">
                Entre em contato com o cliente e registre a resolucao em Logistica &gt; Alertas.
              </p>
              <p className="mt-1 line-clamp-2 text-xs text-parchment">
                {order.delivery?.problem_report}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="mt-2 flex flex-wrap gap-1.5">
        {/* Assign motoboy — for ready_for_pickup orders */}
        {isReadyForPickup && !order.delivery && (
          <button
            onClick={onAssignMotoboy}
            disabled={updating}
            className="flex min-w-[6.5rem] flex-1 items-center justify-center gap-1 rounded-lg bg-blue-500/15 px-2 py-2 text-[11px] font-bold text-blue-300 transition-colors hover:bg-blue-500/25 disabled:opacity-50"
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
            className="flex min-w-[6.5rem] flex-1 items-center justify-center gap-1 rounded-lg bg-gold/15 px-2 py-2 text-[11px] font-bold text-gold transition-colors hover:bg-gold/25 disabled:opacity-50"
          >
            {updating ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <ChevronRight size={13} />
            )}
            {nextLabel}
          </button>
        )}

        {/* Print menu trigger */}
        <div>
          <button
            onClick={() => setPrintMenuOpen((v) => !v)}
            title="Imprimir pedido"
            className="flex items-center justify-center rounded-lg bg-surface-02 hover:bg-surface-03 text-parchment p-2 transition-colors"
          >
            <Printer size={14} />
          </button>
        </div>

        {canDelete && (
          <button
            onClick={onRequestDelete}
            disabled={updating}
            title="Excluir pedido"
            aria-label="Excluir pedido"
            className="flex items-center justify-center rounded-lg border border-red-500/25 bg-red-500/10 p-2 text-red-300 transition-colors hover:bg-red-500/20 disabled:opacity-50"
          >
            <Trash2 size={13} />
          </button>
        )}
      </div>

      {printMenuOpen && (
        <div className="mt-2 grid grid-cols-1 gap-1.5 rounded-lg border border-surface-03 bg-surface-02 p-1.5">
          {(
            [
              { tpl: "completo" as PrintTemplate, label: "Completo" },
              { tpl: "cozinha" as PrintTemplate, label: "Cozinha" },
              { tpl: "entrega" as PrintTemplate, label: "Entrega" },
            ] as { tpl: PrintTemplate; label: string }[]
          ).map(({ tpl, label }) => (
            <button
              key={tpl}
              onClick={() => { onPrint(tpl); setPrintMenuOpen(false); }}
              className="flex items-center justify-start gap-1.5 rounded-lg border border-surface-03 bg-surface-03/50 px-2 py-1.5 text-[10px] font-bold text-parchment transition-colors hover:border-gold/40 hover:text-gold"
            >
              <Printer size={12} className="shrink-0 text-stone" />
              <span className="whitespace-nowrap">{label}</span>
            </button>
          ))}
        </div>
      )}
    </article>
  );
}
