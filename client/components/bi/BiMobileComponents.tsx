import { useState, type ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  LabelList,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export const biMoney = (value?: number | null) =>
  value == null
    ? "Indisponível"
    : value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
export const biNumber = (value?: number | null) =>
  value == null
    ? "Indisponível"
    : value.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
export const biPercent = (value?: number | null) =>
  value == null
    ? "Sem base comparável"
    : `${value > 0 ? "+" : ""}${biNumber(value)}%`;
export function biDate(value?: string | null) {
  if (!value) return "Indisponível";
  return new Date(`${value.slice(0, 10)}T12:00:00`).toLocaleDateString("pt-BR");
}

export function BiPanel({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="min-w-0 rounded-xl border border-surface-03 bg-surface-02 p-3 sm:p-4">
      <h2 className="mb-3 text-sm font-bold text-cream">{title}</h2>
      {children}
    </section>
  );
}

export function BiMetrics({
  items,
}: {
  items: Array<{ label: string; value: string; helper?: string }>;
}) {
  return (
    <section
      aria-label="Indicadores"
      className="grid grid-cols-2 gap-2 sm:grid-cols-3"
    >
      {items.map((item) => (
        <div
          key={item.label}
          className="min-w-0 rounded-xl border border-surface-03 bg-surface-02 p-3"
        >
          <p className="text-[11px] font-semibold uppercase text-stone">
            {item.label}
          </p>
          <p className="mt-2 break-words text-lg font-black text-cream">
            {item.value}
          </p>
          {item.helper && (
            <p className="mt-1 text-[11px] text-stone">{item.helper}</p>
          )}
        </div>
      ))}
    </section>
  );
}

export function BiChoices<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: ReadonlyArray<{ key: NoInfer<T>; label: string }>;
  onChange: (key: T) => void;
}) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-1.5">
      {options.map((option) => (
        <button
          type="button"
          key={option.key}
          aria-pressed={value === option.key}
          onClick={() => onChange(option.key)}
          className={`min-h-10 rounded-lg border px-3 py-2 text-xs font-bold transition ${value === option.key ? "border-gold bg-gold/15 text-gold" : "border-surface-03 bg-surface-01 text-stone hover:text-cream"}`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export type BiChartPoint = {
  label: string;
  date?: string;
  previous_date?: string;
  revenue: number;
  orders: number;
  pizzas: number;
  previous_revenue?: number;
  previous_orders?: number;
  previous_pizzas?: number;
  comparison?: Record<string, { difference: number; percent: number | null }>;
};
const metricLabels = {
  revenue: "Receita confirmada",
  orders: "Pedidos pagos",
  pizzas: "Pizzas vendidas",
};

export function SalesTooltip({
  active,
  payload,
  metric,
}: {
  active?: boolean;
  payload?: Array<{ payload: BiChartPoint }>;
  metric: "revenue" | "orders" | "pizzas";
}) {
  const point = payload?.[0]?.payload;
  if (!active || !point) return null;
  const format = metric === "revenue" ? biMoney : biNumber;
  return (
    <div className="max-w-[260px] rounded-lg border border-surface-03 bg-surface-01 p-3 text-xs text-cream shadow-lg">
      <p className="mb-2 font-bold">
        {point.label}
        {point.date ? ` · ${biDate(point.date)}` : ""}
      </p>
      <p className="text-green-400">
        {metricLabels[metric]}: {format(point[metric])}
      </p>
      {point[`previous_${metric}`] != null && (
        <>
          <p className="mt-1 text-yellow-300">
            Anterior: {format(point[`previous_${metric}`])}
          </p>
          {point.previous_date && (
            <p className="text-stone">{biDate(point.previous_date)}</p>
          )}
        </>
      )}
      <p className="mt-2 text-stone">
        Pedidos: {biNumber(point.orders)} · Receita: {biMoney(point.revenue)}
      </p>
      {point.previous_orders != null && (
        <p className="mt-1 text-stone">
          Pedidos anteriores: {biNumber(point.previous_orders)} · Receita
          anterior: {biMoney(point.previous_revenue)}
        </p>
      )}
      {(
        [
          "orders",
          "revenue",
          ...(metric === "pizzas" ? ["pizzas"] : []),
        ] as const
      ).map((key) => {
        const change = point.comparison?.[key];
        if (!change) return null;
        return (
          <p key={key} className="mt-2 text-cream">
            Diferença de {metricLabels[key].toLowerCase()}:{" "}
            {key === "revenue"
              ? biMoney(change.difference)
              : biNumber(change.difference)}{" "}
            · {biPercent(change.percent)}
          </p>
        );
      })}
    </div>
  );
}

export function BiSalesChart({
  points,
  metric,
  compare = false,
  bars = false,
}: {
  points: BiChartPoint[];
  metric: "revenue" | "orders" | "pizzas";
  compare?: boolean;
  bars?: boolean;
}) {
  const [width, setWidth] = useState(0);
  if (!points.length)
    return (
      <p className="py-8 text-center text-sm text-stone">
        Nenhuma venda registrada no período consultado.
      </p>
    );
  const shared = (
    <>
      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
      <XAxis
        dataKey="label"
        tick={{ fill: "#a8a29e", fontSize: 10 }}
        minTickGap={28}
      />
      <YAxis
        width={48}
        tick={{ fill: "#a8a29e", fontSize: 10 }}
        tickFormatter={(value) =>
          metric === "revenue"
            ? new Intl.NumberFormat("pt-BR", { notation: "compact" }).format(
                value,
              )
            : String(value)
        }
      />
      <Tooltip content={<SalesTooltip metric={metric} />} />
      <Legend wrapperStyle={{ fontSize: 11 }} />
    </>
  );
  return (
    <div
      className="h-64 w-full min-w-0"
      role="img"
      aria-label={`Gráfico de ${metricLabels[metric]}${compare ? ", atual em verde e anterior em amarelo" : ""}`}
    >
      <ResponsiveContainer width="100%" height="100%" onResize={setWidth}>
        {bars ? (
          <BarChart
            data={points}
            margin={{ top: 12, right: 8, left: 0, bottom: 0 }}
          >
            {shared}
            <Bar
              isAnimationActive={false}
              dataKey={metric}
              name="Atual"
              fill="#22C55E"
              radius={[3, 3, 0, 0]}
            >
              {width > 600 && width / points.length > 55 && (
                <LabelList
                  dataKey={metric}
                  position="top"
                  fill="#d6d3d1"
                  fontSize={10}
                  formatter={(value: number) => biNumber(value)}
                />
              )}
            </Bar>
            {compare && (
              <Bar
                isAnimationActive={false}
                dataKey={`previous_${metric}`}
                name="Anterior"
                fill="#EAB308"
              />
            )}
          </BarChart>
        ) : (
          <LineChart
            data={points}
            margin={{ top: 12, right: 8, left: 0, bottom: 0 }}
          >
            {shared}
            <Line
              isAnimationActive={false}
              type="monotone"
              dataKey={metric}
              name="Atual"
              stroke="#22C55E"
              strokeWidth={2}
              dot={points.length < 32}
              activeDot={{ r: 6 }}
            >
              {width > 600 && width / points.length > 55 && (
                <LabelList
                  dataKey={metric}
                  position="top"
                  fill="#d6d3d1"
                  fontSize={10}
                  formatter={(value: number) => biNumber(value)}
                />
              )}
            </Line>
            {compare && (
              <Line
                isAnimationActive={false}
                type="monotone"
                dataKey={`previous_${metric}`}
                name="Anterior"
                stroke="#EAB308"
                strokeWidth={2}
                dot={false}
              />
            )}
          </LineChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
