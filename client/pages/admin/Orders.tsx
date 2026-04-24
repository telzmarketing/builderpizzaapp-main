import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Loader2,
  PackageCheck,
  RefreshCw,
  Route,
  ShoppingBag,
  Utensils,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import { ordersApi, type ApiOrder, type OrderStatus } from "@/lib/api";

const STATUS_LABELS: Record<string, string> = {
  pending: "Aguardando",
  waiting_payment: "Ag. pagamento",
  paid: "Pago",
  aguardando_pagamento: "Ag. pagamento",
  pago: "Pago",
  pagamento_recusado: "Pagamento recusado",
  pagamento_expirado: "Pagamento expirado",
  preparing: "Preparando",
  ready_for_pickup: "Pronto",
  on_the_way: "A caminho",
  delivered: "Entregue",
  cancelled: "Cancelado",
  refunded: "Reembolsado",
};

type KanbanColumn = {
  id: string;
  title: string;
  description: string;
  statuses: OrderStatus[];
  icon: typeof Clock3;
  accent: string;
};

const KANBAN_COLUMNS: KanbanColumn[] = [
  {
    id: "waiting",
    title: "Aguardando pagamento",
    description: "Pedidos criados ou com pagamento em aberto",
    statuses: ["pending", "waiting_payment", "aguardando_pagamento"],
    icon: Clock3,
    accent: "text-orange-300 bg-orange-500/10 border-orange-500/20",
  },
  {
    id: "paid",
    title: "Pago",
    description: "Confirmados pelo fluxo de pagamento",
    statuses: ["paid", "pago"],
    icon: CheckCircle2,
    accent: "text-cyan-300 bg-cyan-500/10 border-cyan-500/20",
  },
  {
    id: "preparing",
    title: "Preparando",
    description: "Pedidos em producao",
    statuses: ["preparing"],
    icon: Utensils,
    accent: "text-gold bg-gold/10 border-gold/20",
  },
  {
    id: "ready",
    title: "Pronto",
    description: "Aguardando retirada ou entrega",
    statuses: ["ready_for_pickup"],
    icon: PackageCheck,
    accent: "text-blue-300 bg-blue-500/10 border-blue-500/20",
  },
  {
    id: "delivery",
    title: "A caminho",
    description: "Saiu para entrega",
    statuses: ["on_the_way"],
    icon: Route,
    accent: "text-violet-300 bg-violet-500/10 border-violet-500/20",
  },
  {
    id: "done",
    title: "Finalizados",
    description: "Entregues",
    statuses: ["delivered"],
    icon: ShoppingBag,
    accent: "text-green-300 bg-green-500/10 border-green-500/20",
  },
  {
    id: "issues",
    title: "Problemas",
    description: "Recusados, expirados, cancelados ou reembolsados",
    statuses: ["pagamento_recusado", "pagamento_expirado", "cancelled", "refunded"],
    icon: AlertTriangle,
    accent: "text-red-300 bg-red-500/10 border-red-500/20",
  },
];

const statusColor = (status: string) => {
  if (status === "delivered") return "bg-green-500/15 text-green-300";
  if (status === "on_the_way" || status === "ready_for_pickup") return "bg-blue-500/15 text-blue-300";
  if (status === "cancelled" || status === "refunded" || status === "pagamento_recusado" || status === "pagamento_expirado") {
    return "bg-red-500/15 text-red-300";
  }
  if (status === "paid" || status === "pago") return "bg-cyan-500/15 text-cyan-300";
  return "bg-gold/15 text-gold";
};

const formatCurrency = (value: number) =>
  value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const formatDateTime = (value: string) =>
  new Date(value).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });

