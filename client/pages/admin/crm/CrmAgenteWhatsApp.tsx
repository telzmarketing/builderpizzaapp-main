import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock3,
  Eye,
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
  XCircle,
} from "lucide-react";
import {
  agenteWhatsAppApi,
  type ApiAgenteWhatsAppDashboard,
  type ApiAgenteWhatsAppMessage,
  type ApiAgenteWhatsAppOutboxAlert,
  type ApiAgenteWhatsAppOutbox,
  type ApiAgenteWhatsAppOutboxMetrics,
  type ApiAgenteWhatsAppProviderState,
  type ApiAgenteWhatsAppSession,
} from "@/lib/api";

type StatusFilter = "all" | ApiAgenteWhatsAppSession["status"];
type OutboxFilter = "all" | "pending" | "processing" | "sent" | "failed" | "dead";

const statusLabels: Record<ApiAgenteWhatsAppSession["status"], string> = {
  open: "Aberta",
  waiting_human: "Fila",
  human: "Humano",
  ai_paused: "IA pausada",
  closed: "Encerrada",
};

const statusClasses: Record<ApiAgenteWhatsAppSession["status"], string> = {
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
  const [outboxSummary, setOutboxSummary] = useState<ApiAgenteWhatsAppOutboxMetrics | null>(null);
  const [outboxItems, setOutboxItems] = useState<ApiAgenteWhatsAppOutbox[]>([]);
  const [outboxAlerts, setOutboxAlerts] = useState<ApiAgenteWhatsAppOutboxAlert[]>([]);
  const [providerStates, setProviderStates] = useState<ApiAgenteWhatsAppProviderState[]>([]);
  const [outboxFilter, setOutboxFilter] = useState<OutboxFilter>("failed");
  const [selectedOutbox, setSelectedOutbox] = useState<ApiAgenteWhatsAppOutbox | null>(null);
  const [sessions, setSessions] = useState<ApiAgenteWhatsAppSession[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ApiAgenteWhatsAppMessage[]>([]);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [search, setSearch] = useState("");
  const [reply, setReply] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [outboxLoading, setOutboxLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [processingQueue, setProcessingQueue] = useState(false);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [providerAction, setProviderAction] = useState<string | null>(null);
  const [error, setError] = useState("");

  const selected = sessions.find((session) => session.id === selectedId) ?? null;

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
    if (!selected) return new Map<string, ApiAgenteWhatsAppMessage>();
    return new Map([[selected.id, messages[messages.length - 1]]]);
  }, [messages, selected]);

  async function loadSessions(preferredId?: string | null) {
    setError("");
    setLoading(true);
    try {
      const [dash, rows, outbox] = await Promise.all([
        agenteWhatsAppApi.dashboard(),
        agenteWhatsAppApi.listSessions({ limit: 100 }),
        agenteWhatsAppApi.outboxMetrics(),
      ]);
      setDashboard(dash);
      setSessions(rows);
      setOutboxSummary(outbox);
      const nextId = preferredId ?? selectedId ?? rows[0]?.id ?? null;
      setSelectedId(nextId);
      if (nextId) await loadDetail(nextId);
      else setMessages([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar o AGENTE WHATSAPP.");
    } finally {
      setLoading(false);
    }
  }

  async function loadDetail(sessionId: string) {
    setDetailLoading(true);
    try {
      const detail = await agenteWhatsAppApi.getSession(sessionId);
      setMessages(detail.messages);
      setSessions((current) => current.map((session) => (
        session.id === detail.session.id ? detail.session : session
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
      agenteWhatsAppApi.listSessions({ limit: 100 }).then(setSessions).catch(() => {});
      agenteWhatsAppApi.outboxAlerts().then((payload) => {
        setOutboxSummary(payload.metrics);
        setOutboxAlerts(payload.alerts);
        setProviderStates(payload.providers);
      }).catch(() => {});
      if (selectedId) loadDetail(selectedId);
    }, 15000);
    return () => window.clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  useEffect(() => {
    loadOutbox(outboxFilter);
    const interval = window.setInterval(() => {
      agenteWhatsAppApi.listOutbox({
        status: outboxFilter === "all" ? undefined : outboxFilter,
        limit: 80,
      }).then(setOutboxItems).catch(() => {});
    }, 15000);
    return () => window.clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [outboxFilter]);

  async function updateSession(data: Partial<Pick<ApiAgenteWhatsAppSession, "status" | "ai_enabled" | "automation_blocked">>) {
    if (!selected) return;
    setSaving(true);
    try {
      const updated = await agenteWhatsAppApi.updateSession(selected.id, data);
      setSessions((current) => current.map((session) => session.id === updated.id ? updated : session));
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
      await loadOutbox();
      setReply("");
      await loadDetail(selected.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao registrar resposta.");
    } finally {
      setSaving(false);
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

  async function createSession() {
    if (!newPhone.trim()) return;
    setSaving(true);
    try {
      const session = await agenteWhatsAppApi.createSession({
        phone: newPhone.trim(),
        origin: "manual",
        provider: "official",
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

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard icon={MessageCircle} label="Conversas abertas" value={dashboard?.sessions_open ?? 0} />
        <StatCard icon={Users} label="Atendimento humano" value={dashboard?.sessions_human ?? 0} />
        <StatCard icon={PauseCircle} label="IA pausada" value={dashboard?.sessions_ai_paused ?? 0} />
        <StatCard icon={Clock3} label="Mensagens hoje" value={dashboard?.messages_today ?? 0} />
      </div>

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
                  <span className="text-sm font-semibold text-cream">{provider.provider}</span>
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
                  <td className="px-4 py-3 text-stone">{item.provider}</td>
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

            <div className="flex gap-1.5 overflow-x-auto pb-1">
              {filterOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => setFilter(option.value)}
                  className={`px-3 py-1.5 rounded-full text-xs border whitespace-nowrap transition-colors ${
                    filter === option.value
                      ? "border-gold bg-gold text-black"
                      : "border-surface-03 text-stone hover:text-cream"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>

            <div className="flex gap-2">
              <input
                value={newPhone}
                onChange={(event) => setNewPhone(event.target.value)}
                placeholder="Telefone"
                className="flex-1 h-10 bg-surface-03 border border-surface-03 rounded-xl px-3 text-sm text-cream outline-none focus:border-gold"
              />
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
    </div>
  );
}
