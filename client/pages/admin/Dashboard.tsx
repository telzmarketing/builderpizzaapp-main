import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, BarChart3, Clock, Megaphone, Package, Search, ShoppingBag, Loader2 } from "lucide-react";
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
      else setError("Nao foi possivel carregar o dashboard.");
      if (ordersRes.status === "fulfilled") setRecentOrders(ordersRes.value);
    }).finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-00 to-surface-00">
      <div className="flex h-screen">
        <AdminSidebar />

        <div className="flex-1 overflow-auto">
          <div className="bg-surface-02 px-8 py-5 border-b border-surface-03 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 sticky top-0 z-20">
            <div>
              <p className="text-gold text-xs font-bold uppercase tracking-[0.18em]">Painel administrativo</p>
              <h2 className="text-2xl font-bold text-cream mt-1">Bem-vindo de volta</h2>
            </div>
            <div className="flex items-center gap-3">
              <div className="hidden md:flex items-center gap-2 rounded-lg border border-surface-03 bg-surface-00/55 px-3 py-2 text-stone min-w-[260px]">
                <Search size={16} />
                <span className="text-sm">Buscar pedidos, produtos...</span>
              </div>
              <Link to="/painel/orders" className="inline-flex items-center gap-2 rounded-lg bg-gold px-4 py-2 text-sm font-bold text-cream hover:bg-gold/90 transition-colors">
                Pedidos
                <ArrowUpRight size={16} />
              </Link>
            </div>
          </div>

          <div className="p-8">
            {error && (
              <div className="mb-6 bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-red-400 text-sm">
                {error}
              </div>
            )}

            {loading ? (
              <div className="flex items-center justify-center py-24">
                <Loader2 size={40} className="animate-spin text-orange-500" />
              </div>
            ) : (
              <>
                <div className="mb-8 grid grid-cols-1 xl:grid-cols-[1.35fr_0.65fr] gap-6">
                  <section className="bg-surface-02 rounded-lg border border-surface-03 p-6">
                    <div className="flex items-start justify-between gap-6">
                      <div>
                        <p className="text-stone text-sm font-semibold">Resumo da loja</p>
                        <h3 className="text-cream text-3xl font-black mt-2">Operacao em tempo real</h3>
                        <p className="text-stone text-sm mt-2 max-w-xl">Acompanhe pedidos, receita e cardapio em uma visao compacta.</p>
                      </div>
                      <div className="hidden md:flex h-14 w-14 items-center justify-center rounded-lg bg-gold/15 text-gold">
                        <BarChart3 size={28} />
                      </div>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-6">
                      <div className="rounded-lg border border-surface-03 bg-surface-00/45 px-4 py-3">
                        <p className="text-stone text-xs">Pedidos</p>
                        <p className="text-cream text-2xl font-bold mt-1">{stats?.total_orders ?? 0}</p>
                      </div>
                      <div className="rounded-lg border border-surface-03 bg-surface-00/45 px-4 py-3">
                        <p className="text-stone text-xs">Produtos</p>
                        <p className="text-cream text-2xl font-bold mt-1">{stats?.total_products ?? 0}</p>
                      </div>
                      <div className="rounded-lg border border-surface-03 bg-surface-00/45 px-4 py-3">
                        <p className="text-stone text-xs">Receita</p>
                        <p className="text-gold text-2xl font-bold mt-1">R${(stats?.total_revenue ?? 0).toFixed(2)}</p>
                      </div>
                    </div>
                  </section>

                  <section className="bg-surface-02 rounded-lg border border-surface-03 p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-stone text-sm">Pendentes</p>
                        <p className="text-cream text-4xl font-black mt-2">{stats?.pending_orders ?? 0}</p>
                      </div>
                      <div className="h-12 w-12 rounded-lg bg-gold/15 text-gold flex items-center justify-center">
                        <Clock size={24} />
                      </div>
                    </div>
                    <p className="text-stone text-sm mt-5">Pedidos aguardando acao operacional.</p>
                    <Link to="/painel/orders" className="mt-5 inline-flex items-center gap-2 text-gold text-sm font-bold hover:text-gold-light">
                      Ver fila de pedidos
                      <ArrowUpRight size={15} />
                    </Link>
                  </section>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                  <StatCard label="Total de Pedidos" value={stats?.total_orders ?? 0} icon={ShoppingBag} tone="text-gold bg-gold/15" />
                  <StatCard label="Total de Produtos" value={stats?.total_products ?? 0} icon={Package} tone="text-blue-400 bg-blue-500/15" />
                  <StatCard label="Pedidos Pendentes" value={stats?.pending_orders ?? 0} icon={Megaphone} tone="text-green-400 bg-green-500/15" />
                  <StatCard label="Receita Total" value={`R$${(stats?.total_revenue ?? 0).toFixed(2)}`} icon={BarChart3} tone="text-purple-400 bg-purple-500/15" />
                </div>

                {recentOrders.length > 0 ? (
                  <div className="bg-surface-02 rounded-lg p-6 border border-surface-03 mb-8">
                    <div className="flex items-center justify-between gap-4 mb-4">
                      <div>
                        <h3 className="text-xl font-bold text-cream">Pedidos Recentes</h3>
                        <p className="text-stone text-sm mt-1">Ultimas movimentacoes recebidas pela loja.</p>
                      </div>
                      <Link to="/painel/orders" className="text-gold text-sm font-bold hover:text-gold-light">Ver todos</Link>
                    </div>
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
                  <div className="bg-surface-02 rounded-lg p-12 border border-surface-03 text-center mb-8">
                    <ShoppingBag size={48} className="text-slate-600 mx-auto mb-4" />
                    <p className="text-stone text-lg">Nenhum pedido ainda</p>
                    <p className="text-stone/70 text-sm mt-2">Os pedidos dos clientes aparecerao aqui.</p>
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <QuickLink to="/painel/products" icon={Package} title="Gerenciar Produtos" text="Adicionar, editar ou remover produtos do cardapio" tone="text-blue-400" />
                  <QuickLink to="/painel/orders" icon={ShoppingBag} title="Gerenciar Pedidos" text="Visualizar e atualizar status dos pedidos" tone="text-gold" />
                  <QuickLink to="/painel/conteudo" icon={BarChart3} title="Editar Conteudo" text="Textos, icones e categorias das paginas" tone="text-purple-400" />
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon: Icon, tone }: { label: string; value: string | number; icon: typeof ShoppingBag; tone: string }) {
  return (
    <div className="bg-surface-02 rounded-lg p-5 border border-surface-03">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <p className="text-stone text-sm">{label}</p>
          <p className="text-cream text-3xl font-bold mt-2 truncate">{value}</p>
        </div>
        <span className={`h-11 w-11 rounded-lg flex items-center justify-center ${tone}`}>
          <Icon size={22} />
        </span>
      </div>
    </div>
  );
}

function QuickLink({ to, icon: Icon, title, text, tone }: { to: string; icon: typeof Package; title: string; text: string; tone: string }) {
  return (
    <Link to={to} className="bg-surface-02 rounded-lg p-5 border border-surface-03 hover:border-gold/50 transition-colors">
      <Icon size={30} className={`${tone} mb-3`} />
      <h3 className="text-cream font-bold">{title}</h3>
      <p className="text-stone text-sm mt-1">{text}</p>
    </Link>
  );
}
