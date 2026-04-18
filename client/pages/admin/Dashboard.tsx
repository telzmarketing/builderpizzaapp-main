import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { BarChart3, Package, Megaphone, ShoppingBag, Loader2 } from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import { adminApi, type ApiDashboard, type ApiOrder } from "@/lib/api";
import { ordersApi } from "@/lib/api";

export default function AdminDashboard() {
  const [stats, setStats] = useState<ApiDashboard | null>(null);
  const [recentOrders, setRecentOrders] = useState<ApiOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

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
    if (s === "on_the_way") return "bg-blue-500/20 text-blue-400";
    if (s === "cancelled" || s === "refunded") return "bg-red-500/20 text-red-400";
    return "bg-gold/20 text-orange-400";
  };

  useEffect(() => {
    Promise.allSettled([
      adminApi.dashboard(),
      ordersApi.list({ limit: 10 }),
    ]).then(([dashRes, ordersRes]) => {
      if (dashRes.status === "fulfilled") setStats(dashRes.value);
      else setError("Não foi possível carregar o dashboard.");
      if (ordersRes.status === "fulfilled") setRecentOrders(ordersRes.value);
    }).finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-00 to-surface-00">
      <div className="flex h-screen">
        <AdminSidebar />

        <div className="flex-1 overflow-auto">
          <div className="bg-surface-02 px-8 py-4 border-b border-surface-03 flex justify-between items-center sticky top-0 z-20">
            <h2 className="text-2xl font-bold text-cream">Dashboard</h2>
            <div className="flex gap-2 text-stone text-sm">
              <span>📡</span><span>📶</span><span>🔋</span>
            </div>
          </div>

          <div className="p-8">
            {error && (
              <div className="mb-6 bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3 text-red-400 text-sm">
                {error}
              </div>
            )}

            {loading ? (
              <div className="flex items-center justify-center py-24">
                <Loader2 size={40} className="animate-spin text-orange-500" />
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                  <div className="bg-surface-02 rounded-xl p-6 border border-surface-03">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-stone text-sm">Total de Pedidos</p>
                        <p className="text-3xl font-bold text-cream mt-2">{stats?.total_orders ?? 0}</p>
                      </div>
                      <ShoppingBag size={32} className="text-orange-500" />
                    </div>
                  </div>

                  <div className="bg-surface-02 rounded-xl p-6 border border-surface-03">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-stone text-sm">Total de Produtos</p>
                        <p className="text-3xl font-bold text-cream mt-2">{stats?.total_products ?? 0}</p>
                      </div>
                      <Package size={32} className="text-blue-500" />
                    </div>
                  </div>

                  <div className="bg-surface-02 rounded-xl p-6 border border-surface-03">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-stone text-sm">Pedidos Pendentes</p>
                        <p className="text-3xl font-bold text-cream mt-2">{stats?.pending_orders ?? 0}</p>
                      </div>
                      <Megaphone size={32} className="text-green-500" />
                    </div>
                  </div>

                  <div className="bg-surface-02 rounded-xl p-6 border border-surface-03">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-stone text-sm">Receita Total</p>
                        <p className="text-3xl font-bold text-cream mt-2">
                          R${(stats?.total_revenue ?? 0).toFixed(2)}
                        </p>
                      </div>
                      <BarChart3 size={32} className="text-purple-500" />
                    </div>
                  </div>
                </div>

                {recentOrders.length > 0 ? (
                  <div className="bg-surface-02 rounded-xl p-6 border border-surface-03 mb-8">
                    <h3 className="text-xl font-bold text-cream mb-4">Pedidos Recentes</h3>
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead>
                          <tr className="border-b border-surface-03">
                            <th className="text-left py-2 px-4 text-stone text-sm">ID</th>
                            <th className="text-left py-2 px-4 text-stone text-sm">Cliente</th>
                            <th className="text-left py-2 px-4 text-stone text-sm">Status</th>
                            <th className="text-left py-2 px-4 text-stone text-sm">Total</th>
                          </tr>
                        </thead>
                        <tbody>
                          {recentOrders.slice(0, 8).map((order) => (
                            <tr key={order.id} className="border-b border-surface-03 last:border-0">
                              <td className="py-3 px-4 text-cream text-sm font-mono">
                                {order.id.slice(0, 8).toUpperCase()}
                              </td>
                              <td className="py-3 px-4 text-parchment text-sm">{order.delivery_name}</td>
                              <td className="py-3 px-4">
                                <span className={`px-3 py-1 rounded-full text-xs font-medium ${statusColor(order.status)}`}>
                                  {STATUS_LABELS[order.status] ?? order.status}
                                </span>
                              </td>
                              <td className="py-3 px-4 text-orange-500 font-bold">
                                R${order.total.toFixed(2)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : (
                  <div className="bg-surface-02 rounded-xl p-12 border border-surface-03 text-center mb-8">
                    <ShoppingBag size={48} className="text-slate-600 mx-auto mb-4" />
                    <p className="text-stone text-lg">Nenhum pedido ainda</p>
                    <p className="text-stone/70 text-sm mt-2">Os pedidos dos clientes aparecerão aqui.</p>
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <Link to="/painel/products" className="bg-surface-02 rounded-xl p-6 border border-surface-03 hover:border-gold/50 transition-colors">
                    <Package size={32} className="text-blue-500 mb-3" />
                    <h3 className="text-cream font-bold">Gerenciar Produtos</h3>
                    <p className="text-stone text-sm mt-1">Adicionar, editar ou remover produtos do cardápio</p>
                  </Link>
                  <Link to="/painel/orders" className="bg-surface-02 rounded-xl p-6 border border-surface-03 hover:border-gold/50 transition-colors">
                    <ShoppingBag size={32} className="text-orange-500 mb-3" />
                    <h3 className="text-cream font-bold">Gerenciar Pedidos</h3>
                    <p className="text-stone text-sm mt-1">Visualizar e atualizar status dos pedidos</p>
                  </Link>
                  <Link to="/painel/conteudo" className="bg-surface-02 rounded-xl p-6 border border-surface-03 hover:border-gold/50 transition-colors">
                    <BarChart3 size={32} className="text-purple-500 mb-3" />
                    <h3 className="text-cream font-bold">Editar Conteúdo</h3>
                    <p className="text-stone text-sm mt-1">Textos, ícones e categorias das páginas</p>
                  </Link>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
