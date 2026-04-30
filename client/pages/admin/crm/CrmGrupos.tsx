import { useEffect, useState } from "react";
import { Loader2, Plus, Trash2, Pencil, X, FolderOpen, PlusCircle, MinusCircle, PlayCircle } from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const unwrap = (json: any) => json?.data ?? json;

type GroupType = "manual" | "dynamic";

interface DynamicRule {
  field: string;
  operator: string;
  value: string;
}

interface Group {
  id: string;
  name: string;
  group_type: GroupType;
  color: string;
  icon: string;
  description?: string;
  member_count: number;
  rules?: DynamicRule[];
}

const emptyForm = (): Partial<Group> => ({
  name: "",
  group_type: "manual",
  color: "#f97316",
  icon: "👥",
  description: "",
  rules: [],
});

const COLORS = [
  "#f97316", "#ef4444", "#8b5cf6", "#3b82f6",
  "#10b981", "#f59e0b", "#ec4899", "#06b6d4",
];

const FIELD_OPTIONS = [
  // Comportamento de pedidos
  { value: "last_order_days",   label: "Dias desde último pedido" },
  { value: "total_orders",      label: "Total de pedidos" },
  { value: "total_spent",       label: "Total gasto (R$)" },
  { value: "avg_ticket",        label: "Ticket médio (R$)" },
  { value: "days_without_order",label: "Dias sem pedido" },
  // Localização
  { value: "city",              label: "Cidade" },
  { value: "neighborhood",      label: "Bairro" },
  // Fidelidade
  { value: "loyalty_points",    label: "Pontos de fidelidade" },
  { value: "loyalty_tier",      label: "Nível de fidelidade" },
  // Perfil
  { value: "birth_month",       label: "Mês de aniversário" },
  { value: "customer_status",   label: "Status do cliente (novo/recorrente/inativo/VIP)" },
  // Produto & histórico
  { value: "product_ordered",   label: "Produto já pedido (nome)" },
  { value: "category_ordered",  label: "Categoria já pedida" },
  // Cupons & campanhas
  { value: "coupon_used",       label: "Usou cupom (código)" },
  { value: "campaign_origin",   label: "Origem de campanha (UTM source)" },
  // Engajamento digital
  { value: "opened_email",      label: "Abriu email (template)" },
  { value: "clicked_email",     label: "Clicou em email" },
  { value: "responded_whatsapp",label: "Respondeu WhatsApp" },
  { value: "whatsapp_sent",     label: "Recebeu WhatsApp (contagem)" },
  // Financeiro
  { value: "has_unpaid_order",  label: "Tem pedido não pago" },
  { value: "payment_method",    label: "Método de pagamento preferido" },
];

const OPERATOR_OPTIONS = [
  { value: ">",        label: "maior que" },
  { value: "<",        label: "menor que" },
  { value: "=",        label: "igual a" },
  { value: "!=",       label: "diferente de" },
  { value: ">=",       label: "maior ou igual" },
  { value: "<=",       label: "menor ou igual" },
  { value: "contains", label: "contém" },
  { value: "in",       label: "está em (lista separada por vírgula)" },
];

