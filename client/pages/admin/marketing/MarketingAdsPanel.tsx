import { useEffect, useState, useCallback } from "react";
import {
  Loader2, RefreshCw, TrendingUp, MousePointerClick,
  Eye, ShoppingCart, DollarSign, Zap, BarChart2,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const unwrap = (j: any) => j?.data ?? j;

const PLATFORMS = ["meta", "google", "tiktok"] as const;
type Platform = (typeof PLATFORMS)[number];

const PLATFORM_META: Record<Platform, { label: string; emoji: string; color: string }> = {
  meta: { label: "Meta Ads", emoji: "📘", color: "text-blue-400" },
  google: { label: "Google Ads", emoji: "🎯", color: "text-green-400" },
  tiktok: { label: "TikTok Ads", emoji: "🎵", color: "text-pink-400" },
};

interface Campaign {
  id: string;
  platform: Platform;
  external_id: string;
  name: string;
  status: string;
  objective: string;
  budget_daily: number;
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  revenue: number;
  ctr: number;
  cpc: number;
  cpa: number;
  roas: number;
  last_synced_at: string | null;
}

interface PlatformInsight {
  platform: string;
  total_spend: number;
  total_impressions: number;
  total_clicks: number;
  total_conversions: number;
  total_revenue: number;
  avg_roas: number;
  campaign_count: number;
}

interface Insights {
  period: string;
  by_platform: PlatformInsight[];
  totals: {
    total_spend: number;
    total_impressions: number;
    total_clicks: number;
    total_conversions: number;
    total_revenue: number;
    avg_roas: number;
  };
}

const fmt = (n: number, prefix = "") =>
  `${prefix}${n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const fmtInt = (n: number) => n.toLocaleString("pt-BR");

export default function MarketingAdsPanel() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [insights, setInsights] = useState<Insights | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState<Platform | "all" | null>(null);
  const [error, setError] = useState("");
  const [activePlatform, setActivePlatform] = useState<Platform | "all">("all");

  const token = localStorage.getItem("admin_token");
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const fetchAll = useCallback(() => {
    setLoading(true);
    setError("");
    Promise.all([
      fetch(`${BASE}/ads/campaigns`, { headers }).then((r) => r.json()).then(unwrap),
      fetch(`${BASE}/ads/insights`, { headers }).then((r) => r.json()).then(unwrap),
    ])
      .then(([cmp, ins]) => {
        setCampaigns(cmp ?? []);
        setInsights(ins);
      })
      .catch(() => setError("Falha ao carregar dados de anúncios."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const syncPlatform = async (platform: Platform | "all") => {
    setSyncing(platform);
    const url = platform === "all" ? `${BASE}/ads/sync-all` : `${BASE}/ads/${platform}/sync`;
    try {
      await fetch(url, { method: "POST", headers });
      fetchAll();
    } catch {
      alert("Erro ao sincronizar.");
    } finally {
      setSyncing(null);
    }
  };

  const filteredCampaigns =
    activePlatform === "all"
      ? campaigns
      : campaigns.filter((c) => c.platform === activePlatform);

  const { totals } = insights ?? { totals: null };

  return (
    <div className="flex flex-col md:flex-row min-h-screen bg-surface-01">
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto p-6 space-y-6">

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-gold mb-1">Marketing</p>
            <h1 className="text-2xl font-bold text-cream">Painel de Anúncios</h1>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => syncPlatform("all")}
              disabled={!!syncing}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gold hover:bg-gold/90 text-black font-semibold text-sm transition-colors disabled:opacity-60"
            >
              {syncing === "all"
                ? <Loader2 size={14} className="animate-spin" />
                : <Zap size={14} />}
              Sincronizar tudo
            </button>
            <button
              onClick={fetchAll}
              className="p-2 rounded-xl bg-surface-02 border border-surface-03 text-stone hover:text-cream transition-colors"
            >
              <RefreshCw size={16} />
            </button>
          </div>
        </div>

        {loading && (
          <div className="flex items-center justify-center h-48">
            <Loader2 className="animate-spin text-gold" size={28} />
          </div>
        )}
        {error && !loading && (
          <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 text-red-400 text-sm">{error}</div>
        )}

        {!loading && !error && (
          <>
            {/* Totals */}
            {totals && (
              <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
                {[
                  { label: "Gasto total", value: fmt(totals.total_spend, "R$ "), icon: DollarSign, color: "text-gold", bg: "bg-gold/10" },
                  { label: "Impressões", value: fmtInt(totals.total_impressions), icon: Eye, color: "text-blue-400", bg: "bg-blue-500/10" },
                  { label: "Cliques", value: fmtInt(totals.total_clicks), icon: MousePointerClick, color: "text-purple-400", bg: "bg-purple-500/10" },
                  { label: "Conversões", value: fmtInt(totals.total_conversions), icon: ShoppingCart, color: "text-green-400", bg: "bg-green-500/10" },
                  { label: "Receita", value: fmt(totals.total_revenue, "R$ "), icon: TrendingUp, color: "text-emerald-400", bg: "bg-emerald-500/10" },
                  { label: "ROAS médio", value: `${totals.avg_roas.toFixed(2)}x`, icon: BarChart2, color: "text-orange-400", bg: "bg-orange-500/10" },
                ].map((m) => (
                  <div key={m.label} className="bg-surface-02 border border-surface-03 rounded-2xl p-4 space-y-2">
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
            )}

            {/* Per-platform breakdown */}
            {insights?.by_platform?.length ? (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {insights.by_platform.map((p) => {
                  const meta = PLATFORM_META[p.platform as Platform] ?? { label: p.platform, emoji: "📊", color: "text-stone" };
                  return (
                    <div key={p.platform} className="bg-surface-02 border border-surface-03 rounded-2xl p-5 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-xl">{meta.emoji}</span>
                          <span className={`font-semibold text-sm ${meta.color}`}>{meta.label}</span>
                        </div>
                        <button
                          onClick={() => syncPlatform(p.platform as Platform)}
                          disabled={!!syncing}
                          className="p-1.5 rounded-lg bg-surface-03 text-stone hover:text-cream transition-colors disabled:opacity-40"
                        >
                          {syncing === p.platform
                            ? <Loader2 size={12} className="animate-spin" />
                            : <RefreshCw size={12} />}
                        </button>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div>
                          <p className="text-stone">Gasto</p>
                          <p className="text-cream font-medium">{fmt(p.total_spend, "R$ ")}</p>
                        </div>
                        <div>
                          <p className="text-stone">Receita</p>
                          <p className="text-cream font-medium">{fmt(p.total_revenue, "R$ ")}</p>
                        </div>
                        <div>
                          <p className="text-stone">Cliques</p>
                          <p className="text-cream font-medium">{fmtInt(p.total_clicks)}</p>
                        </div>
                        <div>
                          <p className="text-stone">ROAS</p>
                          <p className="text-cream font-medium">{p.avg_roas.toFixed(2)}x</p>
                        </div>
                      </div>
                      <p className="text-xs text-stone">{p.campaign_count} campanha(s)</p>
                    </div>
                  );
                })}
              </div>
            ) : null}

            {/* Platform filter */}
            <div className="flex items-center gap-2 flex-wrap">
              {(["all", ...PLATFORMS] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setActivePlatform(p)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-colors border ${
                    activePlatform === p
                      ? "bg-gold text-black border-gold"
                      : "bg-surface-02 border-surface-03 text-stone hover:text-cream"
                  }`}
                >
                  {p === "all" ? "Todas as plataformas" : `${PLATFORM_META[p].emoji} ${PLATFORM_META[p].label}`}
                </button>
              ))}
            </div>

            {/* Campaigns table */}
            <div className="bg-surface-02 border border-surface-03 rounded-2xl overflow-hidden">
              <div className="px-5 py-4 border-b border-surface-03">
                <h2 className="text-sm font-semibold text-cream">
                  Campanhas{filteredCampaigns.length ? ` (${filteredCampaigns.length})` : ""}
                </h2>
              </div>
              {filteredCampaigns.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-stone text-xs border-b border-surface-03">
                        <th className="text-left px-5 py-3">Campanha</th>
                        <th className="text-left px-3 py-3">Status</th>
                        <th className="text-right px-3 py-3">Gasto</th>
                        <th className="text-right px-3 py-3">Impr.</th>
                        <th className="text-right px-3 py-3">Cliques</th>
                        <th className="text-right px-3 py-3">CTR</th>
                        <th className="text-right px-3 py-3">Conv.</th>
                        <th className="text-right px-3 py-3">ROAS</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-03">
                      {filteredCampaigns.map((c) => {
                        const meta = PLATFORM_META[c.platform] ?? { emoji: "📊" };
                        return (
                          <tr key={c.id} className="hover:bg-surface-03/30 transition-colors">
                            <td className="px-5 py-3">
                              <div className="flex items-center gap-2">
                                <span className="text-base">{meta.emoji}</span>
                                <div>
                                  <p className="text-cream font-medium truncate max-w-[200px]">{c.name || c.external_id}</p>
                                  <p className="text-stone text-xs">{c.objective || "—"}</p>
                                </div>
                              </div>
                            </td>
                            <td className="px-3 py-3">
                              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                                c.status === "ACTIVE" ? "bg-green-500/15 text-green-400" :
                                c.status === "PAUSED" ? "bg-yellow-500/15 text-yellow-400" :
                                "bg-surface-03 text-stone"
                              }`}>
                                {c.status || "—"}
                              </span>
                            </td>
                            <td className="px-3 py-3 text-right text-cream">{fmt(c.spend, "R$ ")}</td>
                            <td className="px-3 py-3 text-right text-stone text-xs">{fmtInt(c.impressions)}</td>
                            <td className="px-3 py-3 text-right text-stone text-xs">{fmtInt(c.clicks)}</td>
                            <td className="px-3 py-3 text-right text-stone text-xs">{(c.ctr * 100).toFixed(2)}%</td>
                            <td className="px-3 py-3 text-right text-stone text-xs">{fmtInt(c.conversions)}</td>
                            <td className="px-3 py-3 text-right font-medium text-cream">{c.roas.toFixed(2)}x</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="py-16 text-center">
                  <p className="text-stone text-sm">Nenhuma campanha sincronizada.</p>
                  <p className="text-stone/60 text-xs mt-1">Clique em "Sincronizar tudo" para importar campanhas.</p>
                </div>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
