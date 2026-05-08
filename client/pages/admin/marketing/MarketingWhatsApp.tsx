import { useEffect, useState, useRef } from "react";
import {
  Loader2, Plus, Pencil, Trash2, X, MessageCircle, Send, CheckCircle,
  XCircle, Clock, AlertCircle, BarChart2, Settings, Eye, Zap,
  RefreshCw, Play, Pause, Users, MessageSquare, Megaphone,
  Image, Video,
} from "lucide-react";
import {
  AdminPageContent,
  AdminPageHeader,
  AdminPageShell,
  AdminPageTabs,
  type AdminPageTab,
} from "@/components/admin/AdminPageChrome";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const unwrap = (j: any) => j?.data ?? j;

type Tab = "dashboard" | "templates" | "campanhas" | "disparo" | "monitoramento" | "configuracoes";

const TABS: AdminPageTab<Tab>[] = [
  { id: "dashboard",     label: "Dashboard",      icon: <BarChart2 size={15} /> },
  { id: "templates",     label: "Templates",       icon: <MessageSquare size={15} /> },
  { id: "campanhas",     label: "Campanhas",       icon: <Megaphone size={15} /> },
  { id: "disparo",       label: "Disparo Imediato",icon: <Send size={15} /> },
  { id: "monitoramento", label: "Monitoramento",   icon: <Eye size={15} /> },
  { id: "configuracoes", label: "Configurações",   icon: <Settings size={15} /> },
];

const STATUS_CFG: Record<string, { label: string; cls: string; icon: React.ElementType }> = {
  sent:      { label: "Enviado",  cls: "bg-green-500/20 text-green-400",   icon: CheckCircle },
  delivered: { label: "Entregue", cls: "bg-emerald-500/20 text-emerald-400", icon: CheckCircle },
  read:      { label: "Lido",     cls: "bg-blue-500/20 text-blue-400",     icon: Eye },
  failed:    { label: "Falhou",   cls: "bg-red-500/20 text-red-400",       icon: XCircle },
  pending:   { label: "Pendente", cls: "bg-yellow-500/20 text-yellow-400", icon: Clock },
  queued:    { label: "Na fila",  cls: "bg-surface-03 text-stone",         icon: Clock },
};

const WA_VARS = ["{{nome}}", "{{primeiro_nome}}", "{{telefone}}", "{{email}}",
  "{{endereco}}", "{{bairro}}", "{{cidade}}", "{{ultimo_pedido}}",
  "{{produto_mais_pedido}}", "{{cupom}}", "{{link_pedido}}", "{{valor_total}}",
  "{{data_aniversario}}"];

