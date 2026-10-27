import { useState } from "react";
import {
  AlertCircle,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Loader2,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import TelzLogo from "@/components/TelzLogo";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  BiChoices,
  BiMetrics,
  BiPanel,
  BiSalesChart,
  biDate,
  biMoney,
  biNumber,
  biPercent,
} from "@/components/bi/BiMobileComponents";
import { useBiMobileAnalytics } from "@/components/bi/useBiMobileAnalytics";
import {
  biApi,
  type ApiBIMobileAnalysis,
  type ApiBIMobileAnalytics,
  type ApiBIMobileFilters,
  type ApiBIMobileMonthly,
  type ApiBIMobilePeriod,
} from "@/lib/api";

type Tab = "orders" | "attendance" | "evolution" | "general";
const TABS: Array<{ key: Tab; label: string }> = [
  { key: "orders", label: "Pedidos" },
  { key: "attendance", label: "Atendimento" },
  { key: "evolution", label: "Evolução" },
  { key: "general", label: "Geral" },
];
const PERIODS: Array<{ key: ApiBIMobilePeriod; label: string }> = [
  { key: "today", label: "Hoje" },
  { key: "7d", label: "7 dias" },
  { key: "30d", label: "30 dias" },
  { key: "90d", label: "90 dias" },
  { key: "month", label: "Mês atual" },
];
const MONTHS: Array<{ key: ApiBIMobileMonthly; label: string }> = [
  { key: "6m", label: "6 meses" },
  { key: "12m", label: "12 meses" },
  { key: "year", label: "Ano atual" },
  { key: "previous_year", label: "Ano anterior" },
];
const STATUS_LABELS: Record<string, string> = {
  aguardando_pagamento: "Aguardando pagamento",
  pedido_confirmado: "Confirmado",
  em_preparacao: "Em preparação",
  pronto_para_entrega: "Pronto para entrega",
  em_entrega: "Em entrega",
  entregue: "Entregue",
  cancelado: "Cancelado",
  pending: "Pendente",
  confirmed: "Confirmado",
  preparing: "Em preparação",
  ready: "Pronto",
  ready_for_pickup: "Pronto para retirada",
  out_for_delivery: "Em entrega",
  delivered: "Concluído",
  cancelled: "Cancelado",
  completed: "Concluído",
};
const PAYMENT_LABELS: Record<string, string> = {
  pix: "Pix",
  credit_card: "Crédito",
  debit_card: "Débito",
  cash: "Dinheiro",
  money: "Dinheiro",
  card: "Cartão",
  other: "Outros",
};
const CHANNEL_LABELS: Record<string, string> = {
  own_store: "Loja própria",
  storefront: "Loja própria",
  ifood: "iFood",
  "99food": "99Food",
  keeta: "Keeta",
  delivery: "Delivery",
  dine_in: "Salão",
};
const inputClass =
  "min-h-10 min-w-0 rounded-lg border border-surface-03 bg-surface-01 px-3 text-sm text-cream outline-none focus:border-gold";

