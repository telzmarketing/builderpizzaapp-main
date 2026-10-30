import { useCallback, useEffect, useState } from "react";
import { BarChart3, Clock3, Loader2, RefreshCw, RotateCcw, Truck } from "lucide-react";
import { biApi, type KdsAnalytics } from "@/lib/api";

const periods = [
  ["7d", "7 dias"],
  ["30d", "30 dias"],
  ["90d", "90 dias"],
] as const;

const flowLabels: Record<string, string> = {
  payment_to_preparation: "Pagamento → preparo",
  preparation_to_ready: "Preparo → pronto",
  ready_to_dispatch: "Pronto → expedição",
  dispatch_to_delivery: "Expedição → entrega",
  total: "Tempo total",
};

const stageLabels: Record<string, string> = {
  waiting_kitchen: "Aguardando cozinha",
  preparing: "Em preparo",
  ready_for_pickup: "Prontos",
  in_route: "Em rota",
  delivered: "Entregues",
};

const stationCards = [
  ["KDS Principal", "Pedidos no fluxo", (data: KdsAnalytics) => data.orders.total],
  ["KDS Pizzaiolo", "Preparo → pronto", (data: KdsAnalytics) => data.flow_minutes.preparation_to_ready?.average ?? 0],
  ["KDS Cozinha Preparo", "Unidades produzidas", (data: KdsAnalytics) => data.production.units],
  ["KDS Expedição", "Pronto → expedição", (data: KdsAnalytics) => data.flow_minutes.ready_to_dispatch?.average ?? 0],
  ["KDS Motoboys", "Expedição → entrega", (data: KdsAnalytics) => data.flow_minutes.dispatch_to_delivery?.average ?? 0],
] as const;

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("pt-BR");
}

function metric(value: number) {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(value);
}

function Card({ title, value, detail, icon: Icon }: { title: string; value: string; detail: string; icon: typeof BarChart3 }) {
  return <article className="rounded-2xl border border-surface-03 bg-surface-02 p-4"><div className="flex items-center justify-between gap-3 text-sm text-stone"><span>{title}</span><Icon size={17} className="text-gold" /></div><p className="mt-3 text-3xl font-black text-cream">{value}</p><p className="mt-1 text-xs text-stone">{detail}</p></article>;
}

export default function KdsAnalytics() {
  const [period, setPeriod] = useState("30d");
  const [data, setData] = useState<KdsAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (manual = false) => {
    if (manual) setRefreshing(true);
    setError(null);
    try {
      setData(await biApi.kdsAnalytics(period));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Não foi possível carregar o analítico KDS.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [period]);

  useEffect(() => { void load(); }, [load]);

  return <main className="kds-analytics space-y-5 pb-10" aria-labelledby="kds-analytics-title">
    <header className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
      <div><p className="text-xs font-bold uppercase tracking-[0.18em] text-gold">Módulo KDS</p><h1 id="kds-analytics-title" className="mt-1 text-2xl font-black text-cream sm:text-3xl">Analítico de todos os KDS</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-stone">Consolidação histórica da cozinha, preparo, expedição e motoboys. O painel operacional continua no KDS Principal.</p></div>
      <div className="flex flex-wrap items-center gap-2"><label className="sr-only" htmlFor="kds-period">Período</label><select id="kds-period" value={period} onChange={(event) => setPeriod(event.target.value)} className="min-h-10 rounded-lg border border-surface-03 bg-surface-02 px-3 text-sm text-cream">{periods.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><button type="button" onClick={() => void load(true)} disabled={loading || refreshing} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-surface-03 px-3 text-sm font-bold text-stone hover:border-gold/50 hover:text-cream"><RefreshCw size={15} className={refreshing ? "animate-spin" : ""} />Atualizar</button></div>
    </header>
    {error && <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-100">{error}</div>}
    {loading ? <div className="flex min-h-64 items-center justify-center rounded-2xl border border-surface-03 bg-surface-02 text-sm text-stone"><Loader2 size={24} className="mr-3 animate-spin text-gold" />Carregando analítico KDS...</div> : !data ? <div className="rounded-2xl border border-surface-03 bg-surface-02 p-8 text-center text-sm text-stone">Não há dados analíticos disponíveis para este período.</div> : <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"><Card title="Pedidos no fluxo" value={metric(data.orders.total)} detail={`${metric(data.orders.completed)} concluídos`} icon={BarChart3} /><Card title="Tempo total médio" value={`${metric(data.flow_minutes.total?.average ?? 0)} min`} detail={`${data.flow_minutes.total?.samples ?? 0} amostras`} icon={Clock3} /><Card title="Unidades de produção" value={metric(data.production.units)} detail={`${metric(data.production.attempts)} tentativas`} icon={Truck} /><Card title="Retrabalho" value={metric(data.production.rework_attempts)} detail="tentativas após a primeira" icon={RotateCcw} /></div>
      <section className="rounded-2xl border border-surface-03 bg-surface-02 p-4"><h2 className="text-lg font-black text-cream">Cobertura das estações</h2><p className="mt-1 text-xs text-stone">Indicadores consolidados por estação a partir dos eventos persistidos no fluxo KDS.</p><div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">{stationCards.map(([station, label, getValue]) => { const value = getValue(data); const isTime = station !== "KDS Principal" && station !== "KDS Cozinha Preparo"; return <div key={station} className="rounded-xl border border-surface-03 bg-surface-01 p-3"><p className="text-sm font-bold text-cream">{station}</p><p className="mt-2 text-xs text-stone">{label}</p><p className="mt-1 text-2xl font-black text-gold">{metric(value)}{isTime ? " min" : ""}</p></div>; })}</div></section>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2"><section className="rounded-2xl border border-surface-03 bg-surface-02 p-4"><h2 className="text-lg font-black text-cream">Visão por etapa dos KDS</h2><div className="mt-4 space-y-3">{Object.entries(data.orders.stage_counts).map(([key, value]) => <div key={key}><div className="flex justify-between gap-3 text-sm"><span className="text-stone">{stageLabels[key] ?? key}</span><strong className="text-cream">{metric(value)}</strong></div><div className="mt-1 h-2 overflow-hidden rounded-full bg-surface-03"><div className="h-full rounded-full bg-gold" style={{ width: `${data.orders.total ? Math.min(100, value / data.orders.total * 100) : 0}%` }} /></div></div>)}</div></section><section className="rounded-2xl border border-surface-03 bg-surface-02 p-4"><h2 className="text-lg font-black text-cream">Tempos médios por transição</h2><div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">{Object.entries(data.flow_minutes).map(([key, value]) => <div key={key} className="rounded-xl border border-surface-03 bg-surface-01 p-3"><p className="text-xs text-stone">{flowLabels[key] ?? key}</p><p className="mt-1 text-xl font-black text-cream">{metric(value.average)} min</p><p className="text-[11px] text-stone">{value.samples} amostras</p></div>)}</div></section></div>
      <section className="rounded-2xl border border-surface-03 bg-surface-02 p-4"><div className="flex flex-wrap items-baseline justify-between gap-2"><h2 className="text-lg font-black text-cream">Escopo e qualidade dos dados</h2><p className="text-xs text-stone">Gerado em {formatDate(data.generated_at)} · período {data.date_from} a {data.date_to}</p></div><ul className="mt-4 grid grid-cols-1 gap-2 text-xs leading-5 text-stone md:grid-cols-3">{data.definitions.map((definition) => <li key={definition} className="rounded-lg bg-surface-01 p-3">{definition}</li>)}</ul></section>
    </>}
  </main>;
}
