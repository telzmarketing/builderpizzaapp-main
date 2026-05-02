import { useEffect, useState } from "react";
import {
  Loader2, TrendingUp, DollarSign, MousePointerClick, ShoppingBag,
  Users, Megaphone, BarChart2, Target, RefreshCw, Mail, MessageCircle,
  Eye, Zap, Percent, CreditCard, UserCheck,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const unwrap = (json: any) => json?.data ?? json;

type Period = "today" | "7d" | "30d" | "90d";

interface MarketingStats {
  total_investment: number;
  revenue_generated: number;
  roas: number;
  roi: number;
  cpa: number;
  cac: number;
  visitors: number;
  leads: number;
  clients_generated: number;
  active_campaigns: number;
  whatsapp_sent: number;
  whatsapp_response_rate: number;
  email_sent: number;
  email_open_rate: number;
  clicks: number;
  orders: number;
  online_visitors: number;
  revenue_by_channel: { channel: string; revenue: number }[];
  recent_campaigns: {
    id: string;
    name: string;
    channel: string;
    status: string;
    investment: number;
    revenue: number;
    roas: number;
  }[];
}

const PERIOD_LABELS: Record<Period, string> = {
  today: "Hoje",
  "7d": "7 dias",
  "30d": "30 dias",
  "90d": "90 dias",
};

const CHANNEL_LABELS: Record<string, string> = {
  whatsapp: "WhatsApp",
  email: "E-mail",
  paid_traffic: "Tráfego Pago",
  internal: "Interno",
  remarketing: "Remarketing",
  organic: "Orgânico",
};

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-500/20 text-green-400",
  paused: "bg-yellow-500/20 text-yellow-400",
  draft: "bg-surface-03 text-stone",
  ended: "bg-red-500/20 text-red-400",
};

const STATUS_LABELS: Record<string, string> = {
  active: "Ativo",
  paused: "Pausado",
  draft: "Rascunho",
  ended: "Encerrado",
};

