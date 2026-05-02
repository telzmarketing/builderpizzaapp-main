import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, RefreshCw, Star, Clock, TrendingUp, BarChart2 } from "lucide-react";
import { deliveryApi, type DriverAnalytics } from "@/lib/api";

function monthStart(offset = 0) {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth() + offset, 1).toISOString().split("T")[0];
}

function monthEnd(offset = 0) {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth() + offset + 1, 0).toISOString().split("T")[0];
}

function todayStr() {
  return new Date().toISOString().split("T")[0];
}

function fmtBRL(value: number) {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

const VEHICLE_EMOJI: Record<string, string> = {
  motorcycle: "🏍️",
  bicycle: "🚲",
  car: "🚗",
  walking: "🚶",
};

type Period = "current" | "last" | "custom";

function RatingStars({ rating }: { rating: number | null }) {
  if (rating === null) return <span className="text-stone text-xs">Sem avaliações</span>;
  const full = Math.round(rating);
  return (
    <div className="flex items-center gap-1">
      {[1, 2, 3, 4, 5].map((i) => (
        <Star key={i} size={11} className={i <= full ? "fill-gold text-gold" : "text-stone/40"} />
      ))}
      <span className="text-cream text-xs font-bold ml-1">{rating.toFixed(1)}</span>
    </div>
  );
}

function CompletionBar({ rate }: { rate: number }) {
  const cls = rate >= 90 ? "bg-green-500" : rate >= 70 ? "bg-gold" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-surface-03 overflow-hidden">
        <div className={`h-full rounded-full ${cls}`} style={{ width: `${Math.min(rate, 100)}%` }} />
      </div>
      <span className="text-xs text-cream font-bold w-10 text-right">{rate.toFixed(0)}%</span>
    </div>
  );
}

