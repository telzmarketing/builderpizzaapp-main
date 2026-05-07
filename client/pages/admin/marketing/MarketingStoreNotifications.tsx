import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  Bell,
  CheckCircle2,
  Copy,
  Eye,
  Inbox,
  Loader2,
  Pause,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Settings,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import {
  productsApi,
  storeNotificationsApi,
  type ApiProduct,
  type ApiStoreNotification,
  type ApiStoreNotificationCaptured,
  type ApiStoreNotificationInput,
  type ApiStoreNotificationPage,
  type ApiStoreNotificationPriority,
  type ApiStoreNotificationSettings,
  type ApiStoreNotificationStatus,
  type ApiStoreNotificationSummary,
  type ApiStoreNotificationType,
} from "@/lib/api";

type View = "notifications" | "captured" | "settings";

const IC = "w-full rounded-xl border border-surface-03 bg-surface-03 px-3 py-2 text-sm text-cream outline-none transition-colors focus:border-gold";
const WEEKDAYS = [
  { id: 0, label: "Seg" },
  { id: 1, label: "Ter" },
  { id: 2, label: "Qua" },
  { id: 3, label: "Qui" },
  { id: 4, label: "Sex" },
  { id: 5, label: "Sab" },
  { id: 6, label: "Dom" },
];
const PAGE_OPTIONS: { id: ApiStoreNotificationPage; label: string }[] = [
  { id: "home", label: "Home" },
  { id: "cardapio", label: "Cardapio" },
  { id: "product", label: "Produto" },
  { id: "cart", label: "Carrinho" },
];

const STATUS_LABEL: Record<ApiStoreNotificationStatus, string> = {
  active: "Ativa",
  paused: "Pausada",
};
const TYPE_LABEL: Record<ApiStoreNotificationType | "real", string> = {
  manual: "Manual",
  fomento: "Fomento",
  real: "Real",
};
const PRIORITY_LABEL: Record<ApiStoreNotificationPriority, string> = {
  low: "Baixa",
  medium: "Media",
  high: "Alta",
};
const CAPTURED_STATUS_LABEL: Record<string, string> = {
  pending: "Pendente",
  activated: "Ativada",
  discarded: "Descartada",
};
const CAPTURED_STATUS_COLOR: Record<string, string> = {
  pending: "bg-blue-500/15 text-blue-400",
  activated: "bg-green-500/15 text-green-400",
  discarded: "bg-surface-03 text-stone",
};

const emptyForm = (): ApiStoreNotificationInput => ({
  type: "manual",
  status: "active",
  internal_name: "",
  display_name: "",
  product_id: "",
  neighborhood: "",
  template_text: "{nome}, {bairro}, comprou {produto} - {tempo}",
  priority: "medium",
  weight: 1,
  display_seconds: 7,
  start_time: "18:00",
  end_time: "23:30",
  start_date: null,
  end_date: null,
  weekdays: [0, 1, 2, 3, 4, 5, 6],
});

const defaultSettings = (): Omit<ApiStoreNotificationSettings, "id" | "created_at" | "updated_at"> => ({
  enabled: true,
  real_orders_enabled: true,
  real_percentage: 70,
  manual_percentage: 30,
  initial_delay_seconds: 5,
  min_delay_seconds: 45,
  max_delay_seconds: 120,
  default_display_seconds: 7,
  prevent_same_product_sequence: true,
  prevent_same_neighborhood_sequence: false,
  only_during_store_hours: false,
  allowed_pages: ["home", "cardapio", "product", "cart"],
});

