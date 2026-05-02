import { useEffect, useState, useRef } from "react";
import {
  Loader2, Plus, Pencil, Trash2, X, Zap, Play, List,
  CheckCircle, XCircle, SkipForward, AlertCircle, BarChart2,
  Eye, RefreshCw, MessageSquare, Mail,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";
import {
  marketingAutomationsApi,
  type ApiAutomationEvent,
  type ApiAutomationLog,
  type ApiAutomationTemplate,
  type ApiMarketingAutomation,
} from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────
type Tab = "eventos" | "automacoes" | "templates" | "monitoramento";
type Automation = ApiMarketingAutomation;
type AutomationTemplate = ApiAutomationTemplate;
type AutomationLog = ApiAutomationLog;
type EventRow = ApiAutomationEvent;
type QueueBusy = "enqueue" | "process" | "worker";
type QueueResult = { label: string; data: Record<string, unknown> };

// ── Constants ──────────────────────────────────────────────────────────────
const TRIGGER_LABELS: Record<string, string> = {
  new_customer:       "Novo Cliente Cadastrado",
  first_order:        "Após 1º Pedido",
  repeat_order:       "Após Pedido Recorrente",
  order_completed:    "Pedido Entregue",
  order_cancelled:    "Pedido Cancelado",
  abandoned_cart:     "Carrinho Abandonado",
  reactivation:       "Reativação (sem pedido há N dias)",
  birthday:           "Aniversário do Cliente",
  birthday_week:      "Semana de Aniversário",
  low_points:         "Poucos Pontos de Fidelidade",
  level_up:           "Subiu de Nível (fidelidade)",
  no_engagement:      "Sem Engajamento (N dias sem abrir email/WA)",
  coupon_unused:      "Cupom Expirar em N dias",
  vip_milestone:      "Cliente atingiu status VIP",
  product_back:       "Produto voltou ao cardápio",
  high_value_order:   "Pedido de alto valor (acima de R$X)",
  days_after_last_order: "Apos X dias da ultima compra",
  same_weekday_last_order: "Mesmo dia da semana da ultima compra",
  preferred_purchase_time: "Horario habitual de compra",
  product_purchased: "Produto comprado anteriormente",
  category_purchased: "Categoria comprada anteriormente",
  registered_no_order: "Cadastro sem pedido",
  inactive_customer: "Cliente inativo",
  recurring_customer: "Cliente recorrente",
  vip_customer: "Cliente VIP",
  tag_match: "Cliente com tag especifica",
  group_match: "Cliente em grupo especifico",
  segment_match: "Cliente em segmento especifico",
};

const TRIGGER_VALUE_LABEL: Record<string, string> = {
  reactivation:    "Dias sem pedido",
  no_engagement:   "Dias sem engajamento",
  coupon_unused:   "Dias antes do vencimento",
  high_value_order:"Valor mínimo (R$)",
  abandoned_cart:  "Minutos após abandono",
  days_after_last_order: "Dias apos ultima compra",
  inactive_customer: "Dias sem pedido",
  recurring_customer: "Minimo de pedidos",
  vip_customer: "Total gasto minimo (R$)",
  product_purchased: "ID ou nome do produto",
  category_purchased: "Nome da categoria",
  registered_no_order: "Horas apos cadastro",
  tag_match: "ID, slug ou nome da tag",
  group_match: "ID do grupo",
  segment_match: "Nome do segmento",
};

const CHANNEL_LABELS: Record<string, string> = { whatsapp: "WhatsApp", email: "E-mail" };

const LOG_STATUS_CFG: Record<string, { label: string; cls: string; icon: React.ElementType }> = {
  sent:    { label: "Enviado",  cls: "bg-green-500/20 text-green-400", icon: CheckCircle },
  failed:  { label: "Falhou",   cls: "bg-red-500/20 text-red-400",     icon: XCircle },
  skipped: { label: "Ignorado", cls: "bg-surface-03 text-stone",       icon: SkipForward },
  pending: { label: "Pendente", cls: "bg-yellow-500/20 text-yellow-400", icon: AlertCircle },
};

function fmtDate(s?: string) {
  if (!s) return "—";
  return new Date(s).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function queueStats(result: QueueResult | null) {
  if (!result) return [];
  return Object.entries(result.data).flatMap(([key, value]) => {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      return Object.entries(value as Record<string, unknown>).map(([childKey, childValue]) => ({
        label: `${key}.${childKey}`,
        value: String(childValue ?? 0),
      }));
    }
    return [{ label: key, value: String(value ?? 0) }];
  });
}

const TABS_CFG: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "eventos",      label: "Eventos",     icon: BarChart2 },
  { id: "automacoes",   label: "Automações",  icon: Zap },
  { id: "templates",    label: "Templates",   icon: MessageSquare },
  { id: "monitoramento",label: "Monitoramento",icon: Eye },
];