function fmt(v: number) {
  return (v ?? 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function pct(v: number) {
  return `${((v ?? 0) * 100).toFixed(1)}%`;
}

const EMPTY_STATS: MarketingStats = {
  total_investment: 0, revenue_generated: 0, roas: 0, roi: 0,
  cpa: 0, cac: 0, visitors: 0, leads: 0, clients_generated: 0,
  active_campaigns: 0, whatsapp_sent: 0, whatsapp_response_rate: 0,
  email_sent: 0, email_open_rate: 0, clicks: 0, orders: 0,
  online_visitors: 0, revenue_by_channel: [], recent_campaigns: [],
};

export default function MarketingDashboard() {
  const [period, setPeriod] = useState<Period>("7d");
  const [data, setData] = useState<MarketingStats>(EMPTY_STATS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchData = (p: Period) => {
    const token = localStorage.getItem("admin_token");
    setLoading(true);
    setError("");
    fetch(`${BASE}/marketing/dashboard?period=${p}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error(`Erro ${r.status} ao carregar dashboard.`);
        return r.json();
      })
      .then(unwrap)
      .then((d) => setData({ ...EMPTY_STATS, ...d }))
      .catch((e) => {
        setError(e.message);
        setData(EMPTY_STATS);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(period); }, [period]);

  const maxRevenue = data.revenue_by_channel?.length
    ? Math.max(...data.revenue_by_channel.map((c) => c.revenue), 1)
    : 1;

  const row1 = [
    { label: "Investimento Total",     value: fmt(data.total_investment),     icon: DollarSign,      color: "text-red-400",    bg: "bg-red-500/10" },
    { label: "Receita Gerada",         value: fmt(data.revenue_generated),    icon: TrendingUp,      color: "text-green-400",  bg: "bg-green-500/10" },
    { label: "ROAS",                   value: `${(data.roas ?? 0).toFixed(2)}x`, icon: BarChart2,   color: "text-gold",       bg: "bg-gold/10" },
    { label: "ROI",                    value: `${((data.roi ?? 0) * 100).toFixed(1)}%`, icon: Percent, color: "text-emerald-400", bg: "bg-emerald-500/10" },
    { label: "CPA",                    value: fmt(data.cpa),                  icon: Target,          color: "text-blue-400",   bg: "bg-blue-500/10" },
    { label: "CAC",                    value: fmt(data.cac),                  icon: CreditCard,      color: "text-orange-400", bg: "bg-orange-500/10" },
    { label: "Visitantes",             value: (data.visitors ?? 0).toLocaleString("pt-BR"), icon: Users, color: "text-purple-400", bg: "bg-purple-500/10" },
    { label: "Leads",                  value: (data.leads ?? 0).toLocaleString("pt-BR"), icon: UserCheck, color: "text-cyan-400", bg: "bg-cyan-500/10" },
  ];

  const row2 = [
    { label: "Clientes Gerados",       value: (data.clients_generated ?? 0).toLocaleString("pt-BR"), icon: UserCheck, color: "text-green-400", bg: "bg-green-500/10" },
    { label: "Campanhas Ativas",       value: String(data.active_campaigns ?? 0),  icon: Megaphone,   color: "text-orange-400", bg: "bg-orange-500/10" },
    { label: "Disparos WhatsApp",      value: (data.whatsapp_sent ?? 0).toLocaleString("pt-BR"), icon: MessageCircle, color: "text-green-400", bg: "bg-green-500/10" },
    { label: "Taxa Resposta WA",       value: pct(data.whatsapp_response_rate), icon: MessageCircle, color: "text-green-400", bg: "bg-green-500/10" },
    { label: "Disparos E-mail",        value: (data.email_sent ?? 0).toLocaleString("pt-BR"), icon: Mail, color: "text-blue-400", bg: "bg-blue-500/10" },
    { label: "Taxa Abertura E-mail",   value: pct(data.email_open_rate),     icon: Eye,             color: "text-blue-400",   bg: "bg-blue-500/10" },
    { label: "Cliques",                value: (data.clicks ?? 0).toLocaleString("pt-BR"), icon: MousePointerClick, color: "text-purple-400", bg: "bg-purple-500/10" },
    { label: "Pedidos Gerados",        value: String(data.orders ?? 0),             icon: ShoppingBag,  color: "text-gold",       bg: "bg-gold/10" },
  ];

  return (
    <div className="flex flex-col md:flex-row min-h-screen md:h-screen bg-surface-00 overflow-hidden">
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto p-6 space-y-6">

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-gold mb-1">Marketing</p>
            <h1 className="text-2xl font-bold text-cream">Dashboard de Marketing</h1>
          </div>
          <div className="flex items-center gap-2">
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
            <AdminTopActions />
          </div>
        </div>

        {loading && (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="animate-spin text-gold" size={32} />
          </div>
        )}

        {error && !loading && (
          <div className="rounded-xl bg-yellow-500/10 border border-yellow-500/30 p-4 text-yellow-400 text-sm flex items-center gap-3">
            <Zap size={16} className="flex-shrink-0" />
            <span>{error} — exibindo dados zerados.</span>
          </div>
        )}

        {!loading && (
          <>
            {/* Row 1 — investimento / receita / ROAS / ROI / CPA / CAC / visitantes / leads */}
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
              {row1.map((m) => (
                <div key={m.label} className="bg-surface-02 border border-surface-03 rounded-2xl p-3 space-y-1.5">
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-[10px] text-stone leading-tight">{m.label}</span>
                    <div className={`p-1 rounded-lg ${m.bg} flex-shrink-0`}>
                      <m.icon size={12} className={m.color} />
                    </div>
                  </div>
                  <p className={`text-base font-bold ${m.color}`}>{m.value}</p>
                </div>
              ))}
            </div>

            {/* Row 2 — clientes / campanhas / WA / email / cliques / pedidos */}
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
              {row2.map((m) => (
                <div key={m.label} className="bg-surface-02 border border-surface-03 rounded-2xl p-3 space-y-1.5">
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-[10px] text-stone leading-tight">{m.label}</span>
                    <div className={`p-1 rounded-lg ${m.bg} flex-shrink-0`}>
                      <m.icon size={12} className={m.color} />
                    </div>
                  </div>
                  <p className={`text-base font-bold ${m.color}`}>{m.value}</p>
                </div>
              ))}
            </div>

            {/* Charts row */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

              {/* Receita por canal */}
              <div className="lg:col-span-2 bg-surface-02 border border-surface-03 rounded-2xl p-5">
                <h2 className="text-sm font-semibold text-cream mb-4">Receita por Canal</h2>
                {data.revenue_by_channel?.length ? (
                  <div className="space-y-3">
                    {data.revenue_by_channel.map((c) => (
                      <div key={c.channel} className="space-y-1">
                        <div className="flex justify-between text-xs">
                          <span className="text-stone">{CHANNEL_LABELS[c.channel] ?? c.channel}</span>
                          <span className="text-cream font-medium">{fmt(c.revenue)}</span>
                        </div>
                        <div className="h-2 bg-surface-03 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-gold rounded-full transition-all duration-500"
                            style={{ width: `${(c.revenue / maxRevenue) * 100}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="py-8 text-center">
                    <BarChart2 size={32} className="text-surface-03 mx-auto mb-2" />
                    <p className="text-stone text-sm">Sem dados de receita por canal para o período.</p>
                  </div>
                )}
              </div>

              {/* Visitantes online */}
              <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5 flex flex-col">
                <h2 className="text-sm font-semibold text-cream mb-4">Visitantes</h2>
                <div className="flex-1 flex flex-col items-center justify-center gap-4">
                  <div className="text-center">
                    <div className="flex items-center gap-2 justify-center mb-1">
                      <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                      <p className="text-xs text-stone">Online agora</p>
                    </div>
                    <p className="text-4xl font-bold text-cream">{data.online_visitors ?? 0}</p>
                  </div>
                  <div className="w-full border-t border-surface-03 pt-4 grid grid-cols-2 gap-3">
                    <div className="text-center">
                      <p className="text-xl font-bold text-purple-400">{(data.visitors ?? 0).toLocaleString("pt-BR")}</p>
                      <p className="text-[10px] text-stone mt-0.5">Visitantes</p>
                    </div>
                    <div className="text-center">
                      <p className="text-xl font-bold text-cyan-400">{(data.leads ?? 0).toLocaleString("pt-BR")}</p>
                      <p className="text-[10px] text-stone mt-0.5">Leads</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Funil visitante → pedido */}
            <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5">
              <h2 className="text-sm font-semibold text-cream mb-4">Funil: Visitante → Lead → Cliente → Pedido</h2>
              {(() => {
                const stages = [
                  { label: "Visitantes", value: data.visitors ?? 0, color: "bg-blue-500" },
                  { label: "Leads", value: data.leads ?? 0, color: "bg-purple-500" },
                  { label: "Clientes", value: data.clients_generated ?? 0, color: "bg-gold" },
                  { label: "Pedidos", value: data.orders ?? 0, color: "bg-green-500" },
                ];
                const max = Math.max(...stages.map((s) => s.value), 1);
                return (
                  <div className="grid grid-cols-4 gap-4">
                    {stages.map((s, i) => {
                      const pctVal = i > 0
                        ? stages[i - 1].value > 0 ? ((s.value / stages[i - 1].value) * 100).toFixed(1) : "0.0"
                        : "100";
                      return (
                        <div key={s.label} className="flex flex-col items-center gap-2">
                          <div className="w-full h-24 bg-surface-03 rounded-xl overflow-hidden flex items-end">
                            <div
                              className={`w-full ${s.color} rounded-xl transition-all duration-500`}
                              style={{ height: `${Math.max((s.value / max) * 100, 4)}%` }}
                            />
                          </div>
                          <p className="text-cream font-bold text-sm">{s.value.toLocaleString("pt-BR")}</p>
                          <p className="text-stone text-xs">{s.label}</p>
                          {i > 0 && (
                            <p className="text-[10px] text-stone/60">{pctVal}% conversão</p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                );
              })()}
            </div>

            {/* Campanhas recentes */}
            <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5">
              <h2 className="text-sm font-semibold text-cream mb-4">Campanhas Recentes</h2>
              {data.recent_campaigns?.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-stone text-xs border-b border-surface-03">
                        <th className="text-left pb-2 pr-4">Nome</th>
                        <th className="text-left pb-2 pr-4">Canal</th>
                        <th className="text-left pb-2 pr-4">Status</th>
                        <th className="text-right pb-2 pr-4">Investimento</th>
                        <th className="text-right pb-2 pr-4">Receita</th>
                        <th className="text-right pb-2">ROAS</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-03">
                      {data.recent_campaigns.map((c) => (
                        <tr key={c.id} className="hover:bg-surface-03/40 transition-colors">
                          <td className="py-2.5 pr-4 text-cream font-medium">{c.name}</td>
                          <td className="py-2.5 pr-4 text-stone">{CHANNEL_LABELS[c.channel] ?? c.channel}</td>
                          <td className="py-2.5 pr-4">
                            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[c.status] ?? "bg-surface-03 text-stone"}`}>
                              {STATUS_LABELS[c.status] ?? c.status}
                            </span>
                          </td>
                          <td className="py-2.5 pr-4 text-right text-red-400">{fmt(c.investment)}</td>
                          <td className="py-2.5 pr-4 text-right text-green-400">{fmt(c.revenue)}</td>
                          <td className="py-2.5 text-right text-gold font-semibold">{(c.roas ?? 0).toFixed(2)}x</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="py-8 text-center">
                  <Megaphone size={32} className="text-surface-03 mx-auto mb-2" />
                  <p className="text-stone text-sm">Nenhuma campanha recente no período.</p>
                </div>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
