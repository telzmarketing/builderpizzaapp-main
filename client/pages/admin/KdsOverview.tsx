import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bike,
  ChefHat,
  Clock3,
  Gauge,
  Loader2,
  PackageCheck,
  RefreshCw,
  Route,
  Truck,
  Users,
  WifiOff,
} from "lucide-react";
import { kdsApi, type KdsOverview, type KdsOverviewStage } from "@/lib/api";
import { groupKdsOverviewOrders } from "@/lib/kds";

const POLL_INTERVAL_MS = 15_000;

const STAGES: Array<{
  key: KdsOverviewStage;
  title: string;
  empty: string;
  icon: typeof ChefHat;
  accent: string;
}> = [
  { key: "waiting_kitchen", title: "Aguardando cozinha", empty: "Nenhum pedido aguardando", icon: Clock3, accent: "text-amber-300" },
  { key: "preparing", title: "Em preparo", empty: "Nenhum pedido em preparo", icon: ChefHat, accent: "text-orange-300" },
  { key: "ready_unassigned", title: "Prontos na expedição", empty: "Nenhum pedido pronto aguardando liberação", icon: PackageCheck, accent: "text-sky-300" },
  { key: "assigned_waiting_departure", title: "Aguardando saída", empty: "Nenhum pedido aguardando saída", icon: Bike, accent: "text-emerald-300" },
  { key: "in_route", title: "Em rota", empty: "Nenhum pedido em rota", icon: Route, accent: "text-violet-300" },
];

function elapsed(startedAt: string) {
  const timestamp = new Date(startedAt).getTime();
  if (!Number.isFinite(timestamp)) return "--";
  const minutes = Math.max(0, Math.floor((Date.now() - timestamp) / 60_000));
  return minutes < 60 ? `${minutes}min` : `${Math.floor(minutes / 60)}h ${minutes % 60}min`;
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Não foi possível atualizar o Painel Geral do KDS.";
}

