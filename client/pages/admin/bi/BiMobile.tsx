import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ElementType,
} from "react";
import {
  AlertCircle,
  CalendarDays,
  CheckCircle2,
  Clock3,
  DollarSign,
  Loader2,
  PackageCheck,
  RefreshCw,
  ShoppingBag,
  Truck,
  Users,
} from "lucide-react";
import { biApi, type ApiBIMobile, type ApiBIMobileStatusKey } from "@/lib/api";

type MetricCard = {
  label: string;
  value: string;
  helper?: string;
  icon: ElementType;
};

const STATUS_ITEMS: Array<{
  key: ApiBIMobileStatusKey;
  label: string;
  icon: ElementType;
}> = [
  { key: "aguardando_pagamento", label: "Aguardando pagamento", icon: Clock3 },
  { key: "pedido_confirmado", label: "Pedido confirmado", icon: CheckCircle2 },
  { key: "em_preparacao", label: "Em preparacao", icon: PackageCheck },
  {
    key: "pronto_para_entrega",
    label: "Pronto para entrega",
    icon: ShoppingBag,
  },
  { key: "em_entrega", label: "Em entrega", icon: Truck },
  { key: "entregue", label: "Entregue", icon: CheckCircle2 },
  { key: "cancelado", label: "Cancelado", icon: AlertCircle },
];

function todayInputValue() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 10);
}