function fmtDate(s?: string) {
  if (!s) return "—";
  return new Date(s).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

const IC = "w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold";

interface WaTemplate { id: string; name: string; body: string; category: string; language: string; active: boolean; created_at: string; }
interface WaMessage  { id: string; phone: string; body_sent: string; status: string; sent_at: string; error?: string; customer_name?: string; template_name?: string; provider?: string; message_type?: string; media_type?: string; media_url?: string; caption?: string; }
interface WaCampaign { id: string; name: string; status: string; template_id?: string; group_id?: string; scheduled_at?: string; sent_count: number; delivered_count: number; read_count: number; error_count: number; created_at: string; }
interface WaDashboard { sent: number; delivered: number; read: number; responded: number; errors: number; active_campaigns: number; scheduled_campaigns: number; response_rate: number; orders_generated: number; revenue_generated: number; }
interface WaConfig { connection_type: string; status: string; messages_per_minute: number; interval_seconds: number; daily_limit: number; webhook_url: string; evolution_base_url: string; evolution_api_key: string; evolution_instance: string; }

const EMPTY_DASH: WaDashboard = { sent: 0, delivered: 0, read: 0, responded: 0, errors: 0, active_campaigns: 0, scheduled_campaigns: 0, response_rate: 0, orders_generated: 0, revenue_generated: 0 };
const EMPTY_CFG: WaConfig = { connection_type: "official", status: "disconnected", messages_per_minute: 10, interval_seconds: 3, daily_limit: 1000, webhook_url: "", evolution_base_url: "", evolution_api_key: "", evolution_instance: "" };

export default function MarketingWhatsApp() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const token = localStorage.getItem("admin_token");
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  // ── Dashboard ──
  const [dash, setDash] = useState<WaDashboard>(EMPTY_DASH);
  // ── Templates ──
  const [templates, setTemplates] = useState<WaTemplate[]>([]);
  const [tplLoading, setTplLoading] = useState(false);
  const [showTplModal, setShowTplModal] = useState(false);
  const [editingTplId, setEditingTplId] = useState<string | null>(null);
  const [tplForm, setTplForm] = useState({ name: "", body: "", category: "marketing", language: "pt_BR" });
  // ── Campanhas ──
  const [campaigns, setCampaigns] = useState<WaCampaign[]>([]);
  const [campLoading, setCampLoading] = useState(false);
  const [showCampModal, setShowCampModal] = useState(false);
  const [campForm, setCampForm] = useState({ name: "", template_id: "", group_id: "", scheduled_at: "" });
  // ── Disparo ──
  const [dispForm, setDispForm] = useState({
    provider: "official",
    template_id: "",
    phones: "",
    free_text: "",
    template_variables: "",
    mode: "template",
    schedule: "",
    media_type: "",
    media_url: "",
    caption: "",
    mimetype: "",
    file_name: "",
  });
  const [dispResult, setDispResult] = useState<{ sent: number; failed: number } | null>(null);
  const [dispatching, setDispatching] = useState(false);
  // ── Monitoramento ──
  const [messages, setMessages] = useState<WaMessage[]>([]);
  const [msgLoading, setMsgLoading] = useState(false);
  const monitorRef = useRef<ReturnType<typeof setInterval>>(null);
  // ── Configurações ──
  const [cfg, setCfg] = useState<WaConfig>(EMPTY_CFG);
  const [cfgSaving, setCfgSaving] = useState(false);
  // ── Global ──
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  // fetch helpers
  const fetchDash = () => {
    fetch(`${BASE}/whatsapp/dashboard`, { headers })
      .then(r => r.json()).then(d => setDash({ ...EMPTY_DASH, ...unwrap(d) })).catch(() => {});
  };
  const fetchTemplates = () => {
    setTplLoading(true);
    fetch(`${BASE}/whatsapp/templates`, { headers })
      .then(r => r.json()).then(d => setTemplates(unwrap(d) ?? [])).catch(() => setTemplates([]))
      .finally(() => setTplLoading(false));
  };
  const fetchCampaigns = () => {
    setCampLoading(true);
    fetch(`${BASE}/whatsapp/campaigns`, { headers })
      .then(r => r.json()).then(d => setCampaigns(unwrap(d) ?? [])).catch(() => setCampaigns([]))
      .finally(() => setCampLoading(false));
  };
  const fetchMessages = () => {
    setMsgLoading(true);
    fetch(`${BASE}/whatsapp/messages`, { headers })
      .then(r => r.json()).then(d => setMessages(unwrap(d) ?? [])).catch(() => setMessages([]))
      .finally(() => setMsgLoading(false));
  };
  const fetchConfig = () => {
    fetch(`${BASE}/whatsapp/config`, { headers })
      .then(r => r.json()).then(d => setCfg({ ...EMPTY_CFG, ...unwrap(d) })).catch(() => {});
  };

  useEffect(() => {
    if (tab === "dashboard") { fetchDash(); }
    if (tab === "templates") { fetchTemplates(); }
    if (tab === "campanhas") { fetchCampaigns(); fetchTemplates(); }
    if (tab === "disparo")   { fetchTemplates(); }
    if (tab === "monitoramento") { fetchMessages(); }
    if (tab === "configuracoes") { fetchConfig(); }
  }, [tab]); // eslint-disable-line

  // auto-refresh monitoramento every 10s
  useEffect(() => {
    if (tab === "monitoramento") {
      monitorRef.current = setInterval(fetchMessages, 10000);
    } else {
      if (monitorRef.current) clearInterval(monitorRef.current);
    }
    return () => { if (monitorRef.current) clearInterval(monitorRef.current); };
  }, [tab]); // eslint-disable-line

  // ── Template CRUD ──
  const saveTpl = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tplForm.name.trim() || !tplForm.body.trim()) { alert("Nome e body obrigatórios."); return; }
    setSaving(true);
    try {
      const url = editingTplId ? `${BASE}/whatsapp/templates/${editingTplId}` : `${BASE}/whatsapp/templates`;
      await fetch(url, { method: editingTplId ? "PATCH" : "POST", headers, body: JSON.stringify(tplForm) });
      setShowTplModal(false);
      fetchTemplates();
    } catch { alert("Erro ao salvar."); } finally { setSaving(false); }
  };
  const deleteTpl = async (id: string) => {
    if (!confirm("Excluir template?")) return;
    await fetch(`${BASE}/whatsapp/templates/${id}`, { method: "DELETE", headers });
    fetchTemplates();
  };

  // ── Campaign CRUD ──
  const saveCamp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!campForm.name.trim()) { alert("Nome obrigatório."); return; }
    setSaving(true);
    try {
      await fetch(`${BASE}/whatsapp/campaigns`, { method: "POST", headers, body: JSON.stringify(campForm) });
      setShowCampModal(false);
      setCampForm({ name: "", template_id: "", group_id: "", scheduled_at: "" });
      fetchCampaigns();
    } catch { alert("Erro ao criar campanha."); } finally { setSaving(false); }
  };
  const toggleCamp = async (id: string, status: string) => {
    const newStatus = status === "running" ? "paused" : "running";
    await fetch(`${BASE}/whatsapp/campaigns/${id}`, { method: "PATCH", headers, body: JSON.stringify({ status: newStatus }) });
    fetchCampaigns();
  };
  const deleteCamp = async (id: string) => {
    if (!confirm("Excluir campanha?")) return;
    await fetch(`${BASE}/whatsapp/campaigns/${id}`, { method: "DELETE", headers });
    fetchCampaigns();
  };

  // ── Disparo imediato ──
  const sendNow = async (e: React.FormEvent) => {
    e.preventDefault();
    setDispatching(true);
    setDispResult(null);
    try {
      const phones = dispForm.phones.split(/[\n,]/).map(p => p.trim()).filter(Boolean);
      const variables = dispForm.template_variables.split(/\n/).map(v => v.trim()).filter(Boolean);
      const mediaPayload = dispForm.media_type ? {
        media_type: dispForm.media_type,
        media_url: dispForm.media_url,
        caption: dispForm.caption,
        mimetype: dispForm.mimetype,
        file_name: dispForm.file_name,
      } : {};
      const payload = dispForm.mode === "template"
        ? { provider: dispForm.provider, template_id: dispForm.template_id, phones, variables, ...mediaPayload }
        : { provider: dispForm.provider, free_text: dispForm.free_text, phones, ...mediaPayload };
      const body = JSON.stringify(payload);
      const r = await fetch(`${BASE}/whatsapp/send`, { method: "POST", headers, body });
      const json = await r.json();
      if (!r.ok || json?.success === false) {
        throw new Error(json?.error?.message ?? "Erro ao enviar.");
      }
      const d = unwrap(json);
      setDispResult({ sent: d.sent ?? 0, failed: d.failed ?? 0 });
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao enviar.");
    } finally { setDispatching(false); }
  };

  // ── Config ──
  const saveCfg = async (e: React.FormEvent) => {
    e.preventDefault();
    setCfgSaving(true);
    try {
      const nextCfg = { ...cfg, connection_type: cfg.connection_type === "qr" ? "official" : cfg.connection_type };
      const response = await fetch(`${BASE}/whatsapp/config`, { method: "PATCH", headers, body: JSON.stringify(nextCfg) });
      const json = await response.json();
      if (!response.ok || json?.success === false) {
        throw new Error(json?.error?.message ?? "Erro ao salvar.");
      }
      setCfg({ ...EMPTY_CFG, ...unwrap(json) });
      alert("Configurações salvas.");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao salvar.");
    } finally { setCfgSaving(false); }
  };

  return (
    <AdminPageShell>
      <AdminPageHeader
        eyebrow="Marketing"
        icon={<MessageCircle size={20} />}
        title="Disparador WhatsApp"
        description="Templates, campanhas, disparos e monitoramento em um unico lugar"
      />
      <AdminPageTabs tabs={TABS} active={tab} onChange={(next) => setTab(next as Tab)} />
      <AdminPageContent className="space-y-6">

        {/* ═══ DASHBOARD ═══ */}
        {tab === "dashboard" && (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
              {[
                { label: "Enviados",       value: dash.sent.toLocaleString("pt-BR"),       cls: "text-blue-400" },
                { label: "Entregues",      value: dash.delivered.toLocaleString("pt-BR"),  cls: "text-green-400" },
                { label: "Lidos",          value: dash.read.toLocaleString("pt-BR"),        cls: "text-emerald-400" },
                { label: "Respondidos",    value: dash.responded.toLocaleString("pt-BR"),   cls: "text-gold" },
                { label: "Erros",          value: dash.errors.toLocaleString("pt-BR"),      cls: "text-red-400" },
                { label: "Camp. Ativas",   value: String(dash.active_campaigns),            cls: "text-purple-400" },
                { label: "Agendadas",      value: String(dash.scheduled_campaigns),         cls: "text-orange-400" },
                { label: "Taxa Resposta",  value: `${((dash.response_rate ?? 0) * 100).toFixed(1)}%`, cls: "text-cyan-400" },
                { label: "Pedidos Gerados",value: String(dash.orders_generated),            cls: "text-gold" },
                { label: "Receita Gerada", value: (dash.revenue_generated ?? 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }), cls: "text-green-400" },
              ].map(m => (
                <div key={m.label} className="bg-surface-02 border border-surface-03 rounded-2xl p-4">
                  <p className="text-xs text-stone mb-1">{m.label}</p>
                  <p className={`text-xl font-bold ${m.cls}`}>{m.value}</p>
                </div>
              ))}
            </div>
            {/* Funil WA */}
            <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5">
              <h2 className="text-sm font-semibold text-cream mb-4">Funil de Engajamento</h2>
              {(() => {
                const stages = [
                  { label: "Enviado",    value: dash.sent,      color: "bg-blue-500" },
                  { label: "Entregue",   value: dash.delivered, color: "bg-green-500" },
                  { label: "Lido",       value: dash.read,      color: "bg-emerald-500" },
                  { label: "Respondido", value: dash.responded, color: "bg-gold" },
                ];
                const max = Math.max(...stages.map(s => s.value), 1);
                return (
                  <div className="space-y-3">
                    {stages.map(s => (
                      <div key={s.label} className="flex items-center gap-4">
                        <div className="w-24 text-xs text-stone text-right">{s.label}</div>
                        <div className="flex-1 h-6 bg-surface-03 rounded-xl overflow-hidden">
                          <div className={`h-full ${s.color} rounded-xl flex items-center px-2 transition-all duration-500`}
                            style={{ width: `${Math.max((s.value / max) * 100, 2)}%` }}>
                            <span className="text-xs font-bold text-white/90">{s.value.toLocaleString("pt-BR")}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                );
              })()}
            </div>
          </>
        )}

        {/* ═══ TEMPLATES ═══ */}
        {tab === "templates" && (
          <>
            <div className="flex items-center justify-between">
              <p className="text-stone text-sm">{templates.length} template(s)</p>
              <button onClick={() => { setEditingTplId(null); setTplForm({ name: "", body: "", category: "marketing", language: "pt_BR" }); setShowTplModal(true); }}
                className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-black font-semibold px-4 py-2 rounded-xl text-sm transition-colors">
                <Plus size={16} /> Novo Template
              </button>
            </div>
            {/* Variables reference */}
            <div className="bg-surface-02 border border-surface-03 rounded-xl p-4">
              <p className="text-xs text-stone font-medium mb-2">Variáveis disponíveis:</p>
              <div className="flex flex-wrap gap-1.5">
                {WA_VARS.map(v => (
                  <span key={v} className="px-2 py-0.5 bg-surface-03 text-cream text-xs rounded font-mono cursor-pointer hover:bg-gold/20 hover:text-gold transition-colors"
                    onClick={() => navigator.clipboard.writeText(v)} title="Clique para copiar">{v}</span>
                ))}
              </div>
            </div>
            {tplLoading ? (
              <div className="flex justify-center py-12"><Loader2 className="animate-spin text-gold" size={28} /></div>
            ) : templates.length === 0 ? (
              <div className="flex flex-col items-center py-20 bg-surface-02 border border-surface-03 rounded-2xl">
                <MessageSquare size={40} className="text-surface-03 mb-3" />
                <p className="text-stone text-sm">Nenhum template. <button onClick={() => setShowTplModal(true)} className="text-gold hover:underline">Criar agora</button></p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {templates.map(t => (
                  <div key={t.id} className="bg-surface-02 border border-surface-03 rounded-2xl p-4 space-y-3 flex flex-col">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h3 className="text-cream font-semibold text-sm">{t.name}</h3>
                        <span className="text-xs text-stone">{t.category} · {t.language}</span>
                      </div>
                      <span className={`shrink-0 px-2 py-0.5 rounded-full text-xs ${t.active ? "bg-green-500/20 text-green-400" : "bg-surface-03 text-stone"}`}>
                        {t.active ? "Ativo" : "Inativo"}
                      </span>
                    </div>
                    <div className="flex-1 bg-surface-03 rounded-xl p-3">
                      <p className="text-stone text-xs leading-relaxed font-mono whitespace-pre-wrap line-clamp-4">{t.body}</p>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-stone">{fmtDate(t.created_at)}</span>
                      <div className="flex gap-1">
                        <button onClick={() => { setEditingTplId(t.id); setTplForm({ name: t.name, body: t.body, category: t.category, language: t.language || "pt_BR" }); setShowTplModal(true); }}
                          className="p-1.5 rounded-lg hover:bg-surface-03 text-stone hover:text-cream transition-colors"><Pencil size={13} /></button>
                        <button onClick={() => deleteTpl(t.id)}
                          className="p-1.5 rounded-lg hover:bg-red-500/10 text-stone hover:text-red-400 transition-colors"><Trash2 size={13} /></button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* ═══ CAMPANHAS ═══ */}
        {tab === "campanhas" && (
          <>
            <div className="flex items-center justify-between">
              <p className="text-stone text-sm">{campaigns.length} campanha(s)</p>
              <button onClick={() => setShowCampModal(true)}
                className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-black font-semibold px-4 py-2 rounded-xl text-sm transition-colors">
                <Plus size={16} /> Nova Campanha
              </button>
            </div>
            {campLoading ? (
              <div className="flex justify-center py-12"><Loader2 className="animate-spin text-gold" size={28} /></div>
            ) : campaigns.length === 0 ? (
              <div className="flex flex-col items-center py-20 bg-surface-02 border border-surface-03 rounded-2xl">
                <Megaphone size={40} className="text-surface-03 mb-3" />
                <p className="text-stone text-sm">Nenhuma campanha criada.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {campaigns.map(c => {
                  const isRunning = c.status === "running";
                  return (
                    <div key={c.id} className="bg-surface-02 border border-surface-03 rounded-2xl p-4">
                      <div className="flex items-center justify-between gap-4">
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <h3 className="text-cream font-semibold text-sm">{c.name}</h3>
                            <span className={`text-xs px-2 py-0.5 rounded-full ${
                              c.status === "running" ? "bg-green-500/20 text-green-400" :
                              c.status === "paused" ? "bg-yellow-500/20 text-yellow-400" :
                              c.status === "completed" ? "bg-blue-500/20 text-blue-400" :
                              "bg-surface-03 text-stone"
                            }`}>{c.status}</span>
                          </div>
                          <div className="flex gap-4 text-xs text-stone">
                            <span>Enviados: <span className="text-cream">{c.sent_count}</span></span>
                            <span>Entregues: <span className="text-green-400">{c.delivered_count}</span></span>
                            <span>Lidos: <span className="text-emerald-400">{c.read_count}</span></span>
                            <span>Erros: <span className="text-red-400">{c.error_count}</span></span>
                            {c.scheduled_at && <span>Agend: {fmtDate(c.scheduled_at)}</span>}
                          </div>
                        </div>
                        <div className="flex gap-1 shrink-0">
                          <button onClick={() => toggleCamp(c.id, c.status)}
                            className="p-1.5 rounded-lg hover:bg-surface-03 text-stone hover:text-cream transition-colors">
                            {isRunning ? <Pause size={14} /> : <Play size={14} />}
                          </button>
                          <button onClick={() => deleteCamp(c.id)}
                            className="p-1.5 rounded-lg hover:bg-red-500/10 text-stone hover:text-red-400 transition-colors"><Trash2 size={14} /></button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}

        {/* ═══ DISPARO IMEDIATO ═══ */}
        {tab === "disparo" && (
          <div className="max-w-2xl space-y-6">
            <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5">
              <h2 className="text-sm font-semibold text-cream mb-4">Disparo Imediato</h2>
              <form onSubmit={sendNow} className="space-y-4">
                <div className="flex gap-2">
                  {[{ v: "template", l: "Usar Template" }, { v: "free", l: "Texto Livre" }].map(opt => (
                    <button key={opt.v} type="button"
                      onClick={() => setDispForm(f => ({ ...f, mode: opt.v }))}
                      className={`flex-1 py-2 rounded-xl text-sm font-medium border transition-colors ${dispForm.mode === opt.v ? "bg-gold text-black border-gold" : "border-surface-03 text-stone hover:text-cream"}`}>
                      {opt.l}
                    </button>
                  ))}
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-stone">API de envio *</label>
                  <select value={dispForm.provider} onChange={e => setDispForm(f => ({ ...f, provider: e.target.value }))} className={IC}>
                    <option value="official">WABA / Meta Cloud API</option>
                    <option value="evolution">Evolution API</option>
                  </select>
                  <p className="text-xs text-stone/60">
                    WABA usa templates aprovados para campanha; Evolution envia texto, imagem e video pela instancia configurada.
                  </p>
                </div>
                {dispForm.mode === "template" ? (
                  <div className="space-y-3">
                    <div className="space-y-1">
                      <label className="text-xs text-stone">Template aprovado na Meta *</label>
                      <select value={dispForm.template_id} onChange={e => setDispForm(f => ({ ...f, template_id: e.target.value }))} className={IC}>
                        <option value="">Selecione...</option>
                        {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                      </select>
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-stone">Variaveis do template</label>
                      <textarea
                        value={dispForm.template_variables}
                        onChange={e => setDispForm(f => ({ ...f, template_variables: e.target.value }))}
                        rows={3}
                        placeholder={"Valor para {{1}}\nValor para {{2}}"}
                        className={`${IC} resize-none font-mono text-xs`}
                      />
                      <p className="text-xs text-stone/60">Uma variavel por linha, na mesma ordem aprovada na Meta.</p>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <label className="text-xs text-stone">Mensagem *</label>
                    <textarea value={dispForm.free_text} onChange={e => setDispForm(f => ({ ...f, free_text: e.target.value }))}
                      rows={4} placeholder="Digite a mensagem..." className={`${IC} resize-none font-mono text-xs`} />
                    <div className="flex flex-wrap gap-1 mt-1">
                      {WA_VARS.slice(0, 6).map(v => (
                        <button key={v} type="button"
                          onClick={() => setDispForm(f => ({ ...f, free_text: f.free_text + v }))}
                          className="px-1.5 py-0.5 bg-surface-03 text-stone text-xs rounded hover:text-gold transition-colors">{v}</button>
                      ))}
                    </div>
                  </div>
                )}
                <div className="space-y-3 rounded-xl border border-surface-03 bg-surface-03/30 p-3">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="text-xs text-stone flex items-center gap-1">
                        {dispForm.media_type === "video" ? <Video size={12} /> : <Image size={12} />} Midia
                      </label>
                      <select value={dispForm.media_type} onChange={e => setDispForm(f => ({ ...f, media_type: e.target.value }))} className={IC}>
                        <option value="">Sem midia</option>
                        <option value="image">Imagem</option>
                        <option value="video">Video</option>
                      </select>
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-stone">Mimetype</label>
                      <input type="text" value={dispForm.mimetype} onChange={e => setDispForm(f => ({ ...f, mimetype: e.target.value }))}
                        placeholder={dispForm.media_type === "video" ? "video/mp4" : "image/jpeg"} className={IC} disabled={!dispForm.media_type} />
                    </div>
                  </div>
                  {dispForm.media_type && (
                    <>
                      <div className="space-y-1">
                        <label className="text-xs text-stone">URL HTTPS da midia *</label>
                        <input type="url" value={dispForm.media_url} onChange={e => setDispForm(f => ({ ...f, media_url: e.target.value }))}
                          placeholder={dispForm.media_type === "video" ? "https://site.com/video.mp4" : "https://site.com/imagem.jpg"} className={IC} />
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <label className="text-xs text-stone">Legenda</label>
                          <input type="text" value={dispForm.caption} onChange={e => setDispForm(f => ({ ...f, caption: e.target.value }))}
                            placeholder="Texto opcional da midia" className={IC} />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs text-stone">Nome do arquivo</label>
                          <input type="text" value={dispForm.file_name} onChange={e => setDispForm(f => ({ ...f, file_name: e.target.value }))}
                            placeholder={dispForm.media_type === "video" ? "video.mp4" : "imagem.jpg"} className={IC} />
                        </div>
                      </div>
                      <p className="text-xs text-stone/60">
                        Na WABA com template, a midia e enviada como header do template aprovado. Na Evolution, vai pelo endpoint sendMedia.
                      </p>
                    </>
                  )}
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-stone">Telefones (um por linha ou separado por vírgula) *</label>
                  <textarea value={dispForm.phones} onChange={e => setDispForm(f => ({ ...f, phones: e.target.value }))}
                    rows={4} placeholder={"5511999999999\n5511888888888"} className={`${IC} resize-none font-mono text-xs`} />
                  <p className="text-xs text-stone/60">
                    {dispForm.phones.split(/[\n,]/).filter(p => p.trim()).length} número(s) informado(s)
                  </p>
                </div>
                <p className="text-xs text-stone/70">
                  Disparos em producao sao enviados imediatamente. Agendamento exige worker de fila dedicado.
                </p>
                {dispResult && (
                  <div className="rounded-xl bg-surface-03 p-4 flex items-center justify-around">
                    <div className="text-center"><p className="text-2xl font-bold text-green-400">{dispResult.sent}</p><p className="text-xs text-stone mt-0.5">Enviadas</p></div>
                    <div className="text-center"><p className="text-2xl font-bold text-red-400">{dispResult.failed}</p><p className="text-xs text-stone mt-0.5">Falhas</p></div>
                  </div>
                )}
                <button type="submit" disabled={dispatching}
                  className="w-full py-3 rounded-xl bg-gold hover:bg-gold/90 text-black font-semibold text-sm transition-colors disabled:opacity-60 flex items-center justify-center gap-2">
                  {dispatching ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
                  Disparar Agora
                </button>
              </form>
            </div>
          </div>
        )}

        {/* ═══ MONITORAMENTO ═══ */}
        {tab === "monitoramento" && (
          <>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <p className="text-stone text-sm">Atualização automática a cada 10s</p>
              </div>
              <button onClick={fetchMessages} className="p-2 rounded-xl bg-surface-02 border border-surface-03 text-stone hover:text-cream transition-colors">
                <RefreshCw size={16} />
              </button>
            </div>
            {msgLoading ? (
              <div className="flex justify-center py-12"><Loader2 className="animate-spin text-gold" size={28} /></div>
            ) : (
              <div className="bg-surface-02 border border-surface-03 rounded-2xl overflow-hidden">
                {messages.length === 0 ? (
                  <div className="flex flex-col items-center py-16"><Send size={40} className="text-surface-03 mb-3" /><p className="text-stone text-sm">Nenhuma mensagem enviada ainda.</p></div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-stone text-xs border-b border-surface-03 bg-surface-03/30">
                          {["Cliente", "Telefone", "Provedor", "Tipo", "Template", "Status", "Data/Hora", "Erro"].map(h => (
                            <th key={h} className="text-left p-3">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-surface-03">
                        {messages.map(m => {
                          const sc = STATUS_CFG[m.status] ?? { label: m.status, cls: "bg-surface-03 text-stone", icon: Clock };
                          const SI = sc.icon;
                          return (
                            <tr key={m.id} className="hover:bg-surface-03/30 transition-colors">
                              <td className="p-3 text-cream font-medium">{m.customer_name ?? "—"}</td>
                              <td className="p-3 text-stone font-mono text-xs">{m.phone}</td>
                              <td className="p-3 text-stone text-xs">{m.provider === "evolution" ? "Evolution" : "WABA"}</td>
                              <td className="p-3 text-stone text-xs">{m.media_type || m.message_type || "text"}</td>
                              <td className="p-3 text-stone text-xs">{m.template_name ?? "—"}</td>
                              <td className="p-3"><span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${sc.cls}`}><SI size={10} />{sc.label}</span></td>
                              <td className="p-3 text-stone text-xs whitespace-nowrap">{fmtDate(m.sent_at)}</td>
                              <td className="p-3 text-red-400 text-xs max-w-[160px] truncate">{m.error ?? "—"}</td>
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

        {/* ═══ CONFIGURAÇÕES ═══ */}
        {tab === "configuracoes" && (
          <div className="max-w-2xl">
            <form onSubmit={saveCfg} className="bg-surface-02 border border-surface-03 rounded-2xl p-5 space-y-4">
              <h2 className="text-sm font-semibold text-cream">Configurações de Conexão</h2>
              <div className="space-y-1">
                <label className="text-xs text-stone">Tipo de Conexão</label>
                <select value={cfg.connection_type} onChange={e => setCfg(c => ({ ...c, connection_type: e.target.value }))} className={IC}>
                  <option value="official">WhatsApp Oficial (Cloud API)</option>
                  <option value="evolution">Evolution API</option>
                  <option value="qr" disabled>WhatsApp QR Code (indisponivel sem servico de sessao)</option>
                </select>
                <p className="text-xs text-stone/70">
                  Selecione o provedor padrao. No disparo imediato tambem e possivel escolher WABA ou Evolution por envio.
                </p>
              </div>
              <div className="flex items-center gap-3 p-3 bg-surface-03 rounded-xl">
                <span className={`w-3 h-3 rounded-full ${cfg.status === "connected" ? "bg-green-400" : "bg-red-400"}`} />
                <span className="text-sm text-cream">Status: <span className={cfg.status === "connected" ? "text-green-400" : "text-red-400"}>{cfg.status === "connected" ? "Conectado" : "Desconectado"}</span></span>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs text-stone">Mensagens/minuto</label>
                  <input type="number" min={1} max={60} value={cfg.messages_per_minute}
                    onChange={e => setCfg(c => ({ ...c, messages_per_minute: +e.target.value }))} className={IC} />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-stone">Intervalo (segundos)</label>
                  <input type="number" min={1} value={cfg.interval_seconds}
                    onChange={e => setCfg(c => ({ ...c, interval_seconds: +e.target.value }))} className={IC} />
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-stone">Limite diário de mensagens</label>
                <input type="number" min={1} value={cfg.daily_limit}
                  onChange={e => setCfg(c => ({ ...c, daily_limit: +e.target.value }))} className={IC} />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-stone">Webhook URL (receber status)</label>
                <input type="url" value={cfg.webhook_url} onChange={e => setCfg(c => ({ ...c, webhook_url: e.target.value }))}
                  placeholder={`${BASE}/whatsapp/webhook`} className={IC} />
                <p className="text-xs text-stone/70">
                  Cadastre esta URL na Meta junto com o Verify Token configurado em Integracoes.
                </p>
              </div>
              {cfg.connection_type === "evolution" && (
                <div className="space-y-3 rounded-xl border border-surface-03 bg-surface-03/30 p-3">
                  <h3 className="text-xs font-semibold text-cream">Evolution API</h3>
                  <div className="space-y-1">
                    <label className="text-xs text-stone">URL base</label>
                    <input type="url" value={cfg.evolution_base_url} onChange={e => setCfg(c => ({ ...c, evolution_base_url: e.target.value }))}
                      placeholder="https://evolution.seudominio.com" className={IC} />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="text-xs text-stone">API Key</label>
                      <input type="password" value={cfg.evolution_api_key} onChange={e => setCfg(c => ({ ...c, evolution_api_key: e.target.value }))}
                        placeholder="apikey da Evolution" className={IC} />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-stone">Instancia</label>
                      <input type="text" value={cfg.evolution_instance} onChange={e => setCfg(c => ({ ...c, evolution_instance: e.target.value }))}
                        placeholder="nome-da-instancia" className={IC} />
                    </div>
                  </div>
                </div>
              )}
              <button type="submit" disabled={cfgSaving}
                className="w-full py-2.5 rounded-xl bg-gold hover:bg-gold/90 text-black font-semibold text-sm transition-colors disabled:opacity-60 flex items-center justify-center gap-2">
                {cfgSaving && <Loader2 size={14} className="animate-spin" />} Salvar Configurações
              </button>
            </form>
          </div>
        )}
      </AdminPageContent>

      {/* ── Template modal ── */}
      {showTplModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-5 border-b border-surface-03">
              <h2 className="text-cream font-semibold">{editingTplId ? "Editar Template" : "Novo Template"}</h2>
              <button onClick={() => setShowTplModal(false)} className="text-stone hover:text-cream"><X size={18} /></button>
            </div>
            <form onSubmit={saveTpl} className="p-5 space-y-4">
              <div className="space-y-1">
                <label className="text-xs text-stone">Nome do template aprovado na Meta *</label>
                <input type="text" value={tplForm.name} onChange={e => setTplForm(f => ({ ...f, name: e.target.value }))} placeholder="boas_vindas" className={IC} />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-stone">Categoria</label>
                <select value={tplForm.category} onChange={e => setTplForm(f => ({ ...f, category: e.target.value }))} className={IC}>
                  <option value="marketing">Marketing</option>
                  <option value="utility">Utilidade</option>
                  <option value="authentication">Autenticação</option>
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-stone">Idioma do template</label>
                <input type="text" value={tplForm.language} onChange={e => setTplForm(f => ({ ...f, language: e.target.value }))}
                  placeholder="pt_BR" className={IC} />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-stone">Mensagem *</label>
                <textarea value={tplForm.body} onChange={e => setTplForm(f => ({ ...f, body: e.target.value }))}
                  rows={6} placeholder="Olá {{nome}}, seu pedido foi confirmado!" className={`${IC} resize-none font-mono text-xs`} />
                <div className="flex flex-wrap gap-1 mt-1">
                  {WA_VARS.map(v => (
                    <button key={v} type="button"
                      onClick={() => setTplForm(f => ({ ...f, body: f.body + v }))}
                      className="px-1.5 py-0.5 bg-surface-03 text-stone text-xs rounded hover:text-gold transition-colors">{v}</button>
                  ))}
                </div>
              </div>
              {tplForm.body && (
                <div className="bg-surface-03 rounded-xl p-3">
                  <p className="text-xs text-stone mb-1 font-medium">Pré-visualização:</p>
                  <p className="text-xs text-cream font-mono leading-relaxed whitespace-pre-wrap">{tplForm.body}</p>
                </div>
              )}
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowTplModal(false)} className="flex-1 py-2 rounded-xl border border-surface-03 text-stone hover:text-cream text-sm">Cancelar</button>
                <button type="submit" disabled={saving} className="flex-1 py-2 rounded-xl bg-gold hover:bg-gold/90 text-black font-semibold text-sm disabled:opacity-60 flex items-center justify-center gap-2">
                  {saving && <Loader2 size={14} className="animate-spin" />}{editingTplId ? "Salvar" : "Criar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Campaign modal ── */}
      {showCampModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-md">
            <div className="flex items-center justify-between p-5 border-b border-surface-03">
              <h2 className="text-cream font-semibold">Nova Campanha WhatsApp</h2>
              <button onClick={() => setShowCampModal(false)} className="text-stone hover:text-cream"><X size={18} /></button>
            </div>
            <form onSubmit={saveCamp} className="p-5 space-y-4">
              <div className="space-y-1">
                <label className="text-xs text-stone">Nome da Campanha *</label>
                <input type="text" value={campForm.name} onChange={e => setCampForm(f => ({ ...f, name: e.target.value }))} placeholder="Campanha Black Friday" className={IC} />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-stone">Template</label>
                <select value={campForm.template_id} onChange={e => setCampForm(f => ({ ...f, template_id: e.target.value }))} className={IC}>
                  <option value="">Selecione um template...</option>
                  {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-stone">Grupo de Clientes</label>
                <input type="text" value={campForm.group_id} onChange={e => setCampForm(f => ({ ...f, group_id: e.target.value }))} placeholder="ID do grupo (opcional)" className={IC} />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-stone">Agendar para</label>
                <input type="datetime-local" value={campForm.scheduled_at} onChange={e => setCampForm(f => ({ ...f, scheduled_at: e.target.value }))} className={IC} />
              </div>
              <div className="flex gap-3">
                <button type="button" onClick={() => setShowCampModal(false)} className="flex-1 py-2 rounded-xl border border-surface-03 text-stone text-sm">Cancelar</button>
                <button type="submit" disabled={saving} className="flex-1 py-2 rounded-xl bg-gold hover:bg-gold/90 text-black font-semibold text-sm disabled:opacity-60 flex items-center justify-center gap-2">
                  {saving && <Loader2 size={14} className="animate-spin" />} Criar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      </AdminPageShell>
  );
}