const IC = "w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold";

const emptyAutoForm = (): Partial<Automation> => ({
  name: "", channel: "whatsapp", trigger: "new_customer", trigger_value: "", trigger_delay_hours: 0, template_id: "", message_body: "",
});
const emptyTplForm = (): Partial<AutomationTemplate> => ({
  name: "", channel: "whatsapp", subject: "", body: "", variables: "", category: "marketing",
});

// ══════════════════════════════════════════════════════════════════════════
export default function MarketingAutomacoes() {
  const [tab, setTab] = useState<Tab>("automacoes");

  // ── Automações ──
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [autoLoading, setAutoLoading] = useState(false);
  const [autoError, setAutoError] = useState("");
  const [showAutoModal, setShowAutoModal] = useState(false);
  const [editingAutoId, setEditingAutoId] = useState<string | null>(null);
  const [autoForm, setAutoForm] = useState<Partial<Automation>>(emptyAutoForm());
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState<string | null>(null);
  const [runResult, setRunResult] = useState<Record<string, { sent: number; failed: number; skipped: number }>>({});

  // ── Templates ──
  const [templates, setTemplates] = useState<AutomationTemplate[]>([]);
  const [tplLoading, setTplLoading] = useState(false);
  const [showTplModal, setShowTplModal] = useState(false);
  const [editingTplId, setEditingTplId] = useState<string | null>(null);
  const [tplForm, setTplForm] = useState<Partial<AutomationTemplate>>(emptyTplForm());

  // ── Monitoramento ──
  const [logs, setLogs] = useState<AutomationLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [queueBusy, setQueueBusy] = useState<QueueBusy | null>(null);
  const [queueResult, setQueueResult] = useState<QueueResult | null>(null);
  const monitorRef = useRef<ReturnType<typeof setInterval>>(null);

  // ── Eventos ──
  const [events, setEvents] = useState<EventRow[]>([]);
  const [eventsLoading, setEventsLoading] = useState(false);

  // ── Fetchers ──
  const fetchAutomations = () => {
    setAutoLoading(true); setAutoError("");
    marketingAutomationsApi.list()
      .then(d => setAutomations(d ?? []))
      .catch(() => setAutoError("Falha ao carregar automações."))
      .finally(() => setAutoLoading(false));
  };
  const fetchTemplates = () => {
    setTplLoading(true);
    marketingAutomationsApi.templates()
      .then(d => setTemplates(d ?? []))
      .catch(() => setTemplates([]))
      .finally(() => setTplLoading(false));
  };
  const fetchLogs = () => {
    setLogsLoading(true);
    marketingAutomationsApi.logs()
      .then(d => setLogs(d ?? []))
      .catch(() => setLogs([]))
      .finally(() => setLogsLoading(false));
  };
  const fetchEvents = () => {
    setEventsLoading(true);
    marketingAutomationsApi.events()
      .then(d => setEvents(d ?? []))
      .catch(() => setEvents([]))
      .finally(() => setEventsLoading(false));
  };

  useEffect(() => {
    if (tab === "automacoes")    fetchAutomations();
    if (tab === "templates")     { fetchTemplates(); }
    if (tab === "monitoramento") fetchLogs();
    if (tab === "eventos")       fetchEvents();
  }, [tab]); // eslint-disable-line

  // auto-refresh monitoramento
  useEffect(() => {
    if (tab === "monitoramento") {
      monitorRef.current = setInterval(fetchLogs, 15000);
    } else {
      if (monitorRef.current) clearInterval(monitorRef.current);
    }
    return () => { if (monitorRef.current) clearInterval(monitorRef.current); };
  }, [tab]); // eslint-disable-line

  // ── Automation CRUD ──
  const saveAutomation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!autoForm.name?.trim()) { alert("Nome obrigatório."); return; }
    setSaving(true);
    try {
      if (editingAutoId) {
        await marketingAutomationsApi.update(editingAutoId, autoForm);
      } else {
        await marketingAutomationsApi.create(autoForm);
      }
      setShowAutoModal(false);
      fetchAutomations();
    } catch { alert("Erro ao salvar."); } finally { setSaving(false); }
  };
  const deleteAutomation = async (id: string) => {
    if (!confirm("Excluir automação?")) return;
    await marketingAutomationsApi.remove(id);
    fetchAutomations();
  };
  const toggleAutomation = async (id: string) => {
    const d = await marketingAutomationsApi.toggle(id);
    setAutomations(prev => prev.map(a => a.id === id ? { ...a, active: d.active ?? !a.active } : a));
  };
  const runAutomation = async (id: string) => {
    setRunning(id);
    try {
      const d = await marketingAutomationsApi.run(id);
      setRunResult(prev => ({ ...prev, [id]: { sent: d.sent ?? 0, failed: d.failed ?? 0, skipped: d.skipped ?? 0 } }));
    } catch {
      alert("Erro ao executar automacao.");
    } finally {
      setRunning(null);
    }
  };

  const runQueueAction = async (action: QueueBusy) => {
    setQueueBusy(action);
    try {
      const data = action === "enqueue"
        ? await marketingAutomationsApi.enqueueDue()
        : action === "process"
          ? await marketingAutomationsApi.processQueue()
          : await marketingAutomationsApi.runDue();
      const label = action === "enqueue" ? "Enfileiramento" : action === "process" ? "Processamento" : "Worker completo";
      setQueueResult({ label, data: data as unknown as Record<string, unknown> });
      fetchLogs();
      fetchEvents();
      fetchAutomations();
    } catch {
      alert("Erro ao executar acao da fila.");
    } finally {
      setQueueBusy(null);
    }
  };

  // ── Template CRUD ──
  const saveTemplate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tplForm.name?.trim() || !tplForm.body?.trim()) { alert("Nome e corpo obrigatórios."); return; }
    setSaving(true);
    try {
      if (editingTplId) {
        await marketingAutomationsApi.updateTemplate(editingTplId, tplForm);
      } else {
        await marketingAutomationsApi.createTemplate(tplForm);
      }
      setShowTplModal(false);
      fetchTemplates();
    } catch { alert("Erro ao salvar template."); } finally { setSaving(false); }
  };
  const deleteTpl = async (id: string) => {
    if (!confirm("Excluir template?")) return;
    await marketingAutomationsApi.removeTemplate(id);
    fetchTemplates();
  };

  return (
    <div className="flex flex-col md:flex-row min-h-screen md:h-screen bg-surface-00 overflow-hidden">
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto p-6 space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-gold mb-1">Marketing</p>
            <h1 className="text-2xl font-bold text-cream">Automação de Marketing</h1>
          </div>
          <AdminTopActions />
        </div>

        {/* Tabs */}
        <div className="flex flex-wrap gap-1 bg-surface-02 border border-surface-03 rounded-xl p-1">
          {TABS_CFG.map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => setTab(id)}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${tab === id ? "bg-gold text-black" : "text-stone hover:text-cream hover:bg-surface-03"}`}>
              <Icon size={14} /> {label}
            </button>
          ))}
        </div>

        {/* ═══ EVENTOS ═══ */}
        {tab === "eventos" && (
          <>
            <div className="flex items-center justify-between">
              <p className="text-stone text-sm">{events.length} tipo(s) de evento</p>
              <button onClick={fetchEvents} className="p-2 rounded-xl bg-surface-02 border border-surface-03 text-stone hover:text-cream transition-colors">
                <RefreshCw size={16} />
              </button>
            </div>
            {eventsLoading ? (
              <div className="flex justify-center py-12"><Loader2 className="animate-spin text-gold" size={28} /></div>
            ) : events.length === 0 ? (
              <div className="flex flex-col items-center py-20 bg-surface-02 border border-surface-03 rounded-2xl">
                <BarChart2 size={40} className="text-surface-03 mb-3" />
                <p className="text-stone text-sm">Nenhum evento rastreado ainda.</p>
                <p className="text-stone/60 text-xs mt-1">Os eventos são registrados automaticamente quando as automações são executadas.</p>
              </div>
            ) : (
              <div className="bg-surface-02 border border-surface-03 rounded-2xl overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-stone text-xs border-b border-surface-03 bg-surface-03/30">
                      {["Evento", "Disparos", "Clientes únicos", "Último disparo"].map(h => (
                        <th key={h} className="text-left p-3">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-03">
                    {events.map(ev => (
                      <tr key={ev.event_name} className="hover:bg-surface-03/30 transition-colors">
                        <td className="p-3">
                          <div className="flex items-center gap-2">
                            <Zap size={12} className="text-gold" />
                            <span className="text-cream font-medium text-xs">{TRIGGER_LABELS[ev.event_name] ?? ev.event_name}</span>
                          </div>
                        </td>
                        <td className="p-3 text-cream font-semibold">{ev.count.toLocaleString("pt-BR")}</td>
                        <td className="p-3 text-stone">{ev.unique_customers.toLocaleString("pt-BR")}</td>
                        <td className="p-3 text-stone text-xs">{fmtDate(ev.last_triggered)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        {/* ═══ AUTOMAÇÕES ═══ */}
        {tab === "automacoes" && (
          <>
            <div className="flex items-center justify-between">
              <p className="text-stone text-sm">{automations.length} automação(ões)</p>
              <button onClick={() => { setEditingAutoId(null); setAutoForm(emptyAutoForm()); setShowAutoModal(true); }}
                className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-black font-semibold px-4 py-2 rounded-xl text-sm transition-colors">
                <Plus size={16} /> Nova Automação
              </button>
            </div>
            {autoError && <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 text-red-400 text-sm flex items-center gap-2"><AlertCircle size={14} />{autoError}</div>}
            {autoLoading ? (
              <div className="flex justify-center py-12"><Loader2 className="animate-spin text-gold" size={28} /></div>
            ) : automations.length === 0 ? (
              <div className="flex flex-col items-center py-20 bg-surface-02 border border-surface-03 rounded-2xl">
                <Zap size={40} className="text-surface-03 mb-3" />
                <p className="text-stone text-sm">Nenhuma automação configurada.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4">
                {automations.map(a => {
                  const result = runResult[a.id];
                  const isRunning = running === a.id;
                  return (
                    <div key={a.id} className="bg-surface-02 border border-surface-03 rounded-2xl p-5 space-y-3">
                      <div className="flex items-start justify-between gap-3 flex-wrap">
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <div className="p-2 rounded-xl bg-gold/10"><Zap size={16} className="text-gold" /></div>
                          <div className="min-w-0">
                            <h3 className="text-cream font-semibold text-sm truncate">{a.name}</h3>
                            <div className="flex items-center gap-2 mt-0.5">
                              <span className={`shrink-0 px-2 py-0.5 rounded-full text-xs font-medium ${a.channel === "whatsapp" ? "bg-green-500/20 text-green-400" : "bg-blue-500/20 text-blue-400"}`}>
                                {a.channel === "whatsapp" ? "WhatsApp" : "Email"}
                              </span>
                              <span className="text-xs text-stone">{TRIGGER_LABELS[a.trigger] ?? a.trigger}
                                {a.trigger_value ? ` — ${a.trigger_value}` : ""}
                                {a.trigger_delay_hours ? ` (+${a.trigger_delay_hours}h)` : ""}
                              </span>
                            </div>
                          </div>
                        </div>
                        {/* Toggle */}
                        <button onClick={() => toggleAutomation(a.id)}
                          className={`shrink-0 relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${a.active ? "bg-gold" : "bg-surface-03"}`}>
                          <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${a.active ? "translate-x-6" : "translate-x-1"}`} />
                        </button>
                      </div>

                      <div className="flex items-center gap-4 text-xs text-stone">
                        <span><span className="text-cream font-semibold">{a.runs_total}</span> execuções</span>
                        <span>Último: <span className="text-cream">{fmtDate(a.last_run_at)}</span></span>
                      </div>

                      {result && (
                        <div className="flex items-center gap-3 p-3 rounded-xl bg-surface-03/60 flex-wrap text-xs">
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-500/20 text-green-400"><CheckCircle size={10} /> {result.sent} enviados</span>
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-500/20 text-red-400"><XCircle size={10} /> {result.failed} falhas</span>
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-03 text-stone"><SkipForward size={10} /> {result.skipped} ignorados</span>
                        </div>
                      )}

                      <div className="flex items-center gap-2 flex-wrap">
                        <button onClick={() => runAutomation(a.id)} disabled={isRunning}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-03 hover:bg-gold hover:text-black text-stone text-xs font-medium transition-colors disabled:opacity-60">
                          {isRunning ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
                          {isRunning ? "Executando..." : "Executar agora"}
                        </button>
                        <button onClick={() => { setEditingAutoId(a.id); setAutoForm({ ...a }); setShowAutoModal(true); }}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-03 hover:bg-surface-03/70 text-stone hover:text-cream text-xs font-medium transition-colors">
                          <Pencil size={13} /> Editar
                        </button>
                        <button onClick={() => deleteAutomation(a.id)}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-03 hover:bg-red-500/10 text-stone hover:text-red-400 text-xs font-medium transition-colors">
                          <Trash2 size={13} /> Excluir
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}

        {/* ═══ TEMPLATES ═══ */}
        {tab === "templates" && (
          <>
            <div className="flex items-center justify-between">
              <p className="text-stone text-sm">{templates.length} template(s) de automação</p>
              <button onClick={() => { setEditingTplId(null); setTplForm(emptyTplForm()); setShowTplModal(true); }}
                className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-black font-semibold px-4 py-2 rounded-xl text-sm transition-colors">
                <Plus size={16} /> Novo Template
              </button>
            </div>
            {tplLoading ? (
              <div className="flex justify-center py-12"><Loader2 className="animate-spin text-gold" size={28} /></div>
            ) : templates.length === 0 ? (
              <div className="flex flex-col items-center py-20 bg-surface-02 border border-surface-03 rounded-2xl">
                <MessageSquare size={40} className="text-surface-03 mb-3" />
                <p className="text-stone text-sm">Nenhum template criado.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {templates.map(t => (
                  <div key={t.id} className="bg-surface-02 border border-surface-03 rounded-2xl p-4 space-y-3 flex flex-col">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h3 className="text-cream font-semibold text-sm">{t.name}</h3>
                        <div className="flex gap-1.5 mt-1">
                          <span className={`px-1.5 py-0.5 rounded-full text-xs ${t.channel === "whatsapp" ? "bg-green-500/20 text-green-400" : "bg-blue-500/20 text-blue-400"}`}>
                            {t.channel === "whatsapp" ? "WhatsApp" : "Email"}
                          </span>
                          <span className="px-1.5 py-0.5 rounded-full text-xs bg-surface-03 text-stone">{t.category}</span>
                        </div>
                        {t.subject && <p className="text-gold text-xs mt-1 truncate max-w-[200px]">{t.subject}</p>}
                      </div>
                      <div className="flex gap-1 shrink-0">
                        <button onClick={() => { setEditingTplId(t.id); setTplForm({ ...t }); setShowTplModal(true); }}
                          className="p-1.5 rounded-lg hover:bg-surface-03 text-stone hover:text-cream transition-colors"><Pencil size={12} /></button>
                        <button onClick={() => deleteTpl(t.id)}
                          className="p-1.5 rounded-lg hover:bg-red-500/10 text-stone hover:text-red-400 transition-colors"><Trash2 size={12} /></button>
                      </div>
                    </div>
                    <div className="flex-1 bg-surface-03 rounded-xl p-3">
                      <p className="text-stone text-xs leading-relaxed font-mono line-clamp-3 whitespace-pre-wrap">{t.body}</p>
                    </div>
                    {t.variables && (
                      <div className="flex flex-wrap gap-1">
                        {t.variables.split(",").filter(Boolean).map(v => (
                          <span key={v} className="px-1.5 py-0.5 bg-surface-03 text-stone text-xs rounded font-mono">{v.trim()}</span>
                        ))}
                      </div>
                    )}
                    <p className="text-stone text-xs">{fmtDate(t.created_at)}</p>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* ═══ MONITORAMENTO ═══ */}
        {tab === "monitoramento" && (
          <>
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <p className="text-stone text-sm">Atualização automática a cada 15s</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <button onClick={() => runQueueAction("enqueue")} disabled={!!queueBusy}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-surface-02 border border-surface-03 text-stone hover:text-cream text-xs font-medium transition-colors disabled:opacity-60">
                  {queueBusy === "enqueue" ? <Loader2 size={14} className="animate-spin" /> : <List size={14} />} Enfileirar
                </button>
                <button onClick={() => runQueueAction("process")} disabled={!!queueBusy}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-surface-02 border border-surface-03 text-stone hover:text-cream text-xs font-medium transition-colors disabled:opacity-60">
                  {queueBusy === "process" ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} Processar
                </button>
                <button onClick={() => runQueueAction("worker")} disabled={!!queueBusy}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-gold hover:bg-gold/90 text-black text-xs font-semibold transition-colors disabled:opacity-60">
                  {queueBusy === "worker" ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />} Rodar worker
                </button>
                <button onClick={fetchLogs} className="p-2 rounded-xl bg-surface-02 border border-surface-03 text-stone hover:text-cream transition-colors">
                  <RefreshCw size={16} />
                </button>
              </div>
            </div>
            {queueResult && (
              <div className="bg-surface-02 border border-surface-03 rounded-2xl p-4 space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-cream font-semibold text-sm">{queueResult.label}</h3>
                  <button onClick={() => setQueueResult(null)} className="text-stone hover:text-cream"><X size={14} /></button>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                  {queueStats(queueResult).map(({ label, value }) => (
                    <div key={label} className="rounded-xl bg-surface-03 px-3 py-2">
                      <p className="text-stone/70 text-[11px] uppercase">{label}</p>
                      <p className="text-cream font-semibold text-sm">{value}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {logsLoading ? (
              <div className="flex justify-center py-12"><Loader2 className="animate-spin text-gold" size={28} /></div>
            ) : (
              <div className="bg-surface-02 border border-surface-03 rounded-2xl overflow-hidden">
                {logs.length === 0 ? (
                  <div className="flex flex-col items-center py-16">
                    <List size={40} className="text-surface-03 mb-3" />
                    <p className="text-stone text-sm">Nenhuma execução registrada.</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-stone text-xs border-b border-surface-03 bg-surface-03/30">
                          {["Automação", "Canal", "Cliente", "Status", "Erro", "Data/Hora"].map(h => (
                            <th key={h} className="text-left p-3">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-surface-03">
                        {logs.map(log => {
                          const sc = LOG_STATUS_CFG[log.status] ?? LOG_STATUS_CFG.skipped;
                          const SI = sc.icon;
                          return (
                            <tr key={log.id} className="hover:bg-surface-03/30 transition-colors">
                              <td className="p-3 text-cream text-xs">{log.automation_name ?? "—"}</td>
                              <td className="p-3">
                                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${log.channel === "whatsapp" ? "bg-green-500/20 text-green-400" : "bg-blue-500/20 text-blue-400"}`}>
                                  {log.channel === "whatsapp" ? <MessageSquare size={10} /> : <Mail size={10} />}
                                  {CHANNEL_LABELS[log.channel] ?? log.channel}
                                </span>
                              </td>
                              <td className="p-3 text-stone text-xs font-mono">{log.customer_id ? log.customer_id.slice(0, 8) + "…" : "—"}</td>
                              <td className="p-3"><span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${sc.cls}`}><SI size={10} />{sc.label}</span></td>
                              <td className="p-3 text-red-400 text-xs max-w-[180px] truncate">{log.error ?? "—"}</td>
                              <td className="p-3 text-stone text-xs whitespace-nowrap">{fmtDate(log.created_at)}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </main>

      {/* ── Automação Modal ── */}
      {showAutoModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-5 border-b border-surface-03">
              <h2 className="text-cream font-semibold">{editingAutoId ? "Editar Automação" : "Nova Automação"}</h2>
              <button onClick={() => setShowAutoModal(false)} className="text-stone hover:text-cream"><X size={18} /></button>
            </div>
            <form onSubmit={saveAutomation} className="p-5 space-y-4">
              <div className="space-y-1">
                <label className="text-xs text-stone">Nome *</label>
                <input type="text" value={autoForm.name ?? ""} onChange={e => setAutoForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="Ex: Boas-vindas novo cliente" className={IC} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs text-stone">Canal *</label>
                  <select value={autoForm.channel ?? "whatsapp"} onChange={e => setAutoForm(f => ({ ...f, channel: e.target.value }))} className={IC}>
                    {Object.entries(CHANNEL_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-stone">Delay (horas)</label>
                  <input type="number" min={0} value={autoForm.trigger_delay_hours ?? 0}
                    onChange={e => setAutoForm(f => ({ ...f, trigger_delay_hours: +e.target.value }))} className={IC} />
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-stone">Gatilho *</label>
                <select value={autoForm.trigger ?? "new_customer"} onChange={e => setAutoForm(f => ({ ...f, trigger: e.target.value, trigger_value: "" }))} className={IC}>
                  {Object.entries(TRIGGER_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </div>
              {TRIGGER_VALUE_LABEL[autoForm.trigger ?? ""] && (
                <div className="space-y-1">
                  <label className="text-xs text-stone">{TRIGGER_VALUE_LABEL[autoForm.trigger ?? ""]}</label>
                  <input type="number" min={0} value={autoForm.trigger_value ?? ""}
                    onChange={e => setAutoForm(f => ({ ...f, trigger_value: e.target.value }))} className={IC} />
                </div>
              )}
              <div className="space-y-1">
                <label className="text-xs text-stone">ID do Template (automação)</label>
                <select value={autoForm.template_id ?? ""} onChange={e => setAutoForm(f => ({ ...f, template_id: e.target.value }))} className={IC}>
                  <option value="">Usar mensagem fallback</option>
                  {templates.filter(t => t.channel === autoForm.channel).map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-stone">Mensagem Fallback</label>
                <textarea value={autoForm.message_body ?? ""} onChange={e => setAutoForm(f => ({ ...f, message_body: e.target.value }))}
                  rows={4} placeholder="Mensagem usada quando nenhum template é selecionado" className={`${IC} resize-none`} />
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowAutoModal(false)} className="flex-1 py-2 rounded-xl border border-surface-03 text-stone text-sm">Cancelar</button>
                <button type="submit" disabled={saving}
                  className="flex-1 py-2 rounded-xl bg-gold hover:bg-gold/90 text-black font-semibold text-sm disabled:opacity-60 flex items-center justify-center gap-2">
                  {saving && <Loader2 size={14} className="animate-spin" />}{editingAutoId ? "Salvar" : "Criar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Template Modal ── */}
      {showTplModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-5 border-b border-surface-03">
              <h2 className="text-cream font-semibold">{editingTplId ? "Editar Template" : "Novo Template"}</h2>
              <button onClick={() => setShowTplModal(false)} className="text-stone hover:text-cream"><X size={18} /></button>
            </div>
            <form onSubmit={saveTemplate} className="p-5 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs text-stone">Nome *</label>
                  <input type="text" value={tplForm.name ?? ""} onChange={e => setTplForm(f => ({ ...f, name: e.target.value }))}
                    placeholder="boas_vindas" className={IC} />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-stone">Canal</label>
                  <select value={tplForm.channel ?? "whatsapp"} onChange={e => setTplForm(f => ({ ...f, channel: e.target.value }))} className={IC}>
                    <option value="whatsapp">WhatsApp</option>
                    <option value="email">Email</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs text-stone">Categoria</label>
                  <select value={tplForm.category ?? "marketing"} onChange={e => setTplForm(f => ({ ...f, category: e.target.value }))} className={IC}>
                    <option value="marketing">Marketing</option>
                    <option value="transactional">Transacional</option>
                    <option value="retention">Retenção</option>
                    <option value="reactivation">Reativação</option>
                  </select>
                </div>
                {tplForm.channel === "email" && (
                  <div className="space-y-1">
                    <label className="text-xs text-stone">Assunto</label>
                    <input type="text" value={tplForm.subject ?? ""} onChange={e => setTplForm(f => ({ ...f, subject: e.target.value }))}
                      placeholder="Assunto do email" className={IC} />
                  </div>
                )}
              </div>
              <div className="space-y-1">
                <label className="text-xs text-stone">Corpo *</label>
                <textarea value={tplForm.body ?? ""} onChange={e => setTplForm(f => ({ ...f, body: e.target.value }))}
                  rows={6} placeholder="Olá {{nome}}, temos uma oferta especial para você!" className={`${IC} resize-none font-mono text-xs`} />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-stone">Variáveis utilizadas (separadas por vírgula)</label>
                <input type="text" value={tplForm.variables ?? ""} onChange={e => setTplForm(f => ({ ...f, variables: e.target.value }))}
                  placeholder="{{nome}}, {{cupom}}, {{link_pedido}}" className={IC} />
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowTplModal(false)} className="flex-1 py-2 rounded-xl border border-surface-03 text-stone text-sm">Cancelar</button>
                <button type="submit" disabled={saving}
                  className="flex-1 py-2 rounded-xl bg-gold hover:bg-gold/90 text-black font-semibold text-sm disabled:opacity-60 flex items-center justify-center gap-2">
                  {saving && <Loader2 size={14} className="animate-spin" />}{editingTplId ? "Salvar" : "Criar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
