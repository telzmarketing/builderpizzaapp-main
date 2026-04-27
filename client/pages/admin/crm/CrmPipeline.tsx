import { useEffect, useState, useRef } from "react";
import { Loader2, Plus, X, ChevronRight } from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

interface Pipeline {
  id: string;
  name: string;
  stages: Stage[];
}

interface Stage {
  id: string;
  name: string;
  order: number;
  color?: string;
}

interface CrmCard {
  id: string;
  title: string;
  stage_id: string;
  customer_name?: string;
  customer_phone?: string;
  value: number;
  source?: string;
  responsible?: string;
  tags?: string[];
}

const STAGE_COLORS = [
  "border-t-blue-500",
  "border-t-purple-500",
  "border-t-gold",
  "border-t-orange-500",
  "border-t-green-500",
];

const emptyCard = (): Partial<CrmCard & { customer_id: string }> => ({
  title: "",
  customer_id: "",
  value: 0,
  source: "",
  responsible: "",
});

function fmt(v: number) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default function CrmPipeline() {
  const [pipeline, setPipeline] = useState<Pipeline | null>(null);
  const [cards, setCards] = useState<CrmCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [modalStageId, setModalStageId] = useState<string>("");
  const [form, setForm] = useState<Partial<CrmCard & { customer_id: string }>>(emptyCard());
  const [saving, setSaving] = useState(false);
  const dragCardId = useRef<string | null>(null);

  const token = localStorage.getItem("admin_token");
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const fetchPipeline = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${BASE}/crm/pipelines`, { headers });
      if (!res.ok) throw new Error("Falha ao carregar pipelines.");
      const pipelines: Pipeline[] = await res.json();
      const p = pipelines[0];
      if (!p) { setPipeline(null); setLoading(false); return; }
      setPipeline(p);
      const cardsRes = await fetch(`${BASE}/crm/pipelines/${p.id}/cards`, { headers });
      if (!cardsRes.ok) throw new Error("Falha ao carregar cards.");
      setCards(await cardsRes.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erro desconhecido.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchPipeline(); }, []);

  // Drag & drop handlers
  const handleDragStart = (cardId: string) => {
    dragCardId.current = cardId;
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = async (e: React.DragEvent, stageId: string) => {
    e.preventDefault();
    const cardId = dragCardId.current;
    if (!cardId) return;
    const card = cards.find((c) => c.id === cardId);
    if (!card || card.stage_id === stageId) return;

    // Optimistic update
    setCards((prev) =>
      prev.map((c) => (c.id === cardId ? { ...c, stage_id: stageId } : c))
    );

    try {
      await fetch(`${BASE}/crm/cards/${cardId}/move`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ stage_id: stageId }),
      });
    } catch {
      // Revert on failure
      setCards((prev) =>
        prev.map((c) => (c.id === cardId ? { ...c, stage_id: card.stage_id } : c))
      );
      alert("Erro ao mover card.");
    }
    dragCardId.current = null;
  };

  const moveCardForward = async (card: CrmCard) => {
    if (!pipeline) return;
    const stages = [...pipeline.stages].sort((a, b) => a.order - b.order);
    const currentIdx = stages.findIndex((s) => s.id === card.stage_id);
    if (currentIdx === -1 || currentIdx >= stages.length - 1) return;
    const nextStage = stages[currentIdx + 1];

    setCards((prev) =>
      prev.map((c) => (c.id === card.id ? { ...c, stage_id: nextStage.id } : c))
    );
    try {
      await fetch(`${BASE}/crm/cards/${card.id}/move`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ stage_id: nextStage.id }),
      });
    } catch {
      setCards((prev) =>
        prev.map((c) => (c.id === card.id ? { ...c, stage_id: card.stage_id } : c))
      );
    }
  };

  const openCreate = (stageId: string) => {
    setModalStageId(stageId);
    setForm(emptyCard());
    setShowModal(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title?.trim()) { alert("Título obrigatório."); return; }
    setSaving(true);
    try {
      const res = await fetch(`${BASE}/crm/cards`, {
        method: "POST",
        headers,
        body: JSON.stringify({ ...form, stage_id: modalStageId }),
      });
      if (!res.ok) throw new Error("Erro ao criar card.");
      const newCard = await res.json();
      setCards((prev) => [...prev, newCard]);
      setShowModal(false);
    } catch {
      alert("Erro ao criar card.");
    } finally {
      setSaving(false);
    }
  };

  const stages = pipeline?.stages
    ? [...pipeline.stages].sort((a, b) => a.order - b.order)
    : [];

  return (
    <div className="flex flex-col md:flex-row min-h-screen bg-surface-01">
      <AdminSidebar />
      <main className="flex-1 overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-6 pb-0 flex-shrink-0">
          <p className="text-xs font-semibold uppercase tracking-widest text-gold mb-1">CRM</p>
          <h1 className="text-2xl font-bold text-cream">
            {pipeline?.name ?? "Pipeline"}
          </h1>
        </div>

        {loading && (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="animate-spin text-gold" size={28} />
          </div>
        )}
        {error && !loading && (
          <div className="m-6 rounded-xl bg-red-500/10 border border-red-500/30 p-4 text-red-400 text-sm">
            {error}
          </div>
        )}

        {!loading && !error && pipeline && (
          <div className="flex-1 overflow-x-auto p-6">
            <div className="flex gap-4 h-full" style={{ minWidth: `${stages.length * 280}px` }}>
              {stages.map((stage, si) => {
                const stageCards = cards.filter((c) => c.stage_id === stage.id);
                return (
                  <div
                    key={stage.id}
                    className="flex flex-col w-64 shrink-0"
                    onDragOver={handleDragOver}
                    onDrop={(e) => handleDrop(e, stage.id)}
                  >
                    {/* Column header */}
                    <div
                      className={`bg-surface-02 border border-surface-03 rounded-t-2xl border-t-4 p-3 flex items-center justify-between ${STAGE_COLORS[si % STAGE_COLORS.length]}`}
                    >
                      <div>
                        <p className="text-cream text-sm font-semibold">{stage.name}</p>
                        <p className="text-stone text-xs">{stageCards.length} card{stageCards.length !== 1 ? "s" : ""}</p>
                      </div>
                      <button
                        onClick={() => openCreate(stage.id)}
                        className="p-1 rounded-lg hover:bg-surface-03 text-stone hover:text-cream transition-colors"
                      >
                        <Plus size={16} />
                      </button>
                    </div>

                    {/* Cards */}
                    <div className="flex-1 bg-surface-02/50 border-x border-b border-surface-03 rounded-b-2xl p-2 space-y-2 overflow-y-auto min-h-[200px]">
                      {stageCards.map((card) => (
                        <div
                          key={card.id}
                          draggable
                          onDragStart={() => handleDragStart(card.id)}
                          className="bg-surface-02 border border-surface-03 rounded-xl p-3 cursor-grab active:cursor-grabbing hover:border-gold/40 transition-colors"
                        >
                          <p className="text-cream text-sm font-medium leading-tight mb-2">{card.title}</p>
                          {(card.customer_name || card.customer_phone) && (
                            <p className="text-stone text-xs">
                              {card.customer_name ?? ""} {card.customer_phone ? `· ${card.customer_phone}` : ""}
                            </p>
                          )}
                          {card.value > 0 && (
                            <p className="text-gold text-xs font-semibold mt-1">{fmt(card.value)}</p>
                          )}
                          {card.source && (
                            <p className="text-stone text-xs mt-0.5">Fonte: {card.source}</p>
                          )}
                          {card.responsible && (
                            <p className="text-stone text-xs mt-0.5">Resp: {card.responsible}</p>
                          )}
                          {card.tags && card.tags.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-2">
                              {card.tags.map((tag) => (
                                <span
                                  key={tag}
                                  className="px-1.5 py-0.5 bg-surface-03 text-stone text-xs rounded"
                                >
                                  {tag}
                                </span>
                              ))}
                            </div>
                          )}
                          {si < stages.length - 1 && (
                            <button
                              onClick={() => moveCardForward(card)}
                              className="mt-2 flex items-center gap-1 text-xs text-stone hover:text-gold transition-colors"
                            >
                              <ChevronRight size={12} /> Avançar etapa
                            </button>
                          )}
                        </div>
                      ))}
                      {stageCards.length === 0 && (
                        <div
                          className="h-20 border-2 border-dashed border-surface-03 rounded-xl flex items-center justify-center"
                          onDragOver={handleDragOver}
                          onDrop={(e) => handleDrop(e, stage.id)}
                        >
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

        {/* Modal */}
        {showModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
            <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-md">
              <div className="flex items-center justify-between p-5 border-b border-surface-03">
                <h2 className="text-cream font-semibold">Novo Card</h2>
                <button onClick={() => setShowModal(false)} className="text-stone hover:text-cream">
                  <X size={18} />
                </button>
              </div>
              <form onSubmit={handleSave} className="p-5 space-y-4">
                {[
                  { key: "title", label: "Título *", placeholder: "Nome do negócio..." },
                  { key: "customer_id", label: "ID do Cliente", placeholder: "uuid ou ID" },
                  { key: "source", label: "Fonte", placeholder: "instagram, google..." },
                  { key: "responsible", label: "Responsável", placeholder: "Nome do atendente" },
                ].map(({ key, label, placeholder }) => (
                  <div key={key} className="space-y-1">
                    <label className="text-xs text-stone">{label}</label>
                    <input
                      type="text"
                      value={(form as Record<string, unknown>)[key] as string ?? ""}
                      onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                      placeholder={placeholder}
                      className="w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold"
                    />
                  </div>
                ))}
                <div className="space-y-1">
                  <label className="text-xs text-stone">Valor (R$)</label>
                  <input
                    type="number"
                    min={0}
                    step={0.01}
                    value={form.value ?? 0}
                    onChange={(e) => setForm((f) => ({ ...f, value: parseFloat(e.target.value) || 0 }))}
                    className="w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold"
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
                    Criar Card
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