function fmtDate(value?: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function daysLabel(days: number[]) {
  if (days.length === 7) return "Todos";
  return WEEKDAYS.filter((day) => days.includes(day.id)).map((day) => day.label).join(", ");
}

function productDisplayName(product?: ApiProduct | null) {
  const name = product?.name?.trim();
  if (!name) return "Produto";
  if (name.toLowerCase().startsWith("pizza")) return name;
  const category = [product.category, product.subcategory].filter(Boolean).join(" ").toLowerCase();
  if (product.product_type === "pizza" || category.includes("pizza")) return `Pizza de ${name}`;
  return name;
}

function productName(products: ApiProduct[], productId: string) {
  return productDisplayName(products.find((product) => product.id === productId));
}

export default function MarketingStoreNotifications() {
  const [view, setView] = useState<View>("notifications");
  const [items, setItems] = useState<ApiStoreNotification[]>([]);
  const [captured, setCaptured] = useState<ApiStoreNotificationCaptured[]>([]);
  const [summary, setSummary] = useState<ApiStoreNotificationSummary>({
    active_notifications: 0,
    manual_notifications: 0,
    real_impressions: 0,
    total_impressions: 0,
  });
  const [settings, setSettings] = useState(defaultSettings());
  const [products, setProducts] = useState<ApiProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [activatingCaptured, setActivatingCaptured] = useState<ApiStoreNotificationCaptured | null>(null);
  const [form, setForm] = useState<ApiStoreNotificationInput>(emptyForm());
  const [preview, setPreview] = useState("");

  const load = () => {
    setLoading(true);
    setError("");
    Promise.all([
      storeNotificationsApi.list(),
      storeNotificationsApi.summary(),
      storeNotificationsApi.settings(),
      productsApi.list(false),
    ])
      .then(([list, sum, cfg, productList]) => {
        setItems(list ?? []);
        setSummary(sum);
        setSettings({
          enabled: cfg.enabled,
          real_orders_enabled: cfg.real_orders_enabled,
          real_percentage: cfg.real_percentage,
          manual_percentage: cfg.manual_percentage,
          initial_delay_seconds: cfg.initial_delay_seconds ?? 5,
          min_delay_seconds: cfg.min_delay_seconds,
          max_delay_seconds: cfg.max_delay_seconds,
          default_display_seconds: cfg.default_display_seconds,
          prevent_same_product_sequence: cfg.prevent_same_product_sequence,
          prevent_same_neighborhood_sequence: cfg.prevent_same_neighborhood_sequence,
          only_during_store_hours: cfg.only_during_store_hours,
          allowed_pages: cfg.allowed_pages,
        });
        setProducts(productList ?? []);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Falha ao carregar notificacoes."))
      .finally(() => setLoading(false));
  };

  const loadCaptured = () => {
    storeNotificationsApi
      .listCaptured()
      .then((list) => setCaptured(list ?? []))
      .catch(() => {});
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (view === "captured") loadCaptured();
  }, [view]);

  const activeProducts = useMemo(() => products.filter((product) => product.active), [products]);

  const openCreate = () => {
    setEditingId(null);
    setForm({ ...emptyForm(), product_id: activeProducts[0]?.id ?? "" });
    setPreview("");
    setShowForm(true);
  };

  const openEdit = (item: ApiStoreNotification) => {
    setEditingId(item.id);
    setForm({
      type: item.type,
      status: item.status,
      internal_name: item.internal_name,
      display_name: item.display_name,
      product_id: item.product_id,
      neighborhood: item.neighborhood ?? "",
      template_text: item.template_text,
      priority: item.priority,
      weight: item.weight,
      display_seconds: item.display_seconds,
      start_time: item.start_time.slice(0, 5),
      end_time: item.end_time.slice(0, 5),
      start_date: item.start_date ?? null,
      end_date: item.end_date ?? null,
      weekdays: item.weekdays,
    });
    setPreview("");
    setShowForm(true);
  };

  const openActivateCaptured = (cap: ApiStoreNotificationCaptured) => {
    setActivatingCaptured(cap);
    const firstProduct = activeProducts.find((p) => p.id === cap.product_id) ?? activeProducts[0];
    setForm({
      type: "manual",
      status: "active",
      internal_name: `Pedido: ${cap.buyer_name ?? "Cliente"} - ${cap.product_name ?? "Produto"}`,
      display_name: cap.buyer_name ?? "Cliente",
      product_id: firstProduct?.id ?? "",
      neighborhood: cap.neighborhood ?? "",
      template_text: "{nome}, {bairro}, comprou {produto} - {tempo}",
      priority: "medium",
      weight: 1,
      display_seconds: 7,
      start_time: "00:00",
      end_time: "23:59",
      start_date: null,
      end_date: null,
      weekdays: [0, 1, 2, 3, 4, 5, 6],
    });
    setPreview("");
  };

  const saveForm = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!form.product_id) {
      alert("Selecione um produto.");
      return;
    }
    setSaving(true);
    try {
      if (activatingCaptured) {
        await storeNotificationsApi.activateCaptured(activatingCaptured.id, form);
        setActivatingCaptured(null);
        loadCaptured();
        load();
      } else if (editingId) {
        await storeNotificationsApi.update(editingId, form);
        setShowForm(false);
        load();
      } else {
        await storeNotificationsApi.create(form);
        setShowForm(false);
        load();
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao salvar notificacao.");
    } finally {
      setSaving(false);
    }
  };

  const saveSettings = async () => {
    setSaving(true);
    try {
      await storeNotificationsApi.updateSettings(settings);
      load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao salvar configuracoes.");
    } finally {
      setSaving(false);
    }
  };

  const previewForm = async () => {
    const pName = productName(products, form.product_id);
    try {
      const result = await storeNotificationsApi.preview({
        display_name: form.display_name || "Cliente",
        product_name: pName,
        neighborhood: form.neighborhood,
        template_text: form.template_text,
        relative_time: "2min",
      });
      setPreview(result.message);
    } catch {
      setPreview("");
    }
  };

  const previewItem = async (item: ApiStoreNotification) => {
    try {
      const result = await storeNotificationsApi.preview({
        display_name: item.display_name,
        product_name: productName(products, item.product_id),
        neighborhood: item.neighborhood,
        template_text: item.template_text,
        relative_time: "2min",
      });
      setPreview(result.message);
    } catch {
      setPreview("");
    }
  };

  const toggleDay = (weekday: number) => {
    setForm((current) => {
      const exists = current.weekdays.includes(weekday);
      const weekdays = exists
        ? current.weekdays.filter((day) => day !== weekday)
        : [...current.weekdays, weekday].sort();
      return { ...current, weekdays };
    });
  };

  const togglePage = (page: ApiStoreNotificationPage) => {
    setSettings((current) => {
      const exists = current.allowed_pages.includes(page);
      const allowed_pages = exists
        ? current.allowed_pages.filter((item) => item !== page)
        : [...current.allowed_pages, page];
      return { ...current, allowed_pages };
    });
  };

  const duplicate = async (id: string) => {
    await storeNotificationsApi.duplicate(id);
    load();
  };

  const remove = async (id: string) => {
    if (!confirm("Excluir esta notificacao?")) return;
    await storeNotificationsApi.remove(id);
    load();
  };

  const toggleStatus = async (item: ApiStoreNotification) => {
    await storeNotificationsApi.setStatus(item.id, item.status === "active" ? "paused" : "active");
    load();
  };

  const discardCaptured = async (id: string) => {
    if (!confirm("Descartar esta notificacao capturada?")) return;
    await storeNotificationsApi.discardCaptured(id);
    loadCaptured();
  };

  const metrics = [
    { label: "Notificacoes ativas", value: summary.active_notifications, icon: Bell, color: "text-green-400", bg: "bg-green-500/10" },
    { label: "Notificacoes manuais", value: summary.manual_notifications, icon: Sparkles, color: "text-gold", bg: "bg-gold/10" },
    { label: "Reais exibidas", value: summary.real_impressions, icon: Eye, color: "text-blue-400", bg: "bg-blue-500/10" },
    { label: "Total de exibicoes", value: summary.total_impressions, icon: RefreshCw, color: "text-purple-400", bg: "bg-purple-500/10" },
  ];

  const pendingCaptured = captured.filter((c) => c.status === "pending").length;

  const isFormOpen = showForm || activatingCaptured !== null;

  return (
    <>
      <div className="space-y-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex rounded-xl border border-surface-03 bg-surface-02 p-1">
            <button
              type="button"
              onClick={() => setView("notifications")}
              className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${view === "notifications" ? "bg-gold text-black" : "text-stone hover:text-cream"}`}
            >
              <Bell size={15} /> Notificacoes
            </button>
            <button
              type="button"
              onClick={() => setView("captured")}
              className={`relative flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${view === "captured" ? "bg-gold text-black" : "text-stone hover:text-cream"}`}
            >
              <Inbox size={15} /> Capturadas
              {pendingCaptured > 0 && (
                <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
                  {pendingCaptured}
                </span>
              )}
            </button>
            <button
              type="button"
              onClick={() => setView("settings")}
              className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${view === "settings" ? "bg-gold text-black" : "text-stone hover:text-cream"}`}
            >
              <Settings size={15} /> Configuracoes
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => { load(); if (view === "captured") loadCaptured(); }}
              className="rounded-xl border border-surface-03 bg-surface-02 p-2 text-stone transition-colors hover:text-cream"
              title="Atualizar"
            >
              <RefreshCw size={16} />
            </button>
            {view === "notifications" && (
              <button
                type="button"
                onClick={openCreate}
                className="inline-flex items-center gap-2 rounded-xl bg-gold px-4 py-2 text-sm font-semibold text-black transition-colors hover:bg-gold/90"
              >
                <Plus size={16} /> Nova notificacao
              </button>
            )}
          </div>
        </div>

        {error && (
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex justify-center py-20">
            <Loader2 className="animate-spin text-gold" size={30} />
          </div>
        ) : view === "notifications" ? (
          <>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              {metrics.map((metric) => (
                <div key={metric.label} className="rounded-2xl border border-surface-03 bg-surface-02 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-xs text-stone">{metric.label}</p>
                    <span className={`rounded-lg p-1.5 ${metric.bg}`}>
                      <metric.icon size={14} className={metric.color} />
                    </span>
                  </div>
                  <p className={`mt-2 text-2xl font-bold ${metric.color}`}>{metric.value}</p>
                </div>
              ))}
            </div>

            <div className="overflow-hidden rounded-2xl border border-surface-03 bg-surface-02">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[980px] text-sm">
                  <thead>
                    <tr className="border-b border-surface-03 bg-surface-03/40 text-xs text-stone">
                      {["Status", "Nome interno", "Tipo", "Produto", "Bairro", "Dias ativos", "Horario", "Prioridade", "Ultima exibicao", "Acoes"].map((header) => (
                        <th key={header} className="p-3 text-left font-medium">{header}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-03">
                    {items.length === 0 ? (
                      <tr>
                        <td colSpan={10} className="p-10 text-center text-sm text-stone">
                          Nenhuma notificacao manual cadastrada.
                        </td>
                      </tr>
                    ) : items.map((item) => (
                      <tr key={item.id} className="transition-colors hover:bg-surface-03/25">
                        <td className="p-3">
                          <span className={`rounded-full px-2 py-1 text-xs font-semibold ${item.status === "active" ? "bg-green-500/15 text-green-400" : "bg-yellow-500/15 text-yellow-300"}`}>
                            {STATUS_LABEL[item.status]}
                          </span>
                        </td>
                        <td className="p-3 text-cream">{item.internal_name}</td>
                        <td className="p-3 text-stone">{TYPE_LABEL[item.type]}</td>
                        <td className="p-3 text-stone">{item.product_name ?? productName(products, item.product_id)}</td>
                        <td className="p-3 text-stone">{item.neighborhood || "-"}</td>
                        <td className="p-3 text-stone">{daysLabel(item.weekdays)}</td>
                        <td className="p-3 text-stone">{item.start_time.slice(0, 5)} - {item.end_time.slice(0, 5)}</td>
                        <td className="p-3 text-stone">{PRIORITY_LABEL[item.priority]}</td>
                        <td className="p-3 text-stone">{fmtDate(item.last_displayed_at)}</td>
                        <td className="p-3">
                          <div className="flex items-center gap-1">
                            <button onClick={() => openEdit(item)} className="rounded-lg p-1.5 text-stone hover:bg-surface-03 hover:text-cream" title="Editar">
                              <Pencil size={14} />
                            </button>
                            <button onClick={() => duplicate(item.id)} className="rounded-lg p-1.5 text-stone hover:bg-surface-03 hover:text-cream" title="Duplicar">
                              <Copy size={14} />
                            </button>
                            <button onClick={() => toggleStatus(item)} className="rounded-lg p-1.5 text-stone hover:bg-surface-03 hover:text-cream" title={item.status === "active" ? "Pausar" : "Ativar"}>
                              {item.status === "active" ? <Pause size={14} /> : <Play size={14} />}
                            </button>
                            <button onClick={() => previewItem(item)} className="rounded-lg p-1.5 text-stone hover:bg-surface-03 hover:text-cream" title="Pre-visualizar">
                              <Eye size={14} />
                            </button>
                            <button onClick={() => remove(item.id)} className="rounded-lg p-1.5 text-stone hover:bg-red-500/10 hover:text-red-400" title="Excluir">
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        ) : view === "captured" ? (
          <div className="space-y-4">
            <div className="rounded-2xl border border-surface-03 bg-surface-02 p-4">
              <p className="text-xs text-stone">
                Compras realizadas na loja sao capturadas automaticamente aqui para revisao. Configure e ative para que apareçam como notificacao para outros clientes.
              </p>
            </div>
            <div className="overflow-hidden rounded-2xl border border-surface-03 bg-surface-02">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] text-sm">
                  <thead>
                    <tr className="border-b border-surface-03 bg-surface-03/40 text-xs text-stone">
                      {["Status", "Cliente", "Produto", "Bairro", "Data do pedido", "Capturada em", "Acoes"].map((header) => (
                        <th key={header} className="p-3 text-left font-medium">{header}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-03">
                    {captured.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="p-10 text-center text-sm text-stone">
                          Nenhuma compra capturada ainda. Ative a captura automatica nas Configuracoes.
                        </td>
                      </tr>
                    ) : captured.map((cap) => (
                      <tr key={cap.id} className="transition-colors hover:bg-surface-03/25">
                        <td className="p-3">
                          <span className={`rounded-full px-2 py-1 text-xs font-semibold ${CAPTURED_STATUS_COLOR[cap.status] ?? "bg-surface-03 text-stone"}`}>
                            {CAPTURED_STATUS_LABEL[cap.status] ?? cap.status}
                          </span>
                        </td>
                        <td className="p-3 text-cream">{cap.buyer_name ?? "-"}</td>
                        <td className="p-3 text-stone">{cap.product_name ?? "-"}</td>
                        <td className="p-3 text-stone">{cap.neighborhood ?? "-"}</td>
                        <td className="p-3 text-stone">{fmtDate(cap.order_time)}</td>
                        <td className="p-3 text-stone">{fmtDate(cap.created_at)}</td>
                        <td className="p-3">
                          {cap.status === "pending" && (
                            <div className="flex items-center gap-1">
                              <button
                                onClick={() => openActivateCaptured(cap)}
                                className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs font-medium text-green-400 hover:bg-green-500/10"
                                title="Configurar e ativar"
                              >
                                <CheckCircle2 size={14} /> Ativar
                              </button>
                              <button
                                onClick={() => discardCaptured(cap.id)}
                                className="rounded-lg p-1.5 text-stone hover:bg-red-500/10 hover:text-red-400"
                                title="Descartar"
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            <SettingsCard title="Exibicao na loja">
              <ToggleRow label="Ativar notificacoes na loja" checked={settings.enabled} onChange={(enabled) => setSettings((s) => ({ ...s, enabled }))} />
              <ToggleRow label="Capturar pedidos reais automaticamente para revisao" checked={settings.real_orders_enabled} onChange={(real_orders_enabled) => setSettings((s) => ({ ...s, real_orders_enabled }))} />
              <ToggleRow label="Exibir somente durante horario de funcionamento" checked={settings.only_during_store_hours} onChange={(only_during_store_hours) => setSettings((s) => ({ ...s, only_during_store_hours }))} />
            </SettingsCard>

            <SettingsCard title="Temporizador de aparicao">
              <p className="text-xs text-stone">Controle em quantos segundos a notificacao aparece apos o cliente entrar na loja e o intervalo entre exibicoes.</p>
              <div className="grid grid-cols-3 gap-3">
                <NumberField
                  label="Aparicao inicial (seg)"
                  value={settings.initial_delay_seconds}
                  onChange={(initial_delay_seconds) => setSettings((s) => ({ ...s, initial_delay_seconds }))}
                />
                <NumberField
                  label="Min. entre exibicoes"
                  value={settings.min_delay_seconds}
                  onChange={(min_delay_seconds) => setSettings((s) => ({ ...s, min_delay_seconds }))}
                />
                <NumberField
                  label="Max. entre exibicoes"
                  value={settings.max_delay_seconds}
                  onChange={(max_delay_seconds) => setSettings((s) => ({ ...s, max_delay_seconds }))}
                />
              </div>
              <NumberField
                label="Tempo padrao de exibicao (seg)"
                value={settings.default_display_seconds}
                onChange={(default_display_seconds) => setSettings((s) => ({ ...s, default_display_seconds }))}
              />
            </SettingsCard>

            <SettingsCard title="Regras de sequencia">
              <ToggleRow label="Impedir mesmo produto em sequencia" checked={settings.prevent_same_product_sequence} onChange={(prevent_same_product_sequence) => setSettings((s) => ({ ...s, prevent_same_product_sequence }))} />
              <ToggleRow label="Impedir mesmo bairro em sequencia" checked={settings.prevent_same_neighborhood_sequence} onChange={(prevent_same_neighborhood_sequence) => setSettings((s) => ({ ...s, prevent_same_neighborhood_sequence }))} />
            </SettingsCard>

            <div className="rounded-2xl border border-surface-03 bg-surface-02 p-5 lg:col-span-2">
              <h2 className="text-sm font-semibold text-cream">Paginas permitidas</h2>
              <div className="mt-4 flex flex-wrap gap-2">
                {PAGE_OPTIONS.map((page) => (
                  <button
                    key={page.id}
                    type="button"
                    onClick={() => togglePage(page.id)}
                    className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${settings.allowed_pages.includes(page.id) ? "border-gold bg-gold/15 text-gold" : "border-surface-03 bg-surface-03 text-stone hover:text-cream"}`}
                  >
                    {page.label}
                  </button>
                ))}
              </div>
              <button
                type="button"
                onClick={saveSettings}
                disabled={saving}
                className="mt-5 inline-flex items-center gap-2 rounded-xl bg-gold px-4 py-2 text-sm font-semibold text-black transition-colors hover:bg-gold/90 disabled:opacity-60"
              >
                {saving && <Loader2 size={14} className="animate-spin" />}
                Salvar configuracoes
              </button>
            </div>
          </div>
        )}

        {preview && (
          <div className="rounded-2xl border border-gold/25 bg-gold/10 p-4 text-sm text-cream">
            <span className="text-gold">Pre-visualizacao:</span> {preview}
          </div>
        )}
      </div>

      {isFormOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="max-h-[92dvh] w-full max-w-4xl overflow-y-auto rounded-2xl border border-surface-03 bg-surface-02 shadow-2xl">
            <div className="sticky top-0 z-10 flex items-center justify-between border-b border-surface-03 bg-surface-02 p-5">
              <h2 className="text-lg font-semibold text-cream">
                {activatingCaptured
                  ? "Configurar e ativar notificacao capturada"
                  : editingId
                  ? "Editar notificacao"
                  : "Nova notificacao"}
              </h2>
              <button
                type="button"
                onClick={() => { setShowForm(false); setActivatingCaptured(null); }}
                className="text-stone hover:text-cream"
              >
                <X size={18} />
              </button>
            </div>

            {activatingCaptured && (
              <div className="mx-5 mt-4 rounded-xl border border-gold/20 bg-gold/10 p-3 text-xs text-stone">
                <span className="font-medium text-gold">Pedido original:</span>{" "}
                {activatingCaptured.buyer_name ?? "Cliente"} — {activatingCaptured.product_name ?? "Produto"}
                {activatingCaptured.neighborhood ? ` — ${activatingCaptured.neighborhood}` : ""}
                {activatingCaptured.order_time ? ` — ${fmtDate(activatingCaptured.order_time)}` : ""}
              </div>
            )}

            <form onSubmit={saveForm} className="grid gap-4 p-5 md:grid-cols-2">
              {!activatingCaptured && (
                <>
                  <Field label="Status">
                    <select className={IC} value={form.status} onChange={(e) => setForm((f) => ({ ...f, status: e.target.value as ApiStoreNotificationStatus }))}>
                      <option value="active">Ativa</option>
                      <option value="paused">Pausada</option>
                    </select>
                  </Field>
                  <Field label="Tipo da notificacao">
                    <select className={IC} value={form.type} onChange={(e) => setForm((f) => ({ ...f, type: e.target.value as ApiStoreNotificationType }))}>
                      <option value="manual">Manual</option>
                      <option value="fomento">Fomento</option>
                    </select>
                  </Field>
                </>
              )}
              <Field label="Nome interno">
                <input className={IC} required value={form.internal_name} onChange={(e) => setForm((f) => ({ ...f, internal_name: e.target.value }))} />
              </Field>
              <Field label="Nome exibido">
                <input className={IC} required value={form.display_name} onChange={(e) => setForm((f) => ({ ...f, display_name: e.target.value }))} />
              </Field>
              <Field label="Produto">
                <select className={IC} required value={form.product_id} onChange={(e) => setForm((f) => ({ ...f, product_id: e.target.value }))}>
                  <option value="">Selecione</option>
                  {activeProducts.map((product) => (
                    <option key={product.id} value={product.id}>{product.name}</option>
                  ))}
                </select>
              </Field>
              <Field label="Bairro exibido">
                <input className={IC} value={form.neighborhood ?? ""} onChange={(e) => setForm((f) => ({ ...f, neighborhood: e.target.value }))} />
              </Field>
              <Field label="Horario inicial">
                <input className={IC} required type="time" value={form.start_time} onChange={(e) => setForm((f) => ({ ...f, start_time: e.target.value }))} />
              </Field>
              <Field label="Horario final">
                <input className={IC} required type="time" value={form.end_time} onChange={(e) => setForm((f) => ({ ...f, end_time: e.target.value }))} />
              </Field>
              <Field label="Tempo de apresentacao (seg)">
                <input className={IC} required min={3} type="number" value={form.display_seconds} onChange={(e) => setForm((f) => ({ ...f, display_seconds: Number(e.target.value) }))} />
              </Field>
              <Field label="Prioridade">
                <select className={IC} value={form.priority} onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value as ApiStoreNotificationPriority }))}>
                  <option value="low">Baixa</option>
                  <option value="medium">Media</option>
                  <option value="high">Alta</option>
                </select>
              </Field>
              <Field label="Frequencia / peso">
                <input className={IC} required min={1} type="number" value={form.weight} onChange={(e) => setForm((f) => ({ ...f, weight: Number(e.target.value) }))} />
              </Field>
              <Field label="Data inicial opcional">
                <input className={IC} type="date" value={form.start_date ?? ""} onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value || null }))} />
              </Field>
              <Field label="Data final opcional">
                <input className={IC} type="date" value={form.end_date ?? ""} onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value || null }))} />
              </Field>
              <div className="space-y-2 md:col-span-2">
                <label className="text-xs text-stone">Dias da semana</label>
                <div className="flex flex-wrap gap-2">
                  {WEEKDAYS.map((day) => (
                    <button
                      key={day.id}
                      type="button"
                      onClick={() => toggleDay(day.id)}
                      className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${form.weekdays.includes(day.id) ? "border-gold bg-gold/15 text-gold" : "border-surface-03 bg-surface-03 text-stone hover:text-cream"}`}
                    >
                      {day.label}
                    </button>
                  ))}
                </div>
              </div>
              <Field label="Texto / modelo da notificacao" className="md:col-span-2">
                <textarea className={`${IC} min-h-24`} required value={form.template_text} onChange={(e) => setForm((f) => ({ ...f, template_text: e.target.value }))} />
              </Field>
              {preview && (
                <div className="rounded-xl border border-gold/20 bg-gold/10 p-3 text-sm text-cream md:col-span-2">
                  {preview}
                </div>
              )}
              <div className="flex flex-col-reverse gap-3 pt-2 sm:flex-row md:col-span-2">
                <button
                  type="button"
                  onClick={() => { setShowForm(false); setActivatingCaptured(null); }}
                  className="flex-1 rounded-xl border border-surface-03 px-4 py-2 text-sm text-stone hover:text-cream"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={previewForm}
                  className="flex-1 rounded-xl border border-surface-03 bg-surface-03 px-4 py-2 text-sm text-cream hover:border-gold/50"
                >
                  Pre-visualizar
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 rounded-xl bg-gold px-4 py-2 text-sm font-semibold text-black hover:bg-gold/90 disabled:opacity-60"
                >
                  {saving ? "Salvando..." : activatingCaptured ? "Ativar notificacao" : "Salvar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}

function Field({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  return (
    <label className={`space-y-1 ${className}`}>
      <span className="text-xs text-stone">{label}</span>
      {children}
    </label>
  );
}

function SettingsCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="space-y-4 rounded-2xl border border-surface-03 bg-surface-02 p-5">
      <h2 className="text-sm font-semibold text-cream">{title}</h2>
      {children}
    </div>
  );
}

function ToggleRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className="flex w-full items-center justify-between rounded-xl border border-surface-03 bg-surface-03/50 px-3 py-2 text-left text-sm text-cream"
    >
      <span>{label}</span>
      <span className={`h-6 w-11 rounded-full p-0.5 transition-colors ${checked ? "bg-gold" : "bg-surface-01"}`}>
        <span className={`block h-5 w-5 rounded-full bg-white transition-transform ${checked ? "translate-x-5" : ""}`} />
      </span>
    </button>
  );
}

function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label className="space-y-1">
      <span className="text-xs text-stone">{label}</span>
      <input className={IC} min={0} type="number" value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  );
}