export default function LogisticaAnalytics() {
  const [period, setPeriod] = useState<Period>("current");
  const [customFrom, setCustomFrom] = useState(monthStart());
  const [customTo, setCustomTo] = useState(todayStr());
  const [analytics, setAnalytics] = useState<DriverAnalytics[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const { from, to } = useMemo(() => {
    if (period === "current") return { from: monthStart(), to: monthEnd() };
    if (period === "last") return { from: monthStart(-1), to: monthEnd(-1) };
    return { from: customFrom, to: customTo };
  }, [period, customFrom, customTo]);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError("");
    try {
      const data = await deliveryApi.getAnalytics({ period_from: from, period_to: to });
      setAnalytics(data ?? []);
    } catch {
      setError("Não foi possível carregar os dados de análise.");
    } finally {
      setLoading(false);
    }
  }, [from, to]);

  useEffect(() => { load(); }, [from, to]);

  const totals = useMemo(() => ({
    deliveries: analytics.reduce((s, a) => s + a.total_deliveries, 0),
    pending: analytics.reduce((s, a) => s + a.pending_earnings, 0),
    paid: analytics.reduce((s, a) => s + a.paid_earnings, 0),
  }), [analytics]);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-cream font-bold text-lg">Análises de Desempenho</h3>
          <p className="text-stone text-sm mt-0.5">Métricas por motoboy no período selecionado</p>
        </div>
        <button
          onClick={() => load()}
          className="flex items-center gap-1.5 rounded-xl border border-surface-03 px-3 py-2 text-stone text-sm hover:text-cream transition-colors"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          Atualizar
        </button>
      </div>

      {/* Period filter */}
      <div className="flex flex-wrap gap-3 mb-5">
        <div className="flex rounded-xl overflow-hidden border border-surface-03">
          {(["current", "last", "custom"] as Period[]).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-4 py-2 text-xs font-medium transition-colors ${
                period === p ? "bg-gold text-cream" : "bg-surface-02 text-stone hover:text-cream"
              }`}
            >
              {p === "current" ? "Este mês" : p === "last" ? "Mês anterior" : "Personalizado"}
            </button>
          ))}
        </div>
        {period === "custom" && (
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={customFrom}
              onChange={(e) => setCustomFrom(e.target.value)}
              className="rounded-lg border border-surface-03 bg-surface-02 text-cream text-xs px-3 py-2"
            />
            <span className="text-stone text-xs">até</span>
            <input
              type="date"
              value={customTo}
              onChange={(e) => setCustomTo(e.target.value)}
              className="rounded-lg border border-surface-03 bg-surface-02 text-cream text-xs px-3 py-2"
            />
          </div>
        )}
      </div>

      {/* Period summary */}
      {!loading && analytics.length > 0 && (
        <div className="grid grid-cols-3 gap-3 mb-6">
          <div className="rounded-2xl border border-surface-03 bg-surface-02 px-4 py-3 text-center">
            <p className="text-stone text-[10px] uppercase tracking-widest mb-1">Entregas no período</p>
            <p className="text-gold text-xl font-black">{totals.deliveries}</p>
          </div>
          <div className="rounded-2xl border border-surface-03 bg-surface-02 px-4 py-3 text-center">
            <p className="text-stone text-[10px] uppercase tracking-widest mb-1">A pagar</p>
            <p className="text-orange-300 text-xl font-black">{fmtBRL(totals.pending)}</p>
          </div>
          <div className="rounded-2xl border border-surface-03 bg-surface-02 px-4 py-3 text-center">
            <p className="text-stone text-[10px] uppercase tracking-widest mb-1">Já pago</p>
            <p className="text-green-300 text-xl font-black">{fmtBRL(totals.paid)}</p>
          </div>
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 size={36} className="animate-spin text-gold" />
        </div>
      ) : analytics.length === 0 ? (
        <div className="flex flex-col items-center py-16 text-center">
          <BarChart2 size={48} className="text-stone mb-4" />
          <p className="text-cream font-bold">Nenhum motoboy cadastrado</p>
          <p className="text-stone text-sm mt-1">Cadastre motoboys na aba Motoboys para ver métricas.</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {analytics.map((a) => (
            <div key={a.person_id} className="rounded-2xl border border-surface-03 bg-surface-02 p-5">
              {/* Driver header */}
              <div className="flex items-center gap-3 mb-4">
                <span className="text-2xl">{VEHICLE_EMOJI[a.vehicle_type] ?? "🏍️"}</span>
                <div className="min-w-0">
                  <p className="text-cream font-bold text-sm truncate">{a.person_name}</p>
                  <p className="text-stone text-xs">{a.person_phone}</p>
                </div>
              </div>

              {/* Stats grid */}
              <div className="grid grid-cols-2 gap-3 mb-4">
                <div className="rounded-xl bg-surface-03/50 px-3 py-2.5 text-center">
                  <p className="text-stone text-[10px] uppercase tracking-widest mb-1">Entregas</p>
                  <p className="text-gold text-lg font-black">{a.total_deliveries}</p>
                </div>
                <div className="rounded-xl bg-surface-03/50 px-3 py-2.5 text-center">
                  <p className="text-stone text-[10px] uppercase tracking-widest mb-1">Tempo médio</p>
                  <div className="flex items-center justify-center gap-1">
                    <Clock size={11} className="text-blue-300 flex-shrink-0" />
                    <p className="text-blue-300 text-sm font-bold">
                      {a.avg_duration_minutes !== null ? `${a.avg_duration_minutes}min` : "—"}
                    </p>
                  </div>
                </div>
              </div>

              {/* Rating */}
              <div className="mb-3">
                <p className="text-stone text-[10px] uppercase tracking-widest mb-1.5">Avaliação média</p>
                <RatingStars rating={a.avg_rating} />
              </div>

              {/* Completion rate bar */}
              <div className="mb-4">
                <div className="flex items-center justify-between mb-1">
                  <p className="text-stone text-[10px] uppercase tracking-widest">Taxa de conclusão</p>
                </div>
                <CompletionBar rate={a.completion_rate} />
              </div>

              {/* Earnings */}
              <div className="rounded-xl bg-surface-03/50 px-3 py-2.5">
                <p className="text-stone text-[10px] uppercase tracking-widest mb-2">Repasses no período</p>
                <div className="flex justify-between text-xs">
                  <span className="flex items-center gap-1 text-orange-300">
                    <TrendingUp size={10} />
                    Pendente: <span className="font-bold ml-1">{fmtBRL(a.pending_earnings)}</span>
                  </span>
                  <span className="text-green-300 font-bold">
                    Pago: {fmtBRL(a.paid_earnings)}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
