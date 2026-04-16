import { useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import { ordersApi, type ApiOrder, type OrderStatus } from "@/lib/api";

const STATUS_LABELS: Record<string, string> = {
  pending: "Aguardando",
  waiting_payment: "Ag. Pagamento",
  paid: "Pago",
  preparing: "Preparando",
  ready_for_pickup: "Pronto",
  on_the_way: "A caminho",
  delivered: "Entregue",
  cancelled: "Cancelado",
  refunded: "Reembolsado",
};

const statusColor = (s: string) => {
  if (s === "delivered") return "bg-green-500/20 text-green-400";
  if (s === "on_the_way" || s === "ready_for_pickup") return "bg-blue-500/20 text-blue-400";
  if (s === "cancelled" || s === "refunded") return "bg-red-500/20 text-red-400";
  if (s === "paid") return "bg-cyan-500/20 text-cyan-400";
  return "bg-orange-500/20 text-orange-400";
};

const NEXT_STATUSES: Record<OrderStatus, OrderStatus[]> = {
  pending: ["waiting_payment", "preparing", "cancelled"],
  waiting_payment: ["paid", "cancelled"],
  paid: ["preparing", "cancelled"],
  preparing: ["ready_for_pickup", "on_the_way"],
  ready_for_pickup: ["on_the_way"],
  on_the_way: ["delivered"],
  delivered: [],
  cancelled: [],
  refunded: [],
};

export default function AdminOrders() {
  const [orders, setOrders] = useState<ApiOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [updating, setUpdating] = useState<string | null>(null);

  const fetchOrders = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await ordersApi.list({ limit: 100 });
      setOrders([...data].reverse());
    } catch {
      setError("Não foi possível carregar os pedidos. O backend está rodando?");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchOrders(); }, []);

  const handleUpdateStatus = async (orderId: string, status: OrderStatus) => {
    setUpdating(orderId);
    try {
      const updated = await ordersApi.updateStatus(orderId, status);
      setOrders((prev) => prev.map((o) => (o.id === orderId ? updated : o)));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao atualizar status.");
    } finally {
      setUpdating(null);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-950">
      <div className="flex h-screen">
        <AdminSidebar />

        <div className="flex-1 overflow-auto">
          <div className="bg-slate-800 px-8 py-4 border-b border-slate-700 flex justify-between items-center sticky top-0 z-20">
            <h2 className="text-2xl font-bold text-white">Gerenciar Pedidos</h2>
            <div className="flex items-center gap-4">
              <span className="text-slate-400 text-sm">{orders.length} pedido{orders.length !== 1 ? "s" : ""}</span>
              <button onClick={fetchOrders} disabled={loading} className="text-slate-400 hover:text-white transition-colors disabled:opacity-50">
                <RefreshCw size={18} className={loading ? "animate-spin" : ""} />
              </button>
            </div>
          </div>

          <div className="p-8">
            {error && (
              <div className="mb-6 bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3 text-red-400 text-sm">{error}</div>
            )}

            {loading ? (
              <div className="flex items-center justify-center py-24">
                <Loader2 size={40} className="animate-spin text-orange-500" />
              </div>
            ) : orders.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-24 text-center">
                <span className="text-6xl mb-4">📦</span>
                <p className="text-slate-400 text-xl">Nenhum pedido ainda</p>
                <p className="text-slate-500 text-sm mt-2">Os pedidos dos clientes aparecerão aqui quando realizados.</p>
              </div>
            ) : (
              <div className="space-y-6">
                {orders.map((order) => {
                  const nextStatuses = NEXT_STATUSES[order.status] ?? [];
                  return (
                    <div key={order.id} className="bg-slate-800 rounded-xl p-6 border border-slate-700">
                      <div className="flex justify-between items-start mb-6">
                        <div>
                          <h3 className="text-lg font-bold text-white font-mono">
                            #{order.id.slice(0, 8).toUpperCase()}
                          </h3>
                          <p className="text-slate-400 text-sm">
                            {new Date(order.created_at).toLocaleDateString("pt-BR")} às{" "}
                            {new Date(order.created_at).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
                          </p>
                          <p className="text-slate-400 text-sm mt-1">
                            Cliente: <span className="text-white">{order.delivery_name}</span> · {order.delivery_phone}
                          </p>
                          <p className="text-slate-500 text-xs">{order.delivery_street}, {order.delivery_city}</p>
                        </div>
                        <span className="text-orange-500 font-bold text-lg">R${order.total.toFixed(2)}</span>
                      </div>

                      <div className="mb-6 pb-6 border-b border-slate-700">
                        <h4 className="text-sm font-bold text-slate-300 mb-3">Itens do Pedido</h4>
                        <div className="space-y-2">
                          {order.items.map((item) => {
                            const isMulti = item.flavor_division > 1;
                            const name = isMulti
                              ? item.flavors.map((f) => f.name).join(" + ")
                              : item.product_name;
                            return (
                              <div key={item.id} className="flex justify-between text-sm">
                                <span className="text-slate-300">{name} × {item.quantity} ({item.selected_size})</span>
                                <span className="text-slate-400">R${(item.final_price * item.quantity).toFixed(2)}</span>
                              </div>
                            );
                          })}
                          <div className="flex justify-between text-sm pt-2 border-t border-slate-700">
                            <span className="text-slate-400">Taxa de entrega</span>
                            <span className="text-slate-400">R${order.shipping_fee.toFixed(2)}</span>
                          </div>
                          {order.discount > 0 && (
                            <div className="flex justify-between text-sm text-green-400">
                              <span>Desconto</span>
                              <span>-R${order.discount.toFixed(2)}</span>
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="flex justify-between items-center flex-wrap gap-4">
                        <div>
                          <p className="text-slate-400 text-sm mb-2">Status atual</p>
                          <span className={`px-3 py-1 rounded-full text-xs font-medium ${statusColor(order.status)}`}>
                            {STATUS_LABELS[order.status] ?? order.status}
                          </span>
                        </div>
                        <div className="flex gap-2 flex-wrap">
                          {nextStatuses.map((status) => (
                            <button
                              key={status}
                              onClick={() => handleUpdateStatus(order.id, status)}
                              disabled={updating === order.id}
                              className="px-3 py-2 rounded-lg text-sm font-medium bg-slate-700 text-slate-300 hover:bg-slate-600 disabled:opacity-50 transition-colors flex items-center gap-1"
                            >
                              {updating === order.id && <Loader2 size={12} className="animate-spin" />}
                              → {STATUS_LABELS[status]}
                            </button>
                          ))}
                          {nextStatuses.length === 0 && (
                            <span className="text-slate-500 text-sm">Pedido finalizado</span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
