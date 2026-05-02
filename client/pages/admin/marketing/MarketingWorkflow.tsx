import { useEffect, useState } from "react";
import {
  Loader2, Plus, X, CheckCircle2, XCircle, Clock, AlertCircle,
  MessageCircle, Mail, MousePointerClick, Eye, ChevronDown, ChevronUp,
  RefreshCw, Send, User,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const unwrap = (json: any) => json?.data ?? json;

type WorkflowStatus =
  | "draft"
  | "pending_approval"
  | "adjustment_requested"
  | "approved"
  | "rejected"
  | "scheduled"
  | "running"
  | "finished"
  | "cancelled";

type CampaignType = "whatsapp" | "email" | "paid_traffic";

interface WorkflowComment {
  id: string;
  author: string;
  body: string;
  created_at: string;
}

interface WorkflowApproval {
  id: string;
  name: string;
  campaign_type: CampaignType;
  status: WorkflowStatus;
  audience_description?: string;
  template_preview?: string;
  scheduled_at?: string;
  budget?: number;
  created_by: string;
  approved_by?: string;
  approved_at?: string;
  comments: WorkflowComment[];
  created_at: string;
}

const STATUS_CONFIG: Record<WorkflowStatus, { label: string; className: string; icon: React.ElementType }> = {
  draft:               { label: "Rascunho",             className: "bg-surface-03 text-stone",           icon: Clock },
  pending_approval:    { label: "Aguard. Aprovação",    className: "bg-yellow-500/20 text-yellow-400",   icon: Clock },
  adjustment_requested:{ label: "Ajustes Solicitados",  className: "bg-orange-500/20 text-orange-400",   icon: AlertCircle },
  approved:            { label: "Aprovado",             className: "bg-green-500/20 text-green-400",     icon: CheckCircle2 },
  rejected:            { label: "Reprovado",            className: "bg-red-500/20 text-red-400",         icon: XCircle },
  scheduled:           { label: "Agendado",             className: "bg-blue-500/20 text-blue-400",       icon: Clock },
  running:             { label: "Em Execução",          className: "bg-purple-500/20 text-purple-400",   icon: Send },
  finished:            { label: "Finalizado",           className: "bg-emerald-500/20 text-emerald-400", icon: CheckCircle2 },
  cancelled:           { label: "Cancelado",            className: "bg-surface-03 text-stone",           icon: XCircle },
};

const CAMPAIGN_TYPE_CONFIG: Record<CampaignType, { label: string; icon: React.ElementType; color: string }> = {
  whatsapp:     { label: "WhatsApp",     icon: MessageCircle,    color: "text-green-400" },
  email:        { label: "E-mail",       icon: Mail,             color: "text-blue-400" },
  paid_traffic: { label: "Tráfego Pago", icon: MousePointerClick, color: "text-purple-400" },
};

const STATUS_ORDER: WorkflowStatus[] = [
  "draft", "pending_approval", "adjustment_requested",
  "approved", "rejected", "scheduled", "running", "finished", "cancelled",
];

const emptyForm = () => ({
  name: "",
  campaign_type: "whatsapp" as CampaignType,
  audience_description: "",
  template_preview: "",
  scheduled_at: "",
  budget: "",
});

function fmtDate(s: string) {
  if (!s) return "—";
  return new Date(s).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function fmtCurrency(v: number) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default function MarketingWorkflow() {
  const [items, setItems] = useState<WorkflowApproval[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState<WorkflowStatus | "all">("all");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState(emptyForm());
  const [saving, setSaving] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [commentInputs, setCommentInputs] = useState<Record<string, string>>({});

  const token = localStorage.getItem("admin_token");
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const fetchItems = () => {
    setLoading(true);
    setError("");
    fetch(`${BASE}/marketing/workflows`, { headers })
      .then((r) => { if (!r.ok) throw new Error("Falha ao carregar solicitações."); return r.json(); })
      .then(unwrap)
      .then((data) => setItems(Array.isArray(data) ? data : []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchItems(); }, []);

  const filtered = statusFilter === "all"
    ? items
    : items.filter((i) => i.status === statusFilter);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) { alert("Nome obrigatório."); return; }
    setSaving(true);
    try {
      const res = await fetch(`${BASE}/marketing/workflows`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          ...form,
          budget: form.budget ? parseFloat(form.budget) : null,
          status: "draft",
        }),
      });
      if (!res.ok) throw new Error("Erro ao criar.");
      const created = unwrap(await res.json());
      setItems((prev) => [created, ...prev]);
      setShowModal(false);
      setForm(emptyForm());
    } catch {
      alert("Erro ao criar solicitação.");
    } finally {
      setSaving(false);
    }
  };

  const performAction = async (
    id: string,
    action: "submit" | "approve" | "reject" | "request_adjustments" | "cancel",
    comment?: string,
  ) => {
    setActionLoading(`${id}-${action}`);
    try {
      const res = await fetch(`${BASE}/marketing/workflows/${id}/${action}`, {
        method: "POST",
        headers,
        body: comment ? JSON.stringify({ comment }) : undefined,
      });
      if (!res.ok) throw new Error("Erro ao executar ação.");
      const updated = unwrap(await res.json());
      setItems((prev) => prev.map((item) => (item.id === id ? updated : item)));
    } catch {
      alert("Erro ao executar ação.");
    } finally {
      setActionLoading(null);
    }
  };

  const addComment = async (id: string) => {
    const body = commentInputs[id]?.trim();
    if (!body) return;
    setActionLoading(`${id}-comment`);
    try {
      const res = await fetch(`${BASE}/marketing/workflows/${id}/comments`, {
        method: "POST",
        headers,
        body: JSON.stringify({ body }),
      });
      if (!res.ok) throw new Error();
      const updated = unwrap(await res.json());
      setItems((prev) => prev.map((item) => (item.id === id ? updated : item)));
      setCommentInputs((prev) => ({ ...prev, [id]: "" }));
    } catch {
      alert("Erro ao adicionar comentário.");
    } finally {
      setActionLoading(null);
    }
  };

  const inputCls = "w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold";

  const statusCounts = STATUS_ORDER.reduce((acc, s) => {
    acc[s] = items.filter((i) => i.status === s).length;
    return acc;
  }, {} as Record<WorkflowStatus, number>);

  return (
    <div className="flex flex-col md:flex-row min-h-screen md:h-screen bg-surface-00 overflow-hidden">
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto p-6 space-y-6">

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-gold mb-1">Marketing</p>
            <h1 className="text-2xl font-bold text-cream">Workflow de Aprovação</h1>
            <p className="text-stone text-sm mt-1">Solicite aprovação antes de disparar campanhas</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchItems}
              className="p-2 rounded-xl bg-surface-02 border border-surface-03 text-stone hover:text-cream transition-colors"
            >
              <RefreshCw size={16} />
            </button>
            <button
              onClick={() => setShowModal(true)}
              className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-black font-semibold px-4 py-2 rounded-xl text-sm transition-colors"
            >
              <Plus size={16} /> Nova Solicitação
            </button>
            <AdminTopActions />
          </div>
        </div>

        {/* Status summary pills */}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setStatusFilter("all")}
            className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition-colors ${
              statusFilter === "all"
                ? "bg-gold text-black border-gold"
                : "bg-surface-02 border-surface-03 text-stone hover:text-cream"
            }`}
          >
            Todas ({items.length})
          </button>
          {(["pending_approval", "adjustment_requested", "approved", "rejected"] as WorkflowStatus[]).map((s) => {
            const cfg = STATUS_CONFIG[s];
            const count = statusCounts[s] ?? 0;
            if (count === 0 && statusFilter !== s) return null;
            return (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium border transition-colors ${
                  statusFilter === s
                    ? "bg-gold text-black border-gold"
                    : `bg-surface-02 border-surface-03 ${cfg.className.split(" ")[1]}`
                }`}
              >
                <cfg.icon size={12} />
                {cfg.label} ({count})
              </button>
            );
          })}
        </div>

        {loading && (
          <div className="flex items-center justify-center h-48">
            <Loader2 className="animate-spin text-gold" size={28} />
          </div>
        )}

        {error && !loading && (
          <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 text-red-400 text-sm">
            {error}
          </div>
        )}

        {!loading && !error && filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 bg-surface-02 border border-surface-03 rounded-2xl text-center">
            <CheckCircle2 size={40} className="text-surface-03 mb-3" />
            <p className="text-stone text-sm">Nenhuma solicitação encontrada.</p>
            <button
              onClick={() => setShowModal(true)}
              className="mt-4 text-gold text-sm hover:underline"
            >
              Criar primeira solicitação
            </button>
          </div>
        )}

        {!loading && !error && (
          <div className="space-y-3">
            {filtered.map((item) => {
              const statusCfg = STATUS_CONFIG[item.status];
              const typeCfg = CAMPAIGN_TYPE_CONFIG[item.campaign_type];
              const isExpanded = expanded === item.id;
              const TypeIcon = typeCfg.icon;
              const StatusIcon = statusCfg.icon;

              return (
                <div
                  key={item.id}
                  className="bg-surface-02 border border-surface-03 rounded-2xl overflow-hidden"
                >
                  {/* Card header */}
                  <div className="p-5">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex items-start gap-3 min-w-0">
                        <div className="w-10 h-10 rounded-xl bg-surface-03 flex items-center justify-center flex-shrink-0">
                          <TypeIcon size={18} className={typeCfg.color} />
                        </div>
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2 mb-1">
                            <h3 className="text-cream font-semibold text-sm">{item.name}</h3>
                            <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${statusCfg.className}`}>
                              <StatusIcon size={10} />
                              {statusCfg.label}
                            </span>
                            <span className="text-xs text-stone bg-surface-03 px-2 py-0.5 rounded-full">
                              {typeCfg.label}
                            </span>
                          </div>
                          <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-stone">
                            <span className="flex items-center gap-1"><User size={10} /> {item.created_by}</span>
                            <span>{fmtDate(item.created_at)}</span>
                            {item.scheduled_at && (
                              <span className="flex items-center gap-1">
                                <Clock size={10} /> Agendado: {fmtDate(item.scheduled_at)}
                              </span>
                            )}
                            {item.budget && item.budget > 0 && (
                              <span>Orçamento: {fmtCurrency(item.budget)}</span>
                            )}
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={() => setExpanded(isExpanded ? null : item.id)}
                        className="flex-shrink-0 p-2 rounded-xl hover:bg-surface-03 text-stone hover:text-cream transition-colors"
                      >
                        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </button>
                    </div>

                    {/* Action buttons */}
                    <div className="flex flex-wrap gap-2 mt-4">
                      {item.status === "draft" && (
                        <button
                          onClick={() => performAction(item.id, "submit")}
                          disabled={!!actionLoading}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gold hover:bg-gold/90 text-black text-xs font-semibold transition-colors disabled:opacity-60"
                        >
                          {actionLoading === `${item.id}-submit` && <Loader2 size={12} className="animate-spin" />}
                          Enviar para Aprovação
                        </button>
                      )}
                      {item.status === "pending_approval" && (
                        <>
                          <button
                            onClick={() => performAction(item.id, "approve")}
                            disabled={!!actionLoading}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-green-600 hover:bg-green-500 text-white text-xs font-semibold transition-colors disabled:opacity-60"
                          >
                            {actionLoading === `${item.id}-approve` && <Loader2 size={12} className="animate-spin" />}
                            <CheckCircle2 size={12} /> Aprovar
                          </button>
                          <button
                            onClick={() => performAction(item.id, "request_adjustments")}
                            disabled={!!actionLoading}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-orange-600 hover:bg-orange-500 text-white text-xs font-semibold transition-colors disabled:opacity-60"
                          >
                            {actionLoading === `${item.id}-request_adjustments` && <Loader2 size={12} className="animate-spin" />}
                            <AlertCircle size={12} /> Solicitar Ajustes
                          </button>
                          <button
                            onClick={() => performAction(item.id, "reject")}
                            disabled={!!actionLoading}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-red-600 hover:bg-red-500 text-white text-xs font-semibold transition-colors disabled:opacity-60"
                          >
                            {actionLoading === `${item.id}-reject` && <Loader2 size={12} className="animate-spin" />}
                            <XCircle size={12} /> Reprovar
                          </button>
                        </>
                      )}
                      {["draft", "pending_approval", "adjustment_requested"].includes(item.status) && (
                        <button
                          onClick={() => performAction(item.id, "cancel")}
                          disabled={!!actionLoading}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-surface-03 text-stone hover:text-cream text-xs transition-colors disabled:opacity-60"
                        >
                          Cancelar
                        </button>
                      )}
                      {item.approved_by && (
                        <span className="flex items-center gap-1 text-xs text-green-400">
                          <CheckCircle2 size={12} /> Aprovado por {item.approved_by} em {fmtDate(item.approved_at ?? "")}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Expanded details */}
                  {isExpanded && (
                    <div className="border-t border-surface-03 p-5 space-y-4 bg-surface-03/10">
                      {item.audience_description && (
                        <div>
                          <p className="text-xs text-stone mb-1 font-medium">Público-alvo</p>
                          <p className="text-sm text-cream bg-surface-03 rounded-xl px-3 py-2">{item.audience_description}</p>
                        </div>
                      )}
                      {item.template_preview && (
                        <div>
                          <p className="text-xs text-stone mb-1 font-medium">Prévia da Mensagem</p>
                          <div className="bg-surface-03 rounded-xl px-4 py-3 text-sm text-cream whitespace-pre-wrap font-mono leading-relaxed">
                            {item.template_preview}
                          </div>
                        </div>
                      )}

                      {/* Comments */}
                      <div>
                        <p className="text-xs text-stone mb-2 font-medium">
                          Comentários ({item.comments?.length ?? 0})
                        </p>
                        <div className="space-y-2 mb-3">
                          {(item.comments ?? []).map((c) => (
                            <div key={c.id} className="bg-surface-03 rounded-xl px-3 py-2">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-xs font-semibold text-cream">{c.author}</span>
                                <span className="text-[10px] text-stone">{fmtDate(c.created_at)}</span>
                              </div>
                              <p className="text-xs text-stone">{c.body}</p>
                            </div>
                          ))}
                          {(!item.comments || item.comments.length === 0) && (
                            <p className="text-xs text-stone/60 italic">Nenhum comentário ainda.</p>
                          )}
                        </div>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={commentInputs[item.id] ?? ""}
                            onChange={(e) => setCommentInputs((prev) => ({ ...prev, [item.id]: e.target.value }))}
                            onKeyDown={(e) => e.key === "Enter" && addComment(item.id)}
                            placeholder="Adicionar comentário..."
                            className="flex-1 bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-cream text-xs focus:outline-none focus:border-gold"
                          />
                          <button
                            onClick={() => addComment(item.id)}
                            disabled={actionLoading === `${item.id}-comment`}
                            className="px-3 py-2 rounded-xl bg-gold hover:bg-gold/90 text-black text-xs font-semibold transition-colors disabled:opacity-60"
                          >
                            {actionLoading === `${item.id}-comment`
                              ? <Loader2 size={12} className="animate-spin" />
                              : <Eye size={12} />}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Create modal */}
        {showModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
            <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between p-5 border-b border-surface-03">
                <h2 className="text-cream font-semibold">Nova Solicitação de Aprovação</h2>
                <button onClick={() => setShowModal(false)} className="text-stone hover:text-cream">
                  <X size={18} />
                </button>
              </div>
              <form onSubmit={handleCreate} className="p-5 space-y-4">
                <div className="space-y-1">
                  <label className="text-xs text-stone">Nome da Campanha *</label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder="Ex: Campanha Aniversário Maio"
                    className={inputCls}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs text-stone">Tipo de Campanha</label>
                  <select
                    value={form.campaign_type}
                    onChange={(e) => setForm((f) => ({ ...f, campaign_type: e.target.value as CampaignType }))}
                    className={inputCls}
                  >
                    <option value="whatsapp">WhatsApp</option>
                    <option value="email">E-mail</option>
                    <option value="paid_traffic">Tráfego Pago</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-xs text-stone">Público-alvo</label>
                  <textarea
                    value={form.audience_description}
                    onChange={(e) => setForm((f) => ({ ...f, audience_description: e.target.value }))}
                    rows={2}
                    placeholder="Ex: Clientes que não pedem há 30 dias, grupo VIP..."
                    className={`${inputCls} resize-none`}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs text-stone">Prévia da Mensagem / Template</label>
                  <textarea
                    value={form.template_preview}
                    onChange={(e) => setForm((f) => ({ ...f, template_preview: e.target.value }))}
                    rows={4}
                    placeholder="Cole aqui o texto da mensagem ou descrição do anúncio..."
                    className={`${inputCls} resize-none font-mono text-xs`}
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs text-stone">Data de Disparo</label>
                    <input
                      type="datetime-local"
                      value={form.scheduled_at}
                      onChange={(e) => setForm((f) => ({ ...f, scheduled_at: e.target.value }))}
                      className={inputCls}
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-stone">Orçamento (R$)</label>
                    <input
                      type="number"
                      min={0}
                      step={0.01}
                      value={form.budget}
                      onChange={(e) => setForm((f) => ({ ...f, budget: e.target.value }))}
                      placeholder="0,00"
                      className={inputCls}
                    />
                  </div>
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
                    Criar como Rascunho
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
