type PieDatum = {
  name: string;
  value: number;
};

type RevenueDatum = {
  name: string;
  receita: number;
};

type DashboardChartProps =
  | {
      variant: "pie";
      data: PieDatum[];
      colors: string[];
    }
  | {
      variant: "revenue";
      data: RevenueDatum[];
    };

const money = (value: number) =>
  value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export default function DashboardChart(props: DashboardChartProps) {
  if (props.variant === "pie") {
    return <RevenueRing data={props.data} colors={props.colors} />;
  }

  return <RevenueArea data={props.data} />;
}

function RevenueRing({ data, colors }: { data: PieDatum[]; colors: string[] }) {
  const total = data.reduce((sum, item) => sum + Math.max(item.value, 0), 0);
  const radius = 41;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <svg width="110" height="110" viewBox="0 0 110 110" role="img" aria-label="Distribuicao de receita">
      <circle cx="55" cy="55" r={radius} fill="none" stroke="#2d3d56" strokeWidth="18" />
      {total > 0 &&
        data.map((item, index) => {
          const ratio = Math.max(item.value, 0) / total;
          const dash = ratio * circumference;
          const segment = (
            <circle
              key={item.name}
              cx="55"
              cy="55"
              r={radius}
              fill="none"
              stroke={colors[index % colors.length]}
              strokeWidth="18"
              strokeDasharray={`${dash} ${circumference - dash}`}
              strokeDashoffset={-offset}
              transform="rotate(-90 55 55)"
            >
              <title>{`${item.name}: ${money(item.value)}`}</title>
            </circle>
          );
          offset += dash;
          return segment;
        })}
      <circle cx="55" cy="55" r="28" fill="#172033" />
    </svg>
  );
}

function RevenueArea({ data }: { data: RevenueDatum[] }) {
  const width = 1000;
  const height = 160;
  const values = data.map((item) => Math.max(item.receita, 0));
  const maxValue = niceMax(Math.max(...values, 0));
  const baselineY = height;

  const points = data.map((item, index) => {
    const x = data.length <= 1 ? width / 2 : (width / (data.length - 1)) * index;
    const y = baselineY - (Math.max(item.receita, 0) / maxValue) * height;
    const left = data.length <= 1 ? 50 : (index / (data.length - 1)) * 100;
    const top = (y / height) * 100;
    return { ...item, x, y, left, top };
  });

  const linePath = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
  const areaPath = points.length
    ? `${linePath} L ${points[points.length - 1].x} ${baselineY} L ${points[0].x} ${baselineY} Z`
    : "";
  const gridValues = [maxValue, maxValue / 2, 0];

  return (
    <div className="h-[200px] w-full">
      <div className="grid h-full grid-cols-[4.5rem_minmax(0,1fr)] grid-rows-[1fr_1.75rem]">
        <div className="relative col-start-1 row-start-1 text-[11px] text-stone">
          {gridValues.map((value) => (
            <span
              key={value}
              className="absolute right-3 -translate-y-1/2 whitespace-nowrap tabular-nums"
              style={{ top: `${100 - (value / maxValue) * 100}%` }}
            >
              {formatAxisMoney(value)}
            </span>
          ))}
        </div>

        <div className="relative col-start-2 row-start-1 min-w-0">
          <svg
            className="absolute inset-0 h-full w-full overflow-visible"
            viewBox={`0 0 ${width} ${height}`}
            role="img"
            aria-label="Receita efetivada nos ultimos 7 dias"
            preserveAspectRatio="none"
          >
            <defs>
              <linearGradient id="dashboardRevenueFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#f97316" stopOpacity="0.3" />
                <stop offset="100%" stopColor="#f97316" stopOpacity="0" />
              </linearGradient>
            </defs>

            {gridValues.map((value) => {
              const y = baselineY - (value / maxValue) * height;
              return (
                <line key={value} x1="0" x2={width} y1={y} y2={y} stroke="#2d3d56" strokeDasharray="3 3" />
              );
            })}

            {areaPath && <path d={areaPath} fill="url(#dashboardRevenueFill)" />}
            {linePath && <path d={linePath} fill="none" stroke="#f97316" strokeWidth="2" vectorEffect="non-scaling-stroke" />}
          </svg>

          {points.map((point) => (
            <span
              key={point.name}
              className="absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface-02 bg-gold shadow-sm"
              style={{ left: `${point.left}%`, top: `${point.top}%` }}
              title={`${point.name}: ${money(point.receita)}`}
            />
          ))}
        </div>

        <div className="col-start-2 row-start-2 grid min-w-0 items-end text-center text-[11px] text-stone" style={{ gridTemplateColumns: `repeat(${Math.max(data.length, 1)}, minmax(0, 1fr))` }}>
          {data.map((point) => (
            <span key={point.name} className="truncate px-1">
              {point.name}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function niceMax(value: number) {
  if (value <= 0) return 100;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const normalized = value / magnitude;
  const niceNormalized = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return niceNormalized * magnitude;
}

function formatAxisMoney(value: number) {
  if (value >= 1000) {
    return `R$ ${(value / 1000).toLocaleString("pt-BR", { maximumFractionDigits: value >= 10000 ? 0 : 1 })} mil`;
  }
  return `R$ ${Math.round(value).toLocaleString("pt-BR")}`;
}
