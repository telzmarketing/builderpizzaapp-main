import { useEffect, useState, useRef } from "react";
import {
  Loader2, Plus, X, ChevronRight, Pencil, Trash2, Settings,
  MessageCircle, ClipboardList, StickyNote, History, ArrowRight,
  ChevronDown, ChevronUp, GripVertical, LayoutList,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const unwrap = (json: any) => json?.data ?? json;

interface Pipeline { id: string; name: string; description?: string; stages: Stage[]; }
interface Stage    { id: string; name: string; order: number; color: string; pipeline_id: string; }
interface CrmCard  {
  id: string; title: string; stage_id: string; pipeline_id: string;
  customer_name?: string; customer_phone?: string; customer_id?: string;
  value: number; source?: string; responsible?: string;
  tags?: string[]; notes?: string; created_at?: string;
}
interface CardNote { id: string; body: string; author: string; created_at: string; }
interface CardHistory { id: string; event: string; created_at: string; }

const STAGE_COLORS = [
  "#3b82f6", "#8b5cf6", "#f59e0b", "#f97316", "#10b981",
  "#ec4899", "#06b6d4", "#ef4444", "#84cc16",
];

const COLOR_BORDER: Record<string, string> = {
  "#3b82f6": "border-t-blue-500",   "#8b5cf6": "border-t-purple-500",
  "#f59e0b": "border-t-amber-500",  "#f97316": "border-t-orange-500",
  "#10b981": "border-t-emerald-500","#ec4899": "border-t-pink-500",
  "#06b6d4": "border-t-cyan-500",   "#ef4444": "border-t-red-500",
  "#84cc16": "border-t-lime-500",
};

function fmt(v: number) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}
function fmtDate(s?: string) {
  if (!s) return "—";
  return new Date(s).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

const IC = "w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold";

type ModalMode = "card_create" | "card_detail" | "pipeline_create" | "pipeline_edit" | "stage_manage";

export default function CrmPipeline() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [activePipelineId, setActivePipelineId] = useState<string | null>(null);
  const [cards, setCards] = useState<CrmCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Modals
  const [modal, setModal] = useState<ModalMode | null>(null);
  const [modalStageId, setModalStageId] = useState<string>("");
  const [selectedCard, setSelectedCard] = useState<CrmCard | null>(null);
  const [cardTab, setCardTab] = useState<"details" | "notes" | "tasks" | "history">("details");
  const [cardNotes, setCardNotes] = useState<CardNote[]>([]);
  const [cardHistory, setCardHistory] = useState<CardHistory[]>([]);
  const [newNote, setNewNote] = useState("");
  const [newTask, setNewTask] = useState({ title: "", due_date: "" });

  // Forms
  const [cardForm, setCardForm] = useState<Partial<CrmCard & { customer_id: string }>>({ title: "", customer_id: "", value: 0, source: "", responsible: "" });
  const [pipelineForm, setPipelineForm] = useState({ name: "", description: "" });
  const [stageForm, setStageForm] = useState({ name: "", color: "#3b82f6" });
  const [editingStageId, setEditingStageId] = useState<string | null>(null);
  const [editingPipelineId, setEditingPipelineId] = useState<string | null>(null);

  const [saving, setSaving] = useState(false);
  const [showPipelinePanel, setShowPipelinePanel] = useState(false);

  const dragCardId = useRef<string | null>(null);
  const token = localStorage.getItem("admin_token");
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const activePipeline = pipelines.find(p => p.id === activePipelineId) ?? null;
  const stages = activePipeline ? [...activePipeline.stages].sort((a, b) => a.order - b.order) : [];

  // ── Fetch ──────────────────────────────────────────────────────────────────
  const fetchPipelines = async () => {
    setLoading(true); setError("");
    try {
      const pips: Pipeline[] = unwrap(await (await fetch(`${BASE}/crm/pipelines`, { headers })).json());
      setPipelines(pips ?? []);
      const first = (pips ?? [])[0];
      if (first) {
        setActivePipelineId(first.id);
        await fetchCards(first.id);
      }
    } catch { setError("Falha ao carregar pipelines."); }
    finally { setLoading(false); }
  };

  const fetchCards = async (pipelineId: string) => {
    try {
      const cs: CrmCard[] = unwrap(await (await fetch(`${BASE}/crm/pipelines/${pipelineId}/cards`, { headers })).json());
      setCards(cs ?? []);
    } catch { setCards([]); }
  };

  const fetchCardDetail = async (cardId: string) => {
    try {
      const [notes, hist] = await Promise.all([
        fetch(`${BASE}/crm/cards/${cardId}/notes`, { headers }).then(r => r.json()).then(unwrap),
        fetch(`${BASE}/crm/cards/${cardId}/history`, { headers }).then(r => r.json()).then(unwrap),
      ]);
      setCardNotes(notes ?? []);
      setCardHistory(hist ?? []);
    } catch { setCardNotes([]); setCardHistory([]); }
  };

  useEffect(() => { fetchPipelines(); }, []); // eslint-disable-line

  // Switch pipeline
  const switchPipeline = async (id: string) => {
    setActivePipelineId(id);
    setCards([]);
    await fetchCards(id);
  };

  // ── Drag & drop ────────────────────────────────────────────────────────────
  const handleDragStart = (cardId: string) => { dragCardId.current = cardId; };
  const handleDrop = async (e: React.DragEvent, stageId: string) => {
    e.preventDefault();
    const cardId = dragCardId.current;
    if (!cardId) return;
    const card = cards.find(c => c.id === cardId);
    if (!card || card.stage_id === stageId) return;
    setCards(prev => prev.map(c => c.id === cardId ? { ...c, stage_id: stageId } : c));
    try {
      await fetch(`${BASE}/crm/cards/${cardId}/move`, { method: "PATCH", headers, body: JSON.stringify({ stage_id: stageId }) });
    } catch {
      setCards(prev => prev.map(c => c.id === cardId ? { ...c, stage_id: card.stage_id } : c));
    }
    dragCardId.current = null;
  };

  const moveCardForward = async (card: CrmCard) => {
    const idx = stages.findIndex(s => s.id === card.stage_id);
    if (idx === -1 || idx >= stages.length - 1) return;
    const nextId = stages[idx + 1].id;
    setCards(prev => prev.map(c => c.id === card.id ? { ...c, stage_id: nextId } : c));
    try {
      await fetch(`${BASE}/crm/cards/${card.id}/move`, { method: "PATCH", headers, body: JSON.stringify({ stage_id: nextId }) });
    } catch { setCards(prev => prev.map(c => c.id === card.id ? { ...c, stage_id: card.stage_id } : c)); }
  };

  // ── Pipeline CRUD ──────────────────────────────────────────────────────────
  const savePipeline = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pipelineForm.name.trim()) { alert("Nome obrigatório."); return; }
    setSaving(true);
    try {
      if (editingPipelineId) {
        const updated = unwrap(await (await fetch(`${BASE}/crm/pipelines/${editingPipelineId}`, { method: "PATCH", headers, body: JSON.stringify(pipelineForm) })).json());
        setPipelines(prev => prev.map(p => p.id === editingPipelineId ? { ...p, ...updated } : p));
      } else {
        const created: Pipeline = unwrap(await (await fetch(`${BASE}/crm/pipelines`, { method: "POST", headers, body: JSON.stringify(pipelineForm) })).json());
        setPipelines(prev => [...prev, created]);
        setActivePipelineId(created.id);
        setCards([]);
      }
      setModal(null);
    } catch { alert("Erro ao salvar pipeline."); } finally { setSaving(false); }
  };

  const deletePipeline = async (id: string) => {
    if (!confirm("Excluir pipeline e todos os cards?")) return;
    await fetch(`${BASE}/crm/pipelines/${id}`, { method: "DELETE", headers });
    const remaining = pipelines.filter(p => p.id !== id);
    setPipelines(remaining);
    if (activePipelineId === id) {
      const first = remaining[0];
      setActivePipelineId(first?.id ?? null);
      if (first) fetchCards(first.id); else setCards([]);
    }
  };

  // ── Stage CRUD ─────────────────────────────────────────────────────────────
  const saveStage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stageForm.name.trim() || !activePipelineId) return;
    setSaving(true);
    try {
      if (editingStageId) {
        await fetch(`${BASE}/crm/stages/${editingStageId}`, { method: "PATCH", headers, body: JSON.stringify(stageForm) });
      } else {
        await fetch(`${BASE}/crm/pipelines/${activePipelineId}/stages`, { method: "POST", headers, body: JSON.stringify(stageForm) });
      }
      setEditingStageId(null);
      setStageForm({ name: "", color: "#3b82f6" });
      await fetchPipelines();
    } catch { alert("Erro ao salvar etapa."); } finally { setSaving(false); }
  };

  const deleteStage = async (id: string) => {
    if (!confirm("Excluir etapa? Os cards serão removidos.")) return;
    await fetch(`${BASE}/crm/stages/${id}`, { method: "DELETE", headers });
    await fetchPipelines();
    if (activePipelineId) fetchCards(activePipelineId);
  };

  const moveStage = async (stage: Stage, dir: -1 | 1) => {
    const newOrder = stage.order + dir;
    await fetch(`${BASE}/crm/stages/${stage.id}`, { method: "PATCH", headers, body: JSON.stringify({ order: newOrder }) });
    await fetchPipelines();
  };

  // ── Card CRUD ──────────────────────────────────────────────────────────────
  const saveCard = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cardForm.title?.trim()) { alert("Título obrigatório."); return; }
    setSaving(true);
    try {
      const newCard: CrmCard = unwrap(await (await fetch(`${BASE}/crm/cards`, { method: "POST", headers, body: JSON.stringify({ ...cardForm, stage_id: modalStageId, pipeline_id: activePipelineId }) })).json());
      setCards(prev => [...prev, newCard]);
      setModal(null);
    } catch { alert("Erro ao criar card."); } finally { setSaving(false); }
  };

  const deleteCard = async (id: string) => {
    if (!confirm("Excluir card?")) return;
    await fetch(`${BASE}/crm/cards/${id}`, { method: "DELETE", headers });
    setCards(prev => prev.filter(c => c.id !== id));
    if (selectedCard?.id === id) { setModal(null); setSelectedCard(null); }
  };

  const openCard = (card: CrmCard) => {
    setSelectedCard(card);
    setCardTab("details");
    fetchCardDetail(card.id);
    setModal("card_detail");
  };

  // ── Card quick actions ─────────────────────────────────────────────────────
  const sendWhatsApp = (card: CrmCard) => {
    if (!card.customer_phone) { alert("Card sem telefone cadastrado."); return; }
    const phone = card.customer_phone.replace(/\D/g, "");
    const url = `https://wa.me/${phone}`;
    window.open(url, "_blank");
  };

  const addNote = async () => {
    if (!newNote.trim() || !selectedCard) return;
    try {
      const n: CardNote = unwrap(await (await fetch(`${BASE}/crm/cards/${selectedCard.id}/notes`, { method: "POST", headers, body: JSON.stringify({ body: newNote, author: "Admin" }) })).json());
      setCardNotes(prev => [...prev, n]);
      setNewNote("");
    } catch { alert("Erro ao adicionar nota."); }
  };

  const addTask = async () => {
    if (!newTask.title.trim() || !selectedCard) return;
    try {
      await fetch(`${BASE}/crm/tasks`, { method: "POST", headers, body: JSON.stringify({ title: newTask.title, due_date: newTask.due_date, pipeline_card_id: selectedCard.id, task_type: "followup", status: "pending", priority: "medium" }) });
      setNewTask({ title: "", due_date: "" });
      alert("Tarefa criada.");
    } catch { alert("Erro ao criar tarefa."); }
  };

  const moveCardToStage = async (stageId: string) => {
    if (!selectedCard) return;
    setCards(prev => prev.map(c => c.id === selectedCard.id ? { ...c, stage_id: stageId } : c));
    setSelectedCard(prev => prev ? { ...prev, stage_id: stageId } : prev);
    try {
      await fetch(`${BASE}/crm/cards/${selectedCard.id}/move`, { method: "PATCH", headers, body: JSON.stringify({ stage_id: stageId }) });
    } catch { alert("Erro ao mover card."); }
  };

  return (
    <div className="flex flex-col md:flex-row min-h-screen md:h-screen bg-surface-00 overflow-hidden">
      <AdminSidebar />
      <main className="flex-1 overflow-hidden flex flex-col">

        {/* Header */}
        <div className="p-6 pb-3 flex-shrink-0 flex items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-gold mb-1">CRM</p>
            <h1 className="text-2xl font-bold text-cream">Pipeline</h1>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => { setPipelineForm({ name: "", description: "" }); setEditingPipelineId(null); setModal("pipeline_create"); }}
              className="flex items-center gap-1.5 px-3 py-2 bg-gold hover:bg-gold/90 text-black font-semibold rounded-xl text-sm transition-colors">
              <Plus size={14} /> Novo Pipeline
            </button>
            {activePipeline && (
              <button onClick={() => setModal("stage_manage")}
                className="flex items-center gap-1.5 px-3 py-2 bg-surface-02 border border-surface-03 text-stone hover:text-cream rounded-xl text-sm transition-colors">
                <Settings size={14} /> Etapas
              </button>
            )}
            <AdminTopActions />
          </div>
        </div>

        {/* Pipeline tabs */}
        {pipelines.length > 0 && (
          <div className="px-6 flex items-center gap-2 overflow-x-auto pb-2">
            {pipelines.map(p => (
              <button key={p.id} onClick={() => switchPipeline(p.id)}
                className={`flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-medium border transition-colors whitespace-nowrap ${activePipelineId === p.id ? "bg-gold text-black border-gold" : "border-surface-03 text-stone hover:text-cream"}`}>
                <LayoutList size={13} /> {p.name}
                {activePipelineId === p.id && (
                  <span className="flex gap-0.5 ml-1">
                    <button onClick={e => { e.stopPropagation(); setPipelineForm({ name: p.name, description: p.description ?? "" }); setEditingPipelineId(p.id); setModal("pipeline_edit"); }}
                      className="hover:text-gold transition-colors"><Pencil size={11} /></button>
                    <button onClick={e => { e.stopPropagation(); deletePipeline(p.id); }}
                      className="hover:text-red-400 transition-colors"><Trash2 size={11} /></button>
                  </span>
                )}
              </button>
            ))}
          </div>
        )}

        {loading && <div className="flex justify-center py-16"><Loader2 className="animate-spin text-gold" size={28} /></div>}
        {error && !loading && <div className="m-6 rounded-xl bg-red-500/10 border border-red-500/30 p-4 text-red-400 text-sm">{error}</div>}

        {!loading && !error && pipelines.length === 0 && (
          <div className="flex-1 flex flex-col items-center justify-center py-20">
            <LayoutList size={48} className="text-surface-03 mb-4" />
            <p className="text-stone text-sm mb-4">Nenhum pipeline criado.</p>
            <button onClick={() => { setPipelineForm({ name: "", description: "" }); setEditingPipelineId(null); setModal("pipeline_create"); }}
              className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-black font-semibold px-4 py-2 rounded-xl text-sm">
              <Plus size={16} /> Criar Primeiro Pipeline
            </button>
          </div>
        )}

        {/* Kanban board */}
        {!loading && !error && activePipeline && (
          <div className="flex-1 overflow-x-auto p-6">
            <div className="flex gap-4" style={{ minWidth: `${stages.length * 280 + 60}px` }}>
              {stages.map((stage, si) => {
                const stageCards = cards.filter(c => c.stage_id === stage.id);
                const borderCls = COLOR_BORDER[stage.color] ?? "border-t-gold";
                const total = stageCards.reduce((s, c) => s + c.value, 0);
                return (
                  <div key={stage.id} className="flex flex-col w-64 shrink-0"
                    onDragOver={e => e.preventDefault()} onDrop={e => handleDrop(e, stage.id)}>
                    <div className={`bg-surface-02 border border-surface-03 rounded-t-2xl border-t-4 p-3 flex items-center justify-between ${borderCls}`}>
                      <div>
                        <p className="text-cream text-sm font-semibold">{stage.name}</p>
                        <p className="text-stone text-xs">{stageCards.length} card{stageCards.length !== 1 ? "s" : ""}{total > 0 ? ` · ${fmt(total)}` : ""}</p>
                      </div>
                      <button onClick={() => { setModalStageId(stage.id); setCardForm({ title: "", customer_id: "", value: 0, source: "", responsible: "" }); setModal("card_create"); }}
                        className="p-1 rounded-lg hover:bg-surface-03 text-stone hover:text-cream transition-colors">
                        <Plus size={16} />
                      </button>
                    </div>
                    <div className="flex-1 bg-surface-02/50 border-x border-b border-surface-03 rounded-b-2xl p-2 space-y-2 overflow-y-auto min-h-[200px]">
                      {stageCards.map(card => (
                        <div key={card.id} draggable onDragStart={() => handleDragStart(card.id)}
                          onClick={() => openCard(card)}
                          className="bg-surface-02 border border-surface-03 rounded-xl p-3 cursor-pointer hover:border-gold/40 transition-colors">
                          <p className="text-cream text-sm font-medium leading-tight mb-1">{card.title}</p>
                          {card.customer_name && <p className="text-stone text-xs">{card.customer_name}{card.customer_phone ? ` · ${card.customer_phone}` : ""}</p>}
                          {card.value > 0 && <p className="text-gold text-xs font-semibold mt-1">{fmt(card.value)}</p>}
                          {card.source && <p className="text-stone text-xs mt-0.5">Fonte: {card.source}</p>}
                          {card.responsible && <p className="text-stone text-xs mt-0.5">Resp: {card.responsible}</p>}
                          {card.tags && card.tags.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-1.5">
                              {card.tags.map(tag => <span key={tag} className="px-1.5 py-0.5 bg-surface-03 text-stone text-xs rounded">{tag}</span>)}
                            </div>
                          )}
                          {si < stages.length - 1 && (
                            <button onClick={e => { e.stopPropagation(); moveCardForward(card); }}
                              className="mt-2 flex items-center gap-1 text-xs text-stone hover:text-gold transition-colors">
                              <ChevronRight size={12} /> Avançar
                            </button>
                          )}
                        </div>
                      ))}
                      {stageCards.length === 0 && (
                        <div className="h-20 border-2 border-dashed border-surface-03 rounded-xl flex items-center justify-center"
                          onDragOver={e => e.preventDefault()} onDrop={e => handleDrop(e, stage.id)}>
                          <p className="text-stone text-xs">Arraste um card aqui</p>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ══ MODAL: Card detail ══ */}
        {modal === "card_detail" && selectedCard && (
          <div className="fixed inset-0 z-50 flex items-center justify-end bg-black/50 p-4">
            <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-lg h-[calc(100vh-2rem)] flex flex-col overflow-hidden">
              <div className="flex items-center justify-between p-5 border-b border-surface-03 shrink-0">
                <h2 className="text-cream font-semibold text-sm truncate">{selectedCard.title}</h2>
                <div className="flex gap-1">
                  <button onClick={() => deleteCard(selectedCard.id)}
                    className="p-1.5 rounded-lg hover:bg-red-500/10 text-stone hover:text-red-400 transition-colors"><Trash2 size={14} /></button>
                  <button onClick={() => setModal(null)} className="text-stone hover:text-cream ml-1"><X size={18} /></button>
                </div>
              </div>

              {/* Quick actions */}
              <div className="flex gap-2 p-3 border-b border-surface-03 shrink-0 overflow-x-auto">
                {[
                  { icon: MessageCircle, label: "WhatsApp", action: () => sendWhatsApp(selectedCard), cls: "text-green-400 bg-green-500/10 hover:bg-green-500/20" },
                  { icon: ArrowRight, label: "Mover",
                    action: () => setCardTab("details"),
                    cls: "text-blue-400 bg-blue-500/10 hover:bg-blue-500/20" },
                  { icon: ClipboardList, label: "Tarefa",
                    action: () => setCardTab("tasks"),
                    cls: "text-gold bg-gold/10 hover:bg-gold/20" },
                  { icon: StickyNote, label: "Nota",
                    action: () => setCardTab("notes"),
                    cls: "text-purple-400 bg-purple-500/10 hover:bg-purple-500/20" },
                  { icon: History, label: "Histórico",
                    action: () => setCardTab("history"),
                    cls: "text-stone bg-surface-03 hover:bg-surface-03/70" },
                ].map(({ icon: Icon, label, action, cls }) => (
                  <button key={label} onClick={action}
                    className={`flex flex-col items-center gap-1 px-3 py-2 rounded-xl text-xs font-medium transition-colors shrink-0 ${cls}`}>
                    <Icon size={16} />{label}
                  </button>
                ))}
              </div>

              {/* Tab nav */}
              <div className="flex border-b border-surface-03 shrink-0">
                {(["details", "notes", "tasks", "history"] as const).map(t => (
                  <button key={t} onClick={() => setCardTab(t)}
                    className={`flex-1 py-2 text-xs font-medium transition-colors ${cardTab === t ? "text-gold border-b-2 border-gold" : "text-stone hover:text-cream"}`}>
                    {t === "details" ? "Detalhes" : t === "notes" ? "Notas" : t === "tasks" ? "Tarefas" : "Histórico"}
                  </button>
                ))}
              </div>

              <div className="flex-1 overflow-y-auto p-4">
                {/* Details tab */}
                {cardTab === "details" && (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      {[
                        { label: "Cliente", value: selectedCard.customer_name },
                        { label: "Telefone", value: selectedCard.customer_phone },
                        { label: "Valor", value: selectedCard.value > 0 ? fmt(selectedCard.value) : "—" },
                        { label: "Fonte", value: selectedCard.source },
                        { label: "Responsável", value: selectedCard.responsible },
                        { label: "Criado em", value: fmtDate(selectedCard.created_at) },
                      ].map(({ label, value }) => (
                        <div key={label}>
                          <p className="text-xs text-stone mb-0.5">{label}</p>
                          <p className="text-cream text-sm">{value ?? "—"}</p>
                        </div>
                      ))}
                    </div>
                    {/* Move stage */}
                    <div>
                      <p className="text-xs text-stone mb-2">Mover para etapa:</p>
                      <div className="flex flex-wrap gap-1.5">
                        {stages.map(s => (
                          <button key={s.id} onClick={() => moveCardToStage(s.id)}
                            className={`px-3 py-1 rounded-full text-xs border transition-colors ${selectedCard.stage_id === s.id ? "border-gold text-gold" : "border-surface-03 text-stone hover:text-cream"}`}>
                            {s.name}
                          </button>
                        ))}
                      </div>
                    </div>
                    {selectedCard.notes && (
                      <div><p className="text-xs text-stone mb-1">Observações</p><p className="text-cream text-sm bg-surface-03 rounded-xl p-3">{selectedCard.notes}</p></div>
                    )}
                  </div>
                )}

                {/* Notes tab */}
                {cardTab === "notes" && (
                  <div className="space-y-4">
                    <div className="flex gap-2">
                      <textarea value={newNote} onChange={e => setNewNote(e.target.value)}
                        rows={2} placeholder="Escreva uma nota..." className={`${IC} resize-none text-xs`} />
                      <button onClick={addNote} disabled={!newNote.trim()}
                        className="shrink-0 px-3 py-2 bg-gold hover:bg-gold/90 text-black rounded-xl text-sm font-medium disabled:opacity-50">
                        <StickyNote size={14} />
                      </button>
                    </div>
                    <div className="space-y-2">
                      {cardNotes.length === 0 && <p className="text-stone text-xs text-center py-8">Nenhuma nota.</p>}
                      {cardNotes.map(n => (
                        <div key={n.id} className="bg-surface-03 rounded-xl p-3 space-y-1">
                          <p className="text-cream text-xs leading-relaxed">{n.body}</p>
                          <p className="text-stone text-xs">{n.author} · {fmtDate(n.created_at)}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Tasks tab */}
                {cardTab === "tasks" && (
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <input type="text" value={newTask.title} onChange={e => setNewTask(t => ({ ...t, title: e.target.value }))}
                        placeholder="Título da tarefa" className={IC} />
                      <div className="flex gap-2">
                        <input type="date" value={newTask.due_date} onChange={e => setNewTask(t => ({ ...t, due_date: e.target.value }))} className={IC} />
                        <button onClick={addTask} disabled={!newTask.title.trim()}
                          className="shrink-0 px-3 py-2 bg-gold hover:bg-gold/90 text-black rounded-xl text-sm font-medium disabled:opacity-50">
                          <Plus size={14} />
                        </button>
                      </div>
                    </div>
                    <p className="text-stone text-xs text-center py-4">As tarefas criadas aparecem em CRM → Tarefas.</p>
                  </div>
                )}

                {/* History tab */}
                {cardTab === "history" && (
                  <div className="space-y-2">
                    {cardHistory.length === 0 && <p className="text-stone text-xs text-center py-8">Nenhum histórico.</p>}
                    {cardHistory.map(h => (
                      <div key={h.id} className="flex items-start gap-3 text-xs">
                        <div className="w-1.5 h-1.5 rounded-full bg-gold mt-1.5 shrink-0" />
                        <div>
                          <p className="text-cream">{h.event}</p>
                          <p className="text-stone">{fmtDate(h.created_at)}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ══ MODAL: Create card ══ */}
        {modal === "card_create" && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
            <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-md">
              <div className="flex items-center justify-between p-5 border-b border-surface-03">
                <h2 className="text-cream font-semibold">Novo Card</h2>
                <button onClick={() => setModal(null)} className="text-stone hover:text-cream"><X size={18} /></button>
              </div>
              <form onSubmit={saveCard} className="p-5 space-y-4">
                {[
                  { key: "title", label: "Título *", placeholder: "Nome do negócio..." },
                  { key: "customer_id", label: "ID do Cliente", placeholder: "UUID (opcional)" },
                  { key: "source", label: "Fonte", placeholder: "instagram, google..." },
                  { key: "responsible", label: "Responsável", placeholder: "Nome do atendente" },
                ].map(({ key, label, placeholder }) => (
                  <div key={key} className="space-y-1">
                    <label className="text-xs text-stone">{label}</label>
                    <input type="text" value={(cardForm as Record<string, unknown>)[key] as string ?? ""}
                      onChange={e => setCardForm(f => ({ ...f, [key]: e.target.value }))}
                      placeholder={placeholder} className={IC} />
                  </div>
                ))}
                <div className="space-y-1">
                  <label className="text-xs text-stone">Valor (R$)</label>
                  <input type="number" min={0} step={0.01} value={cardForm.value ?? 0}
                    onChange={e => setCardForm(f => ({ ...f, value: parseFloat(e.target.value) || 0 }))} className={IC} />
                </div>
                <div className="flex gap-3">
                  <button type="button" onClick={() => setModal(null)} className="flex-1 py-2 rounded-xl border border-surface-03 text-stone text-sm">Cancelar</button>
                  <button type="submit" disabled={saving}
                    className="flex-1 py-2 rounded-xl bg-gold hover:bg-gold/90 text-black font-semibold text-sm disabled:opacity-60 flex items-center justify-center gap-2">
                    {saving && <Loader2 size={14} className="animate-spin" />} Criar Card
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ══ MODAL: Create/edit pipeline ══ */}
        {(modal === "pipeline_create" || modal === "pipeline_edit") && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
            <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-sm">
              <div className="flex items-center justify-between p-5 border-b border-surface-03">
                <h2 className="text-cream font-semibold">{editingPipelineId ? "Editar Pipeline" : "Novo Pipeline"}</h2>
                <button onClick={() => setModal(null)} className="text-stone hover:text-cream"><X size={18} /></button>
              </div>
              <form onSubmit={savePipeline} className="p-5 space-y-4">
                <div className="space-y-1">
                  <label className="text-xs text-stone">Nome *</label>
                  <input type="text" value={pipelineForm.name} onChange={e => setPipelineForm(f => ({ ...f, name: e.target.value }))}
                    placeholder="Vendas / Retenção..." className={IC} />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-stone">Descrição</label>
                  <textarea value={pipelineForm.description} onChange={e => setPipelineForm(f => ({ ...f, description: e.target.value }))}
                    rows={2} className={`${IC} resize-none`} />
                </div>
                <div className="flex gap-3">
                  <button type="button" onClick={() => setModal(null)} className="flex-1 py-2 rounded-xl border border-surface-03 text-stone text-sm">Cancelar</button>
                  <button type="submit" disabled={saving}
                    className="flex-1 py-2 rounded-xl bg-gold hover:bg-gold/90 text-black font-semibold text-sm disabled:opacity-60 flex items-center justify-center gap-2">
                    {saving && <Loader2 size={14} className="animate-spin" />} {editingPipelineId ? "Salvar" : "Criar"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ══ MODAL: Stage management ══ */}
        {modal === "stage_manage" && activePipeline && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
            <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-md max-h-[85vh] flex flex-col overflow-hidden">
              <div className="flex items-center justify-between p-5 border-b border-surface-03 shrink-0">
                <h2 className="text-cream font-semibold">Etapas — {activePipeline.name}</h2>
                <button onClick={() => setModal(null)} className="text-stone hover:text-cream"><X size={18} /></button>
              </div>
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {stages.map(s => (
                  <div key={s.id} className="flex items-center gap-2 bg-surface-03 rounded-xl p-3">
                    <GripVertical size={14} className="text-stone shrink-0" />
                    <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: s.color }} />
                    {editingStageId === s.id ? (
                      <>
                        <input value={stageForm.name} onChange={e => setStageForm(f => ({ ...f, name: e.target.value }))}
                          className="flex-1 bg-surface-02 border border-gold rounded-lg px-2 py-1 text-cream text-sm focus:outline-none" />
                        <div className="flex gap-1">
                          {STAGE_COLORS.map(c => (
                            <button key={c} type="button" onClick={() => setStageForm(f => ({ ...f, color: c }))}
                              className={`w-5 h-5 rounded-full ${stageForm.color === c ? "ring-2 ring-white" : ""}`}
                              style={{ backgroundColor: c }} />
                          ))}
                        </div>
                        <button onClick={async e => { e.preventDefault(); await saveStage({ preventDefault: () => {} } as React.FormEvent); setEditingStageId(null); }}
                          className="p-1 text-green-400 hover:text-green-300"><CheckCircle size={14} /></button>
                        <button onClick={() => setEditingStageId(null)} className="p-1 text-stone hover:text-cream"><X size={14} /></button>
                      </>
                    ) : (
                      <>
                        <span className="flex-1 text-cream text-sm">{s.name}</span>
                        <span className="text-stone text-xs">{cards.filter(c => c.stage_id === s.id).length} cards</span>
                        <button onClick={() => moveStage(s, -1)} disabled={s.order <= 1} className="p-1 text-stone hover:text-cream disabled:opacity-30"><ChevronUp size={12} /></button>
                        <button onClick={() => moveStage(s, 1)} className="p-1 text-stone hover:text-cream"><ChevronDown size={12} /></button>
                        <button onClick={() => { setEditingStageId(s.id); setStageForm({ name: s.name, color: s.color }); }}
                          className="p-1 text-stone hover:text-cream"><Pencil size={12} /></button>
                        <button onClick={() => deleteStage(s.id)} className="p-1 text-stone hover:text-red-400"><Trash2 size={12} /></button>
                      </>
                    )}
                  </div>
                ))}

                {/* Add new stage */}
                <form onSubmit={saveStage} className="flex items-center gap-2 mt-2">
                  <input type="text" value={editingStageId ? "" : stageForm.name}
                    onChange={e => setStageForm(f => ({ ...f, name: e.target.value }))}
                    placeholder="Nova etapa..." disabled={!!editingStageId}
                    className="flex-1 bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold disabled:opacity-40" />
                  <div className="flex gap-1">
                    {STAGE_COLORS.slice(0, 5).map(c => (
                      <button key={c} type="button" onClick={() => setStageForm(f => ({ ...f, color: c }))} disabled={!!editingStageId}
                        className={`w-5 h-5 rounded-full disabled:opacity-40 ${stageForm.color === c && !editingStageId ? "ring-2 ring-white" : ""}`}
                        style={{ backgroundColor: c }} />
                    ))}
                  </div>
                  <button type="submit" disabled={saving || !stageForm.name.trim() || !!editingStageId}
                    className="p-2 bg-gold hover:bg-gold/90 text-black rounded-xl disabled:opacity-50">
                    {saving ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                  </button>
                </form>
              </div>
              <div className="p-4 border-t border-surface-03 shrink-0">
                <button onClick={() => setModal(null)} className="w-full py-2 rounded-xl border border-surface-03 text-stone hover:text-cream text-sm">Fechar</button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

// Missing import for CheckCircle used in stage edit
function CheckCircle({ size, className }: { size: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={className}>
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  );
}
