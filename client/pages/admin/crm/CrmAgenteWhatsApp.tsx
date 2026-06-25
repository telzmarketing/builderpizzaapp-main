import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bell,
  Bot,
  CheckCircle2,
  Clock3,
  Eye,
  Image as ImageIcon,
  Link as LinkIcon,
  ListFilter,
  Loader2,
  MessageCircle,
  PauseCircle,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Send,
  UserRound,
  Users,
  Video,
  XCircle,
} from "lucide-react";
import MediaUpload from "@/components/admin/MediaUpload";
import OrderWhatsappNotificationSettingsPanel from "@/components/admin/OrderWhatsappNotificationSettingsPanel";
import {
  agenteWhatsAppApi,
  whatsappGatewayApi,
  type ApiAgenteWhatsAppAIGuardrails,
  type ApiAgenteWhatsAppAIProviderStatus,
  type ApiAgenteWhatsAppAISettings,
  type ApiAgenteWhatsAppAITest,
  type ApiAgenteWhatsAppCampaign,
  type ApiAgenteWhatsAppCampaignTemplate,
  type ApiAgenteWhatsAppConversation,
  type ApiAgenteWhatsAppAutomationRun,
  type ApiAgenteWhatsAppAutomationTemplate,
  type ApiAgenteWhatsAppDashboard,
  type ApiAgenteWhatsAppMessage,
  type ApiAgenteWhatsAppObservability,
  type ApiAgenteWhatsAppOutboxAlert,
  type ApiAgenteWhatsAppOutbox,
  type ApiAgenteWhatsAppOutboxMetrics,
  type ApiAgenteWhatsAppOperationalMetrics,
  type ApiAgenteWhatsAppProviderState,
  type ApiAgenteWhatsAppChannelSettings,
  type ApiAgenteWhatsAppStory,
  type ApiAgenteWhatsAppStoryTemplate,
  type ApiWhatsAppGatewayInstance,
  resolveAssetUrl,
} from "@/lib/api";

type StatusFilter = "all" | ApiAgenteWhatsAppConversation["status"];
type OutboxFilter = "all" | "pending" | "processing" | "sent" | "failed" | "dead";
type CampaignAudience = "manual" | "customers" | "leads";
type StoryMediaType = "image" | "video";
type ModuleTab = "conversations" | "settings" | "order_notifications";

const statusLabels: Record<ApiAgenteWhatsAppConversation["status"], string> = {
  open: "Aberta",
  waiting_human: "Fila",
  human: "Humano",
  ai_paused: "IA pausada",
  closed: "Encerrada",
};

const statusClasses: Record<ApiAgenteWhatsAppConversation["status"], string> = {
  open: "bg-green-500/10 text-green-300 border-green-500/30",
  waiting_human: "bg-amber-500/10 text-amber-300 border-amber-500/30",
  human: "bg-blue-500/10 text-blue-300 border-blue-500/30",
  ai_paused: "bg-purple-500/10 text-purple-300 border-purple-500/30",
  closed: "bg-surface-03 text-stone border-surface-03",
};

const filterOptions: Array<{ value: StatusFilter; label: string }> = [
  { value: "all", label: "Todas" },
  { value: "open", label: "Abertas" },
  { value: "waiting_human", label: "Fila" },
  { value: "human", label: "Humano" },
  { value: "ai_paused", label: "IA pausada" },
  { value: "closed", label: "Encerradas" },
];

const outboxFilterOptions: Array<{ value: OutboxFilter; label: string }> = [
  { value: "all", label: "Todas" },
  { value: "pending", label: "Pendentes" },
  { value: "failed", label: "Falhas" },
  { value: "dead", label: "Mortas" },
  { value: "sent", label: "Enviadas" },
];

const outboxStatusLabels: Record<string, string> = {
  pending: "Pendente",
  processing: "Processando",
  sent: "Enviada",
  failed: "Falha",
  dead: "Morta",
};

const outboxStatusClasses: Record<string, string> = {
  pending: "bg-amber-500/10 text-amber-300 border-amber-500/30",
  processing: "bg-blue-500/10 text-blue-300 border-blue-500/30",
  sent: "bg-green-500/10 text-green-300 border-green-500/30",
  failed: "bg-red-500/10 text-red-300 border-red-500/30",
  dead: "bg-red-600/20 text-red-200 border-red-500/50",
};

const whatsappProviderLabels: Record<string, string> = {
  official: "API Oficial",
  baileys: "Gateway",
};

