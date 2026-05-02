import { useEffect, useState, useRef } from "react";
import {
  Loader2, Plus, Pencil, Trash2, X, Mail, Send, CheckCircle,
  XCircle, Clock, AlertCircle, BarChart2, Settings, Eye, Zap,
  RefreshCw, Play, Pause, MessageSquare, Megaphone,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const unwrap = (j: any) => j?.data ?? j;

type Tab = "dashboard" | "templates" | "campanhas" | "disparo" | "monitoramento" | "configuracoes";

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "dashboard",     label: "Dashboard",       icon: BarChart2 },
  { id: "templates",     label: "Templates",        icon: MessageSquare },
  { id: "campanhas",     label: "Campanhas",        icon: Megaphone },
  { id: "disparo",       label: "Disparo Imediato", icon: Send },
  { id: "monitoramento", label: "Monitoramento",    icon: Eye },
  { id: "configuracoes", label: "Configurações",    icon: Settings },
];

const STATUS_CFG: Record<string, { label: string; cls: string; icon: React.ElementType }> = {
  sent:      { label: "Enviado",   cls: "bg-green-500/20 text-green-400",     icon: CheckCircle },
  delivered: { label: "Entregue",  cls: "bg-emerald-500/20 text-emerald-400", icon: CheckCircle },
  opened:    { label: "Aberto",    cls: "bg-blue-500/20 text-blue-400",       icon: Eye },
  clicked:   { label: "Clicado",   cls: "bg-purple-500/20 text-purple-400",   icon: Zap },
  bounced:   { label: "Bounce",    cls: "bg-orange-500/20 text-orange-400",   icon: AlertCircle },
  failed:    { label: "Falhou",    cls: "bg-red-500/20 text-red-400",         icon: XCircle },
  pending:   { label: "Pendente",  cls: "bg-yellow-500/20 text-yellow-400",   icon: Clock },
  queued:    { label: "Na fila",   cls: "bg-surface-03 text-stone",           icon: Clock },
  unsubscribed: { label: "Descadastrado", cls: "bg-stone/20 text-stone",     icon: XCircle },
};

const EMAIL_VARS = [
  "{{nome}}", "{{primeiro_nome}}", "{{email}}", "{{telefone}}",
  "{{endereco}}", "{{bairro}}", "{{cidade}}", "{{ultimo_pedido}}",
  "{{produto_mais_pedido}}", "{{cupom}}", "{{link_pedido}}", "{{valor_total}}",
  "{{data_aniversario}}", "{{link_descadastro}}",
];