export default function CrmGrupos() {
  const [groups, setGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<Partial<Group>>(emptyForm());
  const [saving, setSaving] = useState(false);

  const token = localStorage.getItem("admin_token");
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const fetchGroups = () => {
    setLoading(true);
    setError("");
    fetch(`${BASE}/crm/groups`, { headers })
      .then((r) => { if (!r.ok) throw new Error("Falha ao carregar grupos."); return r.json(); })
      .then(unwrap)
      .then(setGroups)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchGroups(); }, []);

  const openCreate = () => {
    setEditingId(null);
    setForm(emptyForm());
    setShowModal(true);
  };

  const openEdit = (g: Group) => {
    setEditingId(g.id);
    setForm({ ...g, rules: g.rules ? [...g.rules] : [] });
    setShowModal(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name?.trim()) { alert("Nome obrigatório."); return; }
    setSaving(true);
    try {
      const r = editingId
        ? await fetch(`${BASE}/crm/groups/${editingId}`, {
            method: "PATCH",
            headers,
            body: JSON.stringify(form),
          })
        : await fetch(`${BASE}/crm/groups`, {
            method: "POST",
            headers,
            body: JSON.stringify(form),
          });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        alert(err?.error?.message ?? "Erro ao salvar grupo.");
        return;
      }
      setShowModal(false);
      fetchGroups();
    } catch {
      alert("Erro ao salvar grupo.");
    } finally {
      setSaving(false);
    }
  };

  const handleEvaluate = async (id: string) => {
    const r = await fetch(`${BASE}/crm/groups/${id}/evaluate`, { method: "POST", headers });
    const json = await r.json().catch(() => ({}));
    const msg = json?.data?.message ?? (r.ok ? "Avaliação concluída." : "Erro ao avaliar.");
    alert(msg);
    fetchGroups();
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Excluir grupo?")) return;
    await fetch(`${BASE}/crm/groups/${id}`, { method: "DELETE", headers });
    fetchGroups();
  };

  const addRule = () => {
    setForm((f) => ({
      ...f,
      rules: [...(f.rules ?? []), { field: "last_order_days", operator: ">", value: "30" }],
    }));
  };

  const removeRule = (idx: number) => {
    setForm((f) => ({
      ...f,
      rules: (f.rules ?? []).filter((_, i) => i !== idx),
    }));
  };

  const updateRule = (idx: number, key: keyof DynamicRule, val: string) => {
    setForm((f) => ({
      ...f,
      rules: (f.rules ?? []).map((r, i) => (i === idx ? { ...r, [key]: val } : r)),
    }));
  };

  const inputCls = "w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold";

  return (
    <div className="flex flex-col md:flex-row min-h-screen md:h-screen bg-surface-00 overflow-hidden">
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-gold mb-1">CRM</p>
            <h1 className="text-2xl font-bold text-cream">Grupos & Segmentações</h1>
          </div>
          <button
            onClick={openCreate}
            className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-black font-semibold px-4 py-2 rounded-xl text-sm transition-colors"
          >
            <Plus size={16} /> Novo Grupo
          </button>
        </div>

        {loading && (
          <div className="flex items-center justify-center h-48">
            <Loader2 className="animate-spin text-gold" size={28} />
          </div>
        )}
        {error && !loading && (
          <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 text-red-400 text-sm">{error}</div>
        )}

        {!loading && !error && (
          <>
            {groups.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-center bg-surface-02 border border-surface-03 rounded-2xl">
                <FolderOpen size={40} className="text-surface-03 mb-3" />
                <p className="text-stone text-sm">Nenhum grupo criado ainda.</p>
                <button onClick={openCreate} className="mt-4 text-gold text-sm hover:underline">
                  Criar primeiro grupo
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {groups.map((g) => (
                  <div
                    key={g.id}
                    className="bg-surface-02 border border-surface-03 rounded-2xl p-4 space-y-3"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-3">
                        <span
                          className="w-10 h-10 rounded-xl flex items-center justify-center text-xl shrink-0"
                          style={{ backgroundColor: `${g.color}20` }}
                        >
                          {g.icon}
                        </span>
                        <div>
                          <p className="text-cream font-semibold text-sm">{g.name}</p>
                          <span
                            className={`text-xs px-2 py-0.5 rounded-full ${
                              g.group_type === "dynamic"
                                ? "bg-purple-500/20 text-purple-400"
                                : "bg-surface-03 text-stone"
                            }`}
                          >
                            {g.group_type === "dynamic" ? "Dinâmico" : "Manual"}
                          </span>
                        </div>
                      </div>
                      <div className="flex gap-1 shrink-0">
                        {g.group_type === "dynamic" && (
                          <button
                            onClick={() => handleEvaluate(g.id)}
                            className="p-1.5 rounded-lg hover:bg-purple-500/10 text-stone hover:text-purple-400 transition-colors"
                            title="Avaliar regras e atualizar membros"
                          >
                            <PlayCircle size={13} />
                          </button>
                        )}
                        <button
                          onClick={() => openEdit(g)}
                          className="p-1.5 rounded-lg hover:bg-surface-03 text-stone hover:text-cream transition-colors"
                        >
                          <Pencil size={13} />
                        </button>
                        <button
                          onClick={() => handleDelete(g.id)}
                          className="p-1.5 rounded-lg hover:bg-red-500/10 text-stone hover:text-red-400 transition-colors"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>
                    {g.description && <p className="text-stone text-xs leading-relaxed">{g.description}</p>}
                    <div className="flex items-center justify-between text-xs border-t border-surface-03 pt-3">
                      <span className="text-stone">{g.member_count} membros</span>
                      <div className="w-3 h-3 rounded-full" style={{ backgroundColor: g.color }} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* Modal */}
        {showModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
            <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between p-5 border-b border-surface-03">
                <h2 className="text-cream font-semibold">
                  {editingId ? "Editar Grupo" : "Novo Grupo"}
                </h2>
                <button onClick={() => setShowModal(false)} className="text-stone hover:text-cream">
                  <X size={18} />
                </button>
              </div>
              <form onSubmit={handleSave} className="p-5 space-y-4">
                <div className="space-y-1">
                  <label className="text-xs text-stone">Nome *</label>
                  <input
                    type="text"
                    value={form.name ?? ""}
                    onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder="Ex: Clientes VIP"
                    className={inputCls}
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs text-stone">Tipo</label>
                    <select
                      value={form.group_type ?? "manual"}
                      onChange={(e) => setForm((f) => ({ ...f, group_type: e.target.value as GroupType }))}
                      className={inputCls}
                    >
                      <option value="manual">Manual</option>
                      <option value="dynamic">Dinâmico</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-stone">Ícone (emoji)</label>
                    <input
                      type="text"
                      value={form.icon ?? "👥"}
                      onChange={(e) => setForm((f) => ({ ...f, icon: e.target.value }))}
                      placeholder="👥"
                      className={inputCls}
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-xs text-stone">Cor</label>
                  <div className="flex flex-wrap gap-2">
                    {COLORS.map((c) => (
                      <button
                        key={c}
                        type="button"
                        onClick={() => setForm((f) => ({ ...f, color: c }))}
                        className={`w-7 h-7 rounded-full transition-transform hover:scale-110 ${form.color === c ? "ring-2 ring-white ring-offset-2 ring-offset-surface-02 scale-110" : ""}`}
                        style={{ backgroundColor: c }}
                      />
                    ))}
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-xs text-stone">Descrição</label>
                  <textarea
                    value={form.description ?? ""}
                    onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                    rows={2}
                    className={`${inputCls} resize-none`}
                  />
                </div>

                {/* Dynamic rules */}
                {form.group_type === "dynamic" && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <label className="text-xs text-stone font-medium">Regras de Segmentação</label>
                      <button
                        type="button"
                        onClick={addRule}
                        className="flex items-center gap-1 text-xs text-gold hover:text-gold/80 transition-colors"
                      >
                        <PlusCircle size={14} /> Adicionar regra
                      </button>
                    </div>
                    {(form.rules ?? []).length === 0 && (
                      <p className="text-stone text-xs text-center py-3 border border-dashed border-surface-03 rounded-xl">
                        Nenhuma regra. Clique em "Adicionar regra".
                      </p>
                    )}
                    {(form.rules ?? []).map((rule, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <select
                          value={rule.field}
                          onChange={(e) => updateRule(idx, "field", e.target.value)}
                          className="flex-1 bg-surface-03 border border-surface-03 rounded-xl px-2 py-1.5 text-cream text-xs focus:outline-none focus:border-gold"
                        >
                          {FIELD_OPTIONS.map((o) => (
                            <option key={o.value} value={o.value}>{o.label}</option>
                          ))}
                        </select>
                        <select
                          value={rule.operator}
                          onChange={(e) => updateRule(idx, "operator", e.target.value)}
                          className="w-24 bg-surface-03 border border-surface-03 rounded-xl px-2 py-1.5 text-cream text-xs focus:outline-none focus:border-gold"
                        >
                          {OPERATOR_OPTIONS.map((o) => (
                            <option key={o.value} value={o.value}>{o.label}</option>
                          ))}
                        </select>
                        <input
                          type="text"
                          value={rule.value}
                          onChange={(e) => updateRule(idx, "value", e.target.value)}
                          placeholder="valor"
                          className="w-20 bg-surface-03 border border-surface-03 rounded-xl px-2 py-1.5 text-cream text-xs focus:outline-none focus:border-gold"
                        />
                        <button
                          type="button"
                          onClick={() => removeRule(idx)}
                          className="text-stone hover:text-red-400 transition-colors"
                        >
                          <MinusCircle size={16} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

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
      </main>
    </div>
  );
}
