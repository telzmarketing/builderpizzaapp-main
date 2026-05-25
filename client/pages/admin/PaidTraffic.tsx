import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import {
  Activity,
  BarChart3,
  CheckCircle2,
  Clock,
  Copy,
  Download,
  ExternalLink,
  Filter,
  Globe2,
  LineChart,
  Link2,
  Loader2,
  MapPin,
  Megaphone,
  Monitor,
  PauseCircle,
  PlugZap,
  Plus,
  RefreshCcw,
  Save,
  Settings,
  Trash2,
  Video,
  XCircle,
  Zap,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";
import {
  couponsApi,
  paidTrafficApi,
  productsApi,
  resolveAssetUrl,
  uploadApi,
  type AdIntegration,
  type AdsPixel,
  type ApiCoupon,
  type ApiProduct,
  type CampaignCreative,
  type CampaignLink,
  type CampaignSettings,
  type PaidTrafficDashboard,
  type PaidTrafficRealtime,
  type TrafficCampaign,
} from "@/lib/api";
import { prepareMediaFileForUpload } from "@/lib/mediaCompression";

type Tab = "dashboard" | "campanhas" | "links" | "relatorios" | "integracoes" | "pixels" | "configuracoes";

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
  // Selected weekday indices as a Set. Empty = all days.
  active_weekdays: Set<number>;
  pixel_id: string;
  pixel_events: Set<string>;
};

type PixelForm = {
  platform: string;
  pixel_id: string;
  events_tracked: Set<string>;
  conversion_access_token: string;
  base_code: string;
};

function storefrontOrigin(): string {
  return window.location.origin.replace(/\/$/, "");
}

