import { useEffect, useMemo, useState, type ElementType, type FormEvent, type ReactNode } from "react";
import {
  BarChart3,
  CalendarDays,
  CheckCircle2,
  DollarSign,
  Filter,
  Link2,
  Loader2,
  Megaphone,
  Package,
  PauseCircle,
  Plus,
  Percent,
  RefreshCw,
  Save,
  ShoppingBag,
  Tag,
  Target,
  TrendingUp,
  Trash2,
  Users,
} from "lucide-react";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import {
  AdminPageContent,
  AdminPageHeader,
  AdminPageShell,
  AdminPageTabs,
} from "@/components/admin/AdminPageChrome";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import {
  marketingIntelligenceApi,
  type ApiMarketingGoal,
  type ApiMarketingGoalInput,
  type ApiMarketingGoalMetricKey,
  type ApiMarketingGoalStatus,
  type ApiMarketingIntelligenceCampaign,
  type ApiMarketingIntelligenceChannel,
  type ApiMarketingIntelligenceDashboard,
  type ApiMarketingIntelligenceFunnelStep,
  type ApiMarketingIntelligencePeriod,
  type ApiMarketingIntelligenceProduct,
  type ApiMarketingIntelligencePromotion,
  type ApiMarketingTimelineEvent,
  type ApiMarketingTimelineEventInput,
} from "@/lib/api";

type Tab = "overview" | "campaigns" | "products" | "goals" | "timeline";

const PERIODS: Array<{ key: ApiMarketingIntelligencePeriod; label: string }> = [
  { key: "today", label: "Hoje" },
  { key: "7d", label: "7 dias" },
  { key: "30d", label: "30 dias" },
  { key: "90d", label: "90 dias" },
  { key: "month", label: "Mes atual" },
  { key: "previous_month", label: "Mes anterior" },
];

const TABS: Array<{ id: Tab; label: string; icon: ElementType }> = [
  { id: "overview", label: "Resumo", icon: BarChart3 },
  { id: "campaigns", label: "Campanhas e canais", icon: Megaphone },
  { id: "products", label: "Produtos e promocoes", icon: Package },
  { id: "goals", label: "Metas", icon: Target },
  { id: "timeline", label: "Timeline", icon: CalendarDays },
];

const KPI_KEYS = [
  "revenue",
  "spend",
  "roas",
  "roi",
  "cac",
  "cpa",
  "cpl",
  "average_ticket",
  "orders",
] as const;

const KPI_META: Record<string, { label: string; icon: ElementType; tone: string }> = {
  revenue: { label: "Receita", icon: DollarSign, tone: "text-green-300 bg-green-500/10" },
  spend: { label: "Investimento", icon: TrendingUp, tone: "text-red-300 bg-red-500/10" },
  roas: { label: "ROAS", icon: BarChart3, tone: "text-gold bg-gold/10" },
  roi: { label: "ROI", icon: Percent, tone: "text-emerald-300 bg-emerald-500/10" },
  cac: { label: "CAC", icon: Users, tone: "text-orange-300 bg-orange-500/10" },
  cpa: { label: "CPA", icon: Target, tone: "text-blue-300 bg-blue-500/10" },
  cpl: { label: "CPL", icon: Filter, tone: "text-cyan-300 bg-cyan-500/10" },
  average_ticket: { label: "Ticket medio", icon: ShoppingBag, tone: "text-purple-300 bg-purple-500/10" },
  orders: { label: "Pedidos pagos", icon: ShoppingBag, tone: "text-cream bg-surface-03" },
};

const channelChartConfig = {
  revenue: {
    label: "Receita",
    color: "#c7a45d",
  },
  spend: {
    label: "Investimento",
    color: "#ef4444",
  },
} satisfies ChartConfig;

const GOAL_METRICS: Array<{ key: ApiMarketingGoalMetricKey; label: string; direction: "increase" | "decrease" }> = [
  { key: "revenue", label: "Receita", direction: "increase" },
  { key: "paid_orders", label: "Pedidos pagos", direction: "increase" },
  { key: "leads", label: "Leads", direction: "increase" },
  { key: "conversions", label: "Conversoes", direction: "increase" },
  { key: "roas", label: "ROAS", direction: "increase" },
  { key: "roi", label: "ROI", direction: "increase" },
  { key: "cac", label: "CAC", direction: "decrease" },
  { key: "cpa", label: "CPA", direction: "decrease" },
  { key: "cpl", label: "CPL", direction: "decrease" },
  { key: "average_ticket", label: "Ticket medio", direction: "increase" },
];

const GOAL_STATUS_LABELS: Record<ApiMarketingGoalStatus, string> = {
  active: "Ativa",
  paused: "Pausada",
  completed: "Concluida",
  cancelled: "Cancelada",
};

const PRIORITY_LABELS = {
  low: "Baixa",
  medium: "Media",
  high: "Alta",
} as const;

const EVENT_TYPES = [
  { value: "campaign_created", label: "Campanha criada" },
  { value: "campaign_paused", label: "Campanha pausada" },
  { value: "campaign_ended", label: "Campanha encerrada" },
  { value: "promotion_started", label: "Promocao iniciada" },
  { value: "promotion_ended", label: "Promocao encerrada" },
  { value: "coupon_created", label: "Cupom criado" },
  { value: "coupon_expired", label: "Cupom expirado" },
  { value: "goal_reached", label: "Meta atingida" },
  { value: "goal_closed", label: "Meta encerrada" },
  { value: "budget_changed", label: "Orcamento alterado" },
  { value: "creative_changed", label: "Troca de criativo" },
  { value: "strategy_changed", label: "Mudanca de estrategia" },
  { value: "audience_changed", label: "Alteracao de publico" },
  { value: "ab_test", label: "Teste A/B" },
  { value: "landing_page_launched", label: "Landing page lancada" },
  { value: "important_meeting", label: "Reuniao importante" },
  { value: "strategic_note", label: "Observacao estrategica" },
  { value: "manual_event", label: "Evento manual" },
  { value: "free_event", label: "Evento livre" },
];

const EVENT_CATEGORIES = [
  "meta_ads",
  "google_ads",
  "whatsapp",
  "site",
  "produto",
  "promocao",
  "cupom",
  "financeiro",
  "estrategia",
  "operacional",
];

