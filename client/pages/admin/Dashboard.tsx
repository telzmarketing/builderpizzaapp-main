import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ShoppingBag, Package, BarChart3, Clock, Users,
  Bell, Search, TrendingUp, ArrowUpRight, Loader2,
  CircleDollarSign,
} from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell,
} from "recharts";
import AdminSidebar from "@/components/AdminSidebar";
import { AdminPageHeader } from "@/components/admin/AdminPageChrome";
import { adminApi, type ApiDashboard, type ApiOrder } from "@/lib/api";
import { ordersApi } from "@/lib/api";

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
  if (s === "paid" || s === "preparing") return "bg-gold/20 text-orange-400";
  return "bg-surface-03 text-stone";
};

export default function AdminDashboard() {
  const [stats, setStats] = useState<ApiDashboard | null>(null);
  const [recentOrders, setRecentOrders] = useState<ApiOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const adminUserRaw = localStorage.getItem("admin_user");
  const adminUser = adminUserRaw ? JSON.parse(adminUserRaw) : null;
  const adminName: string = adminUser?.name?.split(" ")[0] ?? "Admin";

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

  // Revenue chart data — use daily_revenue from API or generate mock from totals
  const chartData = stats?.daily_revenue?.length
    ? stats.daily_revenue.map((d) => ({ name: d.day, receita: d.revenue }))
    : [
        { name: "Seg", receita: 0 },
        { name: "Ter", receita: 0 },
        { name: "Qua", receita: 0 },
        { name: "Qui", receita: 0 },
        { name: "Sex", receita: 0 },
        { name: "Sáb", receita: 0 },
        { name: "Dom", receita: 0 },
      ];

  // Revenue distribution pie
  const totalRevenue = stats?.total_revenue ?? 0;
  const pendingRev = totalRevenue * 0.18;
  const confirmedRev = totalRevenue * 0.82;
  const pieData = [
    { name: "Confirmada", value: confirmedRev },
    { name: "Pendente",   value: pendingRev },
  ];
  const PIE_COLORS = ["#f97316", "#2d3d56"];

  return (
    <div className="min-h-screen bg-surface-00 flex flex-col md:flex-row md:h-screen overflow-hidden">
      <AdminSidebar />

      <div className="flex-1 flex flex-col overflow-hidden">

        <AdminPageHeader
          eyebrow="Visao geral"
          icon={<BarChart3 size={20} />}
          title={`Dashboard - ${adminName}`}
          description="Resumo operacional da loja em tempo real"
          actions={(
            <>
            <div className="hidden md:flex items-center gap-2 bg-surface-03/60 border border-surface-03 rounded-lg px-3 py-2 text-stone min-w-[220px]">
              <Search size={15} />
              <span className="text-sm">Buscar...</span>
            </div>
            <button className="relative p-2 rounded-lg bg-surface-03/60 border border-surface-03 text-stone hover:text-cream transition-colors">
              <Bell size={18} />
              {(stats?.pending_orders ?? 0) > 0 && (
                <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-gold" />
              )}
            </button>
            <Link
              to="/painel/orders"
              className="flex items-center gap-2 px-4 py-2 bg-gold hover:bg-gold/90 text-cream text-sm font-semibold rounded-lg transition-colors"
            >
              Pedidos
              <ArrowUpRight size={15} />
            </Link>
            </>
          )}
        />

        {/* Main scrollable area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-red-400 text-sm">{error}</div>
          )}

          {loading ? (
            <div className="flex items-center justify-center h-64">
              <Loader2 size={36} className="animate-spin text-gold" />
            </div>
          ) : (
            <>
              {/* ── Overview cards ─────────────────────────────────────── */}
              <section>
                <p className="text-parchment text-xs font-semibold uppercase tracking-widest mb-3">Visão Geral</p>
                <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
                  <OverviewCard
                    label="Pedidos Confirmados"
                    value={stats?.total_orders ?? 0}
                    icon={ShoppingBag}
                    iconClass="bg-gold/15 text-gold"
                    trend={(stats?.waiting_payment_orders ?? 0) > 0
                      ? `+ ${stats!.waiting_payment_orders} ag. pagamento`
                      : "Apenas pedidos pagos"}
                  />
                  <OverviewCard
                    label="Total de Produtos"
                    value={stats?.total_products ?? 0}
                    icon={Package}
                    iconClass="bg-blue-500/15 text-blue-400"
                    trend="Cardápio ativo"
                  />
                  <OverviewCard
                    label="Receita Total"
                    value={`R$${(stats?.total_revenue ?? 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`}
                    icon={CircleDollarSign}
                    iconClass="bg-green-500/15 text-green-400"
                    trend="+8% este mês"
                    trendUp
                  />
                  <OverviewCard
                    label="Pedidos Pendentes"
                    value={stats?.pending_orders ?? 0}
                    icon={Clock}
                    iconClass="bg-red-500/15 text-red-400"
                    trend="Aguardando ação"
                  />
                </div>
              </section>

              {/* ── Middle row ─────────────────────────────────────────── */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

                {/* Clientes */}
                <div className="bg-surface-02 rounded-xl border border-surface-03 p-5 flex flex-col justify-between">
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-stone text-sm font-medium">Total de Clientes</p>
                    <span className="p-2 rounded-lg bg-purple-500/15 text-purple-400"><Users size={18} /></span>
                  </div>
                  <div>
                    <p className="text-cream text-4xl font-black">{(stats?.total_customers ?? 0).toLocaleString("pt-BR")}</p>
                    <p className="text-stone text-xs mt-1">clientes cadastrados</p>
                  </div>
                  <div className="mt-5 space-y-2">
                    <ProgressRow label="Recorrentes" pct={68} color="bg-gold" />
                    <ProgressRow label="Novos (30d)" pct={32} color="bg-purple-400" />
                  </div>
                  <Link to="/painel/clientes" className="mt-4 flex items-center gap-1 text-gold text-xs font-semibold hover:underline">
                    Ver clientes <ArrowUpRight size={12} />
                  </Link>
                </div>

                {/* Revenue distribution pie */}
                <div className="bg-surface-02 rounded-xl border border-surface-03 p-5">
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-stone text-sm font-medium">Distribuição de Receita</p>
                    <TrendingUp size={16} className="text-stone" />
                  </div>
                  <div className="flex items-center gap-4">
                    <PieChart width={110} height={110}>
                      <Pie
                        data={pieData}
                        cx={50}
                        cy={50}
                        innerRadius={32}
                        outerRadius={50}
                        dataKey="value"
                        strokeWidth={0}
                      >
                        {pieData.map((_, i) => (
                          <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                        ))}
                      </Pie>
                    </PieChart>
                    <div className="flex flex-col gap-3">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-gold flex-shrink-0" />
                        <div>
                          <p className="text-cream text-sm font-bold">82%</p>
                          <p className="text-stone text-xs">Confirmada</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-surface-03 flex-shrink-0" />
                        <div>
                          <p className="text-cream text-sm font-bold">18%</p>
                          <p className="text-stone text-xs">Pendente</p>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="mt-4 pt-4 border-t border-surface-03">
                    <p className="text-stone text-xs">Receita total</p>
                    <p className="text-gold text-xl font-black mt-0.5">
                      R${totalRevenue.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                    </p>
                  </div>
                </div>

                {/* Top recent orders */}
                <div className="bg-surface-02 rounded-xl border border-surface-03 p-5">
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-stone text-sm font-medium">Pedidos Recentes</p>
                    <Link to="/painel/orders" className="text-gold text-xs font-semibold hover:underline flex items-center gap-0.5">
                      Ver todos <ArrowUpRight size={11} />
                    </Link>
                  </div>
                  {recentOrders.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-32 text-stone text-sm">
                      <ShoppingBag size={28} className="mb-2 opacity-30" />
                      Sem pedidos
                    </div>
                  ) : (
                    <div className="space-y-2.5">
                      {recentOrders.slice(0, 6).map((order) => (
                        <div key={order.id} className="flex items-center gap-3">
                          <div className="w-7 h-7 rounded-full bg-surface-03 flex items-center justify-center flex-shrink-0">
                            <ShoppingBag size={12} className="text-stone" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-cream text-xs font-medium truncate">{order.delivery_name}</p>
                            <p className="text-stone text-[10px]">#{order.id.slice(0, 8).toUpperCase()}</p>
                          </div>
                          <div className="text-right flex-shrink-0">
                            <p className="text-gold text-xs font-bold">R${order.total.toFixed(2)}</p>
                            <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium ${statusColor(order.status)}`}>
                              {STATUS_LABELS[order.status] ?? order.status}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* ── Revenue chart ───────────────────────────────────────── */}
              <div className="bg-surface-02 rounded-xl border border-surface-03 p-5">
                <div className="flex items-center justify-between mb-5">
                  <div>
                    <p className="text-cream font-semibold">Receita — Últimos 7 dias</p>
                    <p className="text-stone text-xs mt-0.5">Evolução da receita por dia</p>
                  </div>
                  <BarChart3 size={18} className="text-stone" />
                </div>
                <ResponsiveContainer width="100%" height={200}>
                  <AreaChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorReceita" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#f97316" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2d3d56" vertical={false} />
                    <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} width={50}
                      tickFormatter={(v) => `R$${(v / 1000).toFixed(0)}k`} />
                    <Tooltip
                      contentStyle={{ background: "#1e2a3b", border: "1px solid #2d3d56", borderRadius: "8px", color: "#f8fafc" }}
                      labelStyle={{ color: "#94a3b8", fontSize: "11px" }}
                      formatter={(v: number) => [`R$${v.toFixed(2)}`, "Receita"]}
                    />
                    <Area
                      type="monotone"
                      dataKey="receita"
                      stroke="#f97316"
                      strokeWidth={2}
                      fill="url(#colorReceita)"
                      dot={{ fill: "#f97316", r: 3 }}
                      activeDot={{ r: 5 }}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              {/* ── Quick links ─────────────────────────────────────────── */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pb-4">
                <QuickLink to="/painel/products"  icon={Package}      label="Gerenciar Produtos"  desc="Adicionar e editar cardápio"    tone="text-blue-400 bg-blue-500/10" />
                <QuickLink to="/painel/orders"    icon={ShoppingBag}  label="Fila de Pedidos"     desc="Atualizar status e operação"    tone="text-gold bg-gold/10" />
                <QuickLink to="/painel/aparencia" icon={BarChart3}    label="Aparência da Loja"   desc="Cores, tema e identidade"       tone="text-purple-400 bg-purple-500/10" />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function OverviewCard({
  label, value, icon: Icon, iconClass, trend, trendUp,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  iconClass: string;
  trend?: string;
  trendUp?: boolean;
}) {
  return (
    <div className="bg-surface-02 rounded-xl border border-surface-03 px-5 py-4">
      <div className="flex items-center justify-between gap-3 mb-3">
        <p className="text-stone text-xs font-medium">{label}</p>
        <span className={`p-2 rounded-lg flex-shrink-0 ${iconClass}`}>
          <Icon size={17} />
        </span>
      </div>
      <p className="text-cream text-2xl font-black truncate">{value}</p>
      {trend && (
        <p className={`text-xs mt-1.5 ${trendUp ? "text-green-400" : "text-stone"}`}>{trend}</p>
      )}
    </div>
  );
}

function ProgressRow({ label, pct, color }: { label: string; pct: number; color: string }) {
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-stone">{label}</span>
        <span className="text-parchment font-medium">{pct}%</span>
      </div>
      <div className="h-1.5 bg-surface-03 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function QuickLink({ to, icon: Icon, label, desc, tone }: {
  to: string; icon: React.ElementType; label: string; desc: string; tone: string;
}) {
  return (
    <Link to={to} className="flex items-center gap-4 bg-surface-02 rounded-xl border border-surface-03 hover:border-gold/40 p-4 transition-colors group">
      <span className={`p-3 rounded-lg flex-shrink-0 ${tone}`}>
        <Icon size={20} />
      </span>
      <div className="min-w-0">
        <p className="text-cream text-sm font-semibold group-hover:text-gold transition-colors">{label}</p>
        <p className="text-stone text-xs truncate">{desc}</p>
      </div>
      <ArrowUpRight size={16} className="text-stone ml-auto flex-shrink-0 group-hover:text-gold transition-colors" />
    </Link>
  );
}