function orderTimeLabel(order: ApiOrder) {
  const diff = Date.now() - new Date(order.created_at).getTime();
  const minutes = Math.max(0, Math.floor(diff / 60000));
  if (minutes < 1) return "Agora";
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}min`;
}

export default function AdminOrders() {
  const [orders, setOrders] = useState<ApiOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchOrders = async (silent = false) => {
    if (silent) setRefreshing(true);
    else setLoading(true);
    setError("");
    try {
      const data = await ordersApi.list({ limit: 150 });
      const sorted = [...data].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
      setOrders(sorted);
      setLastUpdated(new Date());
    } catch {
      setError("Nao foi possivel carregar os pedidos. Verifique se o backend esta rodando.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchOrders();
    const interval = window.setInterval(() => fetchOrders(true), 15000);
    return () => window.clearInterval(interval);
  }, []);

  const groupedOrders = useMemo(() => {
    const grouped = new Map<string, ApiOrder[]>();
    KANBAN_COLUMNS.forEach((column) => grouped.set(column.id, []));

    orders.forEach((order) => {
      const column = KANBAN_COLUMNS.find((item) => item.statuses.includes(order.status));
      grouped.get(column?.id ?? "waiting")?.push(order);
    });

    return grouped;
  }, [orders]);

  const activeOrders = orders.filter((order) => !["delivered", "cancelled", "refunded"].includes(order.status)).length;

  return (
    <div className="min-h-screen bg-surface-00 flex h-screen overflow-hidden">
      <AdminSidebar />

      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="bg-surface-02 border-b border-surface-03 px-4 md:px-8 py-4 flex flex-col xl:flex-row xl:items-center xl:justify-between gap-4">
          <div>
            <p className="text-gold text-xs font-bold uppercase tracking-[0.24em]">Kanban operacional</p>
            <h1 className="text-cream text-2xl font-black mt-1">Pedidos</h1>
            <p className="text-stone text-sm mt-1">
              Visualizacao somente leitura. Os cards mudam de coluna conforme o status salvo no banco de dados.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="rounded-xl border border-surface-03 bg-surface-03/60 px-3 py-2">
              <p className="text-stone text-[11px] uppercase tracking-widest">Ativos</p>
              <p className="text-cream text-sm font-black">{activeOrders}</p>
            </div>
            <div className="rounded-xl border border-surface-03 bg-surface-03/60 px-3 py-2">
              <p className="text-stone text-[11px] uppercase tracking-widest">Total carregado</p>
              <p className="text-cream text-sm font-black">{orders.length}</p>
            </div>
            <button
              onClick={() => fetchOrders(true)}
              disabled={loading || refreshing}
              className="inline-flex items-center gap-2 rounded-xl bg-gold px-4 py-2.5 text-sm font-bold text-cream transition hover:bg-gold/90 disabled:opacity-60"
            >
              <RefreshCw size={16} className={loading || refreshing ? "animate-spin" : ""} />
              Atualizar
            </button>
          </div>
        </header>

        <section className="border-b border-surface-03 bg-surface-00 px-4 md:px-8 py-3 flex flex-col md:flex-row md:items-center md:justify-between gap-2">
          <p className="text-stone text-xs">
            Atualizacao automatica a cada 15 segundos. Nenhuma acao manual altera status por esta tela.
          </p>
          {lastUpdated && (
            <p className="text-stone text-xs">
              Ultima leitura: {lastUpdated.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
            </p>
          )}
        </section>

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
              <p className="text-stone text-sm mt-2">Os pedidos aparecem aqui automaticamente quando forem criados.</p>
            </div>
          ) : (
            <div className="h-full overflow-x-auto overflow-y-hidden p-4 md:p-6">
              <div className="flex h-full gap-4 min-w-max">
                {KANBAN_COLUMNS.map((column) => {
                  const Icon = column.icon;
                  const columnOrders = groupedOrders.get(column.id) ?? [];
                  return (
                    <section key={column.id} className="flex h-full w-[300px] flex-col rounded-2xl border border-surface-03 bg-surface-02">
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
                          <span className="rounded-full bg-surface-03 px-2.5 py-1 text-xs font-bold text-parchment">
                            {columnOrders.length}
                          </span>
                        </div>
                      </header>

                      <div className="flex-1 overflow-y-auto p-3 space-y-3">
                        {columnOrders.length === 0 ? (
                          <div className="rounded-xl border border-dashed border-surface-03 p-4 text-center text-xs text-stone">
                            Sem pedidos nesta etapa
                          </div>
                        ) : (
                          columnOrders.map((order) => <OrderCard key={order.id} order={order} />)
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
    </div>
  );
}

function OrderCard({ order }: { order: ApiOrder }) {
  const itemSummary = order.items
    .slice(0, 2)
    .map((item) => {
      const isMulti = item.flavor_division > 1;
      const name = isMulti ? item.flavors.map((flavor) => flavor.name).join(" + ") : item.product_name;
      return `${item.quantity}x ${name}`;
    });

  const remainingItems = Math.max(order.items.length - itemSummary.length, 0);

  return (
    <article className="rounded-2xl border border-surface-03 bg-surface-03/45 p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-cream font-mono text-sm font-black">#{order.id.slice(0, 8).toUpperCase()}</h3>
          <p className="text-stone text-xs mt-1">{formatDateTime(order.created_at)} · {orderTimeLabel(order)}</p>
        </div>
        <span className={`rounded-full px-2 py-1 text-[10px] font-bold whitespace-nowrap ${statusColor(order.status)}`}>
          {STATUS_LABELS[order.status] ?? order.status}
        </span>
      </div>

      <div className="mt-4">
        <p className="text-cream text-sm font-bold truncate">{order.delivery_name}</p>
        <p className="text-stone text-xs mt-1 truncate">{order.delivery_phone}</p>
        <p className="text-stone/80 text-xs mt-1 line-clamp-2">
          {order.delivery_street}, {order.delivery_city}
          {order.delivery_complement ? ` - ${order.delivery_complement}` : ""}
        </p>
      </div>

      <div className="mt-4 rounded-xl bg-surface-02/80 p-3">
        <p className="text-parchment text-xs font-bold mb-2">Itens</p>
        <div className="space-y-1">
          {itemSummary.map((item, index) => (
            <p key={`${order.id}-${index}`} className="text-stone text-xs line-clamp-1">{item}</p>
          ))}
          {remainingItems > 0 && <p className="text-gold text-xs font-semibold">+ {remainingItems} item(ns)</p>}
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-surface-03 pt-3">
        <div>
          <p className="text-stone text-[10px] uppercase tracking-widest">Total</p>
          <p className="text-gold text-lg font-black">{formatCurrency(order.total)}</p>
        </div>
        <div className="text-right">
          <p className="text-stone text-[10px] uppercase tracking-widest">Entrega</p>
          <p className="text-parchment text-xs font-semibold">{order.estimated_time} min</p>
        </div>
      </div>
    </article>
  );
}
