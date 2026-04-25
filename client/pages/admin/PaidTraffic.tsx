import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import {
  Activity,
  BarChart3,
  CheckCircle2,
  Copy,
  Download,
  ExternalLink,
  Filter,
  Globe2,
  LineChart,
  Link2,
  Loader2,
  Megaphone,
  PauseCircle,
  PlugZap,
  Plus,
  RefreshCcw,
  Save,
  Settings,
  Trash2,
  XCircle,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import {
  couponsApi,
  paidTrafficApi,
  productsApi,
  type AdIntegration,
  type ApiCoupon,
  type ApiProduct,
  type CampaignLink,
  type CampaignSettings,
  type PaidTrafficDashboard,
  type TrafficCampaign,
} from "@/lib/api";

type Tab = "dashboard" | "campanhas" | "links" | "relatorios" | "integracoes" | "configuracoes";

type CampaignForm = {
  name: string;
  platform: string;
  status: string;
  daily_budget: string;
  total_budget: string;
  start_date: string;
  end_date: string;
  product_id: string;
  coupon_id: string;
  destination_url: string;
  notes: string;
};

const tabs: Array<{ id: Tab; label: string; icon: typeof BarChart3 }> = [
  { id: "dashboard", label: "Dashboard", icon: BarChart3 },
  { id: "campanhas", label: "Campanhas", icon: Megaphone },
  { id: "links", label: "Links", icon: Link2 },
  { id: "relatorios", label: "Relatorios", icon: LineChart },
  { id: "integracoes", label: "Integracoes", icon: PlugZap },
  { id: "configuracoes", label: "Configuracoes", icon: Settings },
];

const platforms = [
  { value: "meta", label: "Meta Ads" },
  { value: "google", label: "Google Ads" },
  { value: "tiktok", label: "TikTok Ads" },
  { value: "manual", label: "Manual" },
];

const initialCampaignForm: CampaignForm = {
  name: "",
  platform: "manual",
  status: "draft",
  daily_budget: "",
  total_budget: "",
  start_date: "",
  end_date: "",
  product_id: "",
  coupon_id: "",
  destination_url: "",
  notes: "",
};

const formatCurrency = (value: number | null | undefined) =>
  (value ?? 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const formatPercent = (value: number | null | undefined) =>
  `${(((value ?? 0) > 1 ? value ?? 0 : (value ?? 0) * 100)).toLocaleString("pt-BR", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}%`;

const fieldBase =
  "w-full rounded-xl border border-surface-03 bg-surface-03/70 px-3 py-2.5 text-sm text-cream outline-none transition focus:border-gold";

function numberOrNull(value: string) {
  if (value.trim() === "") return null;
  const parsed = Number(value.replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

function campaignToForm(campaign: TrafficCampaign): CampaignForm {
  return {
    name: campaign.name,
    platform: campaign.platform,
    status: campaign.status,
    daily_budget: campaign.daily_budget == null ? "" : String(campaign.daily_budget),
    total_budget: campaign.total_budget == null ? "" : String(campaign.total_budget),
    start_date: campaign.start_date ?? "",
    end_date: campaign.end_date ?? "",
    product_id: campaign.product_id ?? "",
    coupon_id: campaign.coupon_id ?? "",
    destination_url: campaign.destination_url ?? "",
    notes: campaign.notes ?? "",
  };
}

function platformLabel(value: string | null | undefined) {
  return platforms.find((platform) => platform.value === value)?.label ?? value ?? "Manual";
}

export default function AdminPaidTraffic() {
  const [activeTab, setActiveTab] = useState<Tab>("dashboard");
  const [dashboard, setDashboard] = useState<PaidTrafficDashboard | null>(null);
  const [campaigns, setCampaigns] = useState<TrafficCampaign[]>([]);
  const [links, setLinks] = useState<CampaignLink[]>([]);
  const [integrations, setIntegrations] = useState<AdIntegration[]>([]);
  const [settings, setSettings] = useState<CampaignSettings | null>(null);
  const [products, setProducts] = useState<ApiProduct[]>([]);
  const [coupons, setCoupons] = useState<ApiCoupon[]>([]);
  const [campaignForm, setCampaignForm] = useState<CampaignForm>(initialCampaignForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [linkCampaignId, setLinkCampaignId] = useState("");
  const [linkName, setLinkName] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [integrationDraft, setIntegrationDraft] = useState<Record<string, { token: string; account: string }>>({});
  const [settingsDraft, setSettingsDraft] = useState({
    attribution_window_days: "7",
    attribution_model: "last_click",
    default_margin: "0.35",
    target_roas: "3",
    tracking_enabled: true,
  });

  const campaignById = useMemo(() => new Map(campaigns.map((campaign) => [campaign.id, campaign])), [campaigns]);
  const productById = useMemo(() => new Map(products.map((product) => [product.id, product])), [products]);
  const couponById = useMemo(() => new Map(coupons.map((coupon) => [coupon.id, coupon])), [coupons]);

  const loadAll = async () => {
    setLoading(true);
    setError("");
    const [dashRes, campaignRes, linkRes, integrationRes, settingsRes, productRes, couponRes] =
      await Promise.allSettled([
        paidTrafficApi.dashboard(),
        paidTrafficApi.campaigns(),
        paidTrafficApi.links(),
        paidTrafficApi.integrations(),
        paidTrafficApi.settings(),
        productsApi.list(false),
        couponsApi.list(),
      ]);

    if (dashRes.status === "fulfilled") setDashboard(dashRes.value);
    if (campaignRes.status === "fulfilled") setCampaigns(campaignRes.value);
    if (linkRes.status === "fulfilled") setLinks(linkRes.value);
    if (integrationRes.status === "fulfilled") setIntegrations(integrationRes.value);
    if (settingsRes.status === "fulfilled") {
      setSettings(settingsRes.value);
      setSettingsDraft({
        attribution_window_days: String(settingsRes.value.attribution_window_days),
        attribution_model: settingsRes.value.attribution_model,
        default_margin: String(settingsRes.value.default_margin),
        target_roas: String(settingsRes.value.target_roas),
        tracking_enabled: settingsRes.value.tracking_enabled,
      });
    }
    if (productRes.status === "fulfilled") setProducts(productRes.value);
    if (couponRes.status === "fulfilled") setCoupons(couponRes.value);

    if ([dashRes, campaignRes, linkRes, integrationRes, settingsRes].some((res) => res.status === "rejected")) {
      setError("Nao foi possivel carregar todos os dados de trafego pago.");
    }
    setLoading(false);
  };

  const refreshDashboard = async () => {
    try {
      setDashboard(await paidTrafficApi.dashboard());
    } catch {
      setError("Nao foi possivel atualizar o dashboard.");
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  useEffect(() => {
    if (activeTab !== "dashboard") return;
    const interval = window.setInterval(refreshDashboard, 60000);
    return () => window.clearInterval(interval);
  }, [activeTab]);

  useEffect(() => {
    if (!linkCampaignId && campaigns[0]) setLinkCampaignId(campaigns[0].id);
  }, [campaigns, linkCampaignId]);

  const submitCampaign = async (event: FormEvent) => {
    event.preventDefault();
    if (!campaignForm.name.trim()) {
      alert("Informe o nome da campanha.");
      return;
    }
    setSaving(true);
    const payload = {
      name: campaignForm.name.trim(),
      platform: campaignForm.platform,
      status: campaignForm.status,
      daily_budget: numberOrNull(campaignForm.daily_budget),
      total_budget: numberOrNull(campaignForm.total_budget),
      start_date: campaignForm.start_date || null,
      end_date: campaignForm.end_date || null,
      product_id: campaignForm.product_id || null,
      coupon_id: campaignForm.coupon_id || null,
      destination_url: campaignForm.destination_url || null,
      notes: campaignForm.notes || null,
    };
    try {
      const saved = editingId
        ? await paidTrafficApi.updateCampaign(editingId, payload)
        : await paidTrafficApi.createCampaign(payload);
      setCampaigns((prev) => {
        if (editingId) return prev.map((campaign) => (campaign.id === saved.id ? saved : campaign));
        return [saved, ...prev];
      });
      setCampaignForm(initialCampaignForm);
      setEditingId(null);
      setActiveTab("campanhas");
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao salvar campanha.");
    } finally {
      setSaving(false);
    }
  };

  const editCampaign = (campaign: TrafficCampaign) => {
    setCampaignForm(campaignToForm(campaign));
    setEditingId(campaign.id);
    setActiveTab("campanhas");
  };

  const removeCampaign = async (campaign: TrafficCampaign) => {
    if (!confirm(`Remover a campanha "${campaign.name}"?`)) return;
    try {
      await paidTrafficApi.removeCampaign(campaign.id);
      setCampaigns((prev) => prev.filter((item) => item.id !== campaign.id));
      setLinks((prev) => prev.filter((item) => item.campaign_id !== campaign.id));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao remover campanha.");
    }
  };

  const createLink = async () => {
    if (!linkCampaignId) {
      alert("Selecione uma campanha.");
      return;
    }
    try {
      const created = await paidTrafficApi.createLink({
        campaign_id: linkCampaignId,
        name: linkName || undefined,
      });
      setLinks((prev) => [created, ...prev]);
      setLinkName("");
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao gerar link.");
    }
  };

  const copyLink = async (url: string) => {
    await navigator.clipboard?.writeText(url);
  };

  const saveIntegration = async (platform: string) => {
    const draft = integrationDraft[platform] ?? { token: "", account: "" };
    if (!draft.token.trim()) {
      alert("Cole o token de acesso para conectar.");
      return;
    }
    try {
      const saved = await paidTrafficApi.saveIntegration({
        platform,
        access_token: draft.token.trim(),
        account_name: draft.account.trim() || undefined,
      });
      setIntegrations((prev) => {
        const others = prev.filter((item) => item.platform !== platform);
        return [...others, saved].sort((a, b) => a.platform.localeCompare(b.platform));
      });
      setIntegrationDraft((prev) => ({ ...prev, [platform]: { token: "", account: "" } }));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao conectar integracao.");
    }
  };

  const disconnectIntegration = async (platform: string) => {
    try {
      const saved = await paidTrafficApi.disconnectIntegration(platform);
      setIntegrations((prev) => {
        const others = prev.filter((item) => item.platform !== platform);
        return [...others, saved].sort((a, b) => a.platform.localeCompare(b.platform));
      });
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao desconectar integracao.");
    }
  };

  const syncIntegration = async (platform: string) => {
    try {
      const result = await paidTrafficApi.syncIntegration(platform);
      alert(result.message);
      await loadAll();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao sincronizar integracao.");
    }
  };

  const saveSettings = async (event: FormEvent) => {
    event.preventDefault();
    try {
      const saved = await paidTrafficApi.updateSettings({
        attribution_window_days: Number(settingsDraft.attribution_window_days),
        attribution_model: settingsDraft.attribution_model,
        default_margin: Number(settingsDraft.default_margin),
        target_roas: Number(settingsDraft.target_roas),
        tracking_enabled: settingsDraft.tracking_enabled,
      });
      setSettings(saved);
      alert("Configuracoes salvas.");
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao salvar configuracoes.");
    }
  };

  const exportCsv = () => {
    const rows = [
      ["Campanha", "Plataforma", "Investimento", "Receita real", "Pedidos", "ROAS real", "ROAS plataforma", "Diferenca"],
      ...(dashboard?.by_campaign ?? []).map((row) => [
        row.name ?? "",
        platformLabel(row.platform),
        String(row.spend ?? 0),
        String(row.revenue ?? 0),
        String(row.orders ?? 0),
        String(row.roas ?? 0),
        String(row.platform_roas ?? ""),
        String((row.roas ?? 0) - (row.platform_roas ?? 0)),
      ]),
    ];
    const csv = rows.map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(";")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "relatorio-trafego-pago.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-surface-00 flex flex-col md:flex-row md:h-screen overflow-hidden">
      <AdminSidebar />

      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="bg-surface-02 border-b border-surface-03 px-4 md:px-8 py-4 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div>
            <p className="text-gold text-xs font-bold uppercase tracking-[0.24em]">Analytics e anuncios</p>
            <h1 className="text-cream text-2xl font-black mt-1">Trafego Pago</h1>
            <p className="text-stone text-sm mt-1">Receita real dos pedidos, investimento das plataformas e atribuicao por UTM.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button onClick={refreshDashboard} className="inline-flex items-center gap-2 rounded-xl border border-surface-03 bg-surface-03 px-4 py-2 text-sm font-semibold text-parchment hover:text-cream">
              <RefreshCcw size={16} /> Atualizar
            </button>
            <button onClick={() => setActiveTab("campanhas")} className="inline-flex items-center gap-2 rounded-xl bg-gold px-4 py-2 text-sm font-bold text-cream hover:bg-gold/90">
              <Plus size={16} /> Nova campanha
            </button>
          </div>
        </header>

        <section className="border-b border-surface-03 bg-surface-00 px-4 md:px-8 py-3">
          <div className="flex gap-2 overflow-x-auto">
            {tabs.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold whitespace-nowrap transition ${
                  activeTab === id ? "bg-gold text-cream" : "bg-surface-02 text-stone hover:text-cream"
                }`}
              >
                <Icon size={16} />
                {label}
              </button>
            ))}
          </div>
        </section>

        <div className="flex-1 overflow-y-auto p-4 md:p-8">
          {error && <div className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}

          {loading ? (
            <div className="flex h-80 items-center justify-center">
              <Loader2 className="animate-spin text-gold" size={36} />
            </div>
          ) : (
            <>
              {activeTab === "dashboard" && (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
                    <MetricCard label="Investimento" value={formatCurrency(dashboard?.spend)} icon={Activity} />
                    <MetricCard label="Receita real" value={formatCurrency(dashboard?.revenue)} icon={BarChart3} />
                    <MetricCard label="Lucro estimado" value={formatCurrency(dashboard?.estimated_profit)} icon={LineChart} />
                    <MetricCard label="ROAS real" value={`${(dashboard?.roas ?? 0).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}x`} icon={Megaphone} />
                    <MetricCard label="ROI" value={formatPercent(dashboard?.roi)} icon={LineChart} />
                    <MetricCard label="CPA" value={formatCurrency(dashboard?.cpa)} icon={Filter} />
                    <MetricCard label="Ticket medio" value={formatCurrency(dashboard?.average_ticket)} icon={Globe2} />
                    <MetricCard label="Conversao" value={formatPercent(dashboard?.conversion_rate)} icon={CheckCircle2} />
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                    <MiniStat label="Pedidos" value={dashboard?.orders ?? 0} />
                    <MiniStat label="Visitantes" value={dashboard?.visitors ?? 0} />
                    <MiniStat label="Carrinhos abandonados" value={dashboard?.abandoned_carts ?? 0} />
                  </div>

                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                    <Panel title="Resultado por campanha">
                      <CampaignPerformanceTable rows={dashboard?.by_campaign ?? []} />
                    </Panel>
                    <Panel title="Resultado por plataforma">
                      <PlatformPerformance rows={dashboard?.by_platform ?? []} />
                    </Panel>
                  </div>
                </div>
              )}

              {activeTab === "campanhas" && (
                <div className="grid grid-cols-1 xl:grid-cols-[minmax(320px,420px)_1fr] gap-5">
                  <Panel title={editingId ? "Editar campanha" : "Nova campanha"}>
                    <form onSubmit={submitCampaign} className="space-y-3">
                      <Field label="Nome">
                        <input className={fieldBase} value={campaignForm.name} onChange={(e) => setCampaignForm((prev) => ({ ...prev, name: e.target.value }))} placeholder="Promo pizza brotinho" />
                      </Field>
                      <div className="grid grid-cols-2 gap-3">
                        <Field label="Plataforma">
                          <select className={fieldBase} value={campaignForm.platform} onChange={(e) => setCampaignForm((prev) => ({ ...prev, platform: e.target.value }))}>
                            {platforms.map((platform) => <option key={platform.value} value={platform.value}>{platform.label}</option>)}
                          </select>
                        </Field>
                        <Field label="Status">
                          <select className={fieldBase} value={campaignForm.status} onChange={(e) => setCampaignForm((prev) => ({ ...prev, status: e.target.value }))}>
                            <option value="draft">Rascunho</option>
                            <option value="active">Ativa</option>
                            <option value="paused">Pausada</option>
                            <option value="ended">Encerrada</option>
                          </select>
                        </Field>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <Field label="Orcamento diario">
                          <input className={fieldBase} value={campaignForm.daily_budget} onChange={(e) => setCampaignForm((prev) => ({ ...prev, daily_budget: e.target.value }))} inputMode="decimal" />
                        </Field>
                        <Field label="Orcamento total">
                          <input className={fieldBase} value={campaignForm.total_budget} onChange={(e) => setCampaignForm((prev) => ({ ...prev, total_budget: e.target.value }))} inputMode="decimal" />
                        </Field>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <Field label="Inicio">
                          <input type="date" className={fieldBase} value={campaignForm.start_date} onChange={(e) => setCampaignForm((prev) => ({ ...prev, start_date: e.target.value }))} />
                        </Field>
                        <Field label="Fim">
                          <input type="date" className={fieldBase} value={campaignForm.end_date} onChange={(e) => setCampaignForm((prev) => ({ ...prev, end_date: e.target.value }))} />
                        </Field>
                      </div>
                      <Field label="Produto vinculado">
                        <select className={fieldBase} value={campaignForm.product_id} onChange={(e) => setCampaignForm((prev) => ({ ...prev, product_id: e.target.value }))}>
                          <option value="">Nenhum produto</option>
                          {products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}
                        </select>
                      </Field>
                      <Field label="Cupom vinculado">
                        <select className={fieldBase} value={campaignForm.coupon_id} onChange={(e) => setCampaignForm((prev) => ({ ...prev, coupon_id: e.target.value }))}>
                          <option value="">Nenhum cupom</option>
                          {coupons.map((coupon) => <option key={coupon.id} value={coupon.id}>{coupon.code}</option>)}
                        </select>
                      </Field>
                      <Field label="URL destino">
                        <input className={fieldBase} value={campaignForm.destination_url} onChange={(e) => setCampaignForm((prev) => ({ ...prev, destination_url: e.target.value }))} placeholder="https://delivery.moschettieri.com.br/" />
                      </Field>
                      <Field label="Observacoes">
                        <textarea className={`${fieldBase} min-h-20`} value={campaignForm.notes} onChange={(e) => setCampaignForm((prev) => ({ ...prev, notes: e.target.value }))} />
                      </Field>
                      <div className="flex gap-2">
                        <button disabled={saving} className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl bg-gold px-4 py-3 text-sm font-bold text-cream disabled:opacity-60">
                          {saving ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />} Salvar
                        </button>
                        {editingId && (
                          <button type="button" onClick={() => { setEditingId(null); setCampaignForm(initialCampaignForm); }} className="rounded-xl border border-surface-03 px-4 py-3 text-sm font-semibold text-stone hover:text-cream">
                            Cancelar
                          </button>
                        )}
                      </div>
                    </form>
                  </Panel>

                  <Panel title="Campanhas cadastradas">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                      {campaigns.map((campaign) => (
                        <div key={campaign.id} className="rounded-2xl border border-surface-03 bg-surface-03/40 p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <h3 className="text-cream font-bold">{campaign.name}</h3>
                              <p className="text-stone text-xs mt-1">{platformLabel(campaign.platform)} · {campaign.status}</p>
                            </div>
                            <StatusBadge status={campaign.status} />
                          </div>
                          <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
                            <Info label="Diario" value={formatCurrency(campaign.daily_budget)} />
                            <Info label="Total" value={formatCurrency(campaign.total_budget)} />
                            <Info label="Produto" value={campaign.product_id ? productById.get(campaign.product_id)?.name ?? "Produto" : "Nao vinculado"} />
                            <Info label="Cupom" value={campaign.coupon_id ? couponById.get(campaign.coupon_id)?.code ?? "Cupom" : "Nao vinculado"} />
                          </div>
                          <div className="mt-4 flex gap-2">
                            <button onClick={() => editCampaign(campaign)} className="flex-1 rounded-xl bg-surface-02 px-3 py-2 text-sm font-semibold text-parchment hover:text-cream">Editar</button>
                            <button onClick={() => removeCampaign(campaign)} className="rounded-xl bg-red-500/10 px-3 py-2 text-red-300 hover:bg-red-500/20"><Trash2 size={16} /></button>
                          </div>
                        </div>
                      ))}
                      {campaigns.length === 0 && <EmptyState title="Nenhuma campanha criada" text="Crie a primeira campanha para gerar links UTM e atribuir pedidos reais." />}
                    </div>
                  </Panel>
                </div>
              )}

              {activeTab === "links" && (
                <div className="space-y-5">
                  <Panel title="Gerador de link rastreavel">
                    <div className="grid grid-cols-1 lg:grid-cols-[1fr_1fr_auto] gap-3">
                      <select className={fieldBase} value={linkCampaignId} onChange={(e) => setLinkCampaignId(e.target.value)}>
                        {campaigns.map((campaign) => <option key={campaign.id} value={campaign.id}>{campaign.name}</option>)}
                      </select>
                      <input className={fieldBase} value={linkName} onChange={(e) => setLinkName(e.target.value)} placeholder="Nome do criativo ou publico" />
                      <button onClick={createLink} className="inline-flex items-center justify-center gap-2 rounded-xl bg-gold px-4 py-2.5 text-sm font-bold text-cream">
                        <Plus size={16} /> Gerar link
                      </button>
                    </div>
                  </Panel>

                  <Panel title="Links gerados">
                    <div className="space-y-3">
                      {links.map((link) => (
                        <div key={link.id} className="rounded-2xl border border-surface-03 bg-surface-03/40 p-4">
                          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
                            <div className="min-w-0">
                              <p className="text-cream font-bold">{link.name || campaignById.get(link.campaign_id)?.name || "Link de campanha"}</p>
                              <p className="text-stone text-xs mt-1 break-all">{link.final_url}</p>
                            </div>
                            <div className="flex gap-2">
                              <button onClick={() => copyLink(link.final_url)} className="inline-flex items-center gap-2 rounded-xl bg-surface-02 px-3 py-2 text-sm text-parchment hover:text-cream"><Copy size={15} /> Copiar</button>
                              <a href={link.final_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-xl bg-surface-02 px-3 py-2 text-sm text-parchment hover:text-cream"><ExternalLink size={15} /> Abrir</a>
                            </div>
                          </div>
                        </div>
                      ))}
                      {links.length === 0 && <EmptyState title="Nenhum link gerado" text="Selecione uma campanha e gere um link com UTM automaticamente." />}
                    </div>
                  </Panel>
                </div>
              )}

              {activeTab === "relatorios" && (
                <Panel title="Relatorio avancado">
                  <div className="mb-4 flex justify-end">
                    <button onClick={exportCsv} className="inline-flex items-center gap-2 rounded-xl border border-surface-03 bg-surface-03 px-4 py-2 text-sm font-semibold text-parchment hover:text-cream">
                      <Download size={16} /> Exportar CSV
                    </button>
                  </div>
                  <CampaignPerformanceTable rows={dashboard?.by_campaign ?? []} advanced />
                </Panel>
              )}

              {activeTab === "integracoes" && (
                <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
                  {platforms.filter((platform) => platform.value !== "manual").map((platform) => {
                    const integration = integrations.find((item) => item.platform === platform.value);
                    const draft = integrationDraft[platform.value] ?? { token: "", account: "" };
                    const connected = integration?.status === "connected";
                    return (
                      <div key={platform.value} className="rounded-2xl border border-surface-03 bg-surface-02 p-5">
                        <div className="flex items-start justify-between">
                          <div>
                            <h3 className="text-cream font-black">{platform.label}</h3>
                            <p className="text-stone text-xs mt-1">{connected ? "Conectado" : "Desconectado"}</p>
                          </div>
                          {connected ? <CheckCircle2 className="text-green-400" /> : <XCircle className="text-red-300" />}
                        </div>
                        <div className="mt-4 space-y-3">
                          <Field label="Conta vinculada">
                            <input className={fieldBase} value={draft.account} onChange={(e) => setIntegrationDraft((prev) => ({ ...prev, [platform.value]: { ...draft, account: e.target.value } }))} placeholder={integration?.account_name || "Nome da conta"} />
                          </Field>
                          <Field label="Access token">
                            <input type="password" className={fieldBase} value={draft.token} onChange={(e) => setIntegrationDraft((prev) => ({ ...prev, [platform.value]: { ...draft, token: e.target.value } }))} placeholder={connected ? "Token salvo e mascarado" : "Cole o token da plataforma"} />
                          </Field>
                          {integration?.last_error && <p className="text-red-300 text-xs">{integration.last_error}</p>}
                          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                            <button onClick={() => saveIntegration(platform.value)} className="rounded-xl bg-gold px-3 py-2 text-sm font-bold text-cream">Conectar</button>
                            <button onClick={() => syncIntegration(platform.value)} className="rounded-xl bg-surface-03 px-3 py-2 text-sm font-semibold text-parchment hover:text-cream">Testar</button>
                            <button onClick={() => disconnectIntegration(platform.value)} className="rounded-xl bg-red-500/10 px-3 py-2 text-sm font-semibold text-red-300">Desconectar</button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {activeTab === "configuracoes" && (
                <Panel title="Configuracoes de atribuicao">
                  <form onSubmit={saveSettings} className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-3xl">
                    <Field label="Janela de atribuicao (dias)">
                      <input className={fieldBase} value={settingsDraft.attribution_window_days} onChange={(e) => setSettingsDraft((prev) => ({ ...prev, attribution_window_days: e.target.value }))} inputMode="numeric" />
                    </Field>
                    <Field label="Modelo">
                      <select className={fieldBase} value={settingsDraft.attribution_model} onChange={(e) => setSettingsDraft((prev) => ({ ...prev, attribution_model: e.target.value }))}>
                        <option value="last_click">Ultimo clique</option>
                        <option value="first_click">Primeiro clique</option>
                      </select>
                    </Field>
                    <Field label="Margem padrao">
                      <input className={fieldBase} value={settingsDraft.default_margin} onChange={(e) => setSettingsDraft((prev) => ({ ...prev, default_margin: e.target.value }))} inputMode="decimal" />
                    </Field>
                    <Field label="Meta de ROAS">
                      <input className={fieldBase} value={settingsDraft.target_roas} onChange={(e) => setSettingsDraft((prev) => ({ ...prev, target_roas: e.target.value }))} inputMode="decimal" />
                    </Field>
                    <label className="md:col-span-2 flex items-center justify-between rounded-2xl border border-surface-03 bg-surface-03/40 px-4 py-3">
                      <span>
                        <span className="block text-cream text-sm font-bold">Tracking ativo</span>
                        <span className="block text-stone text-xs">Quando desligado, o backend nao registra eventos publicos.</span>
                      </span>
                      <input type="checkbox" checked={settingsDraft.tracking_enabled} onChange={(e) => setSettingsDraft((prev) => ({ ...prev, tracking_enabled: e.target.checked }))} className="h-5 w-5 accent-gold" />
                    </label>
                    <button className="md:col-span-2 inline-flex items-center justify-center gap-2 rounded-xl bg-gold px-4 py-3 text-sm font-bold text-cream">
                      <Save size={16} /> Salvar configuracoes
                    </button>
                  </form>
                  {settings && <p className="mt-4 text-stone text-xs">Ultima atualizacao: {new Date(settings.updated_at).toLocaleString("pt-BR")}</p>}
                </Panel>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-surface-03 bg-surface-02 p-4 md:p-5">
      <h2 className="text-cream text-lg font-black mb-4">{title}</h2>
      {children}
    </section>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-bold text-parchment">{label}</span>
      {children}
    </label>
  );
}

function MetricCard({ label, value, icon: Icon }: { label: string; value: string; icon: typeof BarChart3 }) {
  return (
    <div className="rounded-2xl border border-surface-03 bg-surface-02 p-4">
      <div className="flex items-center justify-between">
        <p className="text-stone text-sm font-medium">{label}</p>
        <span className="rounded-xl bg-gold/15 p-2 text-gold"><Icon size={18} /></span>
      </div>
      <p className="mt-4 text-cream text-2xl font-black">{value}</p>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-surface-03 bg-surface-02 p-4">
      <p className="text-stone text-xs font-semibold uppercase tracking-widest">{label}</p>
      <p className="text-cream text-3xl font-black mt-2">{value.toLocaleString("pt-BR")}</p>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-stone">{label}</p>
      <p className="text-cream font-semibold truncate">{value}</p>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const active = status === "active";
  const paused = status === "paused";
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold ${
      active ? "bg-green-500/15 text-green-300" : paused ? "bg-orange-500/15 text-orange-300" : "bg-surface-03 text-stone"
    }`}>
      {paused ? <PauseCircle size={12} /> : active ? <CheckCircle2 size={12} /> : <Activity size={12} />}
      {status}
    </span>
  );
}

function EmptyState({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-surface-03 p-8 text-center lg:col-span-2">
      <p className="text-cream font-bold">{title}</p>
      <p className="text-stone text-sm mt-1">{text}</p>
    </div>
  );
}

function CampaignPerformanceTable({ rows, advanced = false }: { rows: Array<Record<string, any>>; advanced?: boolean }) {
  if (!rows.length) return <EmptyState title="Sem dados no periodo" text="Os resultados aparecem quando houver eventos, pedidos pagos e metricas sincronizadas." />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead className="text-stone">
          <tr>
            <th className="py-2 pr-3">Campanha</th>
            <th className="py-2 pr-3">Plataforma</th>
            <th className="py-2 pr-3">Investimento</th>
            <th className="py-2 pr-3">Receita real</th>
            <th className="py-2 pr-3">Pedidos</th>
            <th className="py-2 pr-3">ROAS real</th>
            {advanced && <th className="py-2 pr-3">Diferenca</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.campaign_id ?? row.name} className="border-t border-surface-03 text-parchment">
              <td className="py-3 pr-3 font-bold text-cream">{row.name}</td>
              <td className="py-3 pr-3">{platformLabel(row.platform)}</td>
              <td className="py-3 pr-3">{formatCurrency(row.spend)}</td>
              <td className="py-3 pr-3">{formatCurrency(row.revenue)}</td>
              <td className="py-3 pr-3">{row.orders ?? 0}</td>
              <td className="py-3 pr-3">{(row.roas ?? 0).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}x</td>
              {advanced && <td className="py-3 pr-3">{((row.roas ?? 0) - (row.platform_roas ?? 0)).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}x</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PlatformPerformance({ rows }: { rows: Array<Record<string, any>> }) {
  if (!rows.length) return <EmptyState title="Sem plataformas com resultado" text="Conecte uma plataforma ou atribua pedidos por links UTM." />;
  return (
    <div className="space-y-3">
      {rows.map((row) => (
        <div key={row.platform} className="rounded-2xl border border-surface-03 bg-surface-03/40 p-4">
          <div className="flex items-center justify-between">
            <p className="text-cream font-bold">{platformLabel(row.platform)}</p>
            <p className="text-gold font-black">{(row.revenue && row.spend ? row.revenue / row.spend : 0).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}x</p>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-3 text-xs">
            <Info label="Investimento" value={formatCurrency(row.spend)} />
            <Info label="Receita" value={formatCurrency(row.revenue)} />
            <Info label="Pedidos" value={String(row.orders ?? 0)} />
          </div>
        </div>
      ))}
    </div>
  );
}