function normalizeGeneratedLinkUrl(url: string): string {
  const value = url.trim();
  if (!value) return storefrontOrigin();
  if (/^https?:\/\//i.test(value)) return value;
  return value.startsWith("/") ? `${storefrontOrigin()}${value}` : `${storefrontOrigin()}/${value}`;
}

const tabs: Array<{ id: Tab; label: string; icon: typeof BarChart3 }> = [
  { id: "dashboard", label: "Dashboard", icon: BarChart3 },
  { id: "campanhas", label: "Campanhas", icon: Megaphone },
  { id: "links", label: "Links", icon: Link2 },
  { id: "relatorios", label: "Relatorios", icon: LineChart },
  { id: "integracoes", label: "Meta/CAPI", icon: PlugZap },
  { id: "pixels", label: "Pixels", icon: Zap },
  { id: "configuracoes", label: "Configuracoes", icon: Settings },
];

const platforms = [
  { value: "meta", label: "Meta Ads" },
  { value: "google", label: "Google Ads" },
  { value: "tiktok", label: "TikTok Ads" },
  { value: "manual", label: "Manual" },
];

const CREATIVE_IMAGE_PROXY_SAFE_BYTES = 900 * 1024;
const CREATIVE_IMAGE_MAX_BYTES = 5 * 1024 * 1024;
const CREATIVE_VIDEO_MAX_BYTES = 50 * 1024 * 1024;
const COMPRESSIBLE_CREATIVE_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const ALLOWED_CREATIVE_IMAGE_TYPES = new Set([...COMPRESSIBLE_CREATIVE_IMAGE_TYPES, "image/gif"]);

function formatUploadSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.ceil(bytes / 1024)} KB`;
}

const WEEKDAYS = [
  { index: 0, short: "Dom", long: "Domingo" },
  { index: 1, short: "Seg", long: "Segunda" },
  { index: 2, short: "Ter", long: "Terça" },
  { index: 3, short: "Qua", long: "Quarta" },
  { index: 4, short: "Qui", long: "Quinta" },
  { index: 5, short: "Sex", long: "Sexta" },
  { index: 6, short: "Sáb", long: "Sábado" },
];

function parseWeekdays(raw: string | null | undefined): Set<number> {
  if (!raw) return new Set();
  return new Set(raw.split(",").map(Number).filter((n) => n >= 0 && n <= 6));
}

function serializeWeekdays(days: Set<number>): string | null {
  if (days.size === 0) return null;
  return [...days].sort((a, b) => a - b).join(",");
}

function weekdaysLabel(raw: string | null | undefined): string {
  if (!raw) return "Todos os dias";
  const days = raw.split(",").map(Number).sort((a, b) => a - b);
  if (days.length === 7) return "Todos os dias";
  return days.map((d) => WEEKDAYS[d]?.short ?? d).join(" · ");
}

const PIXEL_EVENT_OPTIONS = ["PageView", "ViewContent", "AddToCart", "InitiateCheckout", "Purchase", "Lead"];
const DEFAULT_PIXEL_EVENTS = "PageView,ViewContent,AddToCart,InitiateCheckout,Purchase,Lead";

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
  active_weekdays: new Set(),
  pixel_id: "",
  pixel_events: new Set(["PageView", "InitiateCheckout", "Purchase"]),
};

const initialPixelForm: PixelForm = {
  platform: "meta",
  pixel_id: "",
  events_tracked: parsePixelEvents(DEFAULT_PIXEL_EVENTS),
  conversion_access_token: "",
  base_code: "",
};

const formatCurrency = (value: number | null | undefined) =>
  (value ?? 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const formatPercent = (value: number | null | undefined) =>
  `${(((value ?? 0) > 1 ? value ?? 0 : (value ?? 0) * 100)).toLocaleString("pt-BR", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}%`;

const formatDateTime = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleString("pt-BR") : "-";

const EVENT_LABELS: Record<string, string> = {
  page_view: "Visualizou pagina",
  product_viewed: "Visualizou produto",
  add_to_cart: "Adicionou ao carrinho",
  cart_item_added: "Adicionou ao carrinho",
  checkout_start: "Iniciou checkout",
  checkout_started: "Iniciou checkout",
  order_created: "Pedido criado",
  order_paid: "Pedido pago",
  location_update: "Localizacao atualizada",
};

function eventLabel(eventType: string | null | undefined) {
  if (!eventType) return "-";
  return EVENT_LABELS[eventType] ?? eventType;
}

const fieldBase =
  "w-full rounded-xl border border-surface-03 bg-surface-03/70 px-3 py-2.5 text-sm text-cream outline-none transition focus:border-gold";

function numberOrNull(value: string) {
  if (value.trim() === "") return null;
  const parsed = Number(value.replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

function parsePixelEvents(raw: string | null | undefined): Set<string> {
  if (!raw) return new Set(["PageView", "InitiateCheckout", "Purchase"]);
  return new Set(raw.split(",").map((e) => e.trim()).filter(Boolean));
}

function serializePixelEvents(events: Set<string>): string | null {
  if (events.size === 0) return null;
  return PIXEL_EVENT_OPTIONS.filter((eventName) => events.has(eventName)).join(",");
}

function extractMetaPixelId(code: string): string {
  const match = code.match(/fbq\(['"]init['"],\s*['"]([^'"]+)['"]/i);
  return match?.[1] ?? "";
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
    active_weekdays: parseWeekdays(campaign.active_weekdays),
    pixel_id: campaign.pixel_id ?? "",
    pixel_events: parsePixelEvents(campaign.pixel_events),
  };
}

function platformLabel(value: string | null | undefined) {
  return platforms.find((platform) => platform.value === value)?.label ?? value ?? "Manual";
}

export default function AdminPaidTraffic() {
  const [activeTab, setActiveTab] = useState<Tab>("dashboard");
  const [dashboard, setDashboard] = useState<PaidTrafficDashboard | null>(null);
  const [realtime, setRealtime] = useState<PaidTrafficRealtime | null>(null);
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

  const [pixels, setPixels] = useState<AdsPixel[]>([]);
  const [pixelForm, setPixelForm] = useState<PixelForm>(initialPixelForm);
  const [editingPixelId, setEditingPixelId] = useState<string | null>(null);

  const [creatives, setCreatives] = useState<Record<string, CampaignCreative[]>>({});
  const [expandedCreatives, setExpandedCreatives] = useState<Record<string, boolean>>({});
  const [uploadingCreative, setUploadingCreative] = useState<Record<string, boolean>>({});
  const [previewCreative, setPreviewCreative] = useState<CampaignCreative | null>(null);

  const campaignById = useMemo(() => new Map(campaigns.map((campaign) => [campaign.id, campaign])), [campaigns]);
  const productById = useMemo(() => new Map(products.map((product) => [product.id, product])), [products]);
  const couponById = useMemo(() => new Map(coupons.map((coupon) => [coupon.id, coupon])), [coupons]);

  const loadAll = async () => {
    setLoading(true);
    setError("");
    const [dashRes, realtimeRes, campaignRes, linkRes, integrationRes, settingsRes, productRes, couponRes, pixelRes] =
      await Promise.allSettled([
        paidTrafficApi.dashboard(),
        paidTrafficApi.realtime(),
        paidTrafficApi.campaigns(),
        paidTrafficApi.links(),
        paidTrafficApi.integrations(),
        paidTrafficApi.settings(),
        productsApi.list(false),
        couponsApi.list(),
        paidTrafficApi.pixels(),
      ]);

    if (dashRes.status === "fulfilled") setDashboard(dashRes.value);
    if (realtimeRes.status === "fulfilled") setRealtime(realtimeRes.value);
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
    if (pixelRes.status === "fulfilled") setPixels(pixelRes.value);

    if ([dashRes, campaignRes, linkRes, integrationRes, settingsRes].some((res) => res.status === "rejected")) {
      setError("Nao foi possivel carregar todos os dados de trafego pago.");
    }
    setLoading(false);
  };

  const refreshDashboard = async () => {
    try {
      const [dashboardData, realtimeData] = await Promise.all([
        paidTrafficApi.dashboard(),
        paidTrafficApi.realtime(),
      ]);
      setDashboard(dashboardData);
      setRealtime(realtimeData);
    } catch {
      setError("Nao foi possivel atualizar o dashboard.");
    }
  };

  const refreshRealtime = async () => {
    try {
      setRealtime(await paidTrafficApi.realtime());
    } catch {
      /* realtime polling must not interrupt dashboard use */
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  useEffect(() => {
    if (activeTab !== "dashboard") return;
    const dashboardInterval = window.setInterval(refreshDashboard, 60000);
    const realtimeInterval = window.setInterval(refreshRealtime, 5000);
    return () => {
      window.clearInterval(dashboardInterval);
      window.clearInterval(realtimeInterval);
    };
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
    if (campaignForm.pixel_id && campaignForm.pixel_events.size === 0) {
      alert("Selecione pelo menos um evento do pixel para esta campanha.");
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
      active_weekdays: serializeWeekdays(campaignForm.active_weekdays),
      pixel_id: campaignForm.pixel_id || null,
      pixel_events: serializePixelEvents(campaignForm.pixel_events),
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
        destination_url: storefrontOrigin(),
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

  const toggleCreatives = async (campaignId: string) => {
    const nowExpanded = !expandedCreatives[campaignId];
    setExpandedCreatives((prev) => ({ ...prev, [campaignId]: nowExpanded }));
    if (nowExpanded && !creatives[campaignId]) {
      try {
        const list = await paidTrafficApi.creatives(campaignId);
        setCreatives((prev) => ({ ...prev, [campaignId]: list }));
      } catch {
        setCreatives((prev) => ({ ...prev, [campaignId]: [] }));
      }
    }
  };

  const handleCreativeUpload = async (campaignId: string, file: File) => {
    const isVideo = file.type.startsWith("video/");
    const isImage = file.type.startsWith("image/");
    if (!isImage && !isVideo) {
      alert("Formato nao suportado. Use imagem, MP4, WebM ou MOV.");
      return;
    }
    setUploadingCreative((prev) => ({ ...prev, [campaignId]: true }));
    try {
      let uploadFile = file;
      if (isImage) {
        if (!ALLOWED_CREATIVE_IMAGE_TYPES.has(file.type)) {
          alert("Formato de imagem nao suportado. Use JPG, PNG, WebP ou GIF.");
          return;
        }
        if (file.type === "image/gif" && file.size > CREATIVE_IMAGE_PROXY_SAFE_BYTES) {
          alert("GIFs maiores que 900 KB podem ser bloqueados pelo servidor. Use um GIF menor ou envie como video.");
          return;
        }
        uploadFile = (await prepareMediaFileForUpload(file, {
          maxImageBytes: CREATIVE_IMAGE_PROXY_SAFE_BYTES,
        })).file;
        if (uploadFile.size > CREATIVE_IMAGE_MAX_BYTES) {
          alert(`Arquivo muito grande. Limite: 5 MB para imagens. Tamanho atual: ${formatUploadSize(uploadFile.size)}.`);
          return;
        }
        if (uploadFile.size > CREATIVE_IMAGE_PROXY_SAFE_BYTES) {
          alert(
            `Nao foi possivel reduzir a imagem para envio seguro. Tamanho atual: ${formatUploadSize(uploadFile.size)}. Use uma imagem menor.`,
          );
          return;
        }
      } else if (file.size > CREATIVE_VIDEO_MAX_BYTES) {
        alert("Arquivo muito grande. Limite: 50 MB para videos.");
        return;
      }

      const url = await uploadApi.upload(uploadFile);
      const type = isVideo ? "video" : "image";
      const created = await paidTrafficApi.addCreative(campaignId, {
        media_url: url,
        creative_type: type,
        name: uploadFile.name,
      });
      setCreatives((prev) => ({ ...prev, [campaignId]: [created, ...(prev[campaignId] ?? [])] }));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Erro ao enviar criativo.";
      alert(message.includes("413") ? "Arquivo bloqueado pelo servidor por tamanho. Use uma imagem menor." : message);
    } finally {
      setUploadingCreative((prev) => ({ ...prev, [campaignId]: false }));
    }
  };

  const removeCreative = async (campaignId: string, creativeId: string) => {
    if (!confirm("Remover este criativo?")) return;
    try {
      await paidTrafficApi.deleteCreative(campaignId, creativeId);
      setCreatives((prev) => ({
        ...prev,
        [campaignId]: (prev[campaignId] ?? []).filter((c) => c.id !== creativeId),
      }));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao remover criativo.");
    }
  };

  const savePixel = async (event: FormEvent) => {
    event.preventDefault();
    const extractedPixelId = pixelForm.platform === "meta" ? extractMetaPixelId(pixelForm.base_code) : "";
    const pixelId = pixelForm.pixel_id.trim() || extractedPixelId;
    if (!pixelId) {
      alert("Informe o ID do pixel.");
      return;
    }
    if (pixelForm.events_tracked.size === 0) {
      alert("Selecione pelo menos um evento do pixel.");
      return;
    }
    try {
      const payload: {
        pixel_id: string;
        events_tracked: string;
        conversion_access_token?: string;
        base_code?: string;
      } = {
        pixel_id: pixelId,
        events_tracked: serializePixelEvents(pixelForm.events_tracked) || DEFAULT_PIXEL_EVENTS,
        base_code: pixelForm.base_code.trim(),
      };
      if (!editingPixelId || pixelForm.conversion_access_token.trim()) {
        payload.conversion_access_token = pixelForm.conversion_access_token.trim();
      }
      if (editingPixelId) {
        const updated = await paidTrafficApi.updatePixel(editingPixelId, payload);
        setPixels((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
      } else {
        const created = await paidTrafficApi.createPixel({
          platform: pixelForm.platform,
          ...payload,
        });
        setPixels((prev) => [created, ...prev]);
      }
      setPixelForm(initialPixelForm);
      setEditingPixelId(null);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao salvar pixel.");
    }
  };

  const togglePixel = async (pixel: AdsPixel) => {
    try {
      const updated = await paidTrafficApi.updatePixel(pixel.id, { enabled: !pixel.enabled });
      setPixels((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao atualizar pixel.");
    }
  };

  const removePixel = async (pixel: AdsPixel) => {
    if (!confirm(`Remover o pixel "${pixel.platform.toUpperCase()} · ${pixel.pixel_id}"?`)) return;
    try {
      await paidTrafficApi.deletePixel(pixel.id);
      setPixels((prev) => prev.filter((p) => p.id !== pixel.id));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao remover pixel.");
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
            <AdminTopActions />
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

                  <RealtimeTrackingPanel data={realtime} />

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
                      <Field label="Dias de veiculação">
                        <div className="flex flex-wrap gap-1.5 pt-1">
                          {WEEKDAYS.map(({ index, short, long }) => {
                            const active = campaignForm.active_weekdays.has(index);
                            return (
                              <button
                                key={index}
                                type="button"
                                title={long}
                                onClick={() => setCampaignForm((prev) => {
                                  const next = new Set(prev.active_weekdays);
                                  if (next.has(index)) next.delete(index);
                                  else next.add(index);
                                  return { ...prev, active_weekdays: next };
                                })}
                                className={`rounded-lg px-3 py-1.5 text-xs font-bold transition-colors select-none ${
                                  active
                                    ? "bg-gold text-cream"
                                    : "bg-surface-03 text-stone hover:text-cream"
                                }`}
                              >
                                {short}
                              </button>
                            );
                          })}
                        </div>
                        <p className="text-stone text-[11px] mt-1.5">
                          {campaignForm.active_weekdays.size === 0
                            ? "Nenhum dia selecionado = veicular todos os dias"
                            : `Selecionado: ${weekdaysLabel(serializeWeekdays(campaignForm.active_weekdays))}`}
                        </p>
                      </Field>
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

                      {/* ── Pixel de conversão ── */}
                      <div className="rounded-xl border border-surface-03 bg-surface-03/30 p-3 space-y-3">
                        <p className="text-parchment text-xs font-bold uppercase tracking-wider">Pixel de Conversão</p>
                        <Field label="Pixel vinculado">
                          <select
                            className={fieldBase}
                            value={campaignForm.pixel_id}
                            onChange={(e) => setCampaignForm((prev) => ({ ...prev, pixel_id: e.target.value }))}
                          >
                            <option value="">— Nenhum pixel —</option>
                            {pixels.filter((p) => p.enabled).map((p) => (
                              <option key={p.id} value={p.id}>
                                {p.platform.toUpperCase()} · {p.pixel_id}
                              </option>
                            ))}
                          </select>
                        </Field>
                        {campaignForm.pixel_id && (
                          <Field label="Eventos a disparar">
                            <div className="flex flex-wrap gap-2 pt-1">
                              {PIXEL_EVENT_OPTIONS.map((evt) => {
                                const active = campaignForm.pixel_events.has(evt);
                                return (
                                  <button
                                    key={evt}
                                    type="button"
                                    onClick={() => setCampaignForm((prev) => {
                                      const next = new Set(prev.pixel_events);
                                      if (next.has(evt)) next.delete(evt); else next.add(evt);
                                      return { ...prev, pixel_events: next };
                                    })}
                                    className={`rounded-lg px-3 py-1.5 text-xs font-bold transition-colors select-none ${
                                      active ? "bg-gold text-cream" : "bg-surface-03 text-stone hover:text-cream"
                                    }`}
                                  >
                                    {evt}
                                  </button>
                                );
                              })}
                            </div>
                            <p className="text-stone text-[11px] mt-1.5">
                              {campaignForm.pixel_events.size === 0
                                ? "Nenhum evento selecionado"
                                : `Disparando: ${[...campaignForm.pixel_events].join(", ")}`}
                            </p>
                          </Field>
                        )}
                      </div>

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
                          <div className="mt-3 flex flex-wrap gap-1">
                            {campaign.active_weekdays
                              ? campaign.active_weekdays.split(",").map(Number).sort((a, b) => a - b).map((d) => (
                                  <span key={d} className="rounded-md bg-gold/15 px-2 py-0.5 text-[10px] font-bold text-gold">
                                    {WEEKDAYS[d]?.short ?? d}
                                  </span>
                                ))
                              : <span className="text-stone text-[10px]">Todos os dias</span>
                            }
                          </div>
                          <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
                            <Info label="Diario" value={formatCurrency(campaign.daily_budget)} />
                            <Info label="Total" value={formatCurrency(campaign.total_budget)} />
                            <Info label="Produto" value={campaign.product_id ? productById.get(campaign.product_id)?.name ?? "Produto" : "Nao vinculado"} />
                            <Info label="Cupom" value={campaign.coupon_id ? couponById.get(campaign.coupon_id)?.code ?? "Cupom" : "Nao vinculado"} />
                          </div>
                          <div className="mt-4 flex gap-2">
                            <button onClick={() => editCampaign(campaign)} className="flex-1 rounded-xl bg-surface-02 px-3 py-2 text-sm font-semibold text-parchment hover:text-cream">Editar</button>
                            <button
                              onClick={() => toggleCreatives(campaign.id)}
                              className={`rounded-xl px-3 py-2 text-sm font-semibold transition-colors ${expandedCreatives[campaign.id] ? "bg-gold/20 text-gold" : "bg-surface-02 text-stone hover:text-cream"}`}
                            >
                              Criativos
                            </button>
                            <button onClick={() => removeCampaign(campaign)} className="rounded-xl bg-red-500/10 px-3 py-2 text-red-300 hover:bg-red-500/20"><Trash2 size={16} /></button>
                          </div>

                          {expandedCreatives[campaign.id] && (
                            <div className="mt-4 border-t border-surface-03 pt-4 space-y-3">
                              <div className="flex items-center justify-between">
                                <p className="text-parchment text-xs font-bold uppercase tracking-wider">Criativos</p>
                                <label className={`inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-bold cursor-pointer transition-colors ${uploadingCreative[campaign.id] ? "bg-surface-03 text-stone" : "bg-gold text-cream hover:bg-gold/90"}`}>
                                  {uploadingCreative[campaign.id] ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
                                  {uploadingCreative[campaign.id] ? "Enviando..." : "Adicionar"}
                                  <input
                                    type="file"
                                    accept="image/jpeg,image/png,image/webp,image/gif,video/mp4,video/webm,video/quicktime"
                                    className="hidden"
                                    disabled={uploadingCreative[campaign.id]}
                                    onChange={(e) => {
                                      const file = e.target.files?.[0];
                                      if (file) handleCreativeUpload(campaign.id, file);
                                      e.target.value = "";
                                    }}
                                  />
                                </label>
                              </div>

                              {(creatives[campaign.id] ?? []).length === 0 && !uploadingCreative[campaign.id] && (
                                <p className="text-stone text-xs text-center py-4">Nenhum criativo adicionado ainda.</p>
                              )}

                              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                                {(creatives[campaign.id] ?? []).map((c) => (
                                  <div key={c.id} className="relative group rounded-xl overflow-hidden bg-surface-03 aspect-video cursor-pointer" onClick={() => setPreviewCreative(c)}>
                                    {c.creative_type === "video" ? (
                                      <video
                                        src={resolveAssetUrl(c.media_url)}
                                        className="w-full h-full object-cover"
                                        muted
                                        preload="metadata"
                                      />
                                    ) : (
                                      <img
                                        src={resolveAssetUrl(c.media_url)}
                                        alt={c.name ?? "criativo"}
                                        className="w-full h-full object-cover"
                                      />
                                    )}
                                    {c.creative_type === "video" && (
                                      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                                        <Video size={22} className="text-white/80" />
                                      </div>
                                    )}
                                    <button
                                      onClick={(e) => { e.stopPropagation(); removeCreative(campaign.id, c.id); }}
                                      className="absolute top-1 right-1 rounded-lg bg-black/60 p-1 text-white opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-500/80"
                                    >
                                      <Trash2 size={13} />
                                    </button>
                                    {c.name && (
                                      <p className="absolute bottom-0 left-0 right-0 bg-black/60 px-2 py-1 text-[10px] text-white truncate">
                                        {c.name}
                                      </p>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
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
                      {links.map((link) => {
                        const finalUrl = normalizeGeneratedLinkUrl(link.final_url);
                        return (
                          <div key={link.id} className="rounded-2xl border border-surface-03 bg-surface-03/40 p-4">
                            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
                              <div className="min-w-0">
                                <p className="text-cream font-bold">{link.name || campaignById.get(link.campaign_id)?.name || "Link de campanha"}</p>
                                <p className="text-stone text-xs mt-1 break-all">{finalUrl}</p>
                              </div>
                              <div className="flex gap-2">
                                <button onClick={() => copyLink(finalUrl)} className="inline-flex items-center gap-2 rounded-xl bg-surface-02 px-3 py-2 text-sm text-parchment hover:text-cream"><Copy size={15} /> Copiar</button>
                                <a href={finalUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-xl bg-surface-02 px-3 py-2 text-sm text-parchment hover:text-cream"><ExternalLink size={15} /> Abrir</a>
                              </div>
                            </div>
                          </div>
                        );
                      })}
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
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                  <Panel title="Meta Pixel e Conversions API">
                    <div className="space-y-4">
                      <p className="text-stone text-sm">
                        A integracao da conta Meta Graph fica no modulo Integracoes. Aqui ficam apenas Pixel ID, codigo base da loja e token da Conversions API.
                      </p>
                      {pixels.filter((pixel) => pixel.platform === "meta").map((pixel) => (
                        <div key={pixel.id} className="rounded-2xl border border-surface-03 bg-surface-03/40 p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-cream font-mono text-sm font-bold">{pixel.pixel_id}</p>
                              <p className="text-stone text-xs mt-1">Eventos: {pixel.events_tracked}</p>
                            </div>
                            {pixel.conversion_access_token_configured ? <CheckCircle2 className="text-green-400" /> : <XCircle className="text-red-300" />}
                          </div>
                          <p className="text-stone text-xs mt-3">
                            Token CAPI: {pixel.conversion_access_token_configured ? "configurado" : "pendente"} · Codigo base: {pixel.base_code ? "informado" : "pendente"}
                          </p>
                        </div>
                      ))}
                      {pixels.filter((pixel) => pixel.platform === "meta").length === 0 && (
                        <EmptyState title="Nenhum Meta Pixel" text="Cadastre o Pixel ID, o token da Conversions API e o codigo base na aba Pixels." />
                      )}
                      <button onClick={() => setActiveTab("pixels")} className="rounded-xl bg-gold px-4 py-3 text-sm font-bold text-cream">
                        Configurar pixels
                      </button>
                    </div>
                  </Panel>
                  <Panel title="Separacao das credenciais">
                    <div className="space-y-3 text-sm text-stone">
                      <p><strong className="text-parchment">Modulo Integracoes:</strong> token Meta Graph/OAuth, App ID, App Secret e conta de anuncios.</p>
                      <p><strong className="text-parchment">Modulo Trafego Pago:</strong> Pixel ID, codigo base do pixel, eventos rastreados e token da Conversions API.</p>
                      <p><strong className="text-parchment">Loja online:</strong> carrega automaticamente os pixels ativos e dispara PageView, AddToCart, InitiateCheckout e Purchase conforme configurado.</p>
                    </div>
                  </Panel>
                </div>
              )}

              {activeTab === "pixels" && (
                <div className="grid grid-cols-1 xl:grid-cols-[minmax(320px,400px)_1fr] gap-5">
                  <Panel title={editingPixelId ? "Editar pixel" : "Adicionar pixel"}>
                    <form onSubmit={savePixel} className="space-y-3">
                      <Field label="Plataforma">
                        <select
                          className={fieldBase}
                          value={pixelForm.platform}
                          onChange={(e) => setPixelForm((prev) => ({ ...prev, platform: e.target.value }))}
                          disabled={!!editingPixelId}
                        >
                          <option value="meta">Meta (Facebook)</option>
                          <option value="google">Google</option>
                          <option value="tiktok">TikTok</option>
                        </select>
                      </Field>
                      <Field label="ID do Pixel">
                        <input
                          className={fieldBase}
                          value={pixelForm.pixel_id}
                          onChange={(e) => setPixelForm((prev) => ({ ...prev, pixel_id: e.target.value }))}
                          placeholder={pixelForm.platform === "meta" ? "Ex: 1234567890" : pixelForm.platform === "google" ? "Ex: AW-123456789" : "Ex: ABCDE12345"}
                        />
                        {pixelForm.platform === "meta" && (
                          <p className="text-stone text-[11px] mt-1">Tambem pode colar o codigo base abaixo que o ID sera identificado automaticamente.</p>
                        )}
                      </Field>
                      {pixelForm.platform === "meta" && (
                        <>
                          <Field label="Token da Conversions API">
                            <input
                              type="password"
                              className={fieldBase}
                              value={pixelForm.conversion_access_token}
                              onChange={(e) => setPixelForm((prev) => ({ ...prev, conversion_access_token: e.target.value }))}
                              placeholder={editingPixelId ? "Token salvo. Cole um novo para substituir." : "Cole o token gerado no Pixel da Meta"}
                            />
                            <p className="text-stone text-[11px] mt-1">Este token e do pixel/CAPI. O token Meta Graph da conta fica no modulo Integracoes.</p>
                          </Field>
                          <Field label="Codigo base Meta Pixel">
                            <textarea
                              className={`${fieldBase} min-h-[130px] font-mono text-xs`}
                              value={pixelForm.base_code}
                              onChange={(e) => {
                                const code = e.target.value;
                                const extracted = extractMetaPixelId(code);
                                setPixelForm((prev) => ({
                                  ...prev,
                                  base_code: code,
                                  pixel_id: prev.pixel_id || extracted,
                                }));
                              }}
                              placeholder="Cole aqui o codigo base do Pixel da Meta"
                            />
                            <p className="text-stone text-[11px] mt-1">A loja carrega os pixels ativos automaticamente; o codigo colado fica como referencia e o SDK e injetado de forma controlada.</p>
                          </Field>
                        </>
                      )}
                      <Field label="Eventos rastreados">
                        <div className="flex flex-wrap gap-2 pt-1">
                          {PIXEL_EVENT_OPTIONS.map((evt) => {
                            const active = pixelForm.events_tracked.has(evt);
                            return (
                              <button
                                key={evt}
                                type="button"
                                onClick={() => setPixelForm((prev) => {
                                  const next = new Set(prev.events_tracked);
                                  if (next.has(evt)) next.delete(evt); else next.add(evt);
                                  return { ...prev, events_tracked: next };
                                })}
                                className={`rounded-lg px-3 py-1.5 text-xs font-bold transition-colors select-none ${
                                  active ? "bg-gold text-cream" : "bg-surface-03 text-stone hover:text-cream"
                                }`}
                              >
                                {evt}
                              </button>
                            );
                          })}
                        </div>
                        <p className="text-stone text-[11px] mt-1.5">
                          {pixelForm.events_tracked.size === 0
                            ? "Nenhum evento selecionado"
                            : `Disparando: ${serializePixelEvents(pixelForm.events_tracked)}`}
                        </p>
                      </Field>
                      <div className="flex gap-2">
                        <button className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl bg-gold px-4 py-3 text-sm font-bold text-cream">
                          <Save size={16} /> {editingPixelId ? "Atualizar" : "Adicionar pixel"}
                        </button>
                        {editingPixelId && (
                          <button
                            type="button"
                            onClick={() => { setEditingPixelId(null); setPixelForm(initialPixelForm); }}
                            className="rounded-xl border border-surface-03 px-4 py-3 text-sm font-semibold text-stone hover:text-cream"
                          >
                            Cancelar
                          </button>
                        )}
                      </div>
                    </form>
                  </Panel>

                  <Panel title="Pixels configurados">
                    <div className="space-y-3">
                      {pixels.map((pixel) => (
                        <div key={pixel.id} className="rounded-2xl border border-surface-03 bg-surface-03/40 p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="rounded-lg bg-gold/15 px-2.5 py-1 text-xs font-bold text-gold uppercase">{pixel.platform}</span>
                                <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${pixel.enabled ? "bg-green-500/15 text-green-300" : "bg-surface-03 text-stone"}`}>
                                  {pixel.enabled ? "Ativo" : "Inativo"}
                                </span>
                              </div>
                              <p className="text-cream font-bold mt-2 font-mono text-sm">{pixel.pixel_id}</p>
                              <p className="text-stone text-xs mt-1">Eventos: {pixel.events_tracked}</p>
                              {pixel.platform === "meta" && (
                                <p className="text-stone text-xs mt-1">
                                  Conversions API: {pixel.conversion_access_token_configured ? "token configurado" : "sem token"} · Codigo base: {pixel.base_code ? "informado" : "nao informado"}
                                </p>
                              )}
                            </div>
                          </div>
                          <div className="mt-4 flex flex-wrap gap-2">
                            <button
                              onClick={() => {
                                setEditingPixelId(pixel.id);
                                setPixelForm({
                                  platform: pixel.platform,
                                  pixel_id: pixel.pixel_id,
                                  events_tracked: parsePixelEvents(pixel.events_tracked),
                                  conversion_access_token: "",
                                  base_code: pixel.base_code ?? "",
                                });
                              }}
                              className="rounded-xl bg-surface-02 px-3 py-2 text-sm font-semibold text-parchment hover:text-cream"
                            >
                              Editar
                            </button>
                            <button
                              onClick={() => togglePixel(pixel)}
                              className={`rounded-xl px-3 py-2 text-sm font-semibold ${pixel.enabled ? "bg-orange-500/10 text-orange-300 hover:bg-orange-500/20" : "bg-green-500/10 text-green-300 hover:bg-green-500/20"}`}
                            >
                              {pixel.enabled ? "Desativar" : "Ativar"}
                            </button>
                            <button onClick={() => removePixel(pixel)} className="rounded-xl bg-red-500/10 px-3 py-2 text-red-300 hover:bg-red-500/20">
                              <Trash2 size={16} />
                            </button>
                          </div>
                        </div>
                      ))}
                      {pixels.length === 0 && (
                        <EmptyState
                          title="Nenhum pixel configurado"
                          text="Adicione o ID do pixel da Meta, Google ou TikTok para rastrear conversoes automaticamente."
                        />
                      )}
                    </div>
                  </Panel>
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

      {/* ── Modal de preview de criativo ── */}
      {previewCreative && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
          onClick={() => setPreviewCreative(null)}
        >
          <div
            className="relative max-w-4xl w-full max-h-[90vh] flex flex-col items-center"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setPreviewCreative(null)}
              className="absolute -top-10 right-0 text-white/70 hover:text-white text-sm font-semibold flex items-center gap-1"
            >
              <XCircle size={20} /> Fechar
            </button>

            {previewCreative.creative_type === "video" ? (
              <video
                src={resolveAssetUrl(previewCreative.media_url)}
                controls
                autoPlay
                className="max-h-[80vh] w-full rounded-2xl bg-black"
              />
            ) : (
              <img
                src={resolveAssetUrl(previewCreative.media_url)}
                alt={previewCreative.name ?? "criativo"}
                className="max-h-[80vh] w-auto rounded-2xl object-contain"
              />
            )}

            {previewCreative.name && (
              <p className="mt-3 text-white/80 text-sm font-medium">{previewCreative.name}</p>
            )}
          </div>
        </div>
      )}
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