function todayInputDate() {
  return new Date().toISOString().slice(0, 10);
}

function nowInputDateTime() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 16);
}

function money(value: number | null | undefined) {
  return (value ?? 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function number(value: number | null | undefined) {
  return (value ?? 0).toLocaleString("pt-BR");
}

function ratio(value: number | null | undefined) {
  return `${(value ?? 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}x`;
}

function pctFromRatio(value: number | null | undefined) {
  return `${((value ?? 0) * 100).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

function pctValue(value: number | null | undefined) {
  return `${(value ?? 0).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

function formatKpi(key: string, value: number, unit: string) {
  if (key === "roas") return ratio(value);
  if (key === "roi") return pctFromRatio(value);
  if (unit === "currency") return money(value);
  if (unit === "percent") return pctValue(value);
  return number(value);
}

function platformLabel(value: string | null | undefined) {
  if (!value) return "Nao atribuido";
  const labels: Record<string, string> = {
    facebook: "Facebook",
    google: "Google",
    instagram: "Instagram",
    meta: "Meta Ads",
    tiktok: "TikTok",
    whatsapp: "WhatsApp",
    organic: "Organico",
    direct: "Direto",
    manual: "Manual",
  };
  return labels[value] ?? value;
}

function sourceTypeLabel(value: string | null | undefined) {
  if (!value) return "Fonte";
  const labels: Record<string, string> = {
    traffic: "Trafego",
    traffic_campaign: "Trafego",
    promotion: "Promocao",
    promotion_campaign: "Promocao",
  };
  return labels[value] ?? value;
}

function EmptyState({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-lg border border-dashed border-surface-03 bg-surface-02/60 p-6 text-center">
      <p className="text-sm font-bold text-cream">{title}</p>
      <p className="mt-1 text-sm text-stone">{text}</p>
    </div>
  );
}

type GoalForm = {
  title: string;
  description: string;
  metric_key: ApiMarketingGoalMetricKey;
  target_value: string;
  baseline_value: string;
  comparison_direction: "increase" | "decrease";
  period_start: string;
  period_end: string;
  status: ApiMarketingGoalStatus;
  priority: "low" | "medium" | "high";
  campaign_id: string;
  traffic_campaign_id: string;
  coupon_id: string;
  promotion_id: string;
  product_id: string;
  channel: string;
  notes: string;
};

type TimelineForm = {
  title: string;
  description: string;
  event_type: string;
  event_date: string;
  impact_level: "low" | "medium" | "high";
  category: string;
  tags: string;
  attachment_url: string;
  attachment_type: "url" | "image" | "document" | "other";
  goal_id: string;
  campaign_id: string;
  traffic_campaign_id: string;
  coupon_id: string;
  promotion_id: string;
  product_id: string;
};

function emptyGoalForm(): GoalForm {
  const today = todayInputDate();
  return {
    title: "",
    description: "",
    metric_key: "revenue",
    target_value: "",
    baseline_value: "",
    comparison_direction: "increase",
    period_start: today,
    period_end: today,
    status: "active",
    priority: "medium",
    campaign_id: "",
    traffic_campaign_id: "",
    coupon_id: "",
    promotion_id: "",
    product_id: "",
    channel: "",
    notes: "",
  };
}

function emptyTimelineForm(): TimelineForm {
  return {
    title: "",
    description: "",
    event_type: "manual_event",
    event_date: nowInputDateTime(),
    impact_level: "medium",
    category: "estrategia",
    tags: "",
    attachment_url: "",
    attachment_type: "url",
    goal_id: "",
    campaign_id: "",
    traffic_campaign_id: "",
    coupon_id: "",
    promotion_id: "",
    product_id: "",
  };
}

function Section({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-bold text-cream">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function KpiCard({
  item,
}: {
  item: { key: string; label: string; value: number; unit: string; helper?: string | null };
}) {
  const meta = KPI_META[item.key] ?? { label: item.label, icon: BarChart3, tone: "text-gold bg-gold/10" };
  const Icon = meta.icon;

  return (
    <Card className="border-surface-03 bg-surface-02 text-cream">
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase text-stone">{meta.label}</p>
            <p className="mt-2 text-2xl font-black leading-tight">{formatKpi(item.key, item.value, item.unit)}</p>
          </div>
          <span className={`rounded-lg p-2 ${meta.tone}`}>
            <Icon size={18} />
          </span>
        </div>
        {item.helper && <p className="mt-3 line-clamp-2 text-xs text-stone">{item.helper}</p>}
      </CardContent>
    </Card>
  );
}

function FunnelCard({ items }: { items: ApiMarketingIntelligenceFunnelStep[] }) {
  const max = Math.max(...items.map((item) => item.value), 1);

  return (
    <Card className="border-surface-03 bg-surface-02 text-cream">
      <CardHeader className="p-4 pb-0">
        <CardTitle className="text-base">Funil de conversao</CardTitle>
      </CardHeader>
      <CardContent className="p-4">
        {items.length ? (
          <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
            {items.map((item) => (
              <div key={item.key} className="rounded-lg border border-surface-03 bg-surface-01 p-3">
                <div className="flex h-24 items-end overflow-hidden rounded-md bg-surface-03">
                  <div
                    className="w-full rounded-t-md bg-gold"
                    style={{ height: `${Math.max((item.value / max) * 100, item.value ? 4 : 0)}%` }}
                  />
                </div>
                <p className="mt-3 text-lg font-black text-cream">{number(item.value)}</p>
                <p className="text-xs font-semibold text-stone">{item.label}</p>
                <p className="mt-1 text-[11px] text-gold">{pctValue(item.previous_conversion_pct)} da etapa anterior</p>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title="Sem eventos de funil" text="Os dados aparecem quando houver tracking, carrinho, checkout e pedidos no periodo." />
        )}
      </CardContent>
    </Card>
  );
}

function ChannelChart({ channels }: { channels: ApiMarketingIntelligenceChannel[] }) {
  const chartData = channels.slice(0, 8).map((item) => ({
    name: item.label || item.channel,
    revenue: item.revenue,
    spend: item.spend,
  }));

  return (
    <Card className="border-surface-03 bg-surface-02 text-cream">
      <CardHeader className="p-4 pb-0">
        <CardTitle className="text-base">Receita e investimento por canal</CardTitle>
      </CardHeader>
      <CardContent className="p-4">
        {chartData.length ? (
          <ChartContainer config={channelChartConfig} className="h-[280px] w-full aspect-auto">
            <BarChart data={chartData} margin={{ left: 6, right: 12, top: 12, bottom: 0 }}>
              <CartesianGrid vertical={false} strokeDasharray="3 3" />
              <XAxis dataKey="name" tickLine={false} axisLine={false} tickMargin={8} />
              <YAxis tickLine={false} axisLine={false} tickFormatter={(value) => `R$ ${Number(value) / 1000}k`} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Bar dataKey="revenue" fill="var(--color-revenue)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="spend" fill="var(--color-spend)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ChartContainer>
        ) : (
          <EmptyState title="Sem canais no periodo" text="Os canais aparecem quando houver UTM, campanha, tracking ou pedido atribuido." />
        )}
      </CardContent>
    </Card>
  );
}

function CampaignTable({ rows }: { rows: ApiMarketingIntelligenceCampaign[] }) {
  if (!rows.length) {
    return <EmptyState title="Sem campanhas no periodo" text="Campanhas aparecem quando houver trafego, UTM, metricas ou receita atribuida." />;
  }

  return (
    <Card className="border-surface-03 bg-surface-02 text-cream">
      <Table>
        <TableHeader>
          <TableRow className="border-surface-03 hover:bg-transparent">
            <TableHead>Campanha</TableHead>
            <TableHead>Origem</TableHead>
            <TableHead className="text-right">Investimento</TableHead>
            <TableHead className="text-right">Receita</TableHead>
            <TableHead className="text-right">ROAS</TableHead>
            <TableHead className="text-right">Pedidos</TableHead>
            <TableHead className="text-right">Leads</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.id} className="border-surface-03">
              <TableCell>
                <div className="min-w-[180px]">
                  <p className="font-semibold text-cream">{row.name}</p>
                  <p className="text-xs text-stone">{platformLabel(row.platform)}</p>
                </div>
              </TableCell>
              <TableCell>
                <Badge variant="outline" className="border-surface-03 text-stone">
                  {sourceTypeLabel(row.source_type)}
                </Badge>
              </TableCell>
              <TableCell className="text-right text-red-300">{money(row.spend)}</TableCell>
              <TableCell className="text-right text-green-300">{money(row.revenue)}</TableCell>
              <TableCell className="text-right font-bold text-gold">{ratio(row.roas)}</TableCell>
              <TableCell className="text-right">{number(row.orders)}</TableCell>
              <TableCell className="text-right">{number(row.leads)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

function ChannelTable({ rows }: { rows: ApiMarketingIntelligenceChannel[] }) {
  if (!rows.length) {
    return <EmptyState title="Sem canais no periodo" text="Nenhum canal teve tracking, investimento ou receita atribuida no periodo." />;
  }

  return (
    <Card className="border-surface-03 bg-surface-02 text-cream">
      <Table>
        <TableHeader>
          <TableRow className="border-surface-03 hover:bg-transparent">
            <TableHead>Canal</TableHead>
            <TableHead className="text-right">Visitantes</TableHead>
            <TableHead className="text-right">Cliques</TableHead>
            <TableHead className="text-right">Pedidos</TableHead>
            <TableHead className="text-right">Receita</TableHead>
            <TableHead className="text-right">ROAS</TableHead>
            <TableHead className="text-right">Conversao</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.channel} className="border-surface-03">
              <TableCell className="font-semibold text-cream">{row.label}</TableCell>
              <TableCell className="text-right">{number(row.visitors)}</TableCell>
              <TableCell className="text-right">{number(row.clicks)}</TableCell>
              <TableCell className="text-right">{number(row.orders)}</TableCell>
              <TableCell className="text-right text-green-300">{money(row.revenue)}</TableCell>
              <TableCell className="text-right font-bold text-gold">{ratio(row.roas)}</TableCell>
              <TableCell className="text-right">{pctFromRatio(row.conversion_rate)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

function ProductTable({ rows }: { rows: ApiMarketingIntelligenceProduct[] }) {
  if (!rows.length) {
    return <EmptyState title="Sem produtos no periodo" text="Produtos aparecem quando houver visualizacoes, carrinhos ou pedidos pagos atribuidos." />;
  }

  return (
    <Card className="border-surface-03 bg-surface-02 text-cream">
      <Table>
        <TableHeader>
          <TableRow className="border-surface-03 hover:bg-transparent">
            <TableHead>Produto</TableHead>
            <TableHead className="text-right">Views</TableHead>
            <TableHead className="text-right">Carrinhos</TableHead>
            <TableHead className="text-right">Pedidos</TableHead>
            <TableHead className="text-right">Itens</TableHead>
            <TableHead className="text-right">Receita</TableHead>
            <TableHead className="text-right">Conv.</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.product_id ?? row.name} className="border-surface-03">
              <TableCell>
                <div className="min-w-[180px]">
                  <p className="font-semibold text-cream">{row.name}</p>
                  <p className="text-xs text-stone">{row.category || "Sem categoria"}</p>
                </div>
              </TableCell>
              <TableCell className="text-right">{number(row.views)}</TableCell>
              <TableCell className="text-right">{number(row.carts)}</TableCell>
              <TableCell className="text-right">{number(row.orders)}</TableCell>
              <TableCell className="text-right">{number(row.quantity_sold)}</TableCell>
              <TableCell className="text-right text-green-300">{money(row.revenue)}</TableCell>
              <TableCell className="text-right">{pctFromRatio(row.conversion_rate)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

function PromotionTable({ rows }: { rows: ApiMarketingIntelligencePromotion[] }) {
  if (!rows.length) {
    return <EmptyState title="Sem promocoes no periodo" text="Promocoes aparecem quando houver uso de cupons ou itens promocionais em pedidos pagos." />;
  }

  return (
    <Card className="border-surface-03 bg-surface-02 text-cream">
      <Table>
        <TableHeader>
          <TableRow className="border-surface-03 hover:bg-transparent">
            <TableHead>Promocao</TableHead>
            <TableHead>Tipo</TableHead>
            <TableHead className="text-right">Usos</TableHead>
            <TableHead className="text-right">Pedidos</TableHead>
            <TableHead className="text-right">Receita</TableHead>
            <TableHead className="text-right">Desconto</TableHead>
            <TableHead className="text-right">Ticket medio</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.id} className="border-surface-03">
              <TableCell>
                <div className="min-w-[180px]">
                  <p className="font-semibold text-cream">{row.name}</p>
                  {row.code && <p className="text-xs text-gold">{row.code}</p>}
                </div>
              </TableCell>
              <TableCell>
                <Badge variant="outline" className="border-surface-03 text-stone">
                  {row.promotion_type}
                </Badge>
              </TableCell>
              <TableCell className="text-right">{number(row.uses)}</TableCell>
              <TableCell className="text-right">{number(row.orders)}</TableCell>
              <TableCell className="text-right text-green-300">{money(row.revenue)}</TableCell>
              <TableCell className="text-right text-red-300">{money(row.discount)}</TableCell>
              <TableCell className="text-right">{money(row.average_ticket)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

function GoalFormPanel({
  form,
  editingId,
  saving,
  onChange,
  onCancel,
  onSubmit,
}: {
  form: GoalForm;
  editingId: string | null;
  saving: boolean;
  onChange: (patch: Partial<GoalForm>) => void;
  onCancel: () => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <Card className="border-surface-03 bg-surface-02 text-cream">
      <CardHeader className="p-4 pb-0">
        <CardTitle className="text-base">{editingId ? "Editar meta" : "Nova meta"}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3 p-4">
        <form onSubmit={onSubmit} className="grid gap-3 lg:grid-cols-4">
          <Input
            value={form.title}
            onChange={(event) => onChange({ title: event.target.value })}
            placeholder="Titulo da meta"
            className="border-surface-03 bg-surface-01 text-cream lg:col-span-2"
            required
          />
          <Select
            value={form.metric_key}
            onValueChange={(value) => {
              const metric = GOAL_METRICS.find((item) => item.key === value);
              onChange({
                metric_key: value as ApiMarketingGoalMetricKey,
                comparison_direction: metric?.direction ?? "increase",
              });
            }}
          >
            <SelectTrigger className="border-surface-03 bg-surface-01 text-cream">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {GOAL_METRICS.map((metric) => (
                <SelectItem key={metric.key} value={metric.key}>
                  {metric.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={form.priority} onValueChange={(value) => onChange({ priority: value as GoalForm["priority"] })}>
            <SelectTrigger className="border-surface-03 bg-surface-01 text-cream">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="low">Baixa</SelectItem>
              <SelectItem value="medium">Media</SelectItem>
              <SelectItem value="high">Alta</SelectItem>
            </SelectContent>
          </Select>
          <Input
            value={form.target_value}
            onChange={(event) => onChange({ target_value: event.target.value })}
            placeholder="Valor alvo"
            inputMode="decimal"
            className="border-surface-03 bg-surface-01 text-cream"
            required
          />
          <Input
            value={form.baseline_value}
            onChange={(event) => onChange({ baseline_value: event.target.value })}
            placeholder="Valor base"
            inputMode="decimal"
            className="border-surface-03 bg-surface-01 text-cream"
          />
          <Input
            type="date"
            value={form.period_start}
            onChange={(event) => onChange({ period_start: event.target.value })}
            className="border-surface-03 bg-surface-01 text-cream"
            required
          />
          <Input
            type="date"
            value={form.period_end}
            onChange={(event) => onChange({ period_end: event.target.value })}
            className="border-surface-03 bg-surface-01 text-cream"
            required
          />
          <Select value={form.comparison_direction} onValueChange={(value) => onChange({ comparison_direction: value as GoalForm["comparison_direction"] })}>
            <SelectTrigger className="border-surface-03 bg-surface-01 text-cream">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="increase">Maior e melhor</SelectItem>
              <SelectItem value="decrease">Menor e melhor</SelectItem>
            </SelectContent>
          </Select>
          <Select value={form.status} onValueChange={(value) => onChange({ status: value as ApiMarketingGoalStatus })}>
            <SelectTrigger className="border-surface-03 bg-surface-01 text-cream">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="active">Ativa</SelectItem>
              <SelectItem value="paused">Pausada</SelectItem>
              <SelectItem value="completed">Concluida</SelectItem>
              <SelectItem value="cancelled">Cancelada</SelectItem>
            </SelectContent>
          </Select>
          <Input
            value={form.channel}
            onChange={(event) => onChange({ channel: event.target.value })}
            placeholder="Canal opcional"
            className="border-surface-03 bg-surface-01 text-cream lg:col-span-2"
          />
          <Input
            value={form.campaign_id}
            onChange={(event) => onChange({ campaign_id: event.target.value })}
            placeholder="ID campanha"
            className="border-surface-03 bg-surface-01 text-cream"
          />
          <Input
            value={form.traffic_campaign_id}
            onChange={(event) => onChange({ traffic_campaign_id: event.target.value })}
            placeholder="ID campanha trafego"
            className="border-surface-03 bg-surface-01 text-cream"
          />
          <Input
            value={form.coupon_id}
            onChange={(event) => onChange({ coupon_id: event.target.value })}
            placeholder="ID cupom"
            className="border-surface-03 bg-surface-01 text-cream"
          />
          <Input
            value={form.promotion_id}
            onChange={(event) => onChange({ promotion_id: event.target.value })}
            placeholder="ID promocao"
            className="border-surface-03 bg-surface-01 text-cream"
          />
          <Input
            value={form.product_id}
            onChange={(event) => onChange({ product_id: event.target.value })}
            placeholder="ID produto"
            className="border-surface-03 bg-surface-01 text-cream"
          />
          <Textarea
            value={form.description}
            onChange={(event) => onChange({ description: event.target.value })}
            placeholder="Descricao"
            className="border-surface-03 bg-surface-01 text-cream lg:col-span-2"
          />
          <Textarea
            value={form.notes}
            onChange={(event) => onChange({ notes: event.target.value })}
            placeholder="Observacoes"
            className="border-surface-03 bg-surface-01 text-cream lg:col-span-2"
          />
          <div className="flex flex-wrap gap-2 lg:col-span-4">
            <Button type="submit" className="bg-gold text-surface-00 hover:bg-gold/90" disabled={saving}>
              {saving ? <Loader2 className="animate-spin" /> : <Save />}
              {editingId ? "Salvar meta" : "Criar meta"}
            </Button>
            {editingId && (
              <Button type="button" variant="outline" className="border-surface-03 text-cream" onClick={onCancel}>
                Cancelar edicao
              </Button>
            )}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function GoalsPanel({
  goals,
  onEdit,
  onDelete,
  onStatus,
}: {
  goals: ApiMarketingGoal[];
  onEdit: (goal: ApiMarketingGoal) => void;
  onDelete: (goal: ApiMarketingGoal) => void;
  onStatus: (goal: ApiMarketingGoal, status: ApiMarketingGoalStatus) => void;
}) {
  if (!goals.length) {
    return <EmptyState title="Sem metas cadastradas" text="Cadastre metas para acompanhar o progresso real do Marketing Intelligence." />;
  }

  return (
    <div className="grid gap-4">
      {goals.map((goal) => (
        <Card key={goal.id} className="border-surface-03 bg-surface-02 text-cream">
          <CardContent className="p-4">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-bold text-cream">{goal.title}</h3>
                  <Badge variant="outline" className="border-surface-03 text-stone">{GOAL_STATUS_LABELS[goal.status]}</Badge>
                  <Badge variant="outline" className="border-surface-03 text-gold">{PRIORITY_LABELS[goal.priority]}</Badge>
                  {goal.progress.reached && <Badge className="bg-green-500/15 text-green-300">Atingida</Badge>}
                </div>
                {goal.description && <p className="mt-2 text-sm text-stone">{goal.description}</p>}
                <div className="mt-4 grid gap-3 md:grid-cols-4">
                  <Info label="Atual" value={formatProgressValue(goal.progress.current_value, goal.progress.unit)} />
                  <Info label="Alvo" value={formatProgressValue(goal.target_value, goal.progress.unit)} />
                  <Info label="Periodo" value={`${goal.period_start} ate ${goal.period_end}`} />
                  <Info label="Direcao" value={goal.comparison_direction === "decrease" ? "Menor e melhor" : "Maior e melhor"} />
                </div>
                <div className="mt-4 h-2 overflow-hidden rounded-full bg-surface-03">
                  <div className="h-full rounded-full bg-gold" style={{ width: `${Math.max(goal.progress.progress_pct, 2)}%` }} />
                </div>
                <p className="mt-1 text-xs text-stone">{pctValue(goal.progress.progress_pct)} do alvo calculado com dados reais.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {goal.status !== "completed" && (
                  <Button size="sm" variant="outline" className="border-surface-03 text-cream" onClick={() => onStatus(goal, "completed")}>
                    <CheckCircle2 /> Concluir
                  </Button>
                )}
                {goal.status !== "paused" && (
                  <Button size="sm" variant="outline" className="border-surface-03 text-cream" onClick={() => onStatus(goal, "paused")}>
                    <PauseCircle /> Pausar
                  </Button>
                )}
                <Button size="sm" variant="outline" className="border-surface-03 text-cream" onClick={() => onEdit(goal)}>
                  Editar
                </Button>
                <Button size="sm" variant="destructive" onClick={() => onDelete(goal)}>
                  <Trash2 /> Excluir
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function TimelineFormPanel({
  form,
  editingId,
  saving,
  goals,
  onChange,
  onCancel,
  onSubmit,
}: {
  form: TimelineForm;
  editingId: string | null;
  saving: boolean;
  goals: ApiMarketingGoal[];
  onChange: (patch: Partial<TimelineForm>) => void;
  onCancel: () => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <Card className="border-surface-03 bg-surface-02 text-cream">
      <CardHeader className="p-4 pb-0">
        <CardTitle className="text-base">{editingId ? "Editar evento" : "Novo evento de timeline"}</CardTitle>
      </CardHeader>
      <CardContent className="p-4">
        <form onSubmit={onSubmit} className="grid gap-3 lg:grid-cols-4">
          <Input
            value={form.title}
            onChange={(event) => onChange({ title: event.target.value })}
            placeholder="Titulo do evento"
            className="border-surface-03 bg-surface-01 text-cream lg:col-span-2"
            required
          />
          <Select value={form.event_type} onValueChange={(value) => onChange({ event_type: value })}>
            <SelectTrigger className="border-surface-03 bg-surface-01 text-cream">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {EVENT_TYPES.map((item) => (
                <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            type="datetime-local"
            value={form.event_date}
            onChange={(event) => onChange({ event_date: event.target.value })}
            className="border-surface-03 bg-surface-01 text-cream"
            required
          />
          <Select value={form.impact_level} onValueChange={(value) => onChange({ impact_level: value as TimelineForm["impact_level"] })}>
            <SelectTrigger className="border-surface-03 bg-surface-01 text-cream">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="low">Baixo</SelectItem>
              <SelectItem value="medium">Medio</SelectItem>
              <SelectItem value="high">Alto</SelectItem>
            </SelectContent>
          </Select>
          <Select value={form.category} onValueChange={(value) => onChange({ category: value })}>
            <SelectTrigger className="border-surface-03 bg-surface-01 text-cream">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {EVENT_CATEGORIES.map((item) => (
                <SelectItem key={item} value={item}>{item}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={form.goal_id || "none"} onValueChange={(value) => onChange({ goal_id: value === "none" ? "" : value })}>
            <SelectTrigger className="border-surface-03 bg-surface-01 text-cream">
              <SelectValue placeholder="Meta vinculada" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">Sem meta vinculada</SelectItem>
              {goals.map((goal) => (
                <SelectItem key={goal.id} value={goal.id}>{goal.title}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            value={form.tags}
            onChange={(event) => onChange({ tags: event.target.value })}
            placeholder="Tags separadas por virgula"
            className="border-surface-03 bg-surface-01 text-cream"
          />
          <Input
            value={form.campaign_id}
            onChange={(event) => onChange({ campaign_id: event.target.value })}
            placeholder="ID campanha"
            className="border-surface-03 bg-surface-01 text-cream"
          />
          <Input
            value={form.traffic_campaign_id}
            onChange={(event) => onChange({ traffic_campaign_id: event.target.value })}
            placeholder="ID campanha trafego"
            className="border-surface-03 bg-surface-01 text-cream"
          />
          <Input
            value={form.coupon_id}
            onChange={(event) => onChange({ coupon_id: event.target.value })}
            placeholder="ID cupom"
            className="border-surface-03 bg-surface-01 text-cream"
          />
          <Input
            value={form.promotion_id}
            onChange={(event) => onChange({ promotion_id: event.target.value })}
            placeholder="ID promocao"
            className="border-surface-03 bg-surface-01 text-cream"
          />
          <Input
            value={form.product_id}
            onChange={(event) => onChange({ product_id: event.target.value })}
            placeholder="ID produto"
            className="border-surface-03 bg-surface-01 text-cream"
          />
          <Input
            value={form.attachment_url}
            onChange={(event) => onChange({ attachment_url: event.target.value })}
            placeholder="URL/anexo opcional"
            className="border-surface-03 bg-surface-01 text-cream lg:col-span-2"
          />
          <Select value={form.attachment_type} onValueChange={(value) => onChange({ attachment_type: value as TimelineForm["attachment_type"] })}>
            <SelectTrigger className="border-surface-03 bg-surface-01 text-cream">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="url">URL</SelectItem>
              <SelectItem value="image">Imagem</SelectItem>
              <SelectItem value="document">Documento</SelectItem>
              <SelectItem value="other">Outro</SelectItem>
            </SelectContent>
          </Select>
          <Textarea
            value={form.description}
            onChange={(event) => onChange({ description: event.target.value })}
            placeholder="Descricao"
            className="border-surface-03 bg-surface-01 text-cream lg:col-span-3"
          />
          <div className="flex flex-wrap gap-2 lg:col-span-4">
            <Button type="submit" className="bg-gold text-surface-00 hover:bg-gold/90" disabled={saving}>
              {saving ? <Loader2 className="animate-spin" /> : <Plus />}
              {editingId ? "Salvar evento" : "Criar evento"}
            </Button>
            {editingId && (
              <Button type="button" variant="outline" className="border-surface-03 text-cream" onClick={onCancel}>
                Cancelar edicao
              </Button>
            )}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function TimelinePanel({
  events,
  goals,
  onEdit,
  onDelete,
}: {
  events: ApiMarketingTimelineEvent[];
  goals: ApiMarketingGoal[];
  onEdit: (event: ApiMarketingTimelineEvent) => void;
  onDelete: (event: ApiMarketingTimelineEvent) => void;
}) {
  if (!events.length) {
    return <EmptyState title="Timeline vazia" text="Registre eventos para contextualizar variacoes de performance." />;
  }
  const goalById = new Map(goals.map((goal) => [goal.id, goal.title]));

  return (
    <div className="space-y-3">
      {events.map((event) => (
        <Card key={event.id} className="border-surface-03 bg-surface-02 text-cream">
          <CardContent className="p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold text-gold">{new Date(event.event_date).toLocaleString("pt-BR")}</span>
                  <Badge variant="outline" className="border-surface-03 text-stone">{event.event_type}</Badge>
                  {event.category && <Badge variant="outline" className="border-surface-03 text-stone">{event.category}</Badge>}
                  <Badge className={event.impact_level === "high" ? "bg-red-500/15 text-red-300" : event.impact_level === "medium" ? "bg-gold/15 text-gold" : "bg-surface-03 text-stone"}>
                    {event.impact_level}
                  </Badge>
                </div>
                <h3 className="mt-2 font-bold text-cream">{event.title}</h3>
                {event.description && <p className="mt-1 text-sm text-stone">{event.description}</p>}
                {event.goal_id && <p className="mt-2 text-xs text-gold">Meta: {goalById.get(event.goal_id) ?? event.goal_id}</p>}
                {!!event.tags.length && (
                  <div className="mt-3 flex flex-wrap gap-1">
                    {event.tags.map((tag) => (
                      <Badge key={tag} variant="outline" className="border-surface-03 text-stone">{tag}</Badge>
                    ))}
                  </div>
                )}
                {event.attachment_url && (
                  <a href={event.attachment_url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-gold hover:text-cream">
                    <Link2 size={14} /> {event.attachment_type ?? "url"}
                  </a>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="outline" className="border-surface-03 text-cream" onClick={() => onEdit(event)}>
                  Editar
                </Button>
                <Button size="sm" variant="destructive" onClick={() => onDelete(event)}>
                  <Trash2 /> Excluir
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase text-stone">{label}</p>
      <p className="mt-1 text-sm font-bold text-cream">{value}</p>
    </div>
  );
}

function formatProgressValue(value: number, unit: string) {
  if (unit === "currency") return money(value);
  if (unit === "percent") return pctValue(value);
  return number(value);
}

export default function MarketingIntelligence() {
  const [period, setPeriod] = useState<ApiMarketingIntelligencePeriod>("30d");
  const [tab, setTab] = useState<Tab>("overview");
  const [dashboard, setDashboard] = useState<ApiMarketingIntelligenceDashboard | null>(null);
  const [campaigns, setCampaigns] = useState<ApiMarketingIntelligenceCampaign[]>([]);
  const [channels, setChannels] = useState<ApiMarketingIntelligenceChannel[]>([]);
  const [funnel, setFunnel] = useState<ApiMarketingIntelligenceFunnelStep[]>([]);
  const [products, setProducts] = useState<ApiMarketingIntelligenceProduct[]>([]);
  const [promotions, setPromotions] = useState<ApiMarketingIntelligencePromotion[]>([]);
  const [goals, setGoals] = useState<ApiMarketingGoal[]>([]);
  const [timeline, setTimeline] = useState<ApiMarketingTimelineEvent[]>([]);
  const [goalForm, setGoalForm] = useState<GoalForm>(() => emptyGoalForm());
  const [timelineForm, setTimelineForm] = useState<TimelineForm>(() => emptyTimelineForm());
  const [editingGoalId, setEditingGoalId] = useState<string | null>(null);
  const [editingTimelineId, setEditingTimelineId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async (nextPeriod = period, silent = false) => {
    if (silent) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const params = { period: nextPeriod, limit: 50 };
      const [dashboardData, campaignsData, channelsData, funnelData, productsData, promotionsData, planningData] = await Promise.all([
        marketingIntelligenceApi.dashboard(params),
        marketingIntelligenceApi.campaigns(params),
        marketingIntelligenceApi.channels(params),
        marketingIntelligenceApi.funnel(params),
        marketingIntelligenceApi.products(params),
        marketingIntelligenceApi.promotions(params),
        marketingIntelligenceApi.planning({ limit: 100 }),
      ]);

      setDashboard(dashboardData);
      setCampaigns(campaignsData.campaigns ?? []);
      setChannels(channelsData.channels ?? []);
      setFunnel(funnelData.funnel ?? []);
      setProducts(productsData.products ?? []);
      setPromotions(promotionsData.promotions ?? []);
      setGoals(planningData.goals ?? []);
      setTimeline(planningData.timeline ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel carregar Marketing Intelligence.");
      setDashboard(null);
      setCampaigns([]);
      setChannels([]);
      setFunnel([]);
      setProducts([]);
      setPromotions([]);
      setGoals([]);
      setTimeline([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    load(period);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period]);

  const kpis = useMemo(() => {
    const byKey = new Map((dashboard?.kpis ?? []).map((item) => [item.key, item]));
    return KPI_KEYS.map((key) => {
      const item = byKey.get(key);
      return {
        key,
        label: item?.label ?? KPI_META[key].label,
        value: item?.value ?? 0,
        unit: item?.unit ?? (["revenue", "spend", "cac", "cpa", "cpl", "average_ticket"].includes(key) ? "currency" : "number"),
        helper: item?.helper ?? null,
      };
    });
  }, [dashboard?.kpis]);

  const hasAnyData = Boolean(
    dashboard?.kpis?.some((item) => item.value > 0) ||
      campaigns.length ||
      channels.length ||
      funnel.some((item) => item.value > 0) ||
      products.length ||
      promotions.length ||
      goals.length ||
      timeline.length,
  );

  const submitGoal = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    const metric = GOAL_METRICS.find((item) => item.key === goalForm.metric_key);
    const payload: ApiMarketingGoalInput = {
      title: goalForm.title.trim(),
      description: goalForm.description.trim() || null,
      metric_key: goalForm.metric_key,
      target_value: Number(goalForm.target_value.replace(",", ".")),
      baseline_value: goalForm.baseline_value.trim() ? Number(goalForm.baseline_value.replace(",", ".")) : null,
      comparison_direction: goalForm.comparison_direction || metric?.direction || "increase",
      period_start: goalForm.period_start,
      period_end: goalForm.period_end,
      status: goalForm.status,
      priority: goalForm.priority,
      campaign_id: goalForm.campaign_id.trim() || null,
      traffic_campaign_id: goalForm.traffic_campaign_id.trim() || null,
      coupon_id: goalForm.coupon_id.trim() || null,
      promotion_id: goalForm.promotion_id.trim() || null,
      product_id: goalForm.product_id.trim() || null,
      channel: goalForm.channel.trim() || null,
      notes: goalForm.notes.trim() || null,
      metadata: {},
    };
    try {
      if (editingGoalId) await marketingIntelligenceApi.updateGoal(editingGoalId, payload);
      else await marketingIntelligenceApi.createGoal(payload);
      setGoalForm(emptyGoalForm());
      setEditingGoalId(null);
      await load(period, true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel salvar a meta.");
    } finally {
      setSaving(false);
    }
  };

  const editGoal = (goal: ApiMarketingGoal) => {
    setEditingGoalId(goal.id);
    setGoalForm({
      title: goal.title,
      description: goal.description ?? "",
      metric_key: goal.metric_key,
      target_value: String(goal.target_value ?? ""),
      baseline_value: goal.baseline_value == null ? "" : String(goal.baseline_value),
      comparison_direction: goal.comparison_direction,
      period_start: goal.period_start,
      period_end: goal.period_end,
      status: goal.status,
      priority: goal.priority,
      campaign_id: goal.campaign_id ?? "",
      traffic_campaign_id: goal.traffic_campaign_id ?? "",
      coupon_id: goal.coupon_id ?? "",
      promotion_id: goal.promotion_id ?? "",
      product_id: goal.product_id ?? "",
      channel: goal.channel ?? "",
      notes: goal.notes ?? "",
    });
  };

  const deleteGoal = async (goal: ApiMarketingGoal) => {
    if (!confirm(`Excluir a meta "${goal.title}"?`)) return;
    setSaving(true);
    try {
      await marketingIntelligenceApi.deleteGoal(goal.id);
      await load(period, true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel excluir a meta.");
    } finally {
      setSaving(false);
    }
  };

  const updateGoalStatus = async (goal: ApiMarketingGoal, status: ApiMarketingGoalStatus) => {
    setSaving(true);
    try {
      await marketingIntelligenceApi.updateGoalStatus(goal.id, status);
      await load(period, true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel atualizar a meta.");
    } finally {
      setSaving(false);
    }
  };

  const submitTimeline = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    const payload: ApiMarketingTimelineEventInput = {
      title: timelineForm.title.trim(),
      description: timelineForm.description.trim() || null,
      event_type: timelineForm.event_type,
      event_date: new Date(timelineForm.event_date).toISOString(),
      impact_level: timelineForm.impact_level,
      category: timelineForm.category || null,
      tags: timelineForm.tags.split(",").map((tag) => tag.trim()).filter(Boolean),
      attachment_url: timelineForm.attachment_url.trim() || null,
      attachment_type: timelineForm.attachment_url.trim() ? timelineForm.attachment_type : null,
      goal_id: timelineForm.goal_id || null,
      campaign_id: timelineForm.campaign_id.trim() || null,
      traffic_campaign_id: timelineForm.traffic_campaign_id.trim() || null,
      coupon_id: timelineForm.coupon_id.trim() || null,
      promotion_id: timelineForm.promotion_id.trim() || null,
      product_id: timelineForm.product_id.trim() || null,
      metadata: {},
    };
    try {
      if (editingTimelineId) await marketingIntelligenceApi.updateTimelineEvent(editingTimelineId, payload);
      else await marketingIntelligenceApi.createTimelineEvent(payload);
      setTimelineForm(emptyTimelineForm());
      setEditingTimelineId(null);
      await load(period, true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel salvar o evento.");
    } finally {
      setSaving(false);
    }
  };

  const editTimeline = (item: ApiMarketingTimelineEvent) => {
    const eventDate = new Date(item.event_date);
    eventDate.setMinutes(eventDate.getMinutes() - eventDate.getTimezoneOffset());
    setEditingTimelineId(item.id);
    setTimelineForm({
      title: item.title,
      description: item.description ?? "",
      event_type: item.event_type,
      event_date: eventDate.toISOString().slice(0, 16),
      impact_level: item.impact_level,
      category: item.category ?? "estrategia",
      tags: item.tags.join(", "),
      attachment_url: item.attachment_url ?? "",
      attachment_type: item.attachment_type ?? "url",
      goal_id: item.goal_id ?? "",
      campaign_id: item.campaign_id ?? "",
      traffic_campaign_id: item.traffic_campaign_id ?? "",
      coupon_id: item.coupon_id ?? "",
      promotion_id: item.promotion_id ?? "",
      product_id: item.product_id ?? "",
    });
  };

  const deleteTimeline = async (item: ApiMarketingTimelineEvent) => {
    if (!confirm(`Excluir o evento "${item.title}"?`)) return;
    setSaving(true);
    try {
      await marketingIntelligenceApi.deleteTimelineEvent(item.id);
      await load(period, true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel excluir o evento.");
    } finally {
      setSaving(false);
    }
  };

  const actions = (
    <div className="flex flex-wrap items-center justify-end gap-2">
      <Select value={period} onValueChange={(value) => setPeriod(value as ApiMarketingIntelligencePeriod)}>
        <SelectTrigger className="w-[150px] border-surface-03 bg-surface-02 text-cream">
          <SelectValue placeholder="Periodo" />
        </SelectTrigger>
        <SelectContent>
          {PERIODS.map((item) => (
            <SelectItem key={item.key} value={item.key}>
              {item.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <button
        type="button"
        onClick={() => load(period, true)}
        className="inline-flex h-10 items-center gap-2 rounded-md border border-surface-03 bg-surface-02 px-3 text-sm font-semibold text-cream transition hover:border-gold/50"
      >
        {refreshing ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
        Atualizar
      </button>
    </div>
  );

  if (loading && !dashboard) {
    return (
      <AdminPageShell>
        <AdminPageHeader
          eyebrow="Marketing"
          title="Marketing Intelligence"
          description="Consolidacao executiva de marketing."
          icon={<BarChart3 size={20} />}
          actions={actions}
        />
        <AdminPageContent>
          <div className="flex min-h-[420px] items-center justify-center rounded-lg border border-surface-03 bg-surface-02">
            <div className="flex items-center gap-2 text-sm font-semibold text-stone">
              <Loader2 className="h-5 w-5 animate-spin text-gold" />
              Carregando Marketing Intelligence...
            </div>
          </div>
        </AdminPageContent>
      </AdminPageShell>
    );
  }

  return (
    <AdminPageShell>
      <AdminPageHeader
        eyebrow="Marketing"
        title="Marketing Intelligence"
        description="Consolidacao executiva com pedidos, campanhas, canais, produtos e promocoes."
        icon={<BarChart3 size={20} />}
        actions={actions}
      />
      <AdminPageContent className="space-y-6">
        <AdminPageTabs<Tab> tabs={TABS} active={tab} onChange={setTab} />

        {dashboard && (
          <div className="flex flex-wrap items-center gap-2 text-xs text-stone">
            <Badge variant="outline" className="border-surface-03 text-stone">
              {dashboard.date_from} ate {dashboard.date_to}
            </Badge>
            <Badge variant="outline" className="border-surface-03 text-stone">
              Gerado: {new Date(dashboard.generated_at).toLocaleString("pt-BR")}
            </Badge>
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
            {error}
          </div>
        )}

        {!error && !hasAnyData && (
          <EmptyState
            title="Sem dados de marketing para o periodo"
            text="A consolidacao permanece zerada ate existirem pedidos pagos, eventos de tracking, UTMs, campanhas, cupons ou metricas de anuncios no periodo selecionado."
          />
        )}

        {tab === "overview" && (
          <>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5">
              {kpis.map((item) => (
                <KpiCard key={item.key} item={item} />
              ))}
            </div>

            <div className="grid gap-6 xl:grid-cols-[1fr_0.9fr]">
              <FunnelCard items={funnel} />
              <ChannelChart channels={channels} />
            </div>
          </>
        )}

        {tab === "campaigns" && (
          <div className="grid gap-6">
            <Section title="Campanhas">
              <CampaignTable rows={campaigns} />
            </Section>
            <Section title="Canais">
              <ChannelTable rows={channels} />
            </Section>
          </div>
        )}

        {tab === "products" && (
          <div className="grid gap-6">
            <Section title="Produtos">
              <ProductTable rows={products} />
            </Section>
            <Section title="Promocoes">
              <PromotionTable rows={promotions} />
            </Section>
          </div>
        )}

        {tab === "goals" && (
          <div className="grid gap-6">
            <GoalFormPanel
              form={goalForm}
              editingId={editingGoalId}
              saving={saving}
              onChange={(patch) => setGoalForm((prev) => ({ ...prev, ...patch }))}
              onCancel={() => {
                setEditingGoalId(null);
                setGoalForm(emptyGoalForm());
              }}
              onSubmit={submitGoal}
            />
            <Section
              title="Metas estrategicas"
              action={
                <Badge variant="outline" className="border-surface-03 text-stone">
                  {goals.length} metas
                </Badge>
              }
            >
              <GoalsPanel goals={goals} onEdit={editGoal} onDelete={deleteGoal} onStatus={updateGoalStatus} />
            </Section>
          </div>
        )}

        {tab === "timeline" && (
          <div className="grid gap-6">
            <TimelineFormPanel
              form={timelineForm}
              editingId={editingTimelineId}
              saving={saving}
              goals={goals}
              onChange={(patch) => setTimelineForm((prev) => ({ ...prev, ...patch }))}
              onCancel={() => {
                setEditingTimelineId(null);
                setTimelineForm(emptyTimelineForm());
              }}
              onSubmit={submitTimeline}
            />
            <Section
              title="Timeline inteligente"
              action={
                <Badge variant="outline" className="border-surface-03 text-stone">
                  {timeline.length} eventos
                </Badge>
              }
            >
              <TimelinePanel events={timeline} goals={goals} onEdit={editTimeline} onDelete={deleteTimeline} />
            </Section>
          </div>
        )}
      </AdminPageContent>
    </AdminPageShell>
  );
}