export function biToday() {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Sao_Paulo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  return `${parts.find((part) => part.type === "year")?.value}-${parts.find((part) => part.type === "month")?.value}-${parts.find((part) => part.type === "day")?.value}`;
}
function nextDate(value: string, offset: number) {
  const date = new Date(`${value}T12:00:00`);
  date.setDate(date.getDate() + offset);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
function metricItems(data: ApiBIMobileAnalytics) {
  const total = data.totals;
  return [
    { label: "Pedidos pagos", value: biNumber(total.valid_orders) },
    { label: "Pizzas vendidas", value: biNumber(total.pizzas) },
    { label: "Receita confirmada", value: biMoney(total.revenue) },
    {
      label: "Ticket médio",
      value: biMoney(total.average_ticket),
      helper: "Receita confirmada / pedidos pagos",
    },
  ];
}
function Comparison({ data }: { data: ApiBIMobileAnalytics }) {
  if (!data.previous_totals || !data.period.previous_date_from) return null;
  return (
    <BiPanel title="Comparação histórica">
      <p className="mb-3 text-xs text-stone">
        Atual: {biDate(data.period.date_from)} a {biDate(data.period.date_to)}
        <br />
        Anterior: {biDate(data.period.previous_date_from)} a{" "}
        {biDate(data.period.previous_date_to)}
        <br />
        {data.period.partial
          ? "Períodos parciais até o mesmo horário da operação."
          : data.period.date_to === biToday()
            ? "Janela atual em andamento; comparação anterior considera dias completos."
            : "Períodos completos."}
        {data.period.cutoff && (
          <>
            {" "}
            Horário de corte:{" "}
            {new Date(data.period.cutoff).toLocaleTimeString("pt-BR", {
              timeZone: data.period.timezone,
            })}
            .
          </>
        )}
        {data.period.comparison_rule && (
          <>
            <br />
            {data.period.comparison_rule}
          </>
        )}
      </p>
      <div className="space-y-3 text-xs">
        {[
          { key: "revenue", label: "Receita confirmada", format: biMoney },
          { key: "orders", label: "Pedidos pagos", format: biNumber },
          { key: "pizzas", label: "Pizzas vendidas", format: biNumber },
          { key: "average_ticket", label: "Ticket médio", format: biMoney },
        ].map((item) => {
          const comparison = data.comparison[item.key];
          const currentValue =
            item.key === "orders"
              ? data.totals.valid_orders
              : data.totals[item.key];
          const previousValue =
            item.key === "orders"
              ? data.previous_totals.valid_orders
              : data.previous_totals[item.key];
          return (
            <div key={item.key} className="rounded-lg bg-surface-01 p-3">
              <p className="font-bold text-cream">{item.label}</p>
              <p className="mt-1 text-stone">
                Atual {item.format(currentValue)} · Anterior{" "}
                {item.format(previousValue)}
              </p>
              {comparison && (
                <p
                  className={`mt-1 ${comparison.difference < 0 ? "text-red-300" : "text-green-400"}`}
                >
                  Diferença {item.format(comparison.difference)} ·{" "}
                  {biPercent(comparison.percent)}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </BiPanel>
  );
}
function Orders({ data }: { data: ApiBIMobileAnalytics }) {
  return (
    <>
      <BiMetrics
        items={[
          {
            label: "Pedidos do dia",
            value: biNumber(data.totals.orders),
            helper: "Todos os pedidos criados",
          },
          ...metricItems(data),
          {
            label: "Concluídos",
            value: biNumber(data.totals.completed_orders),
          },
          { label: "Em andamento", value: biNumber(data.totals.active_orders) },
          {
            label: "Cancelados",
            value: biNumber(data.totals.cancelled_orders),
            helper: biMoney(data.totals.cancelled_value),
          },
          {
            label: "Previsão de receita",
            value: biMoney(data.totals.forecast_revenue),
            helper: "Pedidos não cancelados",
          },
          {
            label: "Valor bruto vendido",
            value: biMoney(data.totals.gross_sales),
          },
          { label: "Descontos", value: biMoney(data.totals.discounts) },
        ]}
      />
      <BiPanel title="Status dos pedidos">
        {!data.totals.orders ? (
          <p className="text-sm text-stone">
            Nenhum pedido registrado na data selecionada.
          </p>
        ) : (
          <div className="space-y-2">
            {Object.entries(data.totals.status_counts).map(
              ([status, count]) => (
                <div
                  key={status}
                  className="flex justify-between gap-3 rounded-lg bg-surface-01 p-2 text-xs"
                >
                  <span className="text-stone">
                    {STATUS_LABELS[status] ?? status}
                  </span>
                  <strong>{biNumber(count)}</strong>
                </div>
              ),
            )}
          </div>
        )}
      </BiPanel>
      <Breakdown
        title="Formas de pagamento"
        rows={data.payments.map((item) => ({
          label: PAYMENT_LABELS[item.method] ?? item.method,
          orders: item.orders,
          revenue: item.revenue,
        }))}
      />
    </>
  );
}
function Breakdown({
  title,
  rows,
}: {
  title: string;
  rows: Array<{ label: string; orders: number; revenue: number }>;
}) {
  return (
    <BiPanel title={title}>
      {rows.length ? (
        <div className="space-y-2">
          {rows.map((item) => (
            <div
              key={item.label}
              className="flex items-center justify-between gap-3 rounded-lg bg-surface-01 p-3 text-xs"
            >
              <span className="min-w-0 break-words font-semibold">
                {item.label}
              </span>
              <div className="shrink-0 text-right">
                <p>{biMoney(item.revenue)}</p>
                <p className="text-stone">
                  {biNumber(item.orders)} pedidos pagos
                </p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-stone">
          Nenhum pagamento confirmado no período.
        </p>
      )}
    </BiPanel>
  );
}
function Attendance({ data }: { data: ApiBIMobileAnalytics }) {
  const a = data.attendance;
  const duration = a.avg_attendance_seconds;
  const ai =
    a.ai_status === "enabled"
      ? "Ativa"
      : a.ai_status === "disabled"
        ? "Inativa"
        : "Indisponível";
  return (
    <>
      <BiMetrics
        items={[
          {
            label: "Visitantes únicos",
            value: biNumber(a.unique_visitors),
            helper: "Na data selecionada",
          },
          {
            label: "Acessos / sessões",
            value: biNumber(a.accesses),
            helper: "Na data selecionada",
          },
          {
            label: "Visitantes online",
            value: biNumber(a.visitors_online),
            helper: "Agora · loja pública",
          },
          {
            label: "Clientes online",
            value: biNumber(a.customers_online),
            helper: "Agora · identificados",
          },
          {
            label: "Chatbot online",
            value: biNumber(a.chatbot),
            helper: "Conversas em andamento agora",
          },
          {
            label: "WhatsApp online",
            value: biNumber(a.whatsapp?.conversations_online),
            helper: "Conversas ativas agora",
          },
          {
            label: "Total de atendimentos",
            value: biNumber(a.total_attendances),
            helper: "Na data selecionada",
          },
          {
            label: "Atendimento médio",
            value:
              duration == null
                ? "Indisponível"
                : `${Math.floor(duration / 60)}m ${Math.floor(duration % 60)}s`,
          },
          {
            label: "IA ativa",
            value: ai,
            helper: "Disponibilidade configurada da IA",
          },
          {
            label: "Humano online",
            value: biNumber(a.human_operators),
            helper: "Disponibilidade operacional agora",
          },
          {
            label: "Atendimentos ativos",
            value: biNumber(a.whatsapp?.active_attendances),
            helper: "Agora · WhatsApp",
          },
          {
            label: "Aguardando resposta",
            value: biNumber(a.whatsapp?.waiting_response),
            helper: "Agora · WhatsApp",
          },
          {
            label: "Conversas finalizadas",
            value: biNumber(a.whatsapp?.finalized_today),
            helper: "Hoje · WhatsApp",
          },
          {
            label: "Resposta média",
            value:
              a.whatsapp?.avg_response_time_seconds == null
                ? "Indisponível"
                : `${Math.floor(a.whatsapp.avg_response_time_seconds / 60)}m ${Math.floor(a.whatsapp.avg_response_time_seconds % 60)}s`,
            helper: "Indicador operacional atual",
          },
        ]}
      />
      <BiPanel title="Critérios do atendimento">
        <p className="text-xs leading-relaxed text-stone">
          Visitantes e sessões consideram apenas páginas públicas de vendas.
          Indicadores online mostram a operação agora, inclusive ao consultar
          datas históricas.
        </p>
        {a.availability_note && (
          <p className="mt-3 text-xs text-yellow-200">{a.availability_note}</p>
        )}
      </BiPanel>
    </>
  );
}

export default function BiMobile() {
  const today = biToday();
  const [tab, setTab] = useState<Tab>("orders");
  const [date, setDate] = useState(today);
  const [evolutionOverride, setEvolutionDate] = useState<string | null>(null);
  const evolutionDate = evolutionOverride ?? date;
  const [evolutionPeriod, setEvolutionPeriod] =
    useState<ApiBIMobilePeriod>("today");
  const [generalPeriod, setGeneralPeriod] =
    useState<ApiBIMobilePeriod>("today");
  const [monthly, setMonthly] = useState<ApiBIMobileMonthly>("6m");
  const [grouping, setGrouping] = useState<"day" | "week">("day");
  const [compare, setCompare] = useState(true);
  const [partial, setPartial] = useState(true);
  const [evolutionMetric, setEvolutionMetric] = useState<"orders" | "revenue">(
    "orders",
  );
  const [generalMetric, setGeneralMetric] = useState<
    "orders" | "revenue" | "pizzas"
  >("revenue");
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [analysis, setAnalysis] = useState<ApiBIMobileAnalysis | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const filters: ApiBIMobileFilters = {
    date:
      tab === "evolution" ? evolutionDate : tab === "general" ? today : date,
    period:
      tab === "evolution"
        ? evolutionPeriod
        : tab === "general"
          ? generalPeriod
          : "today",
    compare:
      tab === "evolution"
        ? compare
          ? "previous_month"
          : "none"
        : tab === "general"
          ? generalPeriod === "month"
            ? "previous_month"
            : "previous_period"
          : "none",
    partial: tab === "evolution" ? partial : false,
    monthly: tab === "general" ? monthly : "6m",
    view: tab,
    grouping: tab === "general" && generalPeriod === "90d" ? grouping : "day",
  };
  const { data, loading, refreshing, error, refresh } =
    useBiMobileAnalytics(filters);
  async function analyze() {
    setAnalysisOpen(true);
    setAnalysisLoading(true);
    setAnalysisError(null);
    setAnalysis(null);
    try {
      setAnalysis(await biApi.mobileAnalyze(filters));
    } catch (err) {
      setAnalysisError(
        err instanceof Error
          ? err.message
          : "Não foi possível gerar a análise.",
      );
    } finally {
      setAnalysisLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-surface-01 px-2.5 py-3 text-cream">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-3 pb-8">
        <header className="rounded-xl border border-surface-03 bg-surface-02 p-3">
          <div className="flex items-center justify-between gap-3">
            <TelzLogo className="h-11 shrink-0 text-[32px] text-gold" />
            <div className="min-w-0 text-right">
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gold">
                Business Intelligence
              </p>
              <h1 className="mt-1 text-xl font-black">BI Mobile</h1>
              <p className="text-xs text-stone">Operação em tempo real</p>
            </div>
          </div>
        </header>
        <section className="rounded-xl border border-surface-03 bg-surface-02 p-3">
          <label
            htmlFor="bi-mobile-date"
            className="flex items-center gap-2 text-xs font-bold uppercase text-stone"
          >
            <CalendarDays size={16} className="text-gold" />
            Data de referência
          </label>
          <div className="mt-2 flex gap-2">
            <input
              id="bi-mobile-date"
              type="date"
              value={date}
              max={today}
              onChange={(event) => {
                if (event.target.value && event.target.value <= today)
                  setDate(event.target.value);
              }}
              className={`${inputClass} flex-1`}
            />
            <button
              type="button"
              onClick={() => void refresh()}
              disabled={loading || refreshing}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-surface-03 bg-surface-01 text-gold disabled:opacity-50"
              aria-label="Atualizar BI Mobile"
            >
              <RefreshCw
                size={17}
                className={refreshing ? "animate-spin" : ""}
              />
            </button>
          </div>
          <div
            role="tablist"
            aria-label="Visões do BI Mobile"
            className="mt-3 grid grid-cols-4 gap-1"
          >
            {TABS.map((item) => (
              <button
                type="button"
                key={item.key}
                id={`bi-tab-${item.key}`}
                role="tab"
                aria-selected={tab === item.key}
                aria-controls="bi-content"
                onClick={() => setTab(item.key)}
                className={`min-h-11 min-w-0 whitespace-nowrap rounded-lg px-0.5 text-[8px] font-bold uppercase min-[360px]:text-[9px] sm:text-xs ${tab === item.key ? "bg-gold/15 text-gold ring-1 ring-gold/50" : "text-stone hover:bg-surface-03"}`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </section>
        <div
          id="bi-content"
          role="tabpanel"
          aria-labelledby={`bi-tab-${tab}`}
          className="flex min-w-0 flex-col gap-3"
        >
          {tab === "evolution" && (
            <BiPanel title="Evolução por horário e histórico">
              <div className="flex items-center gap-2">
                <button
                  aria-label="Dia anterior"
                  type="button"
                  onClick={() => {
                    setEvolutionDate(nextDate(evolutionDate, -1));
                    setEvolutionPeriod("today");
                  }}
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-surface-03"
                >
                  <ChevronLeft size={18} />
                </button>
                <input
                  aria-label="Data da evolução"
                  type="date"
                  value={evolutionDate}
                  max={today}
                  onChange={(event) => {
                    if (event.target.value && event.target.value <= today) {
                      setEvolutionDate(event.target.value);
                      setEvolutionPeriod("today");
                    }
                  }}
                  className={`${inputClass} flex-1`}
                />
                <button
                  aria-label="Dia seguinte"
                  type="button"
                  disabled={evolutionDate >= today}
                  onClick={() => {
                    setEvolutionDate(nextDate(evolutionDate, 1));
                    setEvolutionPeriod("today");
                  }}
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-surface-03 disabled:opacity-30"
                >
                  <ChevronRight size={18} />
                </button>
              </div>
              <div className="mt-3">
                <BiChoices<ApiBIMobilePeriod>
                  label="Período da evolução"
                  value={evolutionPeriod}
                  options={PERIODS.filter((item) => item.key !== "90d").map(
                    (item) =>
                      item.key === "today"
                        ? { ...item, label: "Data selecionada" }
                        : item,
                  )}
                  onChange={setEvolutionPeriod}
                />
                {evolutionOverride && (
                  <button
                    type="button"
                    className="mt-3 min-h-10 text-xs text-gold underline"
                    onClick={() => setEvolutionDate(null)}
                  >
                    Usar data principal ({biDate(date)})
                  </button>
                )}
              </div>
              <label className="mt-4 flex min-h-10 items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={compare}
                  onChange={(event) => setCompare(event.target.checked)}
                  className="accent-green-500"
                />
                Comparar com mês anterior
              </label>
              {compare && (
                <label className="flex min-h-10 items-center gap-2 text-xs text-stone">
                  <input
                    type="checkbox"
                    checked={partial}
                    onChange={(event) => setPartial(event.target.checked)}
                  />
                  Comparar o dia atual até o mesmo horário
                </label>
              )}
            </BiPanel>
          )}
          {tab === "general" && (
            <BiPanel title="Período gerencial">
              <BiChoices<ApiBIMobilePeriod>
                label="Período geral"
                value={generalPeriod}
                options={PERIODS}
                onChange={setGeneralPeriod}
              />
              <p className="mt-3 text-xs text-stone">
                Períodos encerram hoje ({biDate(today)}). Os filtros desta aba
                são independentes da data principal.
              </p>
            </BiPanel>
          )}
          {loading ? (
            <div
              role="status"
              className="rounded-xl border border-surface-03 bg-surface-02 p-8 text-center text-sm text-stone"
            >
              <Loader2 className="mx-auto mb-3 animate-spin text-gold" />
              Carregando indicadores reais...
            </div>
          ) : (
            <>
              {error && (
                <div
                  role="alert"
                  className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-100"
                >
                  <p className="flex items-center gap-2 font-bold">
                    <AlertCircle size={18} />
                    Falha ao atualizar o BI
                  </p>
                  <p className="mt-2">{error}</p>
                  {data && (
                    <p className="mt-2">
                      Os dados abaixo correspondem à última atualização
                      concluída.
                    </p>
                  )}
                  <button
                    type="button"
                    onClick={() => void refresh()}
                    className="mt-3 rounded-lg border border-red-300/40 px-3 py-2"
                  >
                    Tentar novamente
                  </button>
                </div>
              )}
              {data && (
                <>
                  <p className="text-[11px] text-stone" role="status">
                    {refreshing ? "Atualizando... · " : ""}Última atualização:{" "}
                    {new Date(data.generated_at).toLocaleTimeString("pt-BR", {
                      timeZone: data.period.timezone || "America/Sao_Paulo",
                    })}{" "}
                    · {biDate(data.period.date_from)} a{" "}
                    {biDate(data.period.date_to)}
                  </p>
                  {data.history.status !== "available" && (
                    <p className="rounded-lg border border-surface-03 p-3 text-xs text-stone">
                      {data.history.status === "no_records" ||
                      data.history.status === "empty"
                        ? "Nenhuma venda registrada no histórico disponível. Dados não importados não fazem parte destes indicadores."
                        : `Histórico: ${data.history.status}. Somente registros persistidos são considerados.`}
                    </p>
                  )}
                  {tab === "orders" && <Orders data={data} />}
                  {tab === "attendance" && <Attendance data={data} />}
                  {tab === "evolution" && (
                    <>
                      <BiMetrics items={metricItems(data)} />
                      <BiPanel
                        title={
                          evolutionPeriod === "today"
                            ? "Evolução por horário"
                            : "Evolução diária"
                        }
                      >
                        <BiChoices<"orders" | "revenue">
                          label="Métrica da evolução"
                          value={evolutionMetric}
                          options={[
                            { key: "orders", label: "Pedidos" },
                            { key: "revenue", label: "Receita" },
                          ]}
                          onChange={setEvolutionMetric}
                        />
                        <div className="mt-4">
                          <BiSalesChart
                            points={data.sales}
                            metric={evolutionMetric}
                            compare={compare}
                          />
                        </div>
                      </BiPanel>
                      {compare && <Comparison data={data} />}
                    </>
                  )}
                  {tab === "general" && (
                    <>
                      <BiMetrics
                        items={[
                          ...metricItems(data),
                          {
                            label: "Média diária de receita",
                            value: biMoney(data.totals.daily_revenue),
                          },
                          {
                            label: "Média diária de pedidos",
                            value: biNumber(data.totals.daily_orders),
                          },
                          {
                            label: "Melhor dia",
                            value: data.totals.best_day
                              ? biDate(data.totals.best_day)
                              : "Sem vendas",
                          },
                          {
                            label: "Pedidos cancelados",
                            value: biNumber(data.totals.cancelled_orders),
                            helper: biMoney(data.totals.cancelled_value),
                          },
                          {
                            label: "Crescimento da receita",
                            value: biPercent(data.comparison.revenue?.percent),
                          },
                        ]}
                      />
                      <BiPanel title="Vendas do período">
                        {generalPeriod === "90d" && (
                          <div className="mb-3">
                            <BiChoices<"day" | "week">
                              label="Agrupamento das vendas"
                              value={grouping}
                              options={[
                                { key: "day", label: "Por dia" },
                                { key: "week", label: "Por semana" },
                              ]}
                              onChange={setGrouping}
                            />
                          </div>
                        )}
                        <BiChoices<"orders" | "revenue" | "pizzas">
                          label="Métrica de vendas"
                          value={generalMetric}
                          options={[
                            { key: "revenue", label: "Faturamento" },
                            { key: "orders", label: "Pedidos" },
                            { key: "pizzas", label: "Pizzas" },
                          ]}
                          onChange={setGeneralMetric}
                        />
                        <div className="mt-4">
                          <BiSalesChart
                            points={data.sales}
                            metric={generalMetric}
                            bars
                          />
                        </div>
                      </BiPanel>
                      <Comparison data={data} />
                      <BiPanel title="Evolução mensal">
                        <BiChoices<ApiBIMobileMonthly>
                          label="Histórico mensal"
                          value={monthly}
                          options={MONTHS}
                          onChange={setMonthly}
                        />
                        <div className="mt-4">
                          <BiSalesChart
                            points={data.monthly.map((item) => ({
                              label: item.month,
                              revenue: item.revenue,
                              orders: item.orders,
                              pizzas: item.pizzas,
                            }))}
                            metric="revenue"
                            bars
                          />
                        </div>
                        <div className="mt-3 overflow-x-auto">
                          <table className="w-full text-left text-xs">
                            <caption className="sr-only">
                              Detalhes reais de cada mês
                            </caption>
                            <thead>
                              <tr className="text-stone">
                                {[
                                  "Mês",
                                  "Receita",
                                  "Pedidos",
                                  "Pizzas",
                                  "Ticket",
                                  "Variação",
                                ].map((label) => (
                                  <th
                                    key={label}
                                    className="whitespace-nowrap p-2"
                                  >
                                    {label}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {data.monthly.map((item) => (
                                <tr
                                  key={item.month}
                                  className="border-t border-surface-03"
                                >
                                  <th
                                    scope="row"
                                    className="whitespace-nowrap p-2"
                                  >
                                    {item.month}
                                    {item.partial ? " (parcial)" : ""}
                                  </th>
                                  <td className="whitespace-nowrap p-2">
                                    {biMoney(item.revenue)}
                                  </td>
                                  <td className="p-2">
                                    {biNumber(item.orders)}
                                  </td>
                                  <td className="p-2">
                                    {biNumber(item.pizzas)}
                                  </td>
                                  <td className="whitespace-nowrap p-2">
                                    {biMoney(item.average_ticket)}
                                  </td>
                                  <td className="whitespace-nowrap p-2">
                                    {biPercent(item.growth_percent)}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </BiPanel>
                      <Breakdown
                        title="Receita por canal"
                        rows={data.channels.map((item) => ({
                          label: CHANNEL_LABELS[item.channel] ?? item.channel,
                          orders: item.orders,
                          revenue: item.revenue,
                        }))}
                      />
                      <button
                        type="button"
                        onClick={() => void analyze()}
                        disabled={analysisLoading || refreshing}
                        className="flex min-h-12 items-center justify-center gap-2 rounded-xl bg-gold px-4 py-3 text-sm font-black text-surface-01 disabled:opacity-60"
                      >
                        <Sparkles size={18} />
                        ANALISAR
                      </button>
                    </>
                  )}
                  <BiPanel title="Critérios dos indicadores">
                    <div className="space-y-2 text-[11px] leading-relaxed text-stone">
                      {data.definitions.map((definition, index) => (
                        <p key={index}>{definition}</p>
                      ))}
                      <p>
                        Fuso: {data.period.timezone}.{" "}
                        {data.period.day_basis === "calendar"
                          ? "Dia civil: 00h a 23h59, preservando o critério histórico"
                          : data.period.day_basis}
                        . Receita confirmada não representa saldo bancário ou
                        repasse líquido de marketplaces.
                      </p>
                      {data.history.first_order_at && (
                        <p>
                          Primeiro pedido disponível:{" "}
                          {biDate(data.history.first_order_at)}.
                        </p>
                      )}
                    </div>
                  </BiPanel>
                </>
              )}
            </>
          )}
        </div>
        <Dialog open={analysisOpen} onOpenChange={setAnalysisOpen}>
          <DialogContent className="border-surface-03 bg-surface-01 text-cream">
            <DialogHeader>
              <DialogTitle>Análise gerencial</DialogTitle>
              <DialogDescription className="text-stone">
                Resultados calculados a partir dos registros persistidos.
                Recomendações são sugestões para avaliação do gestor.
              </DialogDescription>
            </DialogHeader>
            {analysisLoading ? (
              <p role="status" className="flex items-center gap-2 py-6">
                <Loader2 className="animate-spin" />
                Analisando o período...
              </p>
            ) : analysisError ? (
              <p role="alert" className="text-red-300">
                {analysisError}
              </p>
            ) : (
              analysis && (
                <div className="space-y-4">
                  <div>
                    <h3 className="font-bold text-gold">Resumo executivo</h3>
                    <p className="mt-2 text-sm">{analysis.summary}</p>
                  </div>
                  {[
                    {
                      key: "facts",
                      title: "Fatos calculados · desempenho comercial",
                    },
                    {
                      key: "trends",
                      title: "Tendências · comparação histórica",
                    },
                    { key: "attention", title: "Pontos de atenção" },
                    {
                      key: "recommendations",
                      title: "Recomendações · oportunidades",
                    },
                  ].map((section) => (
                    <section key={section.key}>
                      <h3 className="text-sm font-bold text-gold">
                        {section.title}
                      </h3>
                      <ul className="mt-2 list-disc space-y-2 pl-5 text-sm text-stone">
                        {analysis[section.key]?.map(
                          (text: string, index: number) => (
                            <li key={index}>{text}</li>
                          ),
                        )}
                      </ul>
                    </section>
                  ))}
                  <p className="text-xs text-stone">
                    {analysis.ai_note ??
                      "Motor de análise: regras calculadas e verificáveis."}
                  </p>
                </div>
              )
            )}
          </DialogContent>
        </Dialog>
      </div>
    </main>
  );
}