function RealtimeTrackingPanel({ data }: { data: PaidTrafficRealtime | null }) {
  const events = data?.events ?? [];
  const visitors = data?.visitors ?? [];
  const eventCounts = data?.event_counts ?? [];
  const devices = data?.devices ?? [];
  const cities = data?.cities ?? [];
  const maxEventCount = Math.max(...eventCounts.map((item) => item.count), 1);

  return (
    <Panel title="Tracking em tempo real">
      <div className="space-y-5">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <RealtimeMetric label="Online agora" value={data?.online_visitors ?? 0} icon={Activity} tone="text-green-300" />
          <RealtimeMetric label="Sessoes ativas" value={data?.active_sessions ?? 0} icon={Globe2} tone="text-blue-300" />
          <RealtimeMetric label="Eventos recentes" value={data?.total_events ?? 0} icon={Zap} tone="text-gold" />
          <div className="rounded-xl border border-surface-03 bg-surface-03/35 p-3">
            <div className="flex items-center gap-2 text-stone text-xs">
              <Clock size={14} />
              <span>Ultimo evento</span>
            </div>
            <p className="mt-2 text-sm font-bold text-cream">{formatDateTime(data?.last_event_at)}</p>
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] gap-4">
          <div className="rounded-xl border border-surface-03 bg-surface-03/25 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <p className="text-sm font-bold text-cream">Visitantes fazendo algo na loja</p>
              <span className="rounded-full bg-surface-02 px-2.5 py-1 text-[11px] font-semibold text-stone">
                janela {data?.window_minutes ?? 15} min
              </span>
            </div>
            {visitors.length ? (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] text-left text-xs">
                  <thead className="text-stone">
                    <tr>
                      <th className="py-2 pr-3">Status</th>
                      <th className="py-2 pr-3">Cidade</th>
                      <th className="py-2 pr-3">Dispositivo</th>
                      <th className="py-2 pr-3">Pagina atual</th>
                      <th className="py-2 pr-3">Evento atual</th>
                      <th className="py-2 pr-3">Horario</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-03">
                    {visitors.slice(0, 12).map((visitor) => (
                      <tr key={visitor.id} className="text-parchment">
                        <td className="py-2 pr-3">
                          <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 font-bold ${
                            visitor.is_online ? "bg-green-500/15 text-green-300" : "bg-surface-02 text-stone"
                          }`}>
                            <span className={`h-1.5 w-1.5 rounded-full ${visitor.is_online ? "bg-green-300" : "bg-stone"}`} />
                            {visitor.is_online ? "Online" : "Offline"}
                          </span>
                        </td>
                        <td className="py-2 pr-3">
                          <div className="flex items-center gap-1.5">
                            <MapPin size={13} className="text-gold" />
                            <span>{visitor.city || visitor.state || "Sem cidade"}</span>
                          </div>
                        </td>
                        <td className="py-2 pr-3">
                          <div className="flex items-center gap-1.5 text-stone">
                            <Monitor size={13} />
                            <span>{visitor.device || "-"}</span>
                            <span>{visitor.browser ? `- ${visitor.browser}` : ""}</span>
                          </div>
                        </td>
                        <td className="py-2 pr-3 max-w-[210px] truncate text-stone">{visitor.current_page || "-"}</td>
                        <td className="py-2 pr-3 font-semibold text-cream">{eventLabel(visitor.current_event)}</td>
                        <td className="py-2 pr-3 text-stone">{formatDateTime(visitor.current_event_at ?? visitor.last_seen)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState title="Sem visitantes recentes" text="Os visitantes aparecem aqui assim que navegarem pela loja." />
            )}
          </div>

          <div className="grid grid-cols-1 gap-4">
            <div className="rounded-xl border border-surface-03 bg-surface-03/25 p-4">
              <p className="mb-3 text-sm font-bold text-cream">Eventos por tipo</p>
              {eventCounts.length ? (
                <div className="space-y-3">
                  {eventCounts.map((item) => (
                    <div key={item.name} className="space-y-1.5">
                      <div className="flex justify-between gap-3 text-xs">
                        <span className="text-stone">{eventLabel(item.name)}</span>
                        <span className="font-bold text-cream">{item.count}</span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-surface-02">
                        <div className="h-full rounded-full bg-gold" style={{ width: `${(item.count / maxEventCount) * 100}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="py-6 text-center text-sm text-stone">Sem eventos recentes.</p>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <BreakdownList title="Dispositivos" items={devices} />
              <BreakdownList title="Cidades" items={cities} />
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-surface-03 bg-surface-03/25 p-4">
          <p className="mb-3 text-sm font-bold text-cream">Linha do tempo de eventos</p>
          {events.length ? (
            <div className="max-h-[360px] overflow-y-auto pr-1">
              <div className="space-y-2">
                {events.slice(0, 24).map((event) => (
                  <div key={event.id} className="grid grid-cols-1 gap-2 rounded-xl bg-surface-02 px-3 py-2 text-xs md:grid-cols-[150px_1fr_130px_150px] md:items-center">
                    <span className="font-semibold text-cream">{eventLabel(event.event_type)}</span>
                    <span className="min-w-0 truncate text-stone">
                      {event.product_name ? `${event.product_name} - ` : ""}{event.page || "-"}
                    </span>
                    <span className="text-stone">{event.city || "Sem cidade"}</span>
                    <span className="text-right text-stone md:text-left">{formatDateTime(event.created_at)}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="py-6 text-center text-sm text-stone">Nenhum evento na janela atual.</p>
          )}
        </div>
      </div>
    </Panel>
  );
}

function RealtimeMetric({ label, value, icon: Icon, tone }: { label: string; value: number; icon: typeof BarChart3; tone: string }) {
  return (
    <div className="rounded-xl border border-surface-03 bg-surface-03/35 p-3">
      <div className="flex items-center gap-2 text-stone text-xs">
        <Icon size={14} />
        <span>{label}</span>
      </div>
      <p className={`mt-2 text-2xl font-black ${tone}`}>{value.toLocaleString("pt-BR")}</p>
    </div>
  );
}

function BreakdownList({ title, items }: { title: string; items: Array<{ name: string; count: number }> }) {
  return (
    <div className="rounded-xl border border-surface-03 bg-surface-03/25 p-4">
      <p className="mb-3 text-sm font-bold text-cream">{title}</p>
      {items.length ? (
        <div className="space-y-2">
          {items.slice(0, 6).map((item) => (
            <div key={item.name} className="flex items-center justify-between gap-3 text-xs">
              <span className="truncate text-stone">{item.name || "-"}</span>
              <span className="font-bold text-cream">{item.count}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="py-4 text-center text-xs text-stone">Sem dados.</p>
      )}
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