function fmtDate(s?: string) {
  if (!s) return "—";
  return new Date(s).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function stripTags(html: string) {
  return html.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

const IC = "w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold";

interface EmailTemplate {
  id: string;
  name: string;
  subject: string;
  body_html: string;
  category: string;
  active: boolean;
  created_at: string;
}
interface EmailMessage {
  id: string;
  to_email: string;
  subject_sent: string;
  status: string;
  sent_at: string;
  error?: string;
  customer_name?: string;
  template_name?: string;
}
interface EmailCampaign {
  id: string;
  name: string;
  status: string;
  template_id?: string;
  group_id?: string;
  scheduled_at?: string;
  sent_count: number;
  delivered_count: number;
  open_count: number;
  click_count: number;
  bounce_count: number;
  unsubscribe_count: number;
  created_at: string;
}
interface EmailDashboard {
  sent: number;
  delivered: number;
  opened: number;
  clicked: number;
  bounced: number;
  unsubscribed: number;
  errors: number;
  active_campaigns: number;
  scheduled_campaigns: number;
  open_rate: number;
  click_rate: number;
  orders_generated: number;
  revenue_generated: number;
}
interface EmailConfig {
  provider: string;
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  smtp_password: string;
  from_name: string;
  from_email: string;
  reply_to: string;
  status: string;
  daily_limit: number;
  rate_per_hour: number;
}

const EMPTY_DASH: EmailDashboard = {
  sent: 0, delivered: 0, opened: 0, clicked: 0, bounced: 0,
  unsubscribed: 0, errors: 0, active_campaigns: 0, scheduled_campaigns: 0,
  open_rate: 0, click_rate: 0, orders_generated: 0, revenue_generated: 0,
};
const EMPTY_CFG: EmailConfig = {
  provider: "smtp", smtp_host: "", smtp_port: 587, smtp_user: "",
  smtp_password: "", from_name: "Moschettieri", from_email: "",
  reply_to: "", status: "disconnected", daily_limit: 5000, rate_per_hour: 500,
};

export default function MarketingEmail() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const token = localStorage.getItem("admin_token");
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  // ── Dashboard ──
  const [dash, setDash] = useState<EmailDashboard>(EMPTY_DASH);
  // ── Templates ──
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [tplLoading, setTplLoading] = useState(false);
  const [showTplModal, setShowTplModal] = useState(false);
  const [editingTplId, setEditingTplId] = useState<string | null>(null);
  const [tplForm, setTplForm] = useState({ name: "", subject: "", body_html: "", category: "marketing" });
  const [tplPreviewMode, setTplPreviewMode] = useState<"html" | "text">("html");
  // ── Campanhas ──
  const [campaigns, setCampaigns] = useState<EmailCampaign[]>([]);
  const [campLoading, setCampLoading] = useState(false);
  const [showCampModal, setShowCampModal] = useState(false);
  const [campForm, setCampForm] = useState({ name: "", template_id: "", group_id: "", scheduled_at: "" });
  // ── Disparo ──
  const [dispForm, setDispForm] = useState({ template_id: "", emails: "", subject: "", body_html: "", mode: "template", schedule: "" });
  const [dispResult, setDispResult] = useState<{ sent: number; failed: number } | null>(null);
  const [dispatching, setDispatching] = useState(false);
  // ── Monitoramento ──
  const [messages, setMessages] = useState<EmailMessage[]>([]);
  const [msgLoading, setMsgLoading] = useState(false);
  const monitorRef = useRef<ReturnType<typeof setInterval>>(null);
  // ── Configurações ──
  const [cfg, setCfg] = useState<EmailConfig>(EMPTY_CFG);
  const [cfgSaving, setCfgSaving] = useState(false);
  const [cfgTesting, setCfgTesting] = useState(false);
  // ── Global ──
  const [saving, setSaving] = useState(false);

  // fetch helpers
  const fetchDash = () => {
    fetch(`${BASE}/email/dashboard`, { headers })
      .then(r => r.json()).then(d => setDash({ ...EMPTY_DASH, ...unwrap(d) })).catch(() => {});
  };
  const fetchTemplates = () => {
    setTplLoading(true);
    fetch(`${BASE}/email/templates`, { headers })
      .then(r => r.json()).then(d => setTemplates(unwrap(d) ?? [])).catch(() => setTemplates([]))
      .finally(() => setTplLoading(false));
  };
  const fetchCampaigns = () => {
    setCampLoading(true);
    fetch(`${BASE}/email/campaigns`, { headers })
      .then(r => r.json()).then(d => setCampaigns(unwrap(d) ?? [])).catch(() => setCampaigns([]))
      .finally(() => setCampLoading(false));
  };
  const fetchMessages = () => {
    setMsgLoading(true);
    fetch(`${BASE}/email/messages`, { headers })
      .then(r => r.json()).then(d => setMessages(unwrap(d) ?? [])).catch(() => setMessages([]))
      .finally(() => setMsgLoading(false));
  };
  const fetchConfig = () => {
    fetch(`${BASE}/email/config`, { headers })
      .then(r => r.json()).then(d => setCfg({ ...EMPTY_CFG, ...unwrap(d) })).catch(() => {});
  };

  useEffect(() => {
    if (tab === "dashboard")    { fetchDash(); }
    if (tab === "templates")    { fetchTemplates(); }
    if (tab === "campanhas")    { fetchCampaigns(); fetchTemplates(); }
    if (tab === "disparo")      { fetchTemplates(); }
    if (tab === "monitoramento"){ fetchMessages(); }
    if (tab === "configuracoes"){ fetchConfig(); }
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
    if (!tplForm.name.trim() || !tplForm.subject.trim() || !tplForm.body_html.trim()) {
      alert("Nome, assunto e corpo são obrigatórios."); return;
    }
    setSaving(true);
    try {
      const url = editingTplId ? `${BASE}/email/templates/${editingTplId}` : `${BASE}/email/templates`;
      await fetch(url, { method: editingTplId ? "PATCH" : "POST", headers, body: JSON.stringify(tplForm) });
      setShowTplModal(false);
      fetchTemplates();
    } catch { alert("Erro ao salvar."); } finally { setSaving(false); }
  };
  const deleteTpl = async (id: string) => {
    if (!confirm("Excluir template?")) return;
    await fetch(`${BASE}/email/templates/${id}`, { method: "DELETE", headers });
    fetchTemplates();
  };

  // ── Campaign CRUD ──
  const saveCamp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!campForm.name.trim()) { alert("Nome obrigatório."); return; }
    setSaving(true);
    try {
      await fetch(`${BASE}/email/campaigns`, { method: "POST", headers, body: JSON.stringify(campForm) });
      setShowCampModal(false);
      setCampForm({ name: "", template_id: "", group_id: "", scheduled_at: "" });
      fetchCampaigns();
    } catch { alert("Erro ao criar campanha."); } finally { setSaving(false); }
  };
  const toggleCamp = async (id: string, status: string) => {
    const newStatus = status === "running" ? "paused" : "running";
    await fetch(`${BASE}/email/campaigns/${id}`, { method: "PATCH", headers, body: JSON.stringify({ status: newStatus }) });
    fetchCampaigns();
  };
  const deleteCamp = async (id: string) => {
    if (!confirm("Excluir campanha?")) return;
    await fetch(`${BASE}/email/campaigns/${id}`, { method: "DELETE", headers });
    fetchCampaigns();
  };

  // ── Disparo imediato ──
  const sendNow = async (e: React.FormEvent) => {
    e.preventDefault();
    setDispatching(true);
    setDispResult(null);
    try {
      const emails = dispForm.emails.split(/[\n,]/).map(p => p.trim()).filter(Boolean);
      const body = dispForm.mode === "template"
        ? JSON.stringify({ template_id: dispForm.template_id, emails, scheduled_at: dispForm.schedule || undefined })
        : JSON.stringify({ subject: dispForm.subject, body_html: dispForm.body_html, emails, scheduled_at: dispForm.schedule || undefined });
      const r = await fetch(`${BASE}/email/send`, { method: "POST", headers, body });
      const d = unwrap(await r.json());
      setDispResult({ sent: d.sent ?? 0, failed: d.failed ?? 0 });
    } catch { alert("Erro ao enviar."); } finally { setDispatching(false); }
  };

  // ── Test connection ──
  const testConnection = async () => {
    setCfgTesting(true);
    try {
      const r = await fetch(`${BASE}/email/test-connection`, { method: "POST", headers, body: JSON.stringify(cfg) });
      const d = unwrap(await r.json());
      alert(d.success ? "Conexão bem-sucedida!" : `Falha: ${d.error ?? "Erro desconhecido"}`);
    } catch { alert("Erro ao testar conexão."); } finally { setCfgTesting(false); }
  };

  // ── Config ──
  const saveCfg = async (e: React.FormEvent) => {
    e.preventDefault();
    setCfgSaving(true);
    try {
      await fetch(`${BASE}/email/config`, { method: "PATCH", headers, body: JSON.stringify(cfg) });
      alert("Configurações salvas.");
    } catch { alert("Erro ao salvar."); } finally { setCfgSaving(false); }
  };

  return (
    <div className="flex flex-col md:flex-row min-h-screen md:h-screen bg-surface-00 overflow-hidden">
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto p-6 space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-gold mb-1">Marketing</p>
            <h1 className="text-2xl font-bold text-cream">Disparador de Email</h1>
          </div>
          <AdminTopActions />
        </div>

        {/* Tabs */}
        <div className="flex flex-wrap gap-1 bg-surface-02 border border-surface-03 rounded-xl p-1">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => setTab(id)}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${tab === id ? "bg-gold text-black" : "text-stone hover:text-cream hover:bg-surface-03"}`}>
              <Icon size={14} /> {label}
            </button>
          ))}
        </div>

        {/* ═══ DASHBOARD ═══ */}
        {tab === "dashboard" && (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
              {[
                { label: "Enviados",        value: dash.sent.toLocaleString("pt-BR"),           cls: "text-blue-400" },
                { label: "Entregues",       value: dash.delivered.toLocaleString("pt-BR"),       cls: "text-green-400" },
                { label: "Abertos",         value: dash.opened.toLocaleString("pt-BR"),          cls: "text-emerald-400" },
                { label: "Cliques",         value: dash.clicked.toLocaleString("pt-BR"),         cls: "text-purple-400" },
                { label: "Bounces",         value: dash.bounced.toLocaleString("pt-BR"),         cls: "text-orange-400" },
                { label: "Descadastros",    value: dash.unsubscribed.toLocaleString("pt-BR"),    cls: "text-red-400" },
                { label: "Camp. Ativas",    value: String(dash.active_campaigns),                cls: "text-gold" },
                { label: "Agendadas",       value: String(dash.scheduled_campaigns),             cls: "text-cyan-400" },
                { label: "Taxa Abertura",   value: `${((dash.open_rate ?? 0) * 100).toFixed(1)}%`,  cls: "text-emerald-400" },
                { label: "Taxa de Clique",  value: `${((dash.click_rate ?? 0) * 100).toFixed(1)}%`, cls: "text-purple-400" },
                { label: "Pedidos Gerados", value: String(dash.orders_generated),                cls: "text-gold" },
                { label: "Receita Gerada",  value: (dash.revenue_generated ?? 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }), cls: "text-green-400" },
              ].map(m => (
                <div key={m.label} className="bg-surface-02 border border-surface-03 rounded-2xl p-4">
                  <p className="text-xs text-stone mb-1">{m.label}</p>
                  <p className={`text-xl font-bold ${m.cls}`}>{m.value}</p>
                </div>
              ))}
            </div>

            {/* Funil de Email */}
            <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5">
              <h2 className="text-sm font-semibold text-cream mb-4">Funil de Engajamento</h2>
              {(() => {
                const stages = [
                  { label: "Enviado",    value: dash.sent,      color: "bg-blue-500" },
                  { label: "Entregue",   value: dash.delivered, color: "bg-green-500" },
                  { label: "Aberto",     value: dash.opened,    color: "bg-emerald-500" },
                  { label: "Clicado",    value: dash.clicked,   color: "bg-purple-500" },
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
                        <div className="w-14 text-xs text-stone text-right">
                          {max > 0 ? `${((s.value / dash.sent || 0) * 100).toFixed(1)}%` : "0%"}
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
              <button onClick={() => { setEditingTplId(null); setTplForm({ name: "", subject: "", body_html: "", category: "marketing" }); setShowTplModal(true); }}
                className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-black font-semibold px-4 py-2 rounded-xl text-sm transition-colors">
                <Plus size={16} /> Novo Template
              </button>
            </div>

            {/* Variables reference */}
            <div className="bg-surface-02 border border-surface-03 rounded-xl p-4">
              <p className="text-xs text-stone font-medium mb-2">Variáveis disponíveis:</p>
              <div className="flex flex-wrap gap-1.5">
                {EMAIL_VARS.map(v => (
                  <span key={v} className="px-2 py-0.5 bg-surface-03 text-cream text-xs rounded font-mono cursor-pointer hover:bg-gold/20 hover:text-gold transition-colors"
                    onClick={() => navigator.clipboard.writeText(v)} title="Clique para copiar">{v}</span>
                ))}
              </div>
            </div>

            {tplLoading ? (
              <div className="flex justify-center py-12"><Loader2 className="animate-spin text-gold" size={28} /></div>
            ) : templates.length === 0 ? (
              <div className="flex flex-col items-center py-20 bg-surface-02 border border-surface-03 rounded-2xl">
                <Mail size={40} className="text-surface-03 mb-3" />
                <p className="text-stone text-sm">Nenhum template. <button onClick={() => setShowTplModal(true)} className="text-gold hover:underline">Criar agora</button></p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {templates.map(t => (
                  <div key={t.id} className="bg-surface-02 border border-surface-03 rounded-2xl p-4 space-y-3 flex flex-col">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h3 className="text-cream font-semibold text-sm">{t.name}</h3>
                        <p className="text-xs text-gold truncate max-w-[180px]">{t.subject}</p>
                        <span className="text-xs text-stone">{t.category}</span>
                      </div>
                      <span className={`shrink-0 px-2 py-0.5 rounded-full text-xs ${t.active ? "bg-green-500/20 text-green-400" : "bg-surface-03 text-stone"}`}>
                        {t.active ? "Ativo" : "Inativo"}
                      </span>
                    </div>
                    <div className="flex-1 bg-surface-03 rounded-xl p-3">
                      <p className="text-stone text-xs leading-relaxed line-clamp-3">{stripTags(t.body_html)}</p>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-stone">{fmtDate(t.created_at)}</span>
                      <div className="flex gap-1">
                        <button onClick={() => { setEditingTplId(t.id); setTplForm({ name: t.name, subject: t.subject, body_html: t.body_html, category: t.category }); setShowTplModal(true); }}
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
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <h3 className="text-cream font-semibold text-sm">{c.name}</h3>
                            <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${
                              c.status === "running"   ? "bg-green-500/20 text-green-400" :
                              c.status === "paused"    ? "bg-yellow-500/20 text-yellow-400" :
                              c.status === "completed" ? "bg-blue-500/20 text-blue-400" :
                              "bg-surface-03 text-stone"
                            }`}>{c.status}</span>
                          </div>
                          <div className="flex flex-wrap gap-4 text-xs text-stone">
                            <span>Enviados: <span className="text-cream">{c.sent_count}</span></span>
                            <span>Entregues: <span className="text-green-400">{c.delivered_count}</span></span>
                            <span>Abertos: <span className="text-emerald-400">{c.open_count}</span></span>
                            <span>Cliques: <span className="text-purple-400">{c.click_count}</span></span>
                            <span>Bounces: <span className="text-orange-400">{c.bounce_count}</span></span>
                            <span>Descad: <span className="text-red-400">{c.unsubscribe_count}</span></span>
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
                {dispForm.mode === "template" ? (
                  <div className="space-y-1">
                    <label className="text-xs text-stone">Template *</label>
                    <select value={dispForm.template_id} onChange={e => setDispForm(f => ({ ...f, template_id: e.target.value }))} className={IC}>
                      <option value="">Selecione...</option>
                      {templates.map(t => <option key={t.id} value={t.id}>{t.name} — {t.subject}</option>)}
                    </select>
                  </div>
                ) : (
                  <>
                    <div className="space-y-1">
                      <label className="text-xs text-stone">Assunto *</label>
                      <input type="text" value={dispForm.subject} onChange={e => setDispForm(f => ({ ...f, subject: e.target.value }))}
                        placeholder="Assunto do email" className={IC} />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-stone">Corpo (HTML ou texto) *</label>
                      <textarea value={dispForm.body_html} onChange={e => setDispForm(f => ({ ...f, body_html: e.target.value }))}
                        rows={6} placeholder="<p>Olá {{nome}}, seu pedido foi confirmado!</p>" className={`${IC} resize-none font-mono text-xs`} />
                      <div className="flex flex-wrap gap-1 mt-1">
                        {EMAIL_VARS.slice(0, 6).map(v => (
                          <button key={v} type="button"
                            onClick={() => setDispForm(f => ({ ...f, body_html: f.body_html + v }))}
                            className="px-1.5 py-0.5 bg-surface-03 text-stone text-xs rounded hover:text-gold transition-colors">{v}</button>
                        ))}
                      </div>
                    </div>
                  </>
                )}
                <div className="space-y-1">
                  <label className="text-xs text-stone">Endereços de email (um por linha ou separado por vírgula) *</label>
                  <textarea value={dispForm.emails} onChange={e => setDispForm(f => ({ ...f, emails: e.target.value }))}
                    rows={4} placeholder={"joao@exemplo.com\nmaria@exemplo.com"} className={`${IC} resize-none font-mono text-xs`} />
                  <p className="text-xs text-stone/60">
                    {dispForm.emails.split(/[\n,]/).filter(e => e.trim()).length} endereço(s) informado(s)
                  </p>
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-stone">Agendar para (opcional)</label>
                  <input type="datetime-local" value={dispForm.schedule} onChange={e => setDispForm(f => ({ ...f, schedule: e.target.value }))} className={IC} />
                </div>
                {dispResult && (
                  <div className="rounded-xl bg-surface-03 p-4 flex items-center justify-around">
                    <div className="text-center"><p className="text-2xl font-bold text-green-400">{dispResult.sent}</p><p className="text-xs text-stone mt-0.5">Enviados</p></div>
                    <div className="text-center"><p className="text-2xl font-bold text-red-400">{dispResult.failed}</p><p className="text-xs text-stone mt-0.5">Falhas</p></div>
                  </div>
                )}
                <button type="submit" disabled={dispatching}
                  className="w-full py-3 rounded-xl bg-gold hover:bg-gold/90 text-black font-semibold text-sm transition-colors disabled:opacity-60 flex items-center justify-center gap-2">
                  {dispatching ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
                  {dispForm.schedule ? "Agendar Disparo" : "Disparar Agora"}
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
                  <div className="flex flex-col items-center py-16">
                    <Send size={40} className="text-surface-03 mb-3" />
                    <p className="text-stone text-sm">Nenhum email enviado ainda.</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-stone text-xs border-b border-surface-03 bg-surface-03/30">
                          {["Cliente", "Email", "Assunto", "Template", "Status", "Data/Hora", "Erro"].map(h => (
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
                              <td className="p-3 text-stone font-mono text-xs">{m.to_email}</td>
                              <td className="p-3 text-stone text-xs max-w-[160px] truncate">{m.subject_sent}</td>
                              <td className="p-3 text-stone text-xs">{m.template_name ?? "—"}</td>
                              <td className="p-3"><span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${sc.cls}`}><SI size={10} />{sc.label}</span></td>
                              <td className="p-3 text-stone text-xs whitespace-nowrap">{fmtDate(m.sent_at)}</td>
                              <td className="p-3 text-red-400 text-xs max-w-[140px] truncate">{m.error ?? "—"}</td>
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
          <div className="max-w-xl">
            <form onSubmit={saveCfg} className="bg-surface-02 border border-surface-03 rounded-2xl p-5 space-y-4">
              <h2 className="text-sm font-semibold text-cream">Configurações de Email</h2>

              <div className="space-y-1">
                <label className="text-xs text-stone">Provedor</label>
                <select value={cfg.provider} onChange={e => setCfg(c => ({ ...c, provider: e.target.value }))} className={IC}>
                  <option value="smtp">SMTP Próprio</option>
                  <option value="sendgrid">SendGrid</option>
                  <option value="mailgun">Mailgun</option>
                  <option value="ses">Amazon SES</option>
                  <option value="brevo">Brevo (Sendinblue)</option>
                </select>
              </div>

              {cfg.provider === "smtp" && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1 col-span-2 sm:col-span-1">
                    <label className="text-xs text-stone">Host SMTP</label>
                    <input type="text" value={cfg.smtp_host} onChange={e => setCfg(c => ({ ...c, smtp_host: e.target.value }))}
                      placeholder="smtp.gmail.com" className={IC} />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-stone">Porta</label>
                    <input type="number" value={cfg.smtp_port} onChange={e => setCfg(c => ({ ...c, smtp_port: +e.target.value }))} className={IC} />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-stone">Usuário SMTP</label>
                    <input type="text" value={cfg.smtp_user} onChange={e => setCfg(c => ({ ...c, smtp_user: e.target.value }))}
                      placeholder="seu@email.com" className={IC} />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-stone">Senha SMTP</label>
                    <input type="password" value={cfg.smtp_password} onChange={e => setCfg(c => ({ ...c, smtp_password: e.target.value }))}
                      placeholder="••••••••" className={IC} />
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs text-stone">Nome do Remetente</label>
                  <input type="text" value={cfg.from_name} onChange={e => setCfg(c => ({ ...c, from_name: e.target.value }))}
                    placeholder="Moschettieri Pizza" className={IC} />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-stone">Email do Remetente</label>
                  <input type="email" value={cfg.from_email} onChange={e => setCfg(c => ({ ...c, from_email: e.target.value }))}
                    placeholder="noreply@moschettieri.com.br" className={IC} />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs text-stone">Reply-To (opcional)</label>
                <input type="email" value={cfg.reply_to} onChange={e => setCfg(c => ({ ...c, reply_to: e.target.value }))}
                  placeholder="atendimento@moschettieri.com.br" className={IC} />
              </div>

              <div className="flex items-center gap-3 p-3 bg-surface-03 rounded-xl">
                <span className={`w-3 h-3 rounded-full ${cfg.status === "connected" ? "bg-green-400" : "bg-red-400"}`} />
                <span className="text-sm text-cream">Status: <span className={cfg.status === "connected" ? "text-green-400" : "text-red-400"}>
                  {cfg.status === "connected" ? "Conectado" : "Desconectado"}
                </span></span>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs text-stone">Limite diário</label>
                  <input type="number" min={1} value={cfg.daily_limit}
                    onChange={e => setCfg(c => ({ ...c, daily_limit: +e.target.value }))} className={IC} />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-stone">Emails/hora</label>
                  <input type="number" min={1} value={cfg.rate_per_hour}
                    onChange={e => setCfg(c => ({ ...c, rate_per_hour: +e.target.value }))} className={IC} />
                </div>
              </div>

              <div className="flex gap-3">
                <button type="button" onClick={testConnection} disabled={cfgTesting}
                  className="flex-1 py-2.5 rounded-xl border border-surface-03 text-stone hover:text-cream text-sm disabled:opacity-60 flex items-center justify-center gap-2">
                  {cfgTesting ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} />} Testar Conexão
                </button>
                <button type="submit" disabled={cfgSaving}
                  className="flex-1 py-2.5 rounded-xl bg-gold hover:bg-gold/90 text-black font-semibold text-sm disabled:opacity-60 flex items-center justify-center gap-2">
                  {cfgSaving && <Loader2 size={14} className="animate-spin" />} Salvar
                </button>
              </div>
            </form>
          </div>
        )}
      </main>

      {/* ── Template modal ── */}
      {showTplModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-5 border-b border-surface-03">
              <h2 className="text-cream font-semibold">{editingTplId ? "Editar Template" : "Novo Template de Email"}</h2>
              <button onClick={() => setShowTplModal(false)} className="text-stone hover:text-cream"><X size={18} /></button>
            </div>
            <form onSubmit={saveTpl} className="p-5 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs text-stone">Nome *</label>
                  <input type="text" value={tplForm.name} onChange={e => setTplForm(f => ({ ...f, name: e.target.value }))}
                    placeholder="boas_vindas" className={IC} />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-stone">Categoria</label>
                  <select value={tplForm.category} onChange={e => setTplForm(f => ({ ...f, category: e.target.value }))} className={IC}>
                    <option value="marketing">Marketing</option>
                    <option value="transactional">Transacional</option>
                    <option value="retention">Retenção</option>
                    <option value="reactivation">Reativação</option>
                  </select>
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-stone">Assunto *</label>
                <input type="text" value={tplForm.subject} onChange={e => setTplForm(f => ({ ...f, subject: e.target.value }))}
                  placeholder="🍕 Promoção especial para você, {{primeiro_nome}}!" className={IC} />
                <div className="flex flex-wrap gap-1 mt-1">
                  {["{{primeiro_nome}}", "{{cupom}}", "{{produto_mais_pedido}}"].map(v => (
                    <button key={v} type="button"
                      onClick={() => setTplForm(f => ({ ...f, subject: f.subject + v }))}
                      className="px-1.5 py-0.5 bg-surface-03 text-stone text-xs rounded hover:text-gold transition-colors">{v}</button>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs text-stone">Corpo do Email (HTML) *</label>
                  <div className="flex gap-1">
                    {(["html", "text"] as const).map(m => (
                      <button key={m} type="button" onClick={() => setTplPreviewMode(m)}
                        className={`px-2 py-0.5 rounded text-xs ${tplPreviewMode === m ? "bg-gold text-black" : "bg-surface-03 text-stone"}`}>
                        {m === "html" ? "Editor" : "Preview"}
                      </button>
                    ))}
                  </div>
                </div>
                {tplPreviewMode === "html" ? (
                  <>
                    <textarea value={tplForm.body_html} onChange={e => setTplForm(f => ({ ...f, body_html: e.target.value }))}
                      rows={10} placeholder="<p>Olá {{nome}},</p><p>Temos uma promoção especial...</p>"
                      className={`${IC} resize-none font-mono text-xs`} />
                    <div className="flex flex-wrap gap-1">
                      {EMAIL_VARS.map(v => (
                        <button key={v} type="button"
                          onClick={() => setTplForm(f => ({ ...f, body_html: f.body_html + v }))}
                          className="px-1.5 py-0.5 bg-surface-03 text-stone text-xs rounded hover:text-gold transition-colors">{v}</button>
                      ))}
                    </div>
                  </>
                ) : (
                  <div className="bg-white rounded-xl p-4 min-h-[200px] max-h-[400px] overflow-y-auto">
                    {tplForm.body_html ? (
                      <div className="text-black text-sm" dangerouslySetInnerHTML={{ __html: tplForm.body_html }} />
                    ) : (
                      <p className="text-gray-400 text-sm text-center py-8">Nenhum conteúdo para exibir.</p>
                    )}
                  </div>
                )}
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowTplModal(false)}
                  className="flex-1 py-2 rounded-xl border border-surface-03 text-stone hover:text-cream text-sm">Cancelar</button>
                <button type="submit" disabled={saving}
                  className="flex-1 py-2 rounded-xl bg-gold hover:bg-gold/90 text-black font-semibold text-sm disabled:opacity-60 flex items-center justify-center gap-2">
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
              <h2 className="text-cream font-semibold">Nova Campanha de Email</h2>
              <button onClick={() => setShowCampModal(false)} className="text-stone hover:text-cream"><X size={18} /></button>
            </div>
            <form onSubmit={saveCamp} className="p-5 space-y-4">
              <div className="space-y-1">
                <label className="text-xs text-stone">Nome da Campanha *</label>
                <input type="text" value={campForm.name} onChange={e => setCampForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="Newsletter Junho" className={IC} />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-stone">Template</label>
                <select value={campForm.template_id} onChange={e => setCampForm(f => ({ ...f, template_id: e.target.value }))} className={IC}>
                  <option value="">Selecione um template...</option>
                  {templates.map(t => <option key={t.id} value={t.id}>{t.name} — {t.subject}</option>)}
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-stone">Grupo de Clientes</label>
                <input type="text" value={campForm.group_id} onChange={e => setCampForm(f => ({ ...f, group_id: e.target.value }))}
                  placeholder="ID do grupo (opcional)" className={IC} />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-stone">Agendar para</label>
                <input type="datetime-local" value={campForm.scheduled_at} onChange={e => setCampForm(f => ({ ...f, scheduled_at: e.target.value }))} className={IC} />
              </div>
              <div className="flex gap-3">
                <button type="button" onClick={() => setShowCampModal(false)}
                  className="flex-1 py-2 rounded-xl border border-surface-03 text-stone text-sm">Cancelar</button>
                <button type="submit" disabled={saving}
                  className="flex-1 py-2 rounded-xl bg-gold hover:bg-gold/90 text-black font-semibold text-sm disabled:opacity-60 flex items-center justify-center gap-2">
                  {saving && <Loader2 size={14} className="animate-spin" />} Criar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
