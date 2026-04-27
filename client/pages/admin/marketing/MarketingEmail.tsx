import { useEffect, useState } from "react";
import {
  Loader2, Plus, Pencil, Trash2, X, Mail, Send, CheckCircle,
  XCircle, Clock, AlertCircle,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const unwrap = (json: any) => json?.data ?? json;

interface EmailTemplate {
  id: string;
  name: string;
  subject: string;
  body_html: string;
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

type Tab = "templates" | "messages";

const STATUS_CONFIG: Record<string, { label: string; className: string; icon: React.ElementType }> = {
  sent: { label: "Enviado", className: "bg-green-500/20 text-green-400", icon: CheckCircle },
  delivered: { label: "Entregue", className: "bg-emerald-500/20 text-emerald-400", icon: CheckCircle },
  failed: { label: "Falhou", className: "bg-red-500/20 text-red-400", icon: XCircle },
  pending: { label: "Pendente", className: "bg-yellow-500/20 text-yellow-400", icon: Clock },
};

function stripTags(html: string) {
  return html.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

function fmtDate(s: string) {
  if (!s) return "—";
  return new Date(s).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

const emptyForm = () => ({ name: "", subject: "", body_html: "" });
const emptySendForm = () => ({ template_id: "", customer_ids: "" });

export default function MarketingEmail() {
  const [tab, setTab] = useState<Tab>("templates");
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [messages, setMessages] = useState<EmailMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [showSendModal, setShowSendModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm());
  const [saving, setSaving] = useState(false);

  const [sendForm, setSendForm] = useState(emptySendForm());
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState<{ sent: number; failed: number } | null>(null);

  const token = localStorage.getItem("admin_token");
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const fetchTemplates = () => {
    setLoading(true);
    setError("");
    fetch(`${BASE}/email/templates`, { headers })
      .then((r) => { if (!r.ok) throw new Error("Falha ao carregar templates."); return r.json(); })
      .then(unwrap)
      .then(setTemplates)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  const fetchMessages = () => {
    setLoading(true);
    setError("");
    fetch(`${BASE}/email/messages`, { headers })
      .then((r) => { if (!r.ok) throw new Error("Falha ao carregar mensagens."); return r.json(); })
      .then(unwrap)
      .then(setMessages)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (tab === "templates") fetchTemplates();
    else fetchMessages();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const openCreate = () => {
    setEditingId(null);
    setForm(emptyForm());
    setShowTemplateModal(true);
  };

  const openEdit = (t: EmailTemplate) => {
    setEditingId(t.id);
    setForm({ name: t.name, subject: t.subject, body_html: t.body_html });
    setShowTemplateModal(true);
  };

  const handleSaveTemplate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) { alert("Nome obrigatório."); return; }
    if (!form.subject.trim()) { alert("Assunto obrigatório."); return; }
    if (!form.body_html.trim()) { alert("Body HTML obrigatório."); return; }
    setSaving(true);
    try {
      if (editingId) {
        await fetch(`${BASE}/email/templates/${editingId}`, {
          method: "PATCH",
          headers,
          body: JSON.stringify(form),
        });
      } else {
        await fetch(`${BASE}/email/templates`, {
          method: "POST",
          headers,
          body: JSON.stringify(form),
        });
      }
      setShowTemplateModal(false);
      fetchTemplates();
    } catch {
      alert("Erro ao salvar template.");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteTemplate = async (id: string) => {
    if (!confirm("Excluir template?")) return;
    await fetch(`${BASE}/email/templates/${id}`, { method: "DELETE", headers });
    fetchTemplates();
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sendForm.template_id) { alert("Selecione um template."); return; }
    setSending(true);
    setSendResult(null);
    try {
      const customer_ids = sendForm.customer_ids.split(",").map((s) => s.trim()).filter(Boolean);
      const r = await fetch(`${BASE}/email/send`, {
        method: "POST",
        headers,
        body: JSON.stringify({ template_id: sendForm.template_id, customer_ids }),
      });
      const json = await r.json();
      const data = unwrap(json);
      setSendResult({ sent: data.sent ?? 0, failed: data.failed ?? 0 });
    } catch {
      alert("Erro ao enviar e-mail.");
    } finally {
      setSending(false);
    }
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
            <h1 className="text-2xl font-bold text-cream">E-mail Marketing</h1>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex bg-surface-02 rounded-xl border border-surface-03 overflow-hidden w-fit">
          {(["templates", "messages"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-5 py-2 text-sm font-medium transition-colors ${
                tab === t ? "bg-gold text-black" : "text-stone hover:text-cream"
              }`}
            >
              {t === "templates" ? "Templates" : "Mensagens Enviadas"}
            </button>
          ))}
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

        {/* TAB: Templates */}
        {!loading && tab === "templates" && (
          <>
            <div className="flex items-center justify-between">
              <p className="text-stone text-sm">{templates.length} template{templates.length !== 1 ? "s" : ""}</p>
              <button
                onClick={openCreate}
                className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-black font-semibold px-4 py-2 rounded-xl text-sm transition-colors"
              >
                <Plus size={16} /> Novo Template
              </button>
            </div>

            {templates.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 bg-surface-02 border border-surface-03 rounded-2xl">
                <Mail size={40} className="text-surface-03 mb-3" />
                <p className="text-stone text-sm">Nenhum template cadastrado.</p>
                <button onClick={openCreate} className="mt-3 text-gold text-sm hover:underline">
                  Criar primeiro template
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {templates.map((t) => (
                  <div key={t.id} className="bg-surface-02 border border-surface-03 rounded-2xl p-4 space-y-3 flex flex-col">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <h3 className="text-cream font-semibold text-sm truncate">{t.name}</h3>
                        <p className="text-xs text-gold mt-0.5 truncate">{t.subject}</p>
                      </div>
                      <span
                        className={`shrink-0 px-2 py-0.5 rounded-full text-xs font-medium ${
                          t.active ? "bg-green-500/20 text-green-400" : "bg-surface-03 text-stone"
                        }`}
                      >
                        {t.active ? "Ativo" : "Inativo"}
                      </span>
                    </div>
                    <p className="text-stone text-xs leading-relaxed line-clamp-3 flex-1">
                      {stripTags(t.body_html).slice(0, 150)}{stripTags(t.body_html).length > 150 ? "..." : ""}
                    </p>
                    <div className="flex items-center justify-between pt-1">
                      <span className="text-xs text-stone">{fmtDate(t.created_at)}</span>
                      <div className="flex gap-1">
                        <button
                          onClick={() => openEdit(t)}
                          className="p-1.5 rounded-lg hover:bg-surface-03 text-stone hover:text-cream transition-colors"
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          onClick={() => handleDeleteTemplate(t.id)}
                          className="p-1.5 rounded-lg hover:bg-red-500/10 text-stone hover:text-red-400 transition-colors"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* TAB: Mensagens Enviadas */}
        {!loading && tab === "messages" && (
          <>
            <div className="flex items-center justify-between">
              <p className="text-stone text-sm">{messages.length} mensagem{messages.length !== 1 ? "s" : ""}</p>
              <button
                onClick={() => { setSendResult(null); setSendForm(emptySendForm()); setShowSendModal(true); }}
                className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-black font-semibold px-4 py-2 rounded-xl text-sm transition-colors"
              >
                <Send size={16} /> Enviar E-mail
              </button>
            </div>

            <div className="bg-surface-02 border border-surface-03 rounded-2xl overflow-hidden">
              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <Mail size={40} className="text-surface-03 mb-3" />
                  <p className="text-stone text-sm">Nenhum e-mail enviado ainda.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-stone text-xs border-b border-surface-03 bg-surface-03/30">
                        <th className="text-left p-3">Cliente</th>
                        <th className="text-left p-3">E-mail</th>
                        <th className="text-left p-3">Template</th>
                        <th className="text-left p-3">Assunto</th>
                        <th className="text-left p-3">Status</th>
                        <th className="text-left p-3">Data/Hora</th>
                        <th className="text-left p-3">Erro</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-03">
                      {messages.map((m) => {
                        const statusCfg = STATUS_CONFIG[m.status] ?? {
                          label: m.status, className: "bg-surface-03 text-stone", icon: Clock,
                        };
                        const Icon = statusCfg.icon;
                        return (
                          <tr key={m.id} className="hover:bg-surface-03/30 transition-colors">
                            <td className="p-3 text-cream font-medium">{m.customer_name ?? "—"}</td>
                            <td className="p-3 text-stone text-xs">{m.to_email}</td>
                            <td className="p-3 text-stone">{m.template_name ?? "—"}</td>
                            <td className="p-3 text-stone text-xs max-w-[180px] truncate" title={m.subject_sent}>
                              {m.subject_sent}
                            </td>
                            <td className="p-3">
                              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${statusCfg.className}`}>
                                <Icon size={11} /> {statusCfg.label}
                              </span>
                            </td>
                            <td className="p-3 text-stone text-xs whitespace-nowrap">{fmtDate(m.sent_at)}</td>
                            <td className="p-3 text-red-400 text-xs max-w-[180px] truncate" title={m.error}>
                              {m.error ?? "—"}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}

        {/* Modal: Criar/Editar Template */}
        {showTemplateModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
            <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between p-5 border-b border-surface-03">
                <h2 className="text-cream font-semibold">
                  {editingId ? "Editar Template" : "Novo Template de E-mail"}
                </h2>
                <button onClick={() => setShowTemplateModal(false)} className="text-stone hover:text-cream transition-colors">
                  <X size={18} />
                </button>
              </div>
              <form onSubmit={handleSaveTemplate} className="p-5 space-y-4">
                <div className="space-y-1">
                  <label className="text-xs text-stone">Nome do Template *</label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder="Ex: Boas-vindas ao cliente"
                    className={inputClass}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs text-stone">Assunto *</label>
                  <input
                    type="text"
                    value={form.subject}
                    onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))}
                    placeholder="Ex: Bem-vindo(a) à Moschettieri!"
                    className={inputClass}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs text-stone">Body HTML *</label>
                  <textarea
                    value={form.body_html}
                    onChange={(e) => setForm((f) => ({ ...f, body_html: e.target.value }))}
                    rows={10}
                    placeholder={"<h1>Olá!</h1><p>Seu pedido foi confirmado.</p>"}
                    className={`${inputClass} resize-y font-mono text-xs`}
                  />
                </div>

                {form.body_html.trim() && (
                  <div className="space-y-1">
                    <label className="text-xs text-stone">Preview</label>
                    <div
                      className="w-full bg-white rounded-xl p-4 text-sm text-black min-h-[80px] max-h-[300px] overflow-y-auto"
                      dangerouslySetInnerHTML={{ __html: form.body_html }}
                    />
                  </div>
                )}

                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowTemplateModal(false)}
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

        {/* Modal: Enviar E-mail */}
        {showSendModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
            <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-md max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between p-5 border-b border-surface-03">
                <h2 className="text-cream font-semibold">Enviar E-mail Marketing</h2>
                <button onClick={() => setShowSendModal(false)} className="text-stone hover:text-cream transition-colors">
                  <X size={18} />
                </button>
              </div>
              <form onSubmit={handleSend} className="p-5 space-y-4">
                <div className="space-y-1">
                  <label className="text-xs text-stone">Template *</label>
                  <select
                    value={sendForm.template_id}
                    onChange={(e) => setSendForm((f) => ({ ...f, template_id: e.target.value }))}
                    className={inputClass}
                  >
                    <option value="">Selecione um template...</option>
                    {templates.map((t) => (
                      <option key={t.id} value={t.id}>{t.name} — {t.subject}</option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-xs text-stone">IDs dos Clientes</label>
                  <textarea
                    value={sendForm.customer_ids}
                    onChange={(e) => setSendForm((f) => ({ ...f, customer_ids: e.target.value }))}
                    rows={3}
                    placeholder="123, 456, 789"
                    className={`${inputClass} resize-none`}
                  />
                  <p className="text-xs text-stone/60">Separe os IDs por vírgula</p>
                </div>

                <div className="rounded-xl bg-blue-500/10 border border-blue-500/20 p-3 flex items-start gap-2">
                  <Mail size={14} className="text-blue-400 mt-0.5 shrink-0" />
                  <p className="text-xs text-blue-300">
                    Apenas clientes com e-mail cadastrado receberão esta mensagem.
                  </p>
                </div>

                {sendResult && (
                  <div className="rounded-xl bg-surface-03 p-4 flex items-center justify-around">
                    <div className="text-center">
                      <p className="text-2xl font-bold text-green-400">{sendResult.sent}</p>
                      <p className="text-xs text-stone mt-0.5">Enviados</p>
                    </div>
                    <div className="w-px h-8 bg-surface-03" />
                    <div className="text-center">
                      <p className="text-2xl font-bold text-red-400">{sendResult.failed}</p>
                      <p className="text-xs text-stone mt-0.5">Falhas</p>
                    </div>
                  </div>
                )}

                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowSendModal(false)}
                    className="flex-1 py-2 rounded-xl border border-surface-03 text-stone hover:text-cream text-sm transition-colors"
                  >
                    Fechar
                  </button>
                  <button
                    type="submit"
                    disabled={sending}
                    className="flex-1 py-2 rounded-xl bg-gold hover:bg-gold/90 text-black font-semibold text-sm transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
                  >
                    {sending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                    {sending ? "Enviando..." : "Enviar"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
