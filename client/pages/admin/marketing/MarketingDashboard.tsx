import { useEffect, useState } from "react";
import {
  Loader2, TrendingUp, DollarSign, MousePointerClick, ShoppingBag,
  Users, Megaphone, BarChart2, Target, RefreshCw,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const unwrap = (json: any) => json?.data ?? json;

type Period = "today" | "7d" | "30d" | "90d";

interface MarketingStats {
  total_investment: number;
  revenue_generated: number;
  roas: number;
  cpa: number;
  visitors: number;
  active_campaigns: number;
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
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default function MarketingDashboard() {
  const [period, setPeriod] = useState<Period>("7d");
  const [data, setData] = useState<MarketingStats | null>(null);
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
        if (!r.ok) throw new Error("Falha ao carregar dados.");
        return r.json();
      })
      .then(unwrap)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchData(period);
  }, [period]);

  const maxRevenue =
    data?.revenue_by_channel?.length
      ? Math.max(...data.revenue_by_channel.map((c) => c.revenue), 1)
      : 1;

  const metrics = data
    ? [
        {
          label: "Investimento Total",
          value: fmt(data.total_investment),
          icon: DollarSign,
          color: "text-red-400",
          bg: "bg-red-500/10",
        },
        {
          label: "Receita Gerada",
          value: fmt(data.revenue_generated),
          icon: TrendingUp,
          color: "text-green-400",
          bg: "bg-green-500/10",
        },
        {
          label: "ROAS",
          value: `${data.roas.toFixed(2)}x`,
          icon: BarChart2,
          color: "text-gold",
          bg: "bg-gold/10",
        },
        {
          label: "CPA",
          value: fmt(data.cpa),
          icon: Target,
          color: "text-blue-400",
          bg: "bg-blue-500/10",
        },
        {
          label: "Visitantes",
          value: data.visitors.toLocaleString("pt-BR"),
          icon: Users,
          color: "text-purple-400",
          bg: "bg-purple-500/10",
        },
        {
          label: "Campanhas Ativas",
          value: String(data.active_campaigns),
          icon: Megaphone,
          color: "text-orange-400",
          bg: "bg-orange-500/10",
        },
        {
          label: "Cliques",
          value: data.clicks.toLocaleString("pt-BR"),
          icon: MousePointerClick,
          color: "text-cyan-400",
          bg: "bg-cyan-500/10",
        },
        {
          label: "Pedidos",
          value: String(data.orders),
          icon: ShoppingBag,
          color: "text-gold",
          bg: "bg-gold/10",
        },
      ]
    : [];

  return (
    <div className="flex flex-col md:flex-row min-h-screen bg-surface-01">
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-gold mb-1">
              Marketing
            </p>
            <h1 className="text-2xl font-bold text-cream">Dashboard de Marketing</h1>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex bg-surface-02 rounded-xl border border-surface-03 overflow-hidden">
              {(["today", "7d", "30d", "90d"] as Period[]).map((p) => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className={`px-3 py-2 text-sm font-medium transition-colors ${
                    period === p
                      ? "bg-gold text-black"
                      : "text-stone hover:text-cream"
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

        {/* Loading / Error */}
        {loading && (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="animate-spin text-gold" size={32} />
          </div>
        )}
        {error && !loading && (
          <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 text-red-400 text-sm">
            {error}
          </div>
        )}

        {!loading && !error && data && (
          <>
            {/* Metrics grid */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {metrics.map((m) => (
                <div
                  key={m.label}
                  className="bg-surface-02 border border-surface-03 rounded-2xl p-4 space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-stone">{m.label}</span>
                    <div className={`p-1.5 rounded-lg ${m.bg}`}>
                      <m.icon size={14} className={m.color} />
                    </div>
                  </div>
                  <p className={`text-xl font-bold ${m.color}`}>{m.value}</p>
                </div>
              ))}
            </div>

            {/* Charts row */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* Bar chart — Receita por Canal */}
              <div className="lg:col-span-2 bg-surface-02 border border-surface-03 rounded-2xl p-5">
                <h2 className="text-sm font-semibold text-cream mb-4">Receita por Canal</h2>
                {data.revenue_by_channel?.length ? (
                  <div className="space-y-3">
                    {data.revenue_by_channel.map((c) => (
                      <div key={c.channel} className="space-y-1">
                        <div className="flex justify-between text-xs">
                          <span className="text-stone">
                            {CHANNEL_LABELS[c.channel] ?? c.channel}
                          </span>
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
                  <p className="text-stone text-sm text-center py-8">
                    Sem dados de receita por canal para o período.
                  </p>
                )}
              </div>

              {/* Online visitors */}
              <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5 flex flex-col items-center justify-center text-center">
                <Users size={32} className="text-gold mb-3" />
                <p className="text-xs text-stone mb-1">Visitantes Online Agora</p>
                <p className="text-4xl font-bold text-cream">{data.online_visitors}</p>
              </div>
            </div>

            {/* Recent campaigns */}
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
                          <td className="py-2 pr-4 text-cream font-medium">{c.name}</td>
                          <td className="py-2 pr-4 text-stone">
                            {CHANNEL_LABELS[c.channel] ?? c.channel}
                          </td>
                          <td className="py-2 pr-4">
                            <span
                              className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[c.status] ?? "bg-surface-03 text-stone"}`}
                            >
                              {STATUS_LABELS[c.status] ?? c.status}
                            </span>
                          </td>
                          <td className="py-2 pr-4 text-right text-red-400">{fmt(c.investment)}</td>
                          <td className="py-2 pr-4 text-right text-green-400">{fmt(c.revenue)}</td>
                          <td className="py-2 text-right text-gold font-semibold">
                            {c.roas.toFixed(2)}x
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-stone text-sm text-center py-6">
                  Nenhuma campanha recente no período.
                </p>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
