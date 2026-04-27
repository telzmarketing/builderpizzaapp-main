import { useEffect, useState } from "react";
import {
  Loader2, Plus, CheckCircle2, Circle, X, ClipboardList,
  Phone, MessageCircle, FileText, Tag, RefreshCw,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const unwrap = (json: any) => json?.data ?? json;

type TaskStatus = "pending" | "completed";
type TaskType = "whatsapp" | "call" | "proposal" | "coupon" | "followup";
type TaskPriority = "low" | "medium" | "high";

interface Task {
  id: string;
  title: string;
  task_type: TaskType;
  customer_name?: string;
  customer_id?: string;
  responsible?: string;
  due_date?: string;
  priority: TaskPriority;
  description?: string;
  status: TaskStatus;
  completed_at?: string;
}

const TYPE_LABELS: Record<TaskType, string> = {
  whatsapp: "WhatsApp",
  call: "Ligação",
  proposal: "Proposta",
  coupon: "Cupom",
  followup: "Follow-up",
};

const TYPE_ICONS: Record<TaskType, React.ElementType> = {
  whatsapp: MessageCircle,
  call: Phone,
  proposal: FileText,
  coupon: Tag,
  followup: RefreshCw,
};

const TYPE_COLORS: Record<TaskType, string> = {
  whatsapp: "text-green-400 bg-green-500/10",
  call: "text-blue-400 bg-blue-500/10",
  proposal: "text-purple-400 bg-purple-500/10",
  coupon: "text-gold bg-gold/10",
  followup: "text-orange-400 bg-orange-500/10",
};

const PRIORITY_LABELS: Record<TaskPriority, string> = {
  low: "Baixa",
  medium: "Média",
  high: "Alta",
};

const PRIORITY_COLORS: Record<TaskPriority, string> = {
  low: "bg-surface-03 text-stone",
  medium: "bg-yellow-500/20 text-yellow-400",
  high: "bg-red-500/20 text-red-400",
};

const emptyForm = (): Partial<Task> => ({
  title: "",
  task_type: "followup",
  customer_id: "",
  responsible: "",
  due_date: "",
  priority: "medium",
  description: "",
});

export default function CrmTarefas() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "pending" | "completed">("all");
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState<Partial<Task>>(emptyForm());
  const [saving, setSaving] = useState(false);
  const [completing, setCompleting] = useState<string | null>(null);

  const token = localStorage.getItem("admin_token");
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const fetchTasks = () => {
    setLoading(true);
    setError("");
    fetch(`${BASE}/crm/tasks`, { headers })
      .then((r) => { if (!r.ok) throw new Error("Falha ao carregar tarefas."); return r.json(); })
      .then(unwrap)
      .then(setTasks)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchTasks(); }, []);

  const filtered = tasks.filter((t) => {
    if (statusFilter === "pending") return t.status === "pending";
    if (statusFilter === "completed") return t.status === "completed";
    return true;
  });

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title?.trim()) { alert("Título obrigatório."); return; }
    setSaving(true);
    try {
      const res = await fetch(`${BASE}/crm/tasks`, {
        method: "POST",
        headers,
        body: JSON.stringify({ ...form, status: "pending" }),
      });
      if (!res.ok) throw new Error("Erro ao criar tarefa.");
      setShowModal(false);
      fetchTasks();
    } catch {
      alert("Erro ao criar tarefa.");
    } finally {
      setSaving(false);
    }
  };

  const handleComplete = async (task: Task) => {
    setCompleting(task.id);
    const newStatus: TaskStatus = task.status === "pending" ? "completed" : "pending";
    setTasks((prev) =>
      prev.map((t) => (t.id === task.id ? { ...t, status: newStatus } : t))
    );
    try {
      await fetch(`${BASE}/crm/tasks/${task.id}`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ status: newStatus }),
      });
    } catch {
      setTasks((prev) =>
        prev.map((t) => (t.id === task.id ? { ...t, status: task.status } : t))
      );
    } finally {
      setCompleting(null);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Excluir tarefa?")) return;
    await fetch(`${BASE}/crm/tasks/${id}`, { method: "DELETE", headers });
    setTasks((prev) => prev.filter((t) => t.id !== id));
  };

  const inputCls = "w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold";

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
          <button
            onClick={() => { setForm(emptyForm()); setShowModal(true); }}
            className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-black font-semibold px-4 py-2 rounded-xl text-sm transition-colors"
          >
            <Plus size={16} /> Nova Tarefa
          </button>
        </div>

        {/* Filters */}
        <div className="flex bg-surface-02 rounded-xl border border-surface-03 overflow-hidden w-fit">
          {(["all", "pending", "completed"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-4 py-2 text-sm font-medium transition-colors ${statusFilter === s ? "bg-gold text-black" : "text-stone hover:text-cream"}`}
            >
              {s === "all" ? "Todas" : s === "pending" ? "Pendentes" : "Concluídas"}
            </button>
          ))}
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
          <div className="space-y-2">
            {filtered.length === 0 && (
              <div className="flex flex-col items-center justify-center py-20 text-center bg-surface-02 border border-surface-03 rounded-2xl">
                <ClipboardList size={40} className="text-surface-03 mb-3" />
                <p className="text-stone text-sm">Nenhuma tarefa encontrada.</p>
              </div>
            )}
            {filtered.map((task) => {
              const TypeIcon = TYPE_ICONS[task.task_type] ?? ClipboardList;
              const isCompleted = task.status === "completed";
              return (
                <div
                  key={task.id}
                  className={`bg-surface-02 border rounded-2xl p-4 flex items-start gap-4 transition-colors ${
                    isCompleted ? "border-surface-03 opacity-60" : "border-surface-03 hover:border-gold/30"
                  }`}
                >
                  {/* Complete button */}
                  <button
                    onClick={() => handleComplete(task)}
                    disabled={completing === task.id}
                    className="mt-0.5 shrink-0 transition-colors"
                  >
                    {completing === task.id ? (
                      <Loader2 size={20} className="animate-spin text-gold" />
                    ) : isCompleted ? (
                      <CheckCircle2 size={20} className="text-green-400" />
                    ) : (
                      <Circle size={20} className="text-stone hover:text-gold" />
                    )}
                  </button>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <p className={`font-medium text-sm ${isCompleted ? "line-through text-stone" : "text-cream"}`}>
                        {task.title}
                      </p>
                      <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${TYPE_COLORS[task.task_type]}`}>
                        <TypeIcon size={10} />
                        {TYPE_LABELS[task.task_type]}
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${PRIORITY_COLORS[task.priority]}`}>
                        {PRIORITY_LABELS[task.priority]}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-stone">
                      {task.customer_name && <span>Cliente: {task.customer_name}</span>}
                      {task.responsible && <span>Resp: {task.responsible}</span>}
                      {task.due_date && (
                        <span className={new Date(task.due_date) < new Date() && !isCompleted ? "text-red-400" : ""}>
                          Vence: {new Date(task.due_date).toLocaleDateString("pt-BR")}
                        </span>
                      )}
                    </div>
                    {task.description && (
                      <p className="text-stone text-xs mt-1 leading-relaxed">{task.description}</p>
                    )}
                  </div>

                  {/* Delete */}
                  <button
                    onClick={() => handleDelete(task.id)}
                    className="shrink-0 p-1.5 rounded-lg hover:bg-red-500/10 text-stone hover:text-red-400 transition-colors"
                  >
                    <X size={14} />
                  </button>
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
                <h2 className="text-cream font-semibold">Nova Tarefa</h2>
                <button onClick={() => setShowModal(false)} className="text-stone hover:text-cream">
                  <X size={18} />
                </button>
              </div>
              <form onSubmit={handleSave} className="p-5 space-y-4">
                <div className="space-y-1">
                  <label className="text-xs text-stone">Título *</label>
                  <input
                    type="text"
                    value={form.title ?? ""}
                    onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                    placeholder="Ex: Ligar para cliente João"
                    className={inputCls}
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs text-stone">Tipo</label>
                    <select
                      value={form.task_type ?? "followup"}
                      onChange={(e) => setForm((f) => ({ ...f, task_type: e.target.value as TaskType }))}
                      className={inputCls}
                    >
                      {Object.entries(TYPE_LABELS).map(([v, l]) => (
                        <option key={v} value={v}>{l}</option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-stone">Prioridade</label>
                    <select
                      value={form.priority ?? "medium"}
                      onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value as TaskPriority }))}
                      className={inputCls}
                    >
                      {Object.entries(PRIORITY_LABELS).map(([v, l]) => (
                        <option key={v} value={v}>{l}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-xs text-stone">ID do Cliente</label>
                  <input
                    type="text"
                    value={form.customer_id ?? ""}
                    onChange={(e) => setForm((f) => ({ ...f, customer_id: e.target.value }))}
                    placeholder="uuid ou ID do cliente"
                    className={inputCls}
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs text-stone">Responsável</label>
                    <input
                      type="text"
                      value={form.responsible ?? ""}
                      onChange={(e) => setForm((f) => ({ ...f, responsible: e.target.value }))}
                      placeholder="Nome"
                      className={inputCls}
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-stone">Data de Vencimento</label>
                    <input
                      type="date"
                      value={form.due_date ?? ""}
                      onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
                      className={inputCls}
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-xs text-stone">Descrição</label>
                  <textarea
                    value={form.description ?? ""}
                    onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                    rows={3}
                    className={`${inputCls} resize-none`}
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
                    Criar Tarefa
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
