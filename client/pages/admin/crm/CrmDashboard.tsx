import { useEffect, useState } from "react";
import {
  Loader2, Users, KanbanSquare, ClipboardList, FolderOpen, RefreshCw,
  TrendingUp, ShoppingBag, AlertCircle, Cake, MapPin, DollarSign,
  UserCheck, BarChart2, Clock,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const unwrap = (json: any) => json?.data ?? json;

type Period = "today" | "7d" | "30d" | "90d" | "custom";

interface FunnelStage {
  name: string;
  count: number;
}

interface NeighborhoodStat {
  name: string;
  count: number;
}

interface OriginStat {
  name: string;
  count: number;
}

interface CrmDashboardData {
  total_clients: number;
  new_clients: number;
  recurring_clients: number;
  inactive_clients: number;
  birthday_clients: number;
  avg_ticket: number;
  revenue_per_client: number;
  pipeline_cards: number;
  open_opportunities: number;
  pending_tasks: number;
  overdue_tasks: number;
  groups: number;
  funnel: FunnelStage[];
  clients_by_neighborhood: NeighborhoodStat[];
  clients_by_origin: OriginStat[];
}

const PERIOD_LABELS: Record<Period, string> = {
  today: "Hoje",
  "7d": "7 dias",
  "30d": "30 dias",
  "90d": "90 dias",
  custom: "Personalizado",
};

const FUNNEL_COLORS = [
  "bg-blue-500", "bg-purple-500", "bg-gold", "bg-orange-500",
  "bg-green-500", "bg-teal-500", "bg-pink-500", "bg-red-500",
  "bg-indigo-500", "bg-cyan-500",
];

function fmtCurrency(v: number) {
  return (v ?? 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function StatBar({
  data,
  labelKey,
  valueKey,
  color = "bg-gold",
}: {
  data: Record<string, unknown>[];
  labelKey: string;
  valueKey: string;
  color?: string;
}) {
  const max = Math.max(...data.map((d) => Number(d[valueKey]) || 0), 1);
  return (
    <div className="space-y-2">
      {data.map((d, i) => (
        <div key={i} className="space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-stone truncate max-w-[60%]">{String(d[labelKey])}</span>
            <span className="text-cream font-medium">{Number(d[valueKey])}</span>
          </div>
          <div className="h-1.5 bg-surface-03 rounded-full overflow-hidden">
            <div
              className={`h-full ${color} rounded-full transition-all duration-500`}
              style={{ width: `${(Number(d[valueKey]) / max) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function CrmDashboard() {
  const [data, setData] = useState<CrmDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [period, setPeriod] = useState<Period>("30d");

  const fetchData = (p: Period) => {
    const token = localStorage.getItem("admin_token");
    setLoading(true);
    setError("");
    fetch(`${BASE}/crm/dashboard?period=${p}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => { if (!r.ok) throw new Error("Falha ao carregar dashboard CRM."); return r.json(); })
      .then(unwrap)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(period); }, [period]);

  const d = data;
  const maxFunnel = d?.funnel?.length ? Math.max(...d.funnel.map((s) => s.count), 1) : 1;

  const topCards = d ? [
    { label: "Total de Clientes",       value: (d.total_clients ?? 0).toLocaleString("pt-BR"),    icon: Users,       color: "text-gold",     bg: "bg-gold/10" },
    { label: "Novos Clientes",          value: (d.new_clients ?? 0).toLocaleString("pt-BR"),       icon: UserCheck,   color: "text-green-400",bg: "bg-green-500/10" },
    { label: "Clientes Recorrentes",    value: (d.recurring_clients ?? 0).toLocaleString("pt-BR"), icon: TrendingUp,  color: "text-blue-400", bg: "bg-blue-500/10" },
    { label: "Clientes Inativos",       value: (d.inactive_clients ?? 0).toLocaleString("pt-BR"),  icon: AlertCircle, color: "text-red-400",  bg: "bg-red-500/10" },
    { label: "Aniversariantes do Mês",  value: (d.birthday_clients ?? 0).toLocaleString("pt-BR"),  icon: Cake,        color: "text-pink-400", bg: "bg-pink-500/10" },
    { label: "Ticket Médio",            value: fmtCurrency(d.avg_ticket ?? 0),                     icon: DollarSign,  color: "text-gold",     bg: "bg-gold/10" },
    { label: "Receita por Cliente",     value: fmtCurrency(d.revenue_per_client ?? 0),             icon: ShoppingBag, color: "text-emerald-400", bg: "bg-emerald-500/10" },
    { label: "Cards no Pipeline",       value: (d.pipeline_cards ?? 0).toLocaleString("pt-BR"),    icon: KanbanSquare,color: "text-purple-400",bg: "bg-purple-500/10" },
    { label: "Oportunidades Abertas",   value: (d.open_opportunities ?? 0).toLocaleString("pt-BR"),icon: BarChart2,   color: "text-cyan-400", bg: "bg-cyan-500/10" },
    { label: "Tarefas Pendentes",       value: (d.pending_tasks ?? 0).toLocaleString("pt-BR"),     icon: ClipboardList,color: "text-orange-400",bg: "bg-orange-500/10" },
    { label: "Tarefas Atrasadas",       value: (d.overdue_tasks ?? 0).toLocaleString("pt-BR"),     icon: Clock,       color: "text-red-400",  bg: "bg-red-500/10" },
    { label: "Grupos",                  value: (d.groups ?? 0).toLocaleString("pt-BR"),            icon: FolderOpen,  color: "text-indigo-400",bg: "bg-indigo-500/10" },
  ] : [];

  return (
    <div className="flex flex-col md:flex-row min-h-screen bg-surface-01">
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto p-6 space-y-6">

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-gold mb-1">CRM</p>
            <h1 className="text-2xl font-bold text-cream">Dashboard CRM</h1>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex bg-surface-02 rounded-xl border border-surface-03 overflow-hidden">
              {(["today", "7d", "30d", "90d"] as Period[]).map((p) => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className={`px-3 py-2 text-sm font-medium transition-colors ${
                    period === p ? "bg-gold text-black" : "text-stone hover:text-cream"
                  }`}
                >
                  {PERIOD_LABELS[p]}
                </button>
              ))}
            </div>
            <button
              onClick={() => fetchData(period)}
              className="p-2 rounded-xl bg-surface-02 border border-surface-03 text-stone hover:text-cream transition-colors"
            >
              <RefreshCw size={16} />
            </button>
          </div>
        </div>

        {loading && (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="animate-spin text-gold" size={28} />
          </div>
        )}
        {error && !loading && (
          <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 text-red-400 text-sm">{error}</div>
        )}

        {!loading && !error && d && (
          <>
            {/* 12 metric cards */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
              {topCards.map((m) => (
                <div key={m.label} className="bg-surface-02 border border-surface-03 rounded-2xl p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-stone leading-tight">{m.label}</span>
                    <div className={`p-1.5 rounded-lg ${m.bg} flex-shrink-0`}>
                      <m.icon size={14} className={m.color} />
                    </div>
                  </div>
                  <p className={`text-xl font-bold ${m.color}`}>{m.value}</p>
                </div>
              ))}
            </div>

            {/* Charts row */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

              {/* Funil */}
              <div className="lg:col-span-2 bg-surface-02 border border-surface-03 rounded-2xl p-5">
                <h2 className="text-sm font-semibold text-cream mb-5">Funil do CRM por Etapa</h2>
                {d.funnel?.length ? (
                  <div className="space-y-3">
                    {d.funnel.map((stage, i) => (
                      <div key={stage.name} className="flex items-center gap-4">
                        <div className="w-36 text-xs text-stone truncate text-right shrink-0">
                          {stage.name}
                        </div>
                        <div className="flex-1 flex items-center gap-3">
                          <div className="flex-1 h-7 bg-surface-03 rounded-xl overflow-hidden">
                            <div
                              className={`h-full rounded-xl ${FUNNEL_COLORS[i % FUNNEL_COLORS.length]} transition-all duration-500 flex items-center px-3`}
                              style={{ width: `${Math.max((stage.count / maxFunnel) * 100, 4)}%` }}
                            >
                              {stage.count > 0 && (
                                <span className="text-xs font-bold text-white/90">{stage.count}</span>
                              )}
                            </div>
                          </div>
                          <span className="text-xs text-stone w-8 text-right shrink-0">{stage.count}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-stone text-sm text-center py-8">Sem dados de funil disponíveis.</p>
                )}
              </div>

              {/* Clientes ativos vs inativos */}
              <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5">
                <h2 className="text-sm font-semibold text-cream mb-4">Clientes Ativos × Inativos</h2>
                <div className="space-y-4">
                  {(() => {
                    const active = (d.total_clients ?? 0) - (d.inactive_clients ?? 0);
                    const inactive = d.inactive_clients ?? 0;
                    const total = Math.max(active + inactive, 1);
                    const activePct = Math.round((active / total) * 100);
                    const inactivePct = 100 - activePct;
                    return (
                      <>
                        <div className="w-full h-4 bg-surface-03 rounded-full overflow-hidden flex">
                          <div className="bg-green-500 h-full transition-all duration-500" style={{ width: `${activePct}%` }} />
                          <div className="bg-red-500/60 h-full transition-all duration-500" style={{ width: `${inactivePct}%` }} />
                        </div>
                        <div className="space-y-2">
                          <div className="flex items-center justify-between text-xs">
                            <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-green-500 inline-block" /> Ativos</span>
                            <span className="text-cream font-medium">{active.toLocaleString("pt-BR")} ({activePct}%)</span>
                          </div>
                          <div className="flex items-center justify-between text-xs">
                            <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-red-500/60 inline-block" /> Inativos</span>
                            <span className="text-cream font-medium">{inactive.toLocaleString("pt-BR")} ({inactivePct}%)</span>
                          </div>
                        </div>
                        <div className="border-t border-surface-03 pt-3">
                          <p className="text-xs text-stone mb-1">Tarefas</p>
                          <div className="flex gap-4">
                            <div className="text-center">
                              <p className="text-lg font-bold text-orange-400">{d.pending_tasks ?? 0}</p>
                              <p className="text-[10px] text-stone">Pendentes</p>
                            </div>
                            <div className="text-center">
                              <p className="text-lg font-bold text-red-400">{d.overdue_tasks ?? 0}</p>
                              <p className="text-[10px] text-stone">Atrasadas</p>
                            </div>
                            <div className="text-center">
                              <p className="text-lg font-bold text-purple-400">{d.pipeline_cards ?? 0}</p>
                              <p className="text-[10px] text-stone">No Pipeline</p>
                            </div>
                          </div>
                        </div>
                      </>
                    );
                  })()}
                </div>
              </div>
            </div>

            {/* Bottom row: bairros + origem */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

              {/* Clientes por bairro */}
              <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5">
                <div className="flex items-center gap-2 mb-4">
                  <MapPin size={16} className="text-gold" />
                  <h2 className="text-sm font-semibold text-cream">Clientes por Bairro</h2>
                </div>
                {d.clients_by_neighborhood?.length ? (
                  <StatBar data={d.clients_by_neighborhood as unknown as Record<string, unknown>[]} labelKey="name" valueKey="count" color="bg-gold" />
                ) : (
                  <p className="text-stone text-xs text-center py-6">Sem dados de bairro disponíveis.</p>
                )}
              </div>

              {/* Clientes por origem */}
              <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5">
                <div className="flex items-center gap-2 mb-4">
                  <TrendingUp size={16} className="text-purple-400" />
                  <h2 className="text-sm font-semibold text-cream">Clientes por Origem</h2>
                </div>
                {d.clients_by_origin?.length ? (
                  <StatBar data={d.clients_by_origin as unknown as Record<string, unknown>[]} labelKey="name" valueKey="count" color="bg-purple-500" />
                ) : (
                  <p className="text-stone text-xs text-center py-6">Sem dados de origem disponíveis.</p>
                )}
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