export default function KdsOverview() {
  const [overview, setOverview] = useState<KdsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [, setTick] = useState(0);

  const loadOverview = useCallback(async (manual = false) => {
    if (manual) setRefreshing(true);
    try {
      const data = await kdsApi.overview();
      setOverview(data);
      setError(null);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadOverview();
    const poll = window.setInterval(() => void loadOverview(), POLL_INTERVAL_MS);
    return () => window.clearInterval(poll);
  }, [loadOverview]);

  useEffect(() => {
    const timer = window.setInterval(() => setTick((value) => value + 1), 10_000);
    return () => window.clearInterval(timer);
  }, []);

  const groupedOrders = useMemo(
    () => groupKdsOverviewOrders(overview?.orders ?? []),
    [overview?.orders],
  );

  const counters = overview?.counters;
  const operationalCounters = [
    { label: "Aguardando", value: counters?.waiting_kitchen ?? 0, icon: Clock3, color: "text-amber-300" },
    { label: "Em preparo", value: counters?.preparing ?? 0, icon: ChefHat, color: "text-orange-300" },
    { label: "Na expedição", value: counters?.ready_unassigned ?? 0, icon: PackageCheck, color: "text-sky-300" },
    { label: "Aguardando saída", value: counters?.assigned_waiting_departure ?? 0, icon: Truck, color: "text-emerald-300" },
    { label: "Em rota", value: counters?.in_route ?? 0, icon: Route, color: "text-violet-300" },
    { label: "Motoboys livres", value: counters?.drivers_available ?? 0, icon: Bike, color: "text-emerald-300" },
    { label: "Motoboys ocupados", value: counters?.drivers_busy ?? 0, icon: Users, color: "text-rose-300" },
  ];

  if (loading && !overview) {
    return (
      <div className="flex min-h-[24rem] items-center justify-center gap-3 text-stone">
        <Loader2 className="animate-spin text-gold" aria-hidden="true" />
        <span className="font-semibold">Carregando operação KDS...</span>
      </div>
    );
  }

  return (
    <section className="space-y-5" aria-live="polite">
      <div className="flex flex-col gap-3 rounded-2xl border border-surface-03 bg-surface-02 p-4 shadow-soft sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gold/10 text-gold">
            <Gauge aria-hidden="true" />
          </span>
          <div>
            <h2 className="text-lg font-black text-cream">Fluxo operacional em tempo real</h2>
            <p className="text-sm text-stone">
              {overview?.generated_at
                ? `Atualizado às ${new Date(overview.generated_at).toLocaleTimeString("pt-BR")}`
                : "Aguardando sincronização"}
              {" · atualização automática a cada 15s"}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => void loadOverview(true)}
          disabled={refreshing}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-surface-03 bg-surface-01 px-4 font-bold text-parchment transition-colors hover:border-gold/50 disabled:opacity-50"
        >
          <RefreshCw size={17} className={refreshing ? "animate-spin" : ""} aria-hidden="true" />
          {refreshing ? "Atualizando..." : "Atualizar"}
        </button>
      </div>

      {error && (
        <div role="alert" className="flex flex-col gap-3 rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-red-200 sm:flex-row sm:items-center sm:justify-between">
          <span className="flex items-center gap-2"><WifiOff aria-hidden="true" /> {error}</span>
          <button type="button" onClick={() => void loadOverview(true)} className="min-h-11 rounded-lg bg-red-500 px-4 font-bold text-white hover:bg-red-600">
            Tentar novamente
          </button>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
        {operationalCounters.map(({ label, value, icon: Icon, color }) => (
          <article key={label} className="rounded-xl border border-surface-03 bg-surface-02 p-3 shadow-soft">
            <div className={`mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-wide ${color}`}>
              <Icon size={15} aria-hidden="true" /> {label}
            </div>
            <strong className="text-3xl font-black text-cream">{value}</strong>
          </article>
        ))}
      </div>

      {!error && overview?.orders.length === 0 ? (
        <div className="flex min-h-64 flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-surface-03 bg-surface-02 p-8 text-center">
          <PackageCheck size={52} className="text-emerald-300" aria-hidden="true" />
          <h3 className="text-xl font-black text-cream">Operação em dia</h3>
          <p className="text-stone">Nenhum pedido ativo nas etapas do KDS.</p>
        </div>
      ) : (
        <div className="grid items-start gap-4 md:grid-cols-2 xl:grid-cols-5">
          {STAGES.map(({ key, title, empty, icon: Icon, accent }) => {
            const orders = groupedOrders[key];
            return (
              <section key={key} className="min-w-0 rounded-2xl border border-surface-03 bg-surface-02 p-3 shadow-soft">
                <header className="mb-3 flex items-center justify-between gap-2 border-b border-surface-03 pb-3">
                  <h3 className={`flex items-center gap-2 text-sm font-black ${accent}`}><Icon size={18} aria-hidden="true" /> {title}</h3>
                  <span className="rounded-full bg-surface-01 px-2.5 py-1 text-xs font-black text-cream">{orders.length}</span>
                </header>
                {orders.length === 0 ? (
                  <p className="rounded-xl border border-dashed border-surface-03 p-4 text-center text-sm text-stone">{empty}</p>
                ) : (
                  <div className="space-y-2">
                    {orders.map((order) => (
                      <article key={order.id} className="rounded-xl border border-surface-03 bg-surface-01 p-3">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <strong className="text-lg text-cream">#{(order.order_code || order.id.slice(0, 8)).toUpperCase()}</strong>
                            <p className="text-xs font-semibold text-stone">{order.fulfillment_type === "pickup" ? "Retirada" : "Entrega"}</p>
                          </div>
                          <span className="flex shrink-0 items-center gap-1 text-xs font-bold text-amber-300"><Clock3 size={13} aria-hidden="true" /> {elapsed(order.status_started_at)}</span>
                        </div>
                        {order.delivery?.driver_name && (
                          <p className="mt-3 flex items-center gap-1.5 border-t border-surface-03 pt-2 text-xs font-bold text-emerald-300">
                            <Bike size={14} aria-hidden="true" /> {order.delivery.driver_name}
                          </p>
                        )}
                      </article>
                    ))}
                  </div>
                )}
              </section>
            );
          })}
        </div>
      )}
    </section>
  );
}
