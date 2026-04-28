import { useEffect, useState } from "react";
import {
  Loader2, Plus, CheckCircle2, Circle, X, ClipboardList,
  Phone, MessageCircle, Mail, FileText, Tag, RefreshCw,
  ShoppingCart, AlertTriangle, Gift, PackageCheck, UserCheck,
  Filter, ChevronDown,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const unwrap = (json: any) => json?.data ?? json;

type TaskStatus   = "pending" | "in_progress" | "completed" | "overdue" | "cancelled";
type TaskType     = "followup" | "call" | "send_whatsapp" | "send_email" | "proposal" |
                    "post_sale" | "recover_cart" | "resolve_complaint" | "send_coupon" |
                    "confirm_order" | "reactivate" | "return_customer";
type TaskPriority = "low" | "medium" | "high" | "urgent";

interface Task {
  id: string;
  title: string;
  task_type: TaskType;
  customer_name?: string;
  customer_id?: string;
  pipeline_card_id?: string;
  responsible?: string;
  due_date?: string;
  priority: TaskPriority;
  description?: string;
  status: TaskStatus;
  completed_at?: string;
}

const TYPE_CFG: Record<TaskType, { label: string; icon: React.ElementType; cls: string }> = {
  followup:         { label: "Follow-up",          icon: RefreshCw,     cls: "text-orange-400 bg-orange-500/10" },
  call:             { label: "Ligação",             icon: Phone,         cls: "text-blue-400 bg-blue-500/10" },
  send_whatsapp:    { label: "Enviar WhatsApp",     icon: MessageCircle, cls: "text-green-400 bg-green-500/10" },
  send_email:       { label: "Enviar Email",        icon: Mail,          cls: "text-cyan-400 bg-cyan-500/10" },
  proposal:         { label: "Proposta",            icon: FileText,      cls: "text-purple-400 bg-purple-500/10" },
  post_sale:        { label: "Pós-venda",           icon: PackageCheck,  cls: "text-emerald-400 bg-emerald-500/10" },
  recover_cart:     { label: "Recuperar Carrinho",  icon: ShoppingCart,  cls: "text-yellow-400 bg-yellow-500/10" },
  resolve_complaint:{ label: "Resolver Reclamação", icon: AlertTriangle, cls: "text-red-400 bg-red-500/10" },
  send_coupon:      { label: "Enviar Cupom",        icon: Tag,           cls: "text-gold bg-gold/10" },
  confirm_order:    { label: "Confirmar Pedido",    icon: CheckCircle2,  cls: "text-teal-400 bg-teal-500/10" },
  reactivate:       { label: "Reativar Cliente",    icon: UserCheck,     cls: "text-indigo-400 bg-indigo-500/10" },
  return_customer:  { label: "Retornar Cliente",    icon: Gift,          cls: "text-pink-400 bg-pink-500/10" },
};

const STATUS_CFG: Record<TaskStatus, { label: string; cls: string }> = {
  pending:     { label: "Pendente",        cls: "bg-yellow-500/20 text-yellow-400" },
  in_progress: { label: "Em Andamento",    cls: "bg-blue-500/20 text-blue-400" },
  completed:   { label: "Concluída",       cls: "bg-green-500/20 text-green-400" },
  overdue:     { label: "Atrasada",        cls: "bg-red-500/20 text-red-400" },
  cancelled:   { label: "Cancelada",       cls: "bg-surface-03 text-stone" },
};

const PRIORITY_CFG: Record<TaskPriority, { label: string; cls: string }> = {
  low:    { label: "Baixa",   cls: "bg-surface-03 text-stone" },
  medium: { label: "Média",   cls: "bg-yellow-500/20 text-yellow-400" },
  high:   { label: "Alta",    cls: "bg-orange-500/20 text-orange-400" },
  urgent: { label: "Urgente", cls: "bg-red-500/20 text-red-400" },
};

const emptyForm = (): Partial<Task> => ({
  title: "",
  task_type: "followup",
  customer_id: "",
  pipeline_card_id: "",
  responsible: "",
  due_date: "",
  priority: "medium",
  description: "",
});

const IC = "w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold";

export default function CrmTarefas() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState<TaskStatus | "all">("all");
  const [typeFilter, setTypeFilter] = useState<TaskType | "all">("all");
  const [priorityFilter, setPriorityFilter] = useState<TaskPriority | "all">("all");
  const [showFilters, setShowFilters] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<Partial<Task>>(emptyForm());
  const [saving, setSaving] = useState(false);
  const [transitioning, setTransitioning] = useState<string | null>(null);

  const token = localStorage.getItem("admin_token");
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const fetchTasks = () => {
    setLoading(true);
    setError("");
    fetch(`${BASE}/crm/tasks`, { headers })
      .then(r => { if (!r.ok) throw new Error("Falha ao carregar."); return r.json(); })
      .then(unwrap).then(setTasks)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchTasks(); }, []);

  const filtered = tasks.filter(t => {
    if (statusFilter !== "all" && t.status !== statusFilter) return false;
    if (typeFilter !== "all" && t.task_type !== typeFilter) return false;
    if (priorityFilter !== "all" && t.priority !== priorityFilter) return false;
    return true;
  });

  const counts = {
    all: tasks.length,
    pending: tasks.filter(t => t.status === "pending").length,
    in_progress: tasks.filter(t => t.status === "in_progress").length,
    overdue: tasks.filter(t => t.status === "overdue").length,
    completed: tasks.filter(t => t.status === "completed").length,
    cancelled: tasks.filter(t => t.status === "cancelled").length,
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title?.trim()) { alert("Título obrigatório."); return; }
    setSaving(true);
    try {
      if (editingId) {
        await fetch(`${BASE}/crm/tasks/${editingId}`, { method: "PATCH", headers, body: JSON.stringify(form) });
      } else {
        await fetch(`${BASE}/crm/tasks`, { method: "POST", headers, body: JSON.stringify({ ...form, status: "pending" }) });
      }
      setShowModal(false);
      fetchTasks();
    } catch { alert("Erro ao salvar tarefa."); } finally { setSaving(false); }
  };

  const setStatus = async (task: Task, newStatus: TaskStatus) => {
    setTransitioning(task.id);
    setTasks(prev => prev.map(t => t.id === task.id ? { ...t, status: newStatus } : t));
    try {
      await fetch(`${BASE}/crm/tasks/${task.id}`, { method: "PATCH", headers, body: JSON.stringify({ status: newStatus }) });
    } catch {
      setTasks(prev => prev.map(t => t.id === task.id ? { ...t, status: task.status } : t));
    } finally { setTransitioning(null); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Excluir tarefa?")) return;
    await fetch(`${BASE}/crm/tasks/${id}`, { method: "DELETE", headers });
    setTasks(prev => prev.filter(t => t.id !== id));
  };

  const openEdit = (t: Task) => {
    setEditingId(t.id);
    setForm({ ...t });
    setShowModal(true);
  };

  const openCreate = () => {
    setEditingId(null);
    setForm(emptyForm());
    setShowModal(true);
  };

  return (
    <div className="flex flex-col md:flex-row min-h-screen bg-surface-01">
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto p-6 space-y-6">

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-gold mb-1">CRM</p>
            <h1 className="text-2xl font-bold text-cream">Tarefas</h1>
          </div>
          <button onClick={openCreate}
            className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-black font-semibold px-4 py-2 rounded-xl text-sm transition-colors">
            <Plus size={16} /> Nova Tarefa
          </button>
        </div>

        {/* Status pills */}
        <div className="flex flex-wrap gap-2">
          {(Object.keys(counts) as Array<keyof typeof counts>).map(s => (
            <button key={s} onClick={() => setStatusFilter(s as TaskStatus | "all")}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors border ${
                statusFilter === s
                  ? s === "overdue" ? "bg-red-500/20 text-red-400 border-red-500/30"
                    : s === "all" ? "bg-gold text-black border-gold"
                    : "bg-surface-03 text-cream border-surface-03"
                  : "border-surface-03 text-stone hover:text-cream"
              }`}>
              {s === "all" ? "Todas" : STATUS_CFG[s as TaskStatus]?.label ?? s} ({counts[s]})
            </button>
          ))}

          <button onClick={() => setShowFilters(v => !v)}
            className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border border-surface-03 text-stone hover:text-cream transition-colors">
            <Filter size={12} /> Filtros <ChevronDown size={12} className={`transition-transform ${showFilters ? "rotate-180" : ""}`} />
          </button>
        </div>

        {/* Extra filters */}
        {showFilters && (
          <div className="flex flex-wrap gap-3 bg-surface-02 border border-surface-03 rounded-xl p-4">
            <div className="flex flex-col gap-1 min-w-[160px]">
              <label className="text-xs text-stone">Tipo</label>
              <select value={typeFilter} onChange={e => setTypeFilter(e.target.value as TaskType | "all")}
                className="bg-surface-03 border border-surface-03 rounded-lg px-2 py-1.5 text-cream text-xs focus:outline-none focus:border-gold">
                <option value="all">Todos os tipos</option>
                {(Object.entries(TYPE_CFG) as [TaskType, { label: string }][]).map(([v, c]) => (
                  <option key={v} value={v}>{c.label}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1 min-w-[140px]">
              <label className="text-xs text-stone">Prioridade</label>
              <select value={priorityFilter} onChange={e => setPriorityFilter(e.target.value as TaskPriority | "all")}
                className="bg-surface-03 border border-surface-03 rounded-lg px-2 py-1.5 text-cream text-xs focus:outline-none focus:border-gold">
                <option value="all">Todas</option>
                {(Object.entries(PRIORITY_CFG) as [TaskPriority, { label: string }][]).map(([v, c]) => (
                  <option key={v} value={v}>{c.label}</option>
                ))}
              </select>
            </div>
            <button onClick={() => { setTypeFilter("all"); setPriorityFilter("all"); }}
              className="self-end px-3 py-1.5 rounded-lg text-xs text-stone hover:text-cream border border-surface-03 transition-colors">
              Limpar filtros
            </button>
          </div>
        )}

        {loading && <div className="flex justify-center py-12"><Loader2 className="animate-spin text-gold" size={28} /></div>}
        {error && !loading && <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 text-red-400 text-sm">{error}</div>}

        {!loading && !error && (
          <div className="space-y-2">
            {filtered.length === 0 && (
              <div className="flex flex-col items-center justify-center py-20 bg-surface-02 border border-surface-03 rounded-2xl">
                <ClipboardList size={40} className="text-surface-03 mb-3" />
                <p className="text-stone text-sm">Nenhuma tarefa encontrada.</p>
              </div>
            )}
            {filtered.map(task => {
              const tc = TYPE_CFG[task.task_type] ?? TYPE_CFG.followup;
              const TypeIcon = tc.icon;
              const sc = STATUS_CFG[task.status];
              const pc = PRIORITY_CFG[task.priority];
              const isDone = task.status === "completed" || task.status === "cancelled";
              const isOverdue = task.status === "overdue" ||
                (task.due_date && new Date(task.due_date) < new Date() && !isDone);

              return (
                <div key={task.id}
                  className={`bg-surface-02 border rounded-2xl p-4 flex items-start gap-4 transition-colors group ${
                    isDone ? "border-surface-03 opacity-60" :
                    isOverdue ? "border-red-500/30 hover:border-red-500/50" :
                    "border-surface-03 hover:border-gold/30"
                  }`}>

                  {/* Toggle complete */}
                  <button onClick={() => setStatus(task, task.status === "completed" ? "pending" : "completed")}
                    disabled={transitioning === task.id} className="mt-0.5 shrink-0">
                    {transitioning === task.id ? (
                      <Loader2 size={20} className="animate-spin text-gold" />
                    ) : task.status === "completed" ? (
                      <CheckCircle2 size={20} className="text-green-400" />
                    ) : (
                      <Circle size={20} className="text-stone hover:text-gold transition-colors" />
                    )}
                  </button>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${tc.cls}`}>
                        <TypeIcon size={10} /> {tc.label}
                      </span>
                      <p className={`font-medium text-sm ${isDone ? "line-through text-stone" : "text-cream"}`}>
                        {task.title}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2 mb-1.5">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${sc.cls}`}>{sc.label}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full ${pc.cls}`}>{pc.label}</span>
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-stone">
                      {task.customer_name && <span>Cliente: <span className="text-cream">{task.customer_name}</span></span>}
                      {task.responsible && <span>Resp: {task.responsible}</span>}
                      {task.pipeline_card_id && <span>Card: #{task.pipeline_card_id.slice(0, 8)}</span>}
                      {task.due_date && (
                        <span className={isOverdue ? "text-red-400 font-medium" : ""}>
                          Vence: {new Date(task.due_date).toLocaleDateString("pt-BR")}
                          {isOverdue && " ⚠"}
                        </span>
                      )}
                    </div>
                    {task.description && <p className="text-stone text-xs mt-1 leading-relaxed">{task.description}</p>}
                  </div>

                  {/* Actions */}
                  <div className="flex gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                    {task.status === "pending" && (
                      <button onClick={() => setStatus(task, "in_progress")} title="Iniciar"
                        className="p-1.5 rounded-lg hover:bg-blue-500/10 text-stone hover:text-blue-400 transition-colors text-xs px-2">
                        Iniciar
                      </button>
                    )}
                    {(task.status === "pending" || task.status === "in_progress") && (
                      <button onClick={() => setStatus(task, "cancelled")} title="Cancelar"
                        className="p-1.5 rounded-lg hover:bg-surface-03 text-stone hover:text-stone transition-colors text-xs px-2">
                        Cancelar
                      </button>
                    )}
                    <button onClick={() => openEdit(task)}
                      className="p-1.5 rounded-lg hover:bg-surface-03 text-stone hover:text-cream transition-colors">
                      <ClipboardList size={13} />
                    </button>
                    <button onClick={() => handleDelete(task.id)}
                      className="p-1.5 rounded-lg hover:bg-red-500/10 text-stone hover:text-red-400 transition-colors">
                      <X size={14} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Modal */}
        {showModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
            <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-md max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between p-5 border-b border-surface-03">
                <h2 className="text-cream font-semibold">{editingId ? "Editar Tarefa" : "Nova Tarefa"}</h2>
                <button onClick={() => setShowModal(false)} className="text-stone hover:text-cream"><X size={18} /></button>
              </div>
              <form onSubmit={handleSave} className="p-5 space-y-4">
                <div className="space-y-1">
                  <label className="text-xs text-stone">Título *</label>
                  <input type="text" value={form.title ?? ""} onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                    placeholder="Ex: Ligar para cliente João" className={IC} />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs text-stone">Tipo</label>
                    <select value={form.task_type ?? "followup"} onChange={e => setForm(f => ({ ...f, task_type: e.target.value as TaskType }))} className={IC}>
                      {(Object.entries(TYPE_CFG) as [TaskType, { label: string }][]).map(([v, c]) => (
                        <option key={v} value={v}>{c.label}</option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-stone">Prioridade</label>
                    <select value={form.priority ?? "medium"} onChange={e => setForm(f => ({ ...f, priority: e.target.value as TaskPriority }))} className={IC}>
                      {(Object.entries(PRIORITY_CFG) as [TaskPriority, { label: string }][]).map(([v, c]) => (
                        <option key={v} value={v}>{c.label}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {editingId && (
                  <div className="space-y-1">
                    <label className="text-xs text-stone">Status</label>
                    <select value={form.status ?? "pending"} onChange={e => setForm(f => ({ ...f, status: e.target.value as TaskStatus }))} className={IC}>
                      {(Object.entries(STATUS_CFG) as [TaskStatus, { label: string }][]).map(([v, c]) => (
                        <option key={v} value={v}>{c.label}</option>
                      ))}
                    </select>
                  </div>
                )}

                <div className="space-y-1">
                  <label className="text-xs text-stone">ID do Cliente</label>
                  <input type="text" value={form.customer_id ?? ""} onChange={e => setForm(f => ({ ...f, customer_id: e.target.value }))}
                    placeholder="UUID do cliente (opcional)" className={IC} />
                </div>

                <div className="space-y-1">
                  <label className="text-xs text-stone">Card do Pipeline</label>
                  <input type="text" value={form.pipeline_card_id ?? ""} onChange={e => setForm(f => ({ ...f, pipeline_card_id: e.target.value }))}
                    placeholder="ID do card (opcional)" className={IC} />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs text-stone">Responsável</label>
                    <input type="text" value={form.responsible ?? ""} onChange={e => setForm(f => ({ ...f, responsible: e.target.value }))}
                      placeholder="Nome" className={IC} />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-stone">Vencimento</label>
                    <input type="date" value={form.due_date ?? ""} onChange={e => setForm(f => ({ ...f, due_date: e.target.value }))} className={IC} />
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-xs text-stone">Descrição</label>
                  <textarea value={form.description ?? ""} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                    rows={3} className={`${IC} resize-none`} />
                </div>

                <div className="flex gap-3 pt-2">
                  <button type="button" onClick={() => setShowModal(false)}
                    className="flex-1 py-2 rounded-xl border border-surface-03 text-stone hover:text-cream text-sm transition-colors">Cancelar</button>
                  <button type="submit" disabled={saving}
                    className="flex-1 py-2 rounded-xl bg-gold hover:bg-gold/90 text-black font-semibold text-sm disabled:opacity-60 flex items-center justify-center gap-2">
                    {saving && <Loader2 size={14} className="animate-spin" />}
                    {editingId ? "Salvar" : "Criar Tarefa"}
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