function money(value: number) {
  return (value ?? 0).toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

function number(value: number) {
  return (value ?? 0).toLocaleString("pt-BR");
}

function MetricCard({ item }: { item: MetricCard }) {
  const Icon = item.icon;
  return (
    <div className="min-h-[104px] rounded-lg border border-surface-03 bg-surface-02 p-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-bold uppercase leading-snug text-stone">
          {item.label}
        </p>
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gold/10 text-gold">
          <Icon size={16} />
        </span>
      </div>
      <p className="mt-3 break-words text-xl font-black leading-tight text-cream">
        {item.value}
      </p>
      {item.helper && (
        <p className="mt-1 text-[11px] leading-snug text-stone">
          {item.helper}
        </p>
      )}
    </div>
  );
}

function LoadingBlock() {
  return (
    <div className="rounded-lg border border-surface-03 bg-surface-02 p-6 text-center text-sm text-stone">
      <Loader2 className="mx-auto mb-3 h-5 w-5 animate-spin text-gold" />
      Carregando resumo do dia...
    </div>
  );
}

export default function BiMobile() {
  const [selectedDate, setSelectedDate] = useState(todayInputValue);
  const [data, setData] = useState<ApiBIMobile | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(
    async (mode: "initial" | "refresh" = "initial") => {
      if (mode === "refresh") {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);
      try {
        const response = await biApi.mobile(selectedDate);
        setData(response);
      } catch (err) {
        console.error("Erro ao carregar BI Mobile", err);
        setError("Nao foi possivel carregar o BI Mobile.");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [selectedDate],
  );

  useEffect(() => {
    loadData();
  }, [loadData]);

  const metrics = useMemo<MetricCard[]>(() => {
    const current = data;
    return [
      {
        label: "Acessos do dia",
        value: number(current?.visitorsToday ?? 0),
        helper: "Visitantes unicos",
        icon: Users,
      },
      {
        label: "Visitantes online",
        value: number(current?.visitorsOnline ?? 0),
        helper: "Agora",
        icon: Users,
      },
      {
        label: "Clientes online",
        value: number(current?.customersOnline ?? 0),
        helper: "Cadastrados",
        icon: Users,
      },
      {
        label: "Previsao do dia",
        value: money(current?.forecastRevenue ?? 0),
        helper: "Pedidos nao cancelados",
        icon: DollarSign,
      },
      {
        label: "Faturamento efetivado",
        value: money(current?.confirmedRevenue ?? 0),
        helper: "Pagamentos confirmados",
        icon: DollarSign,
      },
      {
        label: "Pedidos do dia",
        value: number(current?.ordersToday ?? 0),
        helper: "Criados na data",
        icon: ShoppingBag,
      },
      {
        label: "Pedidos efetivados",
        value: number(current?.confirmedOrders ?? 0),
        helper: "Confirmados ou em fluxo",
        icon: CheckCircle2,
      },
    ];
  }, [data]);

  const maxStatusCount = Math.max(
    ...STATUS_ITEMS.map((item) => data?.ordersByStatus[item.key] ?? 0),
    1,
  );
  const hasOrders = (data?.ordersToday ?? 0) > 0;

  return (
    <main className="min-h-screen bg-surface-01 px-3 py-4 text-cream">
      <div className="mx-auto flex w-full max-w-md flex-col gap-4 pb-6">
        <header className="rounded-lg border border-surface-03 bg-surface-02 p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.22em] text-gold">
            Business Intelligence
          </p>
          <h1 className="mt-2 text-2xl font-black leading-tight text-cream">
            BI Mobile
          </h1>
          <p className="mt-1 text-sm leading-snug text-stone">
            Resumo operacional do dia
          </p>
        </header>

        <section className="rounded-lg border border-surface-03 bg-surface-02 p-3">
          <div className="flex items-center gap-2">
            <CalendarDays size={16} className="text-gold" />
            <label
              className="text-xs font-bold uppercase text-stone"
              htmlFor="bi-mobile-date"
            >
              Data
            </label>
          </div>
          <div className="mt-3 flex gap-2">
            <input
              id="bi-mobile-date"
              type="date"
              value={selectedDate}
              onChange={(event) =>
                setSelectedDate(event.target.value || todayInputValue())
              }
              className="min-h-11 flex-1 rounded-lg border border-surface-03 bg-surface-01 px-3 text-sm font-semibold text-cream outline-none focus:border-gold"
            />
            <button
              type="button"
              onClick={() => loadData("refresh")}
              disabled={loading || refreshing}
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-surface-03 bg-surface-01 text-gold transition hover:border-gold/60 disabled:cursor-not-allowed disabled:opacity-60"
              aria-label="Atualizar BI Mobile"
              title="Atualizar"
            >
              <RefreshCw
                size={17}
                className={refreshing ? "animate-spin" : ""}
              />
            </button>
          </div>
        </section>

        {loading ? (
          <LoadingBlock />
        ) : error ? (
          <section className="rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-100">
            <div className="flex items-start gap-2">
              <AlertCircle size={18} className="mt-0.5 shrink-0" />
              <div>
                <p className="font-bold">Erro ao carregar dados</p>
                <p className="mt-1 text-red-100/80">{error}</p>
              </div>
            </div>
          </section>
        ) : (
          <>
            <section className="grid grid-cols-2 gap-2">
              {metrics.map((item) => (
                <MetricCard key={item.label} item={item} />
              ))}
            </section>

            <section className="rounded-lg border border-surface-03 bg-surface-02 p-3">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-sm font-black text-cream">
                  Status dos pedidos
                </h2>
                <span className="rounded-full bg-gold/10 px-2 py-1 text-[11px] font-bold text-gold">
                  {number(data?.ordersToday ?? 0)}
                </span>
              </div>

              {!hasOrders ? (
                <div className="mt-3 rounded-lg border border-dashed border-surface-03 bg-surface-01 p-4 text-center text-xs text-stone">
                  Nenhum pedido no dia selecionado.
                </div>
              ) : (
                <div className="mt-3 space-y-2">
                  {STATUS_ITEMS.map((item) => {
                    const Icon = item.icon;
                    const total = data?.ordersByStatus[item.key] ?? 0;
                    const width = `${Math.max((total / maxStatusCount) * 100, total > 0 ? 8 : 0)}%`;
                    return (
                      <div
                        key={item.key}
                        className="rounded-lg border border-surface-03 bg-surface-01 p-2.5"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex min-w-0 items-center gap-2">
                            <Icon size={15} className="shrink-0 text-gold" />
                            <span className="truncate text-xs font-semibold text-cream">
                              {item.label}
                            </span>
                          </div>
                          <span className="text-sm font-black text-cream">
                            {number(total)}
                          </span>
                        </div>
                        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-03">
                          <div
                            className="h-full rounded-full bg-gold"
                            style={{ width }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </main>
  );
}
