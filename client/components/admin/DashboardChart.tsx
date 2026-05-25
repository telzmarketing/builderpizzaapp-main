import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

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

export default function DashboardChart(props: DashboardChartProps) {
  if (props.variant === "pie") {
    return (
      <PieChart width={110} height={110}>
        <Pie
          data={props.data}
          cx={50}
          cy={50}
          innerRadius={32}
          outerRadius={50}
          dataKey="value"
          strokeWidth={0}
        >
          {props.data.map((_, i) => (
            <Cell key={i} fill={props.colors[i % props.colors.length]} />
          ))}
        </Pie>
      </PieChart>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={props.data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="colorReceita" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#f97316" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#2d3d56" vertical={false} />
        <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis
          tick={{ fill: "#94a3b8", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={50}
          tickFormatter={(v) => `R$${(Number(v) / 1000).toFixed(0)}k`}
        />
        <Tooltip
          contentStyle={{ background: "#1e2a3b", border: "1px solid #2d3d56", borderRadius: "8px", color: "#f8fafc" }}
          labelStyle={{ color: "#94a3b8", fontSize: "11px" }}
          formatter={(v) => [`R$${Number(v).toFixed(2)}`, "Receita"]}
        />
        <Area
          type="monotone"
          dataKey="receita"
          stroke="#f97316"
          strokeWidth={2}
          fill="url(#colorReceita)"
          dot={{ fill: "#f97316", r: 3 }}
          activeDot={{ r: 5 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