function fmtDate(value?: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function firstLine(message?: ApiAgenteWhatsAppMessage) {
  if (!message) return "Sem mensagens";
  return message.body || message.message_type;
}

function shortId(value: string) {
  return value.length > 8 ? value.slice(0, 8) : value;
}

function outboxLabel(status: string) {
  return outboxStatusLabels[status] ?? status;
}

function outboxClass(status: string) {
  return outboxStatusClasses[status] ?? "bg-surface-03 text-stone border-surface-03";
}

function alertClass(level: string) {
  return level === "critical"
    ? "border-red-500/30 bg-red-500/10 text-red-200"
    : "border-amber-500/30 bg-amber-500/10 text-amber-200";
}

function healthClass(status?: string) {
  if (status === "critical") return "border-red-500/30 bg-red-500/10 text-red-200";
  if (status === "degraded") return "border-amber-500/30 bg-amber-500/10 text-amber-200";
  return "border-green-500/30 bg-green-500/10 text-green-200";
}

function healthLabel(status?: string) {
  if (status === "critical") return "Critico";
  if (status === "degraded") return "Atencao";
  return "Saudavel";
}

function secondsLabel(value?: number | null) {
  if (value === null || value === undefined) return "-";
  if (value < 60) return `${value}s`;
  const minutes = Math.floor(value / 60);
  const seconds = value % 60;
  if (minutes < 60) return seconds ? `${minutes}min ${seconds}s` : `${minutes}min`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}min`;
}

function campaignStatusClass(status: string) {
  if (status === "scheduled") return "border-blue-500/30 bg-blue-500/10 text-blue-300";
  if (status === "queued" || status === "sending") return "border-amber-500/30 bg-amber-500/10 text-amber-300";
  if (status === "sent") return "border-green-500/30 bg-green-500/10 text-green-300";
  return "border-surface-03 bg-surface-03 text-stone";
}

function campaignStatusLabel(status: string) {
  const labels: Record<string, string> = {
    draft: "Rascunho",
    scheduled: "Agendada",
    sending: "Enviando",
    queued: "Na fila",
    sent: "Enviada",
  };
  return labels[status] ?? status;
}

function storyStatusClass(status: string) {
  if (status === "published") return "border-green-500/30 bg-green-500/10 text-green-300";
  if (status === "scheduled") return "border-blue-500/30 bg-blue-500/10 text-blue-300";
  if (status === "failed") return "border-red-500/30 bg-red-500/10 text-red-300";
  return "border-surface-03 bg-surface-03 text-stone";
}

function storyStatusLabel(status: string) {
  const labels: Record<string, string> = {
    draft: "Rascunho",
    scheduled: "Agendado",
    published: "Publicado",
    failed: "Falhou",
  };
  return labels[status] ?? status;
}

function messageSourceLabel(source: unknown) {
  if (typeof source !== "string") return "";
  const normalized = source.toLowerCase();
  if (normalized.includes("campaign")) return "";
  if (normalized.includes("automation")) return "";
  if (normalized.includes("story")) return "";
  if (normalized.includes("order")) return "Pedido";
  if (normalized.includes("crm_agente_whatsapp")) return "Atendimento";
  if (normalized.includes("ai")) return "IA";
  return "";
}

function StatCard({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof MessageCircle;
  label: string;
  value: number | string;
}) {
  return (
    <div className="bg-surface-02 border border-surface-03 rounded-xl p-4">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs text-stone">{label}</span>
        <Icon size={16} className="text-gold shrink-0" />
      </div>
      <p className="text-2xl font-bold text-cream mt-2">{value}</p>
    </div>
  );
}

export default function CrmAgenteWhatsApp() {
  const [dashboard, setDashboard] = useState<ApiAgenteWhatsAppDashboard | null>(null);
  const [observability, setObservability] = useState<ApiAgenteWhatsAppObservability | null>(null);
  const [campaigns, setCampaigns] = useState<ApiAgenteWhatsAppCampaign[]>([]);
  const [campaignTemplates, setCampaignTemplates] = useState<ApiAgenteWhatsAppCampaignTemplate[]>([]);
  const [automationTemplates, setAutomationTemplates] = useState<ApiAgenteWhatsAppAutomationTemplate[]>([]);
  const [automationResult, setAutomationResult] = useState<ApiAgenteWhatsAppAutomationRun | null>(null);
  const [stories, setStories] = useState<ApiAgenteWhatsAppStory[]>([]);
  const [storyTemplates, setStoryTemplates] = useState<ApiAgenteWhatsAppStoryTemplate[]>([]);
  const [aiSettings, setAiSettings] = useState<ApiAgenteWhatsAppAISettings | null>(null);
  const [aiProviderStatus, setAiProviderStatus] = useState<ApiAgenteWhatsAppAIProviderStatus | null>(null);
  const [aiTestResult, setAiTestResult] = useState<ApiAgenteWhatsAppAITest | null>(null);
  const [aiKeys, setAiKeys] = useState({ openai_api_key: "", anthropic_api_key: "" });
  const [campaignForm, setCampaignForm] = useState({
    name: "",
    audience_type: "manual" as CampaignAudience,
    phones: "",
    message_template: "",
    scheduled_at: "",
  });
  const [storyForm, setStoryForm] = useState({
    title: "",
    media_type: "image" as StoryMediaType,
    media_url: "",
    caption: "",
    cta_text: "",
    cta_url: "",
    scheduled_at: "",
    campaign_id: "",
  });
  const [automationForm, setAutomationForm] = useState({
    key: "recompra",
    limit: 30,
    dry_run: true,
    message_template: "",
  });
  const [outboxSummary, setOutboxSummary] = useState<ApiAgenteWhatsAppOutboxMetrics | null>(null);
  const [outboxItems, setOutboxItems] = useState<ApiAgenteWhatsAppOutbox[]>([]);
  const [outboxAlerts, setOutboxAlerts] = useState<ApiAgenteWhatsAppOutboxAlert[]>([]);
  const [providerStates, setProviderStates] = useState<ApiAgenteWhatsAppProviderState[]>([]);
  const [channelSettings, setChannelSettings] = useState<ApiAgenteWhatsAppChannelSettings | null>(null);
  const [gatewayInstances, setGatewayInstances] = useState<ApiWhatsAppGatewayInstance[]>([]);
  const [outboxFilter, setOutboxFilter] = useState<OutboxFilter>("failed");
  const [selectedOutbox, setSelectedOutbox] = useState<ApiAgenteWhatsAppOutbox | null>(null);
  const [sessions, setSessions] = useState<ApiAgenteWhatsAppConversation[]>([]);
  const [operationalMetrics, setOperationalMetrics] = useState<ApiAgenteWhatsAppOperationalMetrics | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ApiAgenteWhatsAppMessage[]>([]);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [moduleTab, setModuleTab] = useState<ModuleTab>("conversations");
  const [search, setSearch] = useState("");
  const [agentFilter, setAgentFilter] = useState("");
  const [periodFrom, setPeriodFrom] = useState("");
  const [periodTo, setPeriodTo] = useState("");
  const [reply, setReply] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [outboxLoading, setOutboxLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [aiGenerating, setAiGenerating] = useState(false);
  const [aiSuggestion, setAiSuggestion] = useState("");
  const [aiGuardrails, setAiGuardrails] = useState<ApiAgenteWhatsAppAIGuardrails | null>(null);
  const [aiSettingsSaving, setAiSettingsSaving] = useState(false);
  const [processingQueue, setProcessingQueue] = useState(false);
  const [campaignSaving, setCampaignSaving] = useState(false);
  const [campaignDispatchingId, setCampaignDispatchingId] = useState<string | null>(null);
  const [storySaving, setStorySaving] = useState(false);
  const [storyPublishingId, setStoryPublishingId] = useState<string | null>(null);
  const [automationRunning, setAutomationRunning] = useState(false);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [providerAction, setProviderAction] = useState<string | null>(null);
  const [channelSaving, setChannelSaving] = useState(false);
  const [error, setError] = useState("");

  const selected = sessions.find((session) => session.id === selectedId) ?? null;
  const channelProvider = channelSettings?.active_provider === "baileys" ? "baileys" : "official";
  const connectedGatewayInstances = gatewayInstances.filter((instance) => instance.status === "connected");
  const selectedAutomation = automationTemplates.find((item) => item.key === automationForm.key) ?? automationTemplates[0] ?? null;
  const aiModels = aiSettings?.provider === "claude"
    ? ["claude-sonnet-4-20250514", "claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"]
    : aiSettings?.provider === "openai"
      ? ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"]
      : ["internal-rules-v1"];

  const filteredSessions = useMemo(() => {
    const term = search.trim().toLowerCase();
    return sessions.filter((session) => {
      if (filter !== "all" && session.status !== filter) return false;
      if (!term) return true;
      return [
        session.phone,
        session.customer_name,
        session.current_intent,
        session.provider,
      ].filter(Boolean).some((value) => String(value).toLowerCase().includes(term));
    });
  }, [filter, search, sessions]);

  const lastMessageBySession = useMemo(() => {
    const pairs = sessions
      .filter((session) => session.last_message)
      .map((session) => [session.id, session.last_message as ApiAgenteWhatsAppMessage] as const);
    if (selected && messages.length > 0) {
      return new Map([...pairs, [selected.id, messages[messages.length - 1]] as const]);
    }
    return new Map(pairs);
  }, [messages, selected, sessions]);

  const latestInboundMessage = useMemo(() => {
    return [...messages].reverse().find((message) => message.direction === "inbound" && !!message.body) ?? null;
  }, [messages]);

  async function loadSessions(preferredId?: string | null) {
    setError("");
    setLoading(true);
    try {
      const [dash, rows] = await Promise.all([
        agenteWhatsAppApi.dashboard(),
        agenteWhatsAppApi.listConversations({
          status: filter === "all" ? undefined : filter,
          search: search.trim() || undefined,
          assigned_admin_id: agentFilter.trim() || undefined,
          date_from: periodFrom || undefined,
          date_to: periodTo || undefined,
          limit: 120,
        }),
      ]);
      const [liveMetrics, aiSettingsPayload, aiStatusPayload, channelPayload, gatewayPayload] = await Promise.all([
        agenteWhatsAppApi.operationalMetrics().catch(() => null),
        agenteWhatsAppApi.getAISettings().catch(() => null),
        agenteWhatsAppApi.aiProviderStatus().catch(() => null),
        agenteWhatsAppApi.getChannelSettings().catch(() => null),
        whatsappGatewayApi.listInstances().catch(() => []),
      ]);
      setDashboard(dash);
      setSessions(rows);
      setOperationalMetrics(liveMetrics);
      setAiSettings(aiSettingsPayload);
      setAiProviderStatus(aiStatusPayload);
      setChannelSettings(channelPayload);
      setGatewayInstances(gatewayPayload);
      const nextId = preferredId ?? selectedId ?? rows[0]?.id ?? null;
      setSelectedId(nextId);
      if (nextId) await loadDetail(nextId);
      else {
        setMessages([]);
        setAiGuardrails(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar o AGENTE WHATSAPP.");
    } finally {
      setLoading(false);
    }
  }

  async function loadDetail(sessionId: string) {
    setDetailLoading(true);
    try {
      const [detail, guardrails] = await Promise.all([
        agenteWhatsAppApi.getSession(sessionId),
        agenteWhatsAppApi.aiGuardrails(sessionId).catch(() => null),
      ]);
      setMessages(detail.messages);
      setAiGuardrails(guardrails);
      setSessions((current) => current.map((session) => (
        session.id === detail.session.id
          ? {
              ...session,
              ...detail.session,
              last_message: detail.messages[detail.messages.length - 1] ?? session.last_message,
              attendance_mode: detail.session.status === "human" || !detail.session.ai_enabled ? "human" : "ai",
            }
          : session
      )));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar conversa.");
    } finally {
      setDetailLoading(false);
    }
  }

  async function loadOutbox(nextFilter: OutboxFilter = outboxFilter) {
    setOutboxLoading(true);
    try {
      const [rows, metrics] = await Promise.all([
        agenteWhatsAppApi.listOutbox({
          status: nextFilter === "all" ? undefined : nextFilter,
          limit: 80,
        }),
        agenteWhatsAppApi.outboxAlerts(),
      ]);
      setOutboxItems(rows);
      setOutboxSummary(metrics.metrics);
      setOutboxAlerts(metrics.alerts);
      setProviderStates(metrics.providers);
      agenteWhatsAppApi.observability().then(setObservability).catch(() => {});
      setSelectedOutbox((current) => {
        if (!current) return null;
        return rows.find((item) => item.id === current.id) ?? null;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar auditoria da fila.");
    } finally {
      setOutboxLoading(false);
    }
  }

  useEffect(() => {
    loadSessions();
    const interval = window.setInterval(() => {
      agenteWhatsAppApi.listConversations({
        status: filter === "all" ? undefined : filter,
        search: search.trim() || undefined,
        assigned_admin_id: agentFilter.trim() || undefined,
        date_from: periodFrom || undefined,
        date_to: periodTo || undefined,
        limit: 120,
      }).then(setSessions).catch(() => {});
      agenteWhatsAppApi.operationalMetrics().then(setOperationalMetrics).catch(() => {});
      if (selectedId) loadDetail(selectedId);
    }, 15000);
    return () => window.clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  async function updateSession(data: Partial<Pick<ApiAgenteWhatsAppConversation, "status" | "ai_enabled" | "automation_blocked">>) {
    if (!selected) return;
    setSaving(true);
    try {
      const updated = await agenteWhatsAppApi.updateSession(selected.id, data);
      setSessions((current) => current.map((session) => session.id === updated.id ? {
        ...session,
        ...updated,
        attendance_mode: updated.status === "human" || !updated.ai_enabled ? "human" : "ai",
      } : session));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao atualizar conversa.");
    } finally {
      setSaving(false);
    }
  }

  async function sendReply() {
    if (!selected || !reply.trim()) return;
    setSaving(true);
    try {
      await agenteWhatsAppApi.addMessage(selected.id, {
        direction: "outbound",
        sender_type: "human",
        message_type: "text",
        body: reply.trim(),
        provider_status: "queued",
        raw_payload: { source: "crm_agente_whatsapp" },
      });
      await agenteWhatsAppApi.processOutbox(10).catch(() => null);
      const outbox = await agenteWhatsAppApi.outboxMetrics().catch(() => null);
      if (outbox) setOutboxSummary(outbox);
      setReply("");
      setAiSuggestion("");
      await loadDetail(selected.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao registrar resposta.");
    } finally {
      setSaving(false);
    }
  }

  async function suggestAiReply() {
    if (!selected) return;
    const prompt = reply.trim() || latestInboundMessage?.body?.trim();
    if (!prompt) return;
    setAiGenerating(true);
    setError("");
    try {
      const result = await agenteWhatsAppApi.aiRespond(selected.id, {
        message: prompt,
        auto_queue: false,
        record_inbound: false,
      });
      setReply(result.response);
      setAiGuardrails(result.guardrails);
      const tools = result.tool_calls.map((tool) => tool.tool_name).join(", ");
      setAiSuggestion(`Intencao: ${result.intent}${tools ? ` | Ferramentas: ${tools}` : ""}`);
      await loadDetail(selected.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao gerar resposta da IA.");
    } finally {
      setAiGenerating(false);
    }
  }

  async function processQueue() {
    setProcessingQueue(true);
    setError("");
    try {
      await agenteWhatsAppApi.processOutbox(20);
      await loadOutbox();
      if (selectedId) await loadDetail(selectedId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao processar fila de envio.");
    } finally {
      setProcessingQueue(false);
    }
  }

  async function retryOutboxItem(item: ApiAgenteWhatsAppOutbox) {
    setRetryingId(item.id);
    setError("");
    try {
      await agenteWhatsAppApi.retryOutbox(item.id);
      await loadOutbox();
      if (selectedId) await loadDetail(selectedId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao reprocessar item da fila.");
    } finally {
      setRetryingId(null);
    }
  }

  async function pauseProvider(provider: string) {
    setProviderAction(provider);
    setError("");
    try {
      await agenteWhatsAppApi.pauseOutboxProvider(provider, {
        reason: "Pausa manual pelo painel do AGENTE WHATSAPP.",
        minutes: 30,
      });
      await loadOutbox();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao pausar provider.");
    } finally {
      setProviderAction(null);
    }
  }

  async function resumeProvider(provider: string) {
    setProviderAction(provider);
    setError("");
    try {
      await agenteWhatsAppApi.resumeOutboxProvider(provider);
      await loadOutbox();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao retomar provider.");
    } finally {
      setProviderAction(null);
    }
  }

  async function loadCampaigns() {
    try {
      const rows = await agenteWhatsAppApi.listCampaigns();
      setCampaigns(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar campanhas.");
    }
  }

  function campaignPhones() {
    return campaignForm.phones
      .split(/[\n,;]+/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  async function createCampaign() {
    if (!campaignForm.name.trim() || !campaignForm.message_template.trim()) return;
    if (campaignForm.audience_type === "manual" && campaignPhones().length === 0) {
      setError("Informe pelo menos um telefone para campanha manual.");
      return;
    }
    setCampaignSaving(true);
    setError("");
    try {
      await agenteWhatsAppApi.createCampaign({
        name: campaignForm.name.trim(),
        message_template: campaignForm.message_template.trim(),
        audience_type: campaignForm.audience_type,
        phones: campaignPhones(),
        campaign_type: "manual",
        scheduled_at: campaignForm.scheduled_at ? new Date(campaignForm.scheduled_at).toISOString() : null,
      });
      setCampaignForm({
        name: "",
        audience_type: "manual",
        phones: "",
        message_template: "",
        scheduled_at: "",
      });
      await loadCampaigns();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao criar campanha.");
    } finally {
      setCampaignSaving(false);
    }
  }

  async function dispatchCampaign(campaign: ApiAgenteWhatsAppCampaign, force = false) {
    setCampaignDispatchingId(campaign.id);
    setError("");
    try {
      await agenteWhatsAppApi.dispatchCampaign(campaign.id, force);
      await Promise.all([loadCampaigns(), loadOutbox()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao disparar campanha.");
    } finally {
      setCampaignDispatchingId(null);
    }
  }

  async function processScheduledCampaigns() {
    setCampaignSaving(true);
    setError("");
    try {
      await agenteWhatsAppApi.processScheduledCampaigns();
      await Promise.all([loadCampaigns(), loadOutbox()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao processar campanhas agendadas.");
    } finally {
      setCampaignSaving(false);
    }
  }

  async function loadStories() {
    try {
      const rows = await agenteWhatsAppApi.listStories();
      setStories(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar stories.");
    }
  }

  async function createStory() {
    if (!storyForm.title.trim() || !storyForm.media_url.trim()) {
      setError("Informe titulo e midia para criar o story.");
      return;
    }
    setStorySaving(true);
    setError("");
    try {
      await agenteWhatsAppApi.createStory({
        title: storyForm.title.trim(),
        media_type: storyForm.media_type,
        media_url: storyForm.media_url.trim(),
        caption: storyForm.caption.trim() || null,
        cta_text: storyForm.cta_text.trim() || null,
        cta_url: storyForm.cta_url.trim() || null,
        campaign_id: storyForm.campaign_id || null,
        scheduled_at: storyForm.scheduled_at ? new Date(storyForm.scheduled_at).toISOString() : null,
      });
      setStoryForm({
        title: "",
        media_type: "image",
        media_url: "",
        caption: "",
        cta_text: "",
        cta_url: "",
        scheduled_at: "",
        campaign_id: "",
      });
      await loadStories();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao criar story.");
    } finally {
      setStorySaving(false);
    }
  }

  async function publishStory(story: ApiAgenteWhatsAppStory, force = false) {
    setStoryPublishingId(story.id);
    setError("");
    try {
      await agenteWhatsAppApi.publishStory(story.id, force);
      await loadStories();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao publicar story.");
    } finally {
      setStoryPublishingId(null);
    }
  }

  async function processScheduledStories() {
    setStorySaving(true);
    setError("");
    try {
      await agenteWhatsAppApi.processScheduledStories();
      await loadStories();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao processar stories agendados.");
    } finally {
      setStorySaving(false);
    }
  }

  async function runAutomation(dryRun = automationForm.dry_run) {
    setAutomationRunning(true);
    setError("");
    try {
      const result = await agenteWhatsAppApi.runAutomation({
        key: automationForm.key,
        limit: automationForm.limit,
        dry_run: dryRun,
        message_template: automationForm.message_template.trim() || null,
      });
      setAutomationResult(result);
      if (!dryRun) await loadOutbox();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao executar automacao comercial.");
    } finally {
      setAutomationRunning(false);
    }
  }

  async function runDueAutomations() {
    setAutomationRunning(true);
    setError("");
    try {
      await agenteWhatsAppApi.runDueAutomations(10);
      await Promise.all([loadOutbox(), loadSessions(selectedId)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao processar automacoes comerciais.");
    } finally {
      setAutomationRunning(false);
    }
  }

  function updateAISetting<K extends keyof ApiAgenteWhatsAppAISettings>(key: K, value: ApiAgenteWhatsAppAISettings[K]) {
    setAiSettings((current) => current ? { ...current, [key]: value } : current);
  }

  async function saveAISettings() {
    if (!aiSettings) return;
    setAiSettingsSaving(true);
    setError("");
    try {
      const payload = {
        enabled: aiSettings.enabled,
        provider: aiSettings.provider,
        model: aiSettings.model,
        temperature: aiSettings.temperature,
        max_tokens: aiSettings.max_tokens,
        prompt_base: aiSettings.prompt_base,
        business_rules: aiSettings.business_rules,
        tone_of_voice: aiSettings.tone_of_voice,
        objective: aiSettings.objective,
        transfer_instructions: aiSettings.transfer_instructions,
        forbidden_topics: aiSettings.forbidden_topics,
        allowed_tools: aiSettings.allowed_tools,
      };
      const updated = await agenteWhatsAppApi.updateAISettings(payload);
      const status = await agenteWhatsAppApi.aiProviderStatus();
      setAiSettings(updated);
      setAiProviderStatus(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar configuracoes da IA.");
    } finally {
      setAiSettingsSaving(false);
    }
  }

  async function saveAIKeys() {
    const payload: { openai_api_key?: string; anthropic_api_key?: string } = {};
    if (aiKeys.openai_api_key.trim()) payload.openai_api_key = aiKeys.openai_api_key.trim();
    if (aiKeys.anthropic_api_key.trim()) payload.anthropic_api_key = aiKeys.anthropic_api_key.trim();
    if (!payload.openai_api_key && !payload.anthropic_api_key) return;
    setAiSettingsSaving(true);
    setError("");
    try {
      const status = await agenteWhatsAppApi.updateAIKeys(payload);
      const settings = await agenteWhatsAppApi.getAISettings();
      setAiProviderStatus(status);
      setAiSettings(settings);
      setAiKeys({ openai_api_key: "", anthropic_api_key: "" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar chaves da IA.");
    } finally {
      setAiSettingsSaving(false);
    }
  }

  async function testAISettings() {
    setAiSettingsSaving(true);
    setError("");
    try {
      const result = await agenteWhatsAppApi.testAISettings("Responda em uma frase curta confirmando que o AGENTE WHATSAPP esta conectado.");
      setAiTestResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao testar IA.");
    } finally {
      setAiSettingsSaving(false);
    }
  }

  async function saveChannelSettings() {
    if (!channelSettings) return;
    setChannelSaving(true);
    setError("");
    try {
      const updated = await agenteWhatsAppApi.updateChannelSettings({
        active_provider: channelProvider,
        whatsapp_gateway_instance_id: channelSettings.whatsapp_gateway_instance_id || null,
      });
      setChannelSettings(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar canal de envio.");
    } finally {
      setChannelSaving(false);
    }
  }

  async function createSession() {
    if (!newPhone.trim()) return;
    setSaving(true);
    try {
      const session = await agenteWhatsAppApi.createSession({
        phone: newPhone.trim(),
        origin: "manual",
        provider: channelProvider,
        ai_enabled: true,
      });
      setNewPhone("");
      await loadSessions(session.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao abrir conversa.");
    } finally {
      setSaving(false);
    }
  }

  const activeModuleTab = moduleTab as string;

  return (
    <div className="space-y-5">
      {error && (
        <div className="flex items-center justify-between gap-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          <span>{error}</span>
          <button onClick={() => setError("")} className="text-red-200 hover:text-white">
            <XCircle size={16} />
          </button>
        </div>
      )}

      <div className="bg-surface-02 border border-surface-03 rounded-xl p-1 flex gap-1 overflow-x-auto">
        {[
          { value: "conversations" as ModuleTab, label: "Conversas", icon: MessageCircle },
          { value: "settings" as ModuleTab, label: "Configuracoes", icon: Bot },
          { value: "order_notifications" as ModuleTab, label: "Avisos de pedido", icon: Bell },
        ].map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.value}
              onClick={() => setModuleTab(tab.value)}
              className={`h-10 px-3 rounded-lg text-sm font-semibold flex items-center gap-2 whitespace-nowrap transition-colors ${
                activeModuleTab === tab.value
                  ? "bg-gold text-black"
                  : "text-stone hover:text-cream hover:bg-surface-03"
              }`}
            >
              <Icon size={15} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {activeModuleTab === "conversations" && (
        <>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard icon={MessageCircle} label="Conversas abertas" value={dashboard?.sessions_open ?? 0} />
        <StatCard icon={Users} label="Atendimento humano" value={dashboard?.sessions_human ?? 0} />
        <StatCard icon={Clock3} label="Aguardando resposta" value={operationalMetrics?.waiting_response ?? 0} />
        <StatCard icon={Eye} label="Nao lidas" value={operationalMetrics?.unread_messages ?? 0} />
      </div>
        </>
      )}

      {activeModuleTab === "settings" && (
      <>
      <section className="bg-surface-02 border border-surface-03 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-surface-03 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-cream">Canal de envio</h2>
            <p className="text-xs text-stone mt-1">
              Provedor e instancia usados pelo atendimento, IA e fila do AGENTE WHATSAPP
            </p>
          </div>
          <button
            onClick={saveChannelSettings}
            disabled={channelSaving || !channelSettings}
            className="h-9 px-3 rounded-xl bg-gold text-black text-xs font-semibold flex items-center gap-2 disabled:opacity-50"
          >
            {channelSaving ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
            Salvar canal
          </button>
        </div>

        <div className="p-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-xs text-stone">API do agente</label>
            <select
              value={channelProvider}
              onChange={(event) => setChannelSettings((current) => current ? { ...current, active_provider: event.target.value } : current)}
              className="w-full h-10 bg-surface-03 border border-surface-03 rounded-xl px-3 text-sm text-cream outline-none focus:border-gold"
            >
              <option value="official">WhatsApp Oficial (Cloud API)</option>
              <option value="baileys">WhatsApp Gateway</option>
            </select>
            <p className="text-xs text-stone/70">
              Novas conversas manuais e respostas da fila usam este canal. Conversas antigas mantem o provedor em que foram abertas.
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-xs text-stone">Instancia do Gateway</label>
            <select
              value={channelSettings?.whatsapp_gateway_instance_id ?? ""}
              onChange={(event) => setChannelSettings((current) => current ? { ...current, whatsapp_gateway_instance_id: event.target.value || null } : current)}
              disabled={channelProvider !== "baileys"}
              className="w-full h-10 bg-surface-03 border border-surface-03 rounded-xl px-3 text-sm text-cream outline-none focus:border-gold disabled:opacity-50"
            >
              <option value="">Automatico: qualquer instancia conectada</option>
              {gatewayInstances.map((instance) => (
                <option key={instance.id} value={instance.id}>
                  {instance.name} - {instance.status}
                </option>
              ))}
            </select>
            <p className={`text-xs ${channelProvider === "baileys" && !connectedGatewayInstances.length ? "text-red-300" : "text-stone/70"}`}>
              {channelProvider === "baileys"
                ? connectedGatewayInstances.length
                  ? `${connectedGatewayInstances.length} instancia(s) conectada(s) no Gateway.`
                  : "Nenhuma instancia conectada. Conecte no modulo WhatsApp Gateway antes de atender por Gateway."
                : "Instancia usada somente quando o canal for Gateway."}
            </p>
          </div>
        </div>
      </section>

      <section className="bg-surface-02 border border-surface-03 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-surface-03 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-cream">Configuracoes da IA</h2>
            <p className="text-xs text-stone mt-1">
              Prompt, provedor e regras exclusivas do AGENTE WHATSAPP
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold ${
              aiProviderStatus?.active ? "border-green-500/30 bg-green-500/10 text-green-300" : "border-amber-500/30 bg-amber-500/10 text-amber-300"
            }`}>
              <Bot size={14} />
              {aiProviderStatus?.active ? "IA configurada" : "Configurar IA"}
            </span>
            <button
              onClick={testAISettings}
              disabled={aiSettingsSaving || !aiSettings}
              className="h-9 px-3 rounded-xl border border-surface-03 text-stone text-xs font-semibold flex items-center gap-2 disabled:opacity-50"
            >
              {aiSettingsSaving ? <Loader2 size={15} className="animate-spin" /> : <Activity size={15} />}
              Testar
            </button>
            <button
              onClick={saveAISettings}
              disabled={aiSettingsSaving || !aiSettings}
              className="h-9 px-3 rounded-xl bg-gold text-black text-xs font-semibold flex items-center gap-2 disabled:opacity-50"
            >
              {aiSettingsSaving ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
              Salvar IA
            </button>
          </div>
        </div>

        {aiSettings && (
          <div className="p-4 grid grid-cols-1 xl:grid-cols-[360px_minmax(0,1fr)] gap-4">
            <div className="rounded-xl border border-surface-03 bg-surface-00/30 p-4 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-cream">Atendimento com IA</p>
                  <p className="text-xs text-stone mt-0.5">Ativa sugestoes e respostas automaticas permitidas</p>
                </div>
                <button
                  onClick={() => updateAISetting("enabled", !aiSettings.enabled)}
                  className={`h-8 px-3 rounded-full border text-xs font-semibold ${
                    aiSettings.enabled ? "border-green-500/30 bg-green-500/10 text-green-300" : "border-surface-03 text-stone"
                  }`}
                >
                  {aiSettings.enabled ? "Ativa" : "Pausada"}
                </button>
              </div>

              <div>
                <label className="text-xs text-stone">Provedor</label>
                <select
                  value={aiSettings.provider}
                  onChange={(event) => {
                    const provider = event.target.value;
                    const model = provider === "claude" ? "claude-sonnet-4-20250514" : provider === "openai" ? "gpt-4o-mini" : "internal-rules-v1";
                    setAiSettings((current) => current ? { ...current, provider, model } : current);
                  }}
                  className="mt-1 w-full h-10 bg-surface-03 border border-surface-03 rounded-xl px-3 text-sm text-cream outline-none focus:border-gold"
                >
                  <option value="internal">Interno seguro</option>
                  <option value="openai">OpenAI</option>
                  <option value="claude">Claude</option>
                </select>
              </div>

              <div>
                <label className="text-xs text-stone">Modelo</label>
                <select
                  value={aiSettings.model}
                  onChange={(event) => updateAISetting("model", event.target.value)}
                  className="mt-1 w-full h-10 bg-surface-03 border border-surface-03 rounded-xl px-3 text-sm text-cream outline-none focus:border-gold"
                >
                  {aiModels.map((model) => (
                    <option key={model} value={model}>{model}</option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-stone">Temperatura</label>
                  <input
                    type="number"
                    min={0}
                    max={2}
                    step={0.1}
                    value={aiSettings.temperature}
                    onChange={(event) => updateAISetting("temperature", Number(event.target.value) || 0)}
                    className="mt-1 w-full h-10 bg-surface-03 border border-surface-03 rounded-xl px-3 text-sm text-cream outline-none focus:border-gold"
                  />
                </div>
                <div>
                  <label className="text-xs text-stone">Max tokens</label>
                  <input
                    type="number"
                    min={1}
                    max={8192}
                    value={aiSettings.max_tokens}
                    onChange={(event) => updateAISetting("max_tokens", Number(event.target.value) || 1)}
                    className="mt-1 w-full h-10 bg-surface-03 border border-surface-03 rounded-xl px-3 text-sm text-cream outline-none focus:border-gold"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 pt-2 border-t border-surface-03">
                <div>
                  <label className="text-xs text-stone">OpenAI API Key</label>
                  <input
                    type="password"
                    value={aiKeys.openai_api_key}
                    onChange={(event) => setAiKeys((current) => ({ ...current, openai_api_key: event.target.value }))}
                    placeholder={aiSettings.openai_key_preview || "Nao configurada"}
                    className="mt-1 w-full h-10 bg-surface-03 border border-surface-03 rounded-xl px-3 text-sm text-cream outline-none focus:border-gold"
                  />
                </div>
                <div>
                  <label className="text-xs text-stone">Anthropic API Key</label>
                  <input
                    type="password"
                    value={aiKeys.anthropic_api_key}
                    onChange={(event) => setAiKeys((current) => ({ ...current, anthropic_api_key: event.target.value }))}
                    placeholder={aiSettings.anthropic_key_preview || "Nao configurada"}
                    className="mt-1 w-full h-10 bg-surface-03 border border-surface-03 rounded-xl px-3 text-sm text-cream outline-none focus:border-gold"
                  />
                </div>
                <button
                  onClick={saveAIKeys}
                  disabled={aiSettingsSaving || (!aiKeys.openai_api_key.trim() && !aiKeys.anthropic_api_key.trim())}
                  className="h-9 rounded-xl border border-gold/40 text-gold text-xs font-semibold flex items-center justify-center gap-2 disabled:opacity-50"
                >
                  {aiSettingsSaving ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                  Salvar chaves
                </button>
              </div>
            </div>

            <div className="rounded-xl border border-surface-03 bg-surface-00/30 p-4 space-y-3">
              <div>
                <label className="text-xs text-stone">Prompt principal</label>
                <textarea
                  rows={4}
                  value={aiSettings.prompt_base}
                  onChange={(event) => updateAISetting("prompt_base", event.target.value)}
                  className="mt-1 w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-sm text-cream outline-none resize-none focus:border-gold"
                />
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-stone">Objetivo</label>
                  <textarea
                    rows={3}
                    value={aiSettings.objective}
                    onChange={(event) => updateAISetting("objective", event.target.value)}
                    className="mt-1 w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-sm text-cream outline-none resize-none focus:border-gold"
                  />
                </div>
                <div>
                  <label className="text-xs text-stone">Tom de voz</label>
                  <textarea
                    rows={3}
                    value={aiSettings.tone_of_voice}
                    onChange={(event) => updateAISetting("tone_of_voice", event.target.value)}
                    className="mt-1 w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-sm text-cream outline-none resize-none focus:border-gold"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs text-stone">Regras comerciais</label>
                <textarea
                  rows={3}
                  value={aiSettings.business_rules}
                  onChange={(event) => updateAISetting("business_rules", event.target.value)}
                  className="mt-1 w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-sm text-cream outline-none resize-none focus:border-gold"
                />
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-stone">Transferencia humana</label>
                  <textarea
                    rows={3}
                    value={aiSettings.transfer_instructions}
                    onChange={(event) => updateAISetting("transfer_instructions", event.target.value)}
                    className="mt-1 w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-sm text-cream outline-none resize-none focus:border-gold"
                  />
                </div>
                <div>
                  <label className="text-xs text-stone">Limitacoes e proibicoes</label>
                  <textarea
                    rows={3}
                    value={aiSettings.forbidden_topics}
                    onChange={(event) => updateAISetting("forbidden_topics", event.target.value)}
                    className="mt-1 w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-sm text-cream outline-none resize-none focus:border-gold"
                  />
                </div>
              </div>

              {aiTestResult && (
                <div className="rounded-xl border border-green-500/30 bg-green-500/10 px-3 py-2 text-xs text-green-200">
                  <p className="font-semibold">Teste: {aiTestResult.provider} / {aiTestResult.model}</p>
                  <p className="mt-1">{aiTestResult.response}</p>
                  <p className="mt-1 text-green-300/80">Latencia: {aiTestResult.latency_ms}ms - Tokens: {aiTestResult.tokens_input}/{aiTestResult.tokens_output}</p>
                </div>
              )}
            </div>
          </div>
        )}
      </section>
      </>
      )}

      {false && (
        <>
      <section className="bg-surface-02 border border-surface-03 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-surface-03 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-cream">Observabilidade</h2>
            <p className="text-xs text-stone mt-1">
              Saude operacional da fila, providers e alertas internos do AGENTE WHATSAPP
            </p>
          </div>
          <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold ${healthClass(observability?.health_status)}`}>
            <Activity size={14} />
            {healthLabel(observability?.health_status)}
          </span>
        </div>

        <div className="p-4 grid grid-cols-2 lg:grid-cols-5 gap-3">
          <StatCard icon={BarChart3} label="Sucesso de envio" value={`${observability?.success_rate ?? 100}%`} />
          <StatCard icon={AlertTriangle} label="Alertas ativos" value={observability?.active_alerts ?? 0} />
          <StatCard icon={PauseCircle} label="Providers pausados" value={observability?.providers_paused ?? 0} />
          <StatCard icon={Clock3} label="Pendente mais antigo" value={secondsLabel(observability?.oldest_pending_age_seconds)} />
          <StatCard icon={Send} label="Entregas tentadas" value={observability?.attempted_deliveries ?? 0} />
        </div>

        <div className="border-t border-surface-03 p-4 grid grid-cols-1 xl:grid-cols-[1.2fr_1fr] gap-4">
          <div className="rounded-xl border border-surface-03 overflow-hidden">
            <div className="px-4 py-3 border-b border-surface-03">
              <h3 className="text-sm font-bold text-cream">Providers</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[620px] text-sm">
                <thead className="bg-surface-03/60 text-xs text-stone">
                  <tr>
                    <th className="text-left font-medium px-4 py-3">Provider</th>
                    <th className="text-left font-medium px-4 py-3">Status</th>
                    <th className="text-left font-medium px-4 py-3">Sucesso</th>
                    <th className="text-left font-medium px-4 py-3">Falhas</th>
                    <th className="text-left font-medium px-4 py-3">Latencia</th>
                    <th className="text-left font-medium px-4 py-3">Ultima falha</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-03">
                  {(observability?.providers ?? []).map((provider) => (
                    <tr key={provider.provider} className="text-cream">
                      <td className="px-4 py-3 font-semibold">{provider.provider}</td>
                      <td className="px-4 py-3">
                        <span className={`text-[11px] border rounded-full px-2 py-0.5 ${
                          provider.status === "paused"
                            ? "border-red-500/30 bg-red-500/10 text-red-300"
                            : "border-green-500/30 bg-green-500/10 text-green-300"
                        }`}>
                          {provider.status === "paused" ? "Pausado" : "Ativo"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-stone">{provider.success_rate}%</td>
                      <td className="px-4 py-3 text-stone">{provider.failed + provider.dead}</td>
                      <td className="px-4 py-3 text-stone">{secondsLabel(provider.avg_send_latency_seconds)}</td>
                      <td className="px-4 py-3 text-stone">{fmtDate(provider.last_failure_at)}</td>
                    </tr>
                  ))}

                  {(observability?.providers ?? []).length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-stone">Sem providers monitorados</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-1 gap-4">
            <div className="rounded-xl border border-surface-03 overflow-hidden">
              <div className="px-4 py-3 border-b border-surface-03">
                <h3 className="text-sm font-bold text-cream">Erros recentes</h3>
              </div>
              <div className="divide-y divide-surface-03 max-h-56 overflow-y-auto">
                {(observability?.recent_errors ?? []).map((item) => (
                  <div key={item.id} className="px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <span className={`text-[11px] border rounded-full px-2 py-0.5 ${outboxClass(item.status)}`}>
                        {outboxLabel(item.status)}
                      </span>
                      <span className="text-[11px] text-stone">{fmtDate(item.updated_at)}</span>
                    </div>
                    <p className="text-xs text-cream mt-2 truncate">{item.phone} - {whatsappProviderLabels[item.provider] ?? item.provider}</p>
                    <p className="text-xs text-red-300 mt-1 truncate">{item.error || "Sem erro detalhado"}</p>
                  </div>
                ))}

                {(observability?.recent_errors ?? []).length === 0 && (
                  <div className="px-4 py-8 text-center text-sm text-stone">Sem erros recentes</div>
                )}
              </div>
            </div>

            <div className="rounded-xl border border-surface-03 overflow-hidden">
              <div className="px-4 py-3 border-b border-surface-03">
                <h3 className="text-sm font-bold text-cream">Historico de alertas</h3>
              </div>
              <div className="divide-y divide-surface-03 max-h-56 overflow-y-auto">
                {(observability?.alert_history ?? []).slice(0, 8).map((alert) => (
                  <div key={alert.id} className="px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-xs font-semibold text-cream truncate">{alert.title}</span>
                      <span className={`text-[11px] border rounded-full px-2 py-0.5 ${
                        alert.status === "resolved"
                          ? "border-green-500/30 bg-green-500/10 text-green-300"
                          : alert.status === "acknowledged"
                            ? "border-blue-500/30 bg-blue-500/10 text-blue-300"
                            : alertClass(alert.level)
                      }`}>
                        {alert.status}
                      </span>
                    </div>
                    <p className="text-xs text-stone mt-1 truncate">{alert.message}</p>
                    <p className="text-[11px] text-stone mt-1">{fmtDate(alert.last_seen_at || alert.updated_at)}</p>
                  </div>
                ))}

                {(observability?.alert_history ?? []).length === 0 && (
                  <div className="px-4 py-8 text-center text-sm text-stone">Sem alertas registrados</div>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="bg-surface-02 border border-surface-03 rounded-xl p-4">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div>
            <h2 className="text-base font-bold text-cream">Integrações do Atendimento</h2>
            <p className="text-xs text-stone mt-1">
              Campanhas, templates e automacoes continuam nos modulos oficiais. O AGENTE WHATSAPP acompanha conversas, fila e origem das mensagens geradas por esses fluxos.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <a
              href="/painel/marketing/whatsapp"
              className="h-9 px-3 rounded-xl border border-surface-03 text-stone hover:text-cream hover:bg-surface-03 text-xs font-semibold flex items-center gap-2"
            >
              <Send size={14} />
              Disparador WhatsApp
            </a>
            <a
              href="/painel/marketing/automacoes"
              className="h-9 px-3 rounded-xl border border-surface-03 text-stone hover:text-cream hover:bg-surface-03 text-xs font-semibold flex items-center gap-2"
            >
              <RefreshCw size={14} />
              Automacoes
            </a>
          </div>
        </div>
      </section>

      </>
      )}

      {false && (
      <section className="bg-surface-02 border border-surface-03 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-surface-03 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-cream">Campanhas WhatsApp</h2>
            <p className="text-xs text-stone mt-1">
              Crie campanhas com publico, template, agendamento e envio pela fila oficial do AGENTE WHATSAPP
            </p>
          </div>
          <button
            onClick={processScheduledCampaigns}
            disabled={campaignSaving}
            className="h-9 px-3 rounded-xl border border-surface-03 text-stone text-xs font-semibold flex items-center gap-2 disabled:opacity-50"
          >
            {campaignSaving ? <Loader2 size={15} className="animate-spin" /> : <Clock3 size={15} />}
            Processar agendadas
          </button>
        </div>

        <div className="p-4 grid grid-cols-1 xl:grid-cols-[420px_minmax(0,1fr)] gap-4">
          <div className="rounded-xl border border-surface-03 bg-surface-00/30 p-4 space-y-3">
            <div>
              <label className="text-xs text-stone">Nome da campanha</label>
              <input
                value={campaignForm.name}
                onChange={(event) => setCampaignForm((current) => ({ ...current, name: event.target.value }))}
                className="mt-1 w-full h-10 bg-surface-03 border border-surface-03 rounded-xl px-3 text-sm text-cream outline-none focus:border-gold"
                placeholder="Ex: Recompra quinta-feira"
              />
            </div>

            <div>
              <label className="text-xs text-stone">Publico</label>
              <select
                value={campaignForm.audience_type}
                onChange={(event) => setCampaignForm((current) => ({ ...current, audience_type: event.target.value as CampaignAudience }))}
                className="mt-1 w-full h-10 bg-surface-03 border border-surface-03 rounded-xl px-3 text-sm text-cream outline-none focus:border-gold"
              >
                <option value="manual">Lista manual</option>
                <option value="customers">Clientes com consentimento WhatsApp</option>
                <option value="leads">Leads WhatsApp</option>
              </select>
            </div>

            {campaignForm.audience_type === "manual" && (
              <div>
                <label className="text-xs text-stone">Telefones</label>
                <textarea
                  value={campaignForm.phones}
                  onChange={(event) => setCampaignForm((current) => ({ ...current, phones: event.target.value }))}
                  rows={3}
                  className="mt-1 w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-sm text-cream outline-none resize-none focus:border-gold"
                  placeholder="Um telefone por linha ou separados por virgula"
                />
              </div>
            )}

            <div>
              <label className="text-xs text-stone">Templates rapidos</label>
              <div className="mt-1 flex flex-wrap gap-2">
                {campaignTemplates.map((template) => (
                  <button
                    key={template.id}
                    type="button"
                    onClick={() => setCampaignForm((current) => ({ ...current, message_template: template.body }))}
                    className="px-3 py-1.5 rounded-full border border-surface-03 text-xs text-stone hover:text-cream hover:bg-surface-03"
                  >
                    {template.name}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="text-xs text-stone">Mensagem</label>
              <textarea
                value={campaignForm.message_template}
                onChange={(event) => setCampaignForm((current) => ({ ...current, message_template: event.target.value }))}
                rows={4}
                className="mt-1 w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-sm text-cream outline-none resize-none focus:border-gold"
                placeholder="Use {{nome}}, {{primeiro_nome}} ou {{telefone}}"
              />
            </div>

            <div>
              <label className="text-xs text-stone">Agendar para</label>
              <input
                type="datetime-local"
                value={campaignForm.scheduled_at}
                onChange={(event) => setCampaignForm((current) => ({ ...current, scheduled_at: event.target.value }))}
                className="mt-1 w-full h-10 bg-surface-03 border border-surface-03 rounded-xl px-3 text-sm text-cream outline-none focus:border-gold"
              />
            </div>

            <button
              onClick={createCampaign}
              disabled={campaignSaving || !campaignForm.name.trim() || !campaignForm.message_template.trim()}
              className="w-full h-10 rounded-xl bg-gold text-black text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {campaignSaving ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
              Salvar campanha
            </button>
          </div>

          <div className="rounded-xl border border-surface-03 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[780px] text-sm">
                <thead className="bg-surface-03/60 text-xs text-stone">
                  <tr>
                    <th className="text-left font-medium px-4 py-3">Campanha</th>
                    <th className="text-left font-medium px-4 py-3">Status</th>
                    <th className="text-left font-medium px-4 py-3">Publico</th>
                    <th className="text-left font-medium px-4 py-3">Fila</th>
                    <th className="text-left font-medium px-4 py-3">Agendamento</th>
                    <th className="text-right font-medium px-4 py-3">Acoes</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-03">
                  {campaigns.map((campaign) => (
                    <tr key={campaign.id} className="text-cream">
                      <td className="px-4 py-3">
                        <p className="font-semibold truncate">{campaign.name}</p>
                        <p className="text-xs text-stone truncate">{campaign.message_template}</p>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-[11px] border rounded-full px-2 py-0.5 ${campaignStatusClass(campaign.status)}`}>
                          {campaignStatusLabel(campaign.status)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-stone">
                        {campaign.audience.audience_type === "manual"
                          ? `${campaign.audience.phones?.length ?? 0} telefone(s)`
                          : campaign.audience.audience_type === "customers"
                            ? "Clientes consentidos"
                            : "Leads WhatsApp"}
                      </td>
                      <td className="px-4 py-3 text-stone">
                        {campaign.metrics.sent ?? 0} env. / {campaign.metrics.pending ?? 0} pend. / {campaign.metrics.failed ?? 0} falha
                      </td>
                      <td className="px-4 py-3 text-stone">{fmtDate(campaign.scheduled_at)}</td>
                      <td className="px-4 py-3">
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => dispatchCampaign(campaign, false)}
                            disabled={campaignDispatchingId === campaign.id}
                            className="h-8 px-3 rounded-xl border border-gold/40 text-gold hover:bg-gold/10 text-xs font-semibold flex items-center gap-2 disabled:opacity-50"
                          >
                            {campaignDispatchingId === campaign.id ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                            Disparar
                          </button>
                          {campaign.status === "scheduled" && (
                            <button
                              onClick={() => dispatchCampaign(campaign, true)}
                              disabled={campaignDispatchingId === campaign.id}
                              className="h-8 px-3 rounded-xl border border-amber-500/30 text-amber-300 hover:bg-amber-500/10 text-xs font-semibold disabled:opacity-50"
                            >
                              Agora
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}

                  {campaigns.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-stone">Nenhuma campanha criada</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>
      )}

      {false && (

      <section className="bg-surface-02 border border-surface-03 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-surface-03 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-cream">Stories WhatsApp</h2>
            <p className="text-xs text-stone mt-1">
              Biblioteca de status com upload de imagem/video, CTA, agendamento e publicacao controlada
            </p>
          </div>
          <button
            onClick={processScheduledStories}
            disabled={storySaving}
            className="h-9 px-3 rounded-xl border border-surface-03 text-stone text-xs font-semibold flex items-center gap-2 disabled:opacity-50"
          >
            {storySaving ? <Loader2 size={15} className="animate-spin" /> : <Clock3 size={15} />}
            Processar agendados
          </button>
        </div>

        <div className="p-4 grid grid-cols-1 xl:grid-cols-[420px_minmax(0,1fr)] gap-4">
          <div className="rounded-xl border border-surface-03 bg-surface-00/30 p-4 space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-[1fr_130px] gap-3">
              <div>
                <label className="text-xs text-stone">Titulo</label>
                <input
                  value={storyForm.title}
                  onChange={(event) => setStoryForm((current) => ({ ...current, title: event.target.value }))}
                  className="mt-1 w-full h-10 bg-surface-03 border border-surface-03 rounded-xl px-3 text-sm text-cream outline-none focus:border-gold"
                  placeholder="Ex: Oferta da noite"
                />
              </div>
              <div>
                <label className="text-xs text-stone">Midia</label>
                <select
                  value={storyForm.media_type}
                  onChange={(event) => setStoryForm((current) => ({ ...current, media_type: event.target.value as StoryMediaType, media_url: "" }))}
                  className="mt-1 w-full h-10 bg-surface-03 border border-surface-03 rounded-xl px-3 text-sm text-cream outline-none focus:border-gold"
                >
                  <option value="image">Imagem</option>
                  <option value="video">Video</option>
                </select>
              </div>
            </div>

            <MediaUpload
              value={storyForm.media_url}
              onChange={(value) => setStoryForm((current) => ({ ...current, media_url: value }))}
              mediaType={storyForm.media_type}
              label="Arquivo do story"
              hint="Use uma imagem ou video vertical sempre que possivel."
              sizeGuide="Recomendado para rapidez: imagem 1080x1920 WebP/JPG ate 250KB; video MP4/WebM 720x1280, 5 a 12s, ideal ate 2MB."
            />

            <div>
              <label className="text-xs text-stone">Templates rapidos</label>
              <div className="mt-1 flex flex-wrap gap-2">
                {storyTemplates.map((template) => (
                  <button
                    key={template.id}
                    type="button"
                    onClick={() => setStoryForm((current) => ({
                      ...current,
                      title: template.title,
                      caption: template.caption,
                      cta_text: template.cta_text || "",
                      cta_url: template.cta_url || "",
                    }))}
                    className="px-3 py-1.5 rounded-full border border-surface-03 text-xs text-stone hover:text-cream hover:bg-surface-03"
                  >
                    {template.name}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="text-xs text-stone">Legenda</label>
              <textarea
                value={storyForm.caption}
                onChange={(event) => setStoryForm((current) => ({ ...current, caption: event.target.value }))}
                rows={3}
                className="mt-1 w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-sm text-cream outline-none resize-none focus:border-gold"
                placeholder="Texto que acompanha o status"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-stone">CTA</label>
                <input
                  value={storyForm.cta_text}
                  onChange={(event) => setStoryForm((current) => ({ ...current, cta_text: event.target.value }))}
                  className="mt-1 w-full h-10 bg-surface-03 border border-surface-03 rounded-xl px-3 text-sm text-cream outline-none focus:border-gold"
                  placeholder="Pedir agora"
                />
              </div>
              <div>
                <label className="text-xs text-stone">Link CTA</label>
                <input
                  value={storyForm.cta_url}
                  onChange={(event) => setStoryForm((current) => ({ ...current, cta_url: event.target.value }))}
                  className="mt-1 w-full h-10 bg-surface-03 border border-surface-03 rounded-xl px-3 text-sm text-cream outline-none focus:border-gold"
                  placeholder="https://..."
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-stone">Campanha</label>
                <select
                  value={storyForm.campaign_id}
                  onChange={(event) => setStoryForm((current) => ({ ...current, campaign_id: event.target.value }))}
                  className="mt-1 w-full h-10 bg-surface-03 border border-surface-03 rounded-xl px-3 text-sm text-cream outline-none focus:border-gold"
                >
                  <option value="">Sem campanha</option>
                  {campaigns.map((campaign) => (
                    <option key={campaign.id} value={campaign.id}>{campaign.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-stone">Agendar para</label>
                <input
                  type="datetime-local"
                  value={storyForm.scheduled_at}
                  onChange={(event) => setStoryForm((current) => ({ ...current, scheduled_at: event.target.value }))}
                  className="mt-1 w-full h-10 bg-surface-03 border border-surface-03 rounded-xl px-3 text-sm text-cream outline-none focus:border-gold"
                />
              </div>
            </div>

            <button
              onClick={createStory}
              disabled={storySaving || !storyForm.title.trim() || !storyForm.media_url.trim()}
              className="w-full h-10 rounded-xl bg-gold text-black text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {storySaving ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
              Salvar story
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-3 gap-3">
            {stories.map((story) => (
              <div key={story.id} className="rounded-xl border border-surface-03 bg-surface-00/30 overflow-hidden flex flex-col">
                <div className="aspect-[9/16] bg-surface-03 relative overflow-hidden">
                  {story.media_type === "video" ? (
                    <video src={resolveAssetUrl(story.media_url)} className="h-full w-full object-cover" muted playsInline />
                  ) : (
                    <img src={resolveAssetUrl(story.media_url)} alt={story.title} className="h-full w-full object-cover" />
                  )}
                  <div className="absolute left-2 top-2 flex items-center gap-1.5">
                    <span className={`text-[11px] border rounded-full px-2 py-0.5 ${storyStatusClass(story.status)}`}>
                      {storyStatusLabel(story.status)}
                    </span>
                    <span className="rounded-full border border-black/30 bg-black/50 px-2 py-0.5 text-[11px] text-white">
                      {story.media_type === "video" ? <Video size={11} className="inline mr-1" /> : <ImageIcon size={11} className="inline mr-1" />}
                      {story.media_type === "video" ? "Video" : "Imagem"}
                    </span>
                  </div>
                </div>
                <div className="p-3 flex-1 flex flex-col gap-3">
                  <div>
                    <p className="text-sm font-semibold text-cream truncate">{story.title}</p>
                    <p className="text-xs text-stone mt-1 line-clamp-2">{story.caption || "Sem legenda"}</p>
                  </div>
                  {(story.cta_text || story.cta_url) && (
                    <div className="flex items-center gap-2 text-xs text-gold">
                      <LinkIcon size={13} />
                      <span className="truncate">{story.cta_text || story.cta_url}</span>
                    </div>
                  )}
                  <div className="grid grid-cols-2 gap-2 text-[11px] text-stone">
                    <span>Agend: {fmtDate(story.scheduled_at)}</span>
                    <span>Publ: {fmtDate(story.published_at)}</span>
                    <span>Views: {story.metrics.views ?? 0}</span>
                    <span>Resp: {story.metrics.replies ?? 0}</span>
                  </div>
                  <div className="mt-auto flex gap-2">
                    <button
                      onClick={() => publishStory(story, false)}
                      disabled={storyPublishingId === story.id || story.status === "published"}
                      className="flex-1 h-9 rounded-xl border border-gold/40 text-gold hover:bg-gold/10 text-xs font-semibold flex items-center justify-center gap-2 disabled:opacity-50"
                    >
                      {storyPublishingId === story.id ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                      Publicar
                    </button>
                    {story.status === "scheduled" && (
                      <button
                        onClick={() => publishStory(story, true)}
                        disabled={storyPublishingId === story.id}
                        className="h-9 px-3 rounded-xl border border-amber-500/30 text-amber-300 hover:bg-amber-500/10 text-xs font-semibold disabled:opacity-50"
                      >
                        Agora
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}

            {stories.length === 0 && (
              <div className="md:col-span-2 2xl:col-span-3 rounded-xl border border-surface-03 px-4 py-12 text-center text-sm text-stone">
                Nenhum story criado
              </div>
            )}
          </div>
        </div>
      </section>
      )}

      {moduleTab === "conversations" && (
        <>

      {false && (
      <section className="bg-surface-02 border border-surface-03 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-surface-03 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-cream">Automacoes Comerciais</h2>
            <p className="text-xs text-stone mt-1">
              Recompra, reativacao, carrinho abandonado, aniversario e fidelidade com deduplicacao por cliente
            </p>
          </div>
          <button
            onClick={runDueAutomations}
            disabled={automationRunning}
            className="h-9 px-3 rounded-xl border border-surface-03 text-stone text-xs font-semibold flex items-center gap-2 disabled:opacity-50"
          >
            {automationRunning ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
            Rodar todas
          </button>
        </div>

        <div className="p-4 grid grid-cols-1 xl:grid-cols-[420px_minmax(0,1fr)] gap-4">
          <div className="rounded-xl border border-surface-03 bg-surface-00/30 p-4 space-y-3">
            <div>
              <label className="text-xs text-stone">Automacao</label>
              <select
                value={automationForm.key}
                onChange={(event) => {
                  const next = automationTemplates.find((item) => item.key === event.target.value);
                  setAutomationForm((current) => ({
                    ...current,
                    key: event.target.value,
                    message_template: next?.default_message || "",
                  }));
                  setAutomationResult(null);
                }}
                className="mt-1 w-full h-10 bg-surface-03 border border-surface-03 rounded-xl px-3 text-sm text-cream outline-none focus:border-gold"
              >
                {automationTemplates.map((item) => (
                  <option key={item.key} value={item.key}>{item.name}</option>
                ))}
              </select>
              {selectedAutomation && (
                <p className="mt-2 text-xs text-stone">{selectedAutomation.description}</p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-stone">Limite</label>
                <input
                  type="number"
                  min={1}
                  max={300}
                  value={automationForm.limit}
                  onChange={(event) => setAutomationForm((current) => ({ ...current, limit: Number(event.target.value) || 1 }))}
                  className="mt-1 w-full h-10 bg-surface-03 border border-surface-03 rounded-xl px-3 text-sm text-cream outline-none focus:border-gold"
                />
              </div>
              <div>
                <label className="text-xs text-stone">Cooldown</label>
                <div className="mt-1 h-10 rounded-xl border border-surface-03 bg-surface-03 px-3 text-sm text-stone flex items-center">
                  {selectedAutomation?.cooldown_days ?? "-"} dia(s)
                </div>
              </div>
            </div>

            <div>
              <label className="text-xs text-stone">Mensagem</label>
              <textarea
                value={automationForm.message_template || selectedAutomation?.default_message || ""}
                onChange={(event) => setAutomationForm((current) => ({ ...current, message_template: event.target.value }))}
                rows={4}
                className="mt-1 w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-sm text-cream outline-none resize-none focus:border-gold"
                placeholder="Use {{nome}}, {{primeiro_nome}}, {{telefone}} ou {{pontos}}"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => runAutomation(true)}
                disabled={automationRunning || !automationForm.key}
                className="h-10 rounded-xl border border-surface-03 text-stone text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {automationRunning ? <Loader2 size={15} className="animate-spin" /> : <Eye size={15} />}
                Previa
              </button>
              <button
                onClick={() => runAutomation(false)}
                disabled={automationRunning || !automationForm.key}
                className="h-10 rounded-xl bg-gold text-black text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {automationRunning ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
                Enfileirar
              </button>
            </div>
          </div>

          <div className="rounded-xl border border-surface-03 overflow-hidden">
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 p-4 border-b border-surface-03">
              <StatCard icon={Users} label="Elegiveis" value={automationResult?.eligible ?? 0} />
              <StatCard icon={Send} label="Na fila" value={automationResult?.queued ?? 0} />
              <StatCard icon={CheckCircle2} label="Enfileiradas" value={automationResult?.enqueued ?? 0} />
              <StatCard icon={PauseCircle} label="Ignoradas" value={automationResult?.skipped ?? 0} />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-sm">
                <thead className="bg-surface-03/60 text-xs text-stone">
                  <tr>
                    <th className="text-left font-medium px-4 py-3">Cliente</th>
                    <th className="text-left font-medium px-4 py-3">Telefone</th>
                    <th className="text-left font-medium px-4 py-3">Motivo</th>
                    <th className="text-left font-medium px-4 py-3">Ultimo pedido</th>
                    <th className="text-left font-medium px-4 py-3">Fidelidade</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-03">
                  {(automationResult?.candidates ?? []).map((candidate) => (
                    <tr key={`${automationResult?.key}-${candidate.customer_id}`} className="text-cream">
                      <td className="px-4 py-3 font-semibold">{candidate.name}</td>
                      <td className="px-4 py-3 text-stone">{candidate.phone}</td>
                      <td className="px-4 py-3 text-stone">{candidate.reason}</td>
                      <td className="px-4 py-3 text-stone">{fmtDate(candidate.last_order_at)}</td>
                      <td className="px-4 py-3 text-stone">{candidate.loyalty_points ?? "-"}</td>
                    </tr>
                  ))}

                  {!automationResult && (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-stone">Execute uma previa para ver clientes elegiveis</td>
                    </tr>
                  )}

                  {automationResult && automationResult.candidates.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-stone">Nenhum cliente elegivel no momento</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>
      )}

      {false && (
      <>
      <div className="bg-surface-02 border border-surface-03 rounded-xl px-4 py-3 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3 text-xs text-stone">
          <span className="text-cream font-semibold">Fila de envio</span>
          <span>Pendentes: {outboxSummary?.pending ?? 0}</span>
          <span>Queued: {outboxSummary?.queued_messages ?? 0}</span>
          <span>Falhas: {outboxSummary?.failed ?? 0}</span>
          <span>Mortas: {outboxSummary?.dead ?? 0}</span>
          <span>Latencia media: {outboxSummary?.avg_send_latency_seconds ?? "-"}s</span>
        </div>
        <button
          onClick={processQueue}
          disabled={processingQueue}
          className="h-9 px-3 rounded-xl border border-gold/40 bg-gold/10 text-gold text-xs font-semibold flex items-center justify-center gap-2 disabled:opacity-50"
        >
          {processingQueue ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
          Processar fila
        </button>
      </div>

      {outboxAlerts.length > 0 && (
        <div className="space-y-2">
          {outboxAlerts.map((alert) => (
            <div key={`${alert.code}-${alert.message}`} className={`flex items-center gap-3 rounded-xl border px-4 py-3 text-sm ${alertClass(alert.level)}`}>
              <AlertTriangle size={17} className="shrink-0" />
              <span>{alert.message}</span>
            </div>
          ))}
        </div>
      )}

      <section className="bg-surface-02 border border-surface-03 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-surface-03 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-cream">Auditoria da fila</h2>
            <p className="text-xs text-stone mt-1">
              Ultimo erro: {outboxSummary?.last_error ? outboxSummary.last_error : "sem erro registrado"}
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex gap-1.5 overflow-x-auto pb-1">
              {outboxFilterOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => setOutboxFilter(option.value)}
                  className={`px-3 py-1.5 rounded-full text-xs border whitespace-nowrap transition-colors ${
                    outboxFilter === option.value
                      ? "border-gold bg-gold text-black"
                      : "border-surface-03 text-stone hover:text-cream"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <button
              onClick={() => loadOutbox()}
              disabled={outboxLoading}
              className="h-9 px-3 rounded-xl border border-surface-03 text-stone text-xs font-semibold flex items-center gap-2 disabled:opacity-50"
            >
              {outboxLoading ? <Loader2 size={15} className="animate-spin" /> : <ListFilter size={15} />}
              Atualizar
            </button>
          </div>
        </div>

        <div className="p-4 border-b border-surface-03 grid grid-cols-1 md:grid-cols-2 gap-3">
          {providerStates.map((provider) => (
            <div key={provider.provider} className="rounded-xl border border-surface-03 bg-surface-00/30 p-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-cream">{whatsappProviderLabels[provider.provider] ?? provider.provider}</span>
                  <span className={`text-[11px] border rounded-full px-2 py-0.5 ${
                    provider.status === "paused"
                      ? "border-red-500/30 bg-red-500/10 text-red-300"
                      : "border-green-500/30 bg-green-500/10 text-green-300"
                  }`}>
                    {provider.status === "paused" ? "Pausado" : "Ativo"}
                  </span>
                </div>
                <p className="text-xs text-stone mt-1">
                  Falhas: {provider.consecutive_failures}/{provider.failure_threshold}
                  {provider.paused_until ? ` - ate ${fmtDate(provider.paused_until)}` : ""}
                </p>
                {provider.paused_reason && (
                  <p className="text-xs text-red-300 mt-1">{provider.paused_reason}</p>
                )}
              </div>
              <div className="flex gap-2">
                {provider.status === "paused" ? (
                  <button
                    onClick={() => resumeProvider(provider.provider)}
                    disabled={providerAction === provider.provider}
                    className="h-9 px-3 rounded-xl border border-green-500/30 bg-green-500/10 text-green-300 text-xs font-semibold flex items-center gap-2 disabled:opacity-50"
                  >
                    {providerAction === provider.provider ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                    Retomar
                  </button>
                ) : (
                  <button
                    onClick={() => pauseProvider(provider.provider)}
                    disabled={providerAction === provider.provider}
                    className="h-9 px-3 rounded-xl border border-red-500/30 bg-red-500/10 text-red-300 text-xs font-semibold flex items-center gap-2 disabled:opacity-50"
                  >
                    {providerAction === provider.provider ? <Loader2 size={14} className="animate-spin" /> : <PauseCircle size={14} />}
                    Pausar
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-sm">
            <thead className="bg-surface-03/60 text-xs text-stone">
              <tr>
                <th className="text-left font-medium px-4 py-3">Status</th>
                <th className="text-left font-medium px-4 py-3">Telefone</th>
                <th className="text-left font-medium px-4 py-3">Mensagem</th>
                <th className="text-left font-medium px-4 py-3">Provider</th>
                <th className="text-left font-medium px-4 py-3">Tentativas</th>
                <th className="text-left font-medium px-4 py-3">Atualizado</th>
                <th className="text-right font-medium px-4 py-3">Acoes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-03">
              {outboxLoading && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-stone">
                    <Loader2 size={20} className="animate-spin inline-block" />
                  </td>
                </tr>
              )}

              {!outboxLoading && outboxItems.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-stone">
                    Nenhum item encontrado
                  </td>
                </tr>
              )}

              {!outboxLoading && outboxItems.map((item) => (
                <tr key={item.id} className="text-cream hover:bg-surface-03/40">
                  <td className="px-4 py-3">
                    <span className={`text-[11px] border rounded-full px-2 py-0.5 ${outboxClass(item.status)}`}>
                      {outboxLabel(item.status)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-stone">{item.phone}</td>
                  <td className="px-4 py-3 max-w-[260px]">
                    <p className="truncate">{item.message_body || item.message_type || shortId(item.message_id)}</p>
                    {item.error && <p className="text-xs text-red-300 truncate mt-1">{item.error}</p>}
                  </td>
                  <td className="px-4 py-3 text-stone">{whatsappProviderLabels[item.provider] ?? item.provider}</td>
                  <td className="px-4 py-3 text-stone">{item.attempts}/{item.max_attempts}</td>
                  <td className="px-4 py-3 text-stone">{fmtDate(item.updated_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => setSelectedOutbox(item)}
                        className="h-8 w-8 rounded-xl border border-surface-03 text-stone hover:text-cream flex items-center justify-center"
                        title="Ver detalhe"
                      >
                        <Eye size={14} />
                      </button>
                      {["failed", "dead", "pending"].includes(item.status) && (
                        <button
                          onClick={() => retryOutboxItem(item)}
                          disabled={retryingId === item.id}
                          className="h-8 w-8 rounded-xl border border-gold/40 text-gold hover:bg-gold/10 flex items-center justify-center disabled:opacity-50"
                          title="Reprocessar"
                        >
                          {retryingId === item.id ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {selectedOutbox && (
          <div className="border-t border-surface-03 p-4 grid grid-cols-1 lg:grid-cols-[1fr_1.4fr] gap-4">
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="text-stone">Item</span>
                <span className="text-cream font-mono text-xs">{shortId(selectedOutbox.id)}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-stone">Mensagem</span>
                <span className="text-cream font-mono text-xs">{shortId(selectedOutbox.message_id)}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-stone">Provedor</span>
                <span className="text-cream">{selectedOutbox.provider}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-stone">Proxima tentativa</span>
                <span className="text-cream">{fmtDate(selectedOutbox.next_attempt_at)}</span>
              </div>
            </div>
            <div className="rounded-xl border border-surface-03 bg-surface-00/40 p-3">
              <p className="text-xs uppercase tracking-wide text-stone mb-2">Erro</p>
              <p className="text-sm text-cream whitespace-pre-wrap break-words">
                {selectedOutbox.error || "Sem erro registrado"}
              </p>
              {selectedOutbox.provider_message_id && (
                <p className="text-xs text-stone mt-3">Provider ID: {selectedOutbox.provider_message_id}</p>
              )}
            </div>
          </div>
        )}
      </section>

      </>
      )}

      {activeModuleTab === "order_notifications" && (
        <OrderWhatsappNotificationSettingsPanel />
      )}

      {activeModuleTab === "conversations" && (
      <div className="grid grid-cols-1 xl:grid-cols-[380px_minmax(0,1fr)] gap-4 min-h-[640px]">
        <section className="bg-surface-02 border border-surface-03 rounded-xl overflow-hidden flex flex-col min-h-[640px]">
          <div className="p-4 border-b border-surface-03 space-y-3">
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone" />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Buscar conversa"
                  className="w-full h-10 bg-surface-03 border border-surface-03 rounded-xl pl-9 pr-3 text-sm text-cream outline-none focus:border-gold"
                />
              </div>
              <button
                onClick={() => loadSessions()}
                className="h-10 w-10 rounded-xl border border-surface-03 bg-surface-03 text-stone hover:text-cream flex items-center justify-center"
                disabled={loading}
              >
                {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              </button>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
              {filterOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => setFilter(option.value)}
                  className={`min-w-0 h-8 px-2 rounded-lg text-[11px] leading-tight border text-center transition-colors overflow-hidden ${
                    filter === option.value
                      ? "border-gold bg-gold text-black"
                      : "border-surface-03 bg-surface-03/60 text-stone hover:text-cream"
                  }`}
                >
                  <span className="block truncate">{option.label}</span>
                </button>
              ))}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <input
                value={agentFilter}
                onChange={(event) => setAgentFilter(event.target.value)}
                placeholder="Atendente/agente"
                className="h-9 bg-surface-03 border border-surface-03 rounded-xl px-3 text-xs text-cream outline-none focus:border-gold"
              />
              <input
                type="date"
                value={periodFrom}
                onChange={(event) => setPeriodFrom(event.target.value)}
                className="h-9 bg-surface-03 border border-surface-03 rounded-xl px-3 text-xs text-cream outline-none focus:border-gold"
              />
              <input
                type="date"
                value={periodTo}
                onChange={(event) => setPeriodTo(event.target.value)}
                className="h-9 bg-surface-03 border border-surface-03 rounded-xl px-3 text-xs text-cream outline-none focus:border-gold"
              />
            </div>

            <div className="flex gap-2">
              <input
                value={newPhone}
                onChange={(event) => setNewPhone(event.target.value)}
                placeholder="Telefone"
                className="flex-1 h-10 bg-surface-03 border border-surface-03 rounded-xl px-3 text-sm text-cream outline-none focus:border-gold"
              />
              <span className="h-10 w-28 bg-surface-03 border border-surface-03 rounded-xl px-2 text-[11px] text-stone flex items-center justify-center">
                {channelProvider === "baileys" ? "Gateway" : "Oficial"}
              </span>
              <button
                onClick={createSession}
                disabled={saving || !newPhone.trim()}
                className="h-10 px-3 rounded-xl bg-gold text-black font-semibold disabled:opacity-50 flex items-center gap-1"
              >
                <Plus size={15} />
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto">
            {loading && (
              <div className="h-48 flex items-center justify-center text-stone">
                <Loader2 size={22} className="animate-spin" />
              </div>
            )}

            {!loading && filteredSessions.length === 0 && (
              <div className="h-48 flex items-center justify-center text-sm text-stone">
                Nenhuma conversa encontrada
              </div>
            )}

            {!loading && filteredSessions.map((session) => {
              const last = lastMessageBySession.get(session.id);
              return (
                <button
                  key={session.id}
                  onClick={() => {
                    setSelectedId(session.id);
                    loadDetail(session.id);
                  }}
                  className={`w-full text-left p-4 border-b border-surface-03 hover:bg-surface-03/60 transition-colors ${
                    selectedId === session.id ? "bg-surface-03/80" : ""
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-cream truncate">
                        {session.customer_name || session.phone}
                      </p>
                      <p className="text-xs text-stone truncate">{session.phone}</p>
                    </div>
                    <span className={`text-[11px] border rounded-full px-2 py-0.5 shrink-0 ${statusClasses[session.status]}`}>
                      {statusLabels[session.status]}
                    </span>
                  </div>
                  <div className="mt-2 flex items-center justify-between gap-3">
                    <p className="text-xs text-stone truncate">{firstLine(last)}</p>
                    <span className="text-[11px] text-stone shrink-0">{fmtDate(session.last_message_at || session.updated_at)}</span>
                  </div>
                  <div className="mt-2 flex items-center justify-between gap-2">
                    <span className={`text-[11px] border rounded-full px-2 py-0.5 ${
                      session.attendance_mode === "human"
                        ? "border-blue-500/30 bg-blue-500/10 text-blue-300"
                        : "border-green-500/30 bg-green-500/10 text-green-300"
                    }`}>
                      {session.attendance_mode === "human" ? "Humano" : "IA"}
                    </span>
                    {session.unread_count > 0 && (
                      <span className="rounded-full bg-gold px-2 py-0.5 text-[11px] font-bold text-black">
                        {session.unread_count} nao lida(s)
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </section>

        <section className="bg-surface-02 border border-surface-03 rounded-xl overflow-hidden min-h-[640px] flex flex-col">
          {!selected && (
            <div className="flex-1 flex flex-col items-center justify-center text-stone gap-3">
              <MessageCircle size={32} />
              <p className="text-sm">Selecione uma conversa</p>
            </div>
          )}

          {selected && (
            <>
              <div className="p-4 border-b border-surface-03 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h2 className="text-lg font-bold text-cream truncate">{selected.customer_name || selected.phone}</h2>
                    <span className={`text-xs border rounded-full px-2 py-0.5 ${statusClasses[selected.status]}`}>
                      {statusLabels[selected.status]}
                    </span>
                    <span className={`text-xs border rounded-full px-2 py-0.5 ${
                      selected.ai_enabled ? "border-green-500/30 text-green-300 bg-green-500/10" : "border-purple-500/30 text-purple-300 bg-purple-500/10"
                    }`}>
                      {selected.ai_enabled ? "IA ativa" : "IA pausada"}
                    </span>
                  </div>
                  <p className="text-sm text-stone mt-1">{selected.phone} · {selected.provider}</p>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  <button
                    onClick={() => updateSession({ status: "human", ai_enabled: false })}
                    disabled={saving}
                    className="px-3 py-2 rounded-xl border border-blue-500/30 bg-blue-500/10 text-blue-300 text-xs font-semibold flex items-center gap-1 disabled:opacity-50"
                  >
                    <UserRound size={14} /> Assumir
                  </button>
                  <button
                    onClick={() => updateSession({ status: "ai_paused", ai_enabled: false, automation_blocked: true })}
                    disabled={saving}
                    className="px-3 py-2 rounded-xl border border-purple-500/30 bg-purple-500/10 text-purple-300 text-xs font-semibold flex items-center gap-1 disabled:opacity-50"
                  >
                    <PauseCircle size={14} /> Pausar IA
                  </button>
                  <button
                    onClick={() => updateSession({ status: "open", ai_enabled: true, automation_blocked: false })}
                    disabled={saving}
                    className="px-3 py-2 rounded-xl border border-green-500/30 bg-green-500/10 text-green-300 text-xs font-semibold flex items-center gap-1 disabled:opacity-50"
                  >
                    <Bot size={14} /> Devolver IA
                  </button>
                  <button
                    onClick={() => updateSession({ status: "closed", ai_enabled: false })}
                    disabled={saving}
                    className="px-3 py-2 rounded-xl border border-surface-03 text-stone text-xs font-semibold flex items-center gap-1 disabled:opacity-50"
                  >
                    <CheckCircle2 size={14} /> Encerrar
                  </button>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-surface-00/40">
                {detailLoading && (
                  <div className="h-40 flex items-center justify-center text-stone">
                    <Loader2 size={22} className="animate-spin" />
                  </div>
                )}

                {!detailLoading && messages.length === 0 && (
                  <div className="h-40 flex items-center justify-center text-sm text-stone">
                    Sem mensagens
                  </div>
                )}

                {!detailLoading && messages.map((message) => {
                  const outbound = message.direction === "outbound";
                  const sourceLabel = messageSourceLabel(message.raw_payload?.source);
                  return (
                    <div key={message.id} className={`flex ${outbound ? "justify-end" : "justify-start"}`}>
                      <div className={`max-w-[78%] rounded-2xl px-4 py-3 border ${
                        outbound
                          ? "bg-gold/10 border-gold/30 text-cream rounded-br-md"
                          : "bg-surface-02 border-surface-03 text-cream rounded-bl-md"
                      }`}>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-[11px] uppercase tracking-wide text-stone">
                            {message.sender_type}
                          </span>
                          <span className="text-[11px] text-stone">{fmtDate(message.created_at)}</span>
                          {message.provider_status && (
                            <span className="text-[11px] text-gold">{message.provider_status}</span>
                          )}
                          {sourceLabel && (
                            <span className="text-[11px] text-blue-300">{sourceLabel}</span>
                          )}
                        </div>
                        <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">
                          {message.body || message.message_type}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="p-4 border-t border-surface-03">
                <div className="mb-2 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                  <button
                    onClick={suggestAiReply}
                    disabled={aiGenerating || (!reply.trim() && !latestInboundMessage?.body)}
                    className="h-9 px-3 rounded-xl border border-green-500/30 bg-green-500/10 text-green-300 text-xs font-semibold flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    {aiGenerating ? <Loader2 size={14} className="animate-spin" /> : <Bot size={14} />}
                    Sugerir IA
                  </button>
                  {aiSuggestion && (
                    <span className="text-[11px] text-stone truncate">{aiSuggestion}</span>
                  )}
                </div>
                {aiGuardrails && aiGuardrails.status !== "allowed" && (
                  <div className={`mb-2 rounded-xl border px-3 py-2 text-[11px] ${
                    aiGuardrails.status === "blocked"
                      ? "border-amber-500/30 bg-amber-500/10 text-amber-200"
                      : "border-blue-500/30 bg-blue-500/10 text-blue-200"
                  }`}>
                    <span className="font-semibold">
                      {aiGuardrails.status === "blocked" ? "Envio automatico bloqueado" : "Atencao da IA"}
                    </span>
                    <span className="ml-2">
                      {[...aiGuardrails.reasons, ...aiGuardrails.warnings].join(" ") || "Guardrails ativos para esta conversa."}
                    </span>
                  </div>
                )}
                <div className="flex gap-2">
                  <textarea
                    value={reply}
                    onChange={(event) => setReply(event.target.value)}
                    rows={2}
                    placeholder="Mensagem"
                    className="flex-1 bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-sm text-cream outline-none resize-none focus:border-gold"
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && !event.shiftKey) {
                        event.preventDefault();
                        sendReply();
                      }
                    }}
                  />
                  <button
                    onClick={sendReply}
                    disabled={saving || !reply.trim()}
                    className="w-12 rounded-xl bg-gold text-black flex items-center justify-center disabled:opacity-50"
                  >
                    {saving ? <Loader2 size={17} className="animate-spin" /> : <Send size={17} />}
                  </button>
                </div>
              </div>
            </>
          )}
        </section>
      </div>
      )}
        </>
      )}
    </div>
  );
}
