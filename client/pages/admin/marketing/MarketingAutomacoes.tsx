import { useEffect, useState } from "react";
import {
  Loader2, Plus, Pencil, Trash2, X, Zap, Play, List,
  CheckCircle, XCircle, SkipForward, AlertCircle,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const unwrap = (json: any) => json?.data ?? json;

interface Automation {
  id: string;
  name: string;
  trigger: string;
  trigger_value?: string;
  channel: string;
  template_id?: string;
  message_body?: string;
  active: boolean;
  runs_total: number;
  last_run_at?: string;
  created_at: string;
}

interface AutomationLog {
  id: string;
  customer_id?: string;
  channel: string;
  status: string;
  error?: string;
  created_at: string;
}

const TRIGGER_LABELS: Record<string, string> = {
  abandoned_cart: "Carrinho Abandonado",
  reactivation: "Reativação de Cliente",
  birthday: "Aniversário",
  first_order: "Após 1º Pedido",
  new_customer: "Novo Cliente",
};

const CHANNEL_LABELS: Record<string, string> = {
  whatsapp: "WhatsApp",
  email: "E-mail",
};

const TRIGGER_DESCRIPTIONS: Record<string, string> = {
  abandoned_cart: "Envia quando cliente adicionou ao carrinho mas não finalizou o pedido",
  reactivation: "Envia para clientes que não pedem há N dias",
  birthday: "Envia no dia do aniversário do cliente",
  first_order: "Envia após o cliente completar o primeiro pedido",
  new_customer: "Envia quando um novo cliente se cadastra",
};

const LOG_STATUS_CONFIG: Record<string, { label: string; className: string; icon: React.ElementType }> = {
  sent: { label: "Enviado", className: "bg-green-500/20 text-green-400", icon: CheckCircle },
  failed: { label: "Falhou", className: "bg-red-500/20 text-red-400", icon: XCircle },
  skipped: { label: "Ignorado", className: "bg-surface-03 text-stone", icon: SkipForward },
};

function fmtDate(s?: string) {
  if (!s) return "—";
  return new Date(s).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

const emptyForm = (): Partial<Automation> => ({
  name: "",
  channel: "whatsapp",
  trigger: "new_customer",
  trigger_value: "",
  template_id: "",
  message_body: "",
});

export default function MarketingAutomacoes() {
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<Partial<Automation>>(emptyForm());
  const [saving, setSaving] = useState(false);

  const [running, setRunning] = useState<string | null>(null);
  const [runResult, setRunResult] = useState<Record<string, { sent: number; failed: number; skipped: number }>>({});

  const [showLogs, setShowLogs] = useState<string | null>(null);
  const [logs, setLogs] = useState<AutomationLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);

  const token = localStorage.getItem("admin_token");
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const fetchAutomations = () => {
    setLoading(true);
    setError("");
    fetch(`${BASE}/automations`, { headers })
      .then((r) => { if (!r.ok) throw new Error("Falha ao carregar automações."); return r.json(); })
      .then(unwrap)
      .then(setAutomations)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchAutomations(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const openCreate = () => {
    setEditingId(null);
    setForm(emptyForm());
    setShowModal(true);
  };

  const openEdit = (a: Automation) => {
    setEditingId(a.id);
    setForm({ ...a });
    setShowModal(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name?.trim()) { alert("Nome obrigatório."); return; }
    setSaving(true);
    try {
      if (editingId) {
        await fetch(`${BASE}/automations/${editingId}`, {
          method: "PATCH",
          headers,
          body: JSON.stringify(form),
        });
      } else {
        await fetch(`${BASE}/automations`, {
          method: "POST",
          headers,
          body: JSON.stringify(form),
        });
      }
      setShowModal(false);
      fetchAutomations();
    } catch {
      alert("Erro ao salvar automação.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Excluir automação?")) return;
    await fetch(`${BASE}/automations/${id}`, { method: "DELETE", headers });
    fetchAutomations();
  };

  const handleToggle = async (id: string) => {
    await fetch(`${BASE}/automations/${id}/toggle`, { method: "POST", headers })
      .then((r) => r.json())
      .then(unwrap)
      .then((data) => {
        setAutomations((prev) =>
          prev.map((a) => (a.id === id ? { ...a, active: data.active ?? !a.active } : a))
        );
      })
      .catch(() => alert("Erro ao alternar automação."));
  };

  const handleRun = async (id: string) => {
    setRunning(id);
    await fetch(`${BASE}/automations/${id}/run`, { method: "POST", headers })
      .then((r) => r.json())
      .then(unwrap)
      .then((data) => {
        setRunResult((prev) => ({
          ...prev,
          [id]: { sent: data.sent ?? 0, failed: data.failed ?? 0, skipped: data.skipped ?? 0 },
        }));
      })
      .catch(() => alert("Erro ao executar automação."))
      .finally(() => setRunning(null));
  };

  const fetchLogs = (id: string) => {
    setLogsLoading(true);
    setLogs([]);
    fetch(`${BASE}/automations/${id}/logs`, { headers })
      .then((r) => r.json())
      .then(unwrap)
      .then(setLogs)
      .catch(() => {})
      .finally(() => setLogsLoading(false));
    setShowLogs(id);
  };

  const inputClass = "w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold";

  return (
    <div className="flex flex-col md:flex-row min-h-screen bg-surface-01">
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-gold mb-1">Marketing</p>
            <h1 className="text-2xl font-bold text-cream">Automações de Marketing</h1>
          </div>
          <button
            onClick={openCreate}
            className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-black font-semibold px-4 py-2 rounded-xl text-sm transition-colors"
          >
            <Plus size={16} /> Nova Automação
          </button>
        </div>

        {/* Error */}
        {error && !loading && (
          <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 text-red-400 text-sm flex items-center gap-2">
            <AlertCircle size={16} /> {error}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center h-48">
            <Loader2 className="animate-spin text-gold" size={28} />
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && automations.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 bg-surface-02 border border-surface-03 rounded-2xl">
            <Zap size={40} className="text-surface-03 mb-3" />
            <p className="text-stone text-sm">Nenhuma automação configurada.</p>
            <button onClick={openCreate} className="mt-3 text-gold text-sm hover:underline">
              Criar primeira automação
            </button>
          </div>
        )}

        {/* Automation cards */}
        {!loading && !error && automations.length > 0 && (
          <div className="grid grid-cols-1 gap-4">
            {automations.map((a) => {
              const result = runResult[a.id];
              const isRunning = running === a.id;
              return (
                <div key={a.id} className="bg-surface-02 border border-surface-03 rounded-2xl p-5 space-y-3">
                  {/* Top row */}
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <div className="p-2 rounded-xl bg-gold/10">
                        <Zap size={16} className="text-gold" />
                      </div>
                      <h3 className="text-cream font-semibold text-base truncate">{a.name}</h3>
                      <span
                        className={`shrink-0 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                          a.channel === "whatsapp"
                            ? "bg-green-500/20 text-green-400"
                            : "bg-blue-500/20 text-blue-400"
                        }`}
                      >
                        {CHANNEL_LABELS[a.channel] ?? a.channel}
                      </span>
                    </div>
                    {/* Toggle */}
                    <button
                      onClick={() => handleToggle(a.id)}
                      className={`shrink-0 relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${
                        a.active ? "bg-gold" : "bg-surface-03"
                      }`}
                      title={a.active ? "Desativar" : "Ativar"}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                          a.active ? "translate-x-6" : "translate-x-1"
                        }`}
                      />
                    </button>
                  </div>

                  {/* Trigger */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs bg-surface-03 text-cream px-2.5 py-1 rounded-lg font-medium">
                      {TRIGGER_LABELS[a.trigger] ?? a.trigger}
                      {a.trigger_value ? ` — ${a.trigger_value} dias` : ""}
                    </span>
                  </div>

                  {/* Description */}
                  <p className="text-stone text-xs leading-relaxed">
                    {TRIGGER_DESCRIPTIONS[a.trigger] ?? "Automação personalizada"}
                  </p>

                  {/* Stats */}
                  <div className="flex items-center gap-4 text-xs text-stone">
                    <span>
                      <span className="text-cream font-semibold">{a.runs_total}</span> execuções totais
                    </span>
                    <span>
                      Última execução: <span className="text-cream">{fmtDate(a.last_run_at)}</span>
                    </span>
                  </div>

                  {/* Run result inline */}
                  {result && (
                    <div className="flex items-center gap-3 p-3 rounded-xl bg-surface-03/60 flex-wrap">
                      <span className="text-xs text-stone font-medium">Resultado:</span>
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-500/20 text-green-400">
                        <CheckCircle size={11} /> {result.sent} enviados
                      </span>
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-500/20 text-red-400">
                        <XCircle size={11} /> {result.failed} falhas
                      </span>
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-surface-03 text-stone">
                        <SkipForward size={11} /> {result.skipped} ignorados
                      </span>
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex items-center gap-2 flex-wrap pt-1">
                    <button
                      onClick={() => handleRun(a.id)}
                      disabled={isRunning}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-03 hover:bg-gold hover:text-black text-stone hover:text-black text-xs font-medium transition-colors disabled:opacity-60"
                    >
                      {isRunning ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
                      {isRunning ? "Executando..." : "Executar agora"}
                    </button>
                    <button
                      onClick={() => fetchLogs(a.id)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-03 hover:bg-surface-03/70 text-stone hover:text-cream text-xs font-medium transition-colors"
                    >
                      <List size={13} /> Ver logs
                    </button>
                    <button
                      onClick={() => openEdit(a)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-03 hover:bg-surface-03/70 text-stone hover:text-cream text-xs font-medium transition-colors"
                    >
                      <Pencil size={13} /> Editar
                    </button>
                    <button
                      onClick={() => handleDelete(a.id)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-03 hover:bg-red-500/10 text-stone hover:text-red-400 text-xs font-medium transition-colors"
                    >
                      <Trash2 size={13} /> Excluir
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Modal: Criar/Editar Automação */}
        {showModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
            <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between p-5 border-b border-surface-03">
                <h2 className="text-cream font-semibold">
                  {editingId ? "Editar Automação" : "Nova Automação"}
                </h2>
                <button onClick={() => setShowModal(false)} className="text-stone hover:text-cream transition-colors">
                  <X size={18} />
                </button>
              </div>
              <form onSubmit={handleSave} className="p-5 space-y-4">
                {/* Nome */}
                <div className="space-y-1">
                  <label className="text-xs text-stone">Nome *</label>
                  <input
                    type="text"
                    value={form.name ?? ""}
                    onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder="Ex: Boas-vindas novo cliente"
                    className={inputClass}
                  />
                </div>

                {/* Canal */}
                <div className="space-y-1">
                  <label className="text-xs text-stone">Canal *</label>
                  <select
                    value={form.channel ?? "whatsapp"}
                    onChange={(e) => setForm((f) => ({ ...f, channel: e.target.value }))}
                    className={inputClass}
                  >
                    {Object.entries(CHANNEL_LABELS).map(([v, l]) => (
                      <option key={v} value={v}>{l}</option>
                    ))}
                  </select>
                </div>

                {/* Gatilho */}
                <div className="space-y-1">
                  <label className="text-xs text-stone">Gatilho *</label>
                  <select
                    value={form.trigger ?? "new_customer"}
                    onChange={(e) => setForm((f) => ({ ...f, trigger: e.target.value, trigger_value: "" }))}
                    className={inputClass}
                  >
                    {Object.entries(TRIGGER_LABELS).map(([v, l]) => (
                      <option key={v} value={v}>{l}</option>
                    ))}
                  </select>
                  {form.trigger && TRIGGER_DESCRIPTIONS[form.trigger] && (
                    <p className="text-xs text-stone/70 mt-1">{TRIGGER_DESCRIPTIONS[form.trigger]}</p>
                  )}
                </div>

                {/* Valor do gatilho (só para reactivation) */}
                {form.trigger === "reactivation" && (
                  <div className="space-y-1">
                    <label className="text-xs text-stone">Dias sem pedido *</label>
                    <input
                      type="number"
                      min={1}
                      value={form.trigger_value ?? ""}
                      onChange={(e) => setForm((f) => ({ ...f, trigger_value: e.target.value }))}
                      placeholder="Ex: 30"
                      className={inputClass}
                    />
                  </div>
                )}

                {/* ID do Template */}
                <div className="space-y-1">
                  <label className="text-xs text-stone">ID do Template</label>
                  <input
                    type="text"
                    value={form.template_id ?? ""}
                    onChange={(e) => setForm((f) => ({ ...f, template_id: e.target.value }))}
                    placeholder="ID do template WhatsApp ou E-mail"
                    className={inputClass}
                  />
                  <p className="text-xs text-stone/60">
                    Informe o ID do template cadastrado em WhatsApp ou E-mail Marketing. Opcional se usar mensagem fallback.
                  </p>
                </div>

                {/* Mensagem fallback */}
                <div className="space-y-1">
                  <label className="text-xs text-stone">Mensagem Fallback</label>
                  <textarea
                    value={form.message_body ?? ""}
                    onChange={(e) => setForm((f) => ({ ...f, message_body: e.target.value }))}
                    rows={4}
                    placeholder="Mensagem usada caso o ID do template não seja preenchido"
                    className={`${inputClass} resize-none`}
                  />
                </div>

                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowModal(false)}
                    className="flex-1 py-2 rounded-xl border border-surface-03 text-stone hover:text-cream text-sm transition-colors"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    disabled={saving}
                    className="flex-1 py-2 rounded-xl bg-gold hover:bg-gold/90 text-black font-semibold text-sm transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
                  >
                    {saving && <Loader2 size={14} className="animate-spin" />}
                    {editingId ? "Salvar" : "Criar"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Modal: Logs */}
        {showLogs && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
            <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-2xl max-h-[85vh] overflow-y-auto">
              <div className="flex items-center justify-between p-5 border-b border-surface-03">
                <h2 className="text-cream font-semibold">
                  Logs da Automação
                </h2>
                <button
                  onClick={() => { setShowLogs(null); setLogs([]); }}
                  className="text-stone hover:text-cream transition-colors"
                >
                  <X size={18} />
                </button>
              </div>
              <div className="p-5">
                {logsLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="animate-spin text-gold" size={24} />
                  </div>
                ) : logs.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <List size={32} className="text-surface-03 mb-2" />
                    <p className="text-stone text-sm">Nenhum log registrado ainda.</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {logs.map((log) => {
                      const cfg = LOG_STATUS_CONFIG[log.status] ?? {
                        label: log.status, className: "bg-surface-03 text-stone", icon: List,
                      };
                      const Icon = cfg.icon;
                      return (
                        <div
                          key={log.id}
                          className="flex items-center gap-3 p-3 rounded-xl bg-surface-03/40 flex-wrap"
                        >
                          <span
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium shrink-0 ${cfg.className}`}
                          >
                            <Icon size={11} /> {cfg.label}
                          </span>
                          <span className="text-xs text-stone">
                            Canal: <span className="text-cream">{CHANNEL_LABELS[log.channel] ?? log.channel}</span>
                          </span>
                          {log.customer_id && (
                            <span className="text-xs text-stone">
                              Cliente: <span className="text-cream font-mono">{log.customer_id}</span>
                            </span>
                          )}
                          <span className="text-xs text-stone ml-auto whitespace-nowrap">
                            {fmtDate(log.created_at)}
                          </span>
                          {log.error && (
                            <span
                              className="w-full text-xs text-red-400 mt-1 truncate"
                              title={log.error}
                            >
                              Erro: {log.error}
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
