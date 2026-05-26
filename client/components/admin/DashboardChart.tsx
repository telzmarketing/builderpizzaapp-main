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
  const width = 640;
  const height = 200;
  const padding = { top: 10, right: 12, bottom: 28, left: 52 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const values = data.map((item) => Math.max(item.receita, 0));
  const maxValue = Math.max(...values, 1);
  const baselineY = padding.top + chartHeight;

  const points = data.map((item, index) => {
    const x =
      padding.left +
      (data.length <= 1 ? chartWidth / 2 : (chartWidth / (data.length - 1)) * index);
    const y = baselineY - (Math.max(item.receita, 0) / maxValue) * chartHeight;
    return { ...item, x, y };
  });

  const linePath = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
  const areaPath = points.length
    ? `${linePath} L ${points[points.length - 1].x} ${baselineY} L ${points[0].x} ${baselineY} Z`
    : "";
  const gridValues = [maxValue, maxValue / 2, 0];

  return (
    <div className="h-[200px] w-full">
      <svg className="h-full w-full overflow-visible" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Receita efetivada nos ultimos 7 dias" preserveAspectRatio="none">
        <defs>
          <linearGradient id="dashboardRevenueFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#f97316" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#f97316" stopOpacity="0" />
          </linearGradient>
        </defs>

        {gridValues.map((value) => {
          const y = baselineY - (value / maxValue) * chartHeight;
          return (
            <g key={value}>
              <line x1={padding.left} x2={width - padding.right} y1={y} y2={y} stroke="#2d3d56" strokeDasharray="3 3" />
              <text x={padding.left - 10} y={y + 4} textAnchor="end" fill="#94a3b8" fontSize="11">
                {value >= 1000 ? `R$${(value / 1000).toFixed(0)}k` : `R$${Math.round(value)}`}
              </text>
            </g>
          );
        })}

        {areaPath && <path d={areaPath} fill="url(#dashboardRevenueFill)" />}
        {linePath && <path d={linePath} fill="none" stroke="#f97316" strokeWidth="2" vectorEffect="non-scaling-stroke" />}

        {points.map((point) => (
          <g key={point.name}>
            <circle cx={point.x} cy={point.y} r="3" fill="#f97316" vectorEffect="non-scaling-stroke">
              <title>{`${point.name}: ${money(point.receita)}`}</title>
            </circle>
            <text x={point.x} y={height - 8} textAnchor="middle" fill="#94a3b8" fontSize="11">
              {point.name}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
