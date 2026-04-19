import { useEffect, useState } from "react";
import { Plus, Pencil, Trash2, Save, X, ToggleLeft, ToggleRight } from "lucide-react";
import { chatbotAdminApi, type ChatbotFAQ } from "@/lib/chatbotApi";

const CATEGORIES = ["geral", "cardapio", "pedidos", "pagamento", "entrega", "promos", "outros"];

interface ModalProps {
  faq: Partial<ChatbotFAQ> | null;
  onClose: () => void;
  onSave: (data: Partial<ChatbotFAQ>) => Promise<void>;
}

function FAQModal({ faq, onClose, onSave }: ModalProps) {
  const [form, setForm] = useState<Partial<ChatbotFAQ>>({
    pergunta: "", resposta: "", categoria: "geral", prioridade: 0, ativo: true, ...faq,
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const upd = (k: keyof ChatbotFAQ, v: unknown) => setForm((p) => ({ ...p, [k]: v }));

  const submit = async () => {
    if (!form.pergunta?.trim() || !form.resposta?.trim()) { setErr("Preencha pergunta e resposta."); return; }
    setSaving(true); setErr("");
    try { await onSave(form); } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Erro."); setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
      <div className="bg-surface-01 border border-surface-03 rounded-2xl w-full max-w-lg space-y-4 p-6">
        <div className="flex items-center justify-between">
          <h4 className="text-cream font-bold">{faq?.id ? "Editar FAQ" : "Nova entrada FAQ"}</h4>
          <button onClick={onClose} className="text-stone hover:text-cream"><X size={18} /></button>
        </div>

        <div>
          <label className="block text-parchment text-xs font-medium mb-1">Pergunta</label>
          <input value={form.pergunta ?? ""} onChange={(e) => upd("pergunta", e.target.value)}
            className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold"
            placeholder="Qual o prazo de entrega?" />
        </div>

        <div>
          <label className="block text-parchment text-xs font-medium mb-1">Resposta</label>
          <textarea value={form.resposta ?? ""} onChange={(e) => upd("resposta", e.target.value)}
            rows={4}
            className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold resize-none"
            placeholder="Nosso prazo médio é de 40 a 60 minutos..." />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-parchment text-xs font-medium mb-1">Categoria</label>
            <select value={form.categoria ?? "geral"} onChange={(e) => upd("categoria", e.target.value)}
              className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold">
              {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-parchment text-xs font-medium mb-1">Prioridade (0 = baixa)</label>
            <input type="number" min={0} max={100}
              value={form.prioridade ?? 0} onChange={(e) => upd("prioridade", Number(e.target.value))}
              className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold" />
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button onClick={() => upd("ativo", !form.ativo)}
            className={`relative w-11 h-6 rounded-full transition-colors ${form.ativo ? "bg-gold" : "bg-surface-03"}`}>
            <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${form.ativo ? "translate-x-6" : "translate-x-1"}`} />
          </button>
          <span className="text-parchment text-sm">{form.ativo ? "Ativo" : "Inativo"}</span>
        </div>

        {err && <p className="text-red-400 text-xs">{err}</p>}

        <div className="flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 rounded-lg border border-surface-03 text-stone hover:text-parchment text-sm">Cancelar</button>
          <button onClick={submit} disabled={saving}
            className="flex items-center gap-2 bg-gold hover:bg-gold/90 disabled:opacity-50 text-cream font-bold px-5 py-2 rounded-lg text-sm">
            <Save size={14} /> {saving ? "Salvando..." : "Salvar"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ChatbotFAQ() {
  const [items, setItems] = useState<ChatbotFAQ[]>([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<Partial<ChatbotFAQ> | null | false>(false);
  const [filter, setFilter] = useState("todos");

  const load = () => chatbotAdminApi.listFAQ().then(setItems).finally(() => setLoading(false));
  useEffect(() => { load(); }, []);

  const saveItem = async (data: Partial<ChatbotFAQ>) => {
    if (data.id) await chatbotAdminApi.updateFAQ(data.id, data);
    else         await chatbotAdminApi.createFAQ(data);
    await load();
    setModal(false);
  };

  const del = async (id: string) => {
    if (!confirm("Excluir esta entrada FAQ?")) return;
    await chatbotAdminApi.deleteFAQ(id);
    setItems((p) => p.filter((x) => x.id !== id));
  };

  const toggle = async (item: ChatbotFAQ) => {
    const updated = await chatbotAdminApi.updateFAQ(item.id, { ativo: !item.ativo });
    setItems((p) => p.map((x) => x.id === item.id ? updated : x));
  };

  const cats = ["todos", ...Array.from(new Set(items.map((i) => i.categoria)))];
  const visible = filter === "todos" ? items : items.filter((i) => i.categoria === filter);

  if (loading) return <div className="text-stone text-center py-16">Carregando...</div>;

  return (
    <div className="max-w-4xl space-y-5">
      {modal !== false && (
        <FAQModal
          faq={modal}
          onClose={() => setModal(false)}
          onSave={saveItem}
        />
      )}

      <div className="flex items-center justify-between">
        <h3 className="text-cream font-bold text-base">Base de FAQ</h3>
        <button onClick={() => setModal(null)}
          className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-4 rounded-lg text-sm transition-colors">
          <Plus size={14} /> Nova entrada
        </button>
      </div>

      {/* Category filter */}
      <div className="flex gap-2 flex-wrap">
        {cats.map((c) => (
          <button key={c} onClick={() => setFilter(c)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors border ${
              filter === c ? "bg-gold/20 border-gold text-gold" : "bg-surface-03 border-surface-03 text-stone hover:text-parchment"
            }`}>{c}</button>
        ))}
      </div>

      {visible.length === 0 ? (
        <p className="text-stone text-sm text-center py-12">Nenhuma entrada FAQ. Clique em "Nova entrada" para começar.</p>
      ) : (
        <div className="space-y-2">
          {visible.map((item) => (
            <div key={item.id} className="bg-surface-02 rounded-xl px-4 py-3 border border-surface-03 flex gap-3 items-start">
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-medium ${item.ativo ? "text-cream" : "text-stone line-through"}`}>{item.pergunta}</p>
                <p className="text-stone text-xs mt-1 line-clamp-2">{item.resposta}</p>
                <div className="flex gap-2 mt-1.5">
                  <span className="bg-surface-03 text-stone text-xs px-2 py-0.5 rounded-full">{item.categoria}</span>
                  {item.prioridade > 0 && <span className="bg-gold/10 text-gold text-xs px-2 py-0.5 rounded-full">P{item.prioridade}</span>}
                </div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <button onClick={() => toggle(item)} className="text-stone hover:text-parchment transition-colors">
                  {item.ativo ? <ToggleRight size={18} className="text-gold" /> : <ToggleLeft size={18} />}
                </button>
                <button onClick={() => setModal(item)} className="text-stone hover:text-parchment transition-colors">
                  <Pencil size={15} />
                </button>
                <button onClick={() => del(item.id)} className="text-stone hover:text-red-400 transition-colors">
                  <Trash2 size={15} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="text-stone text-xs">Total: {items.length} entradas — {items.filter((i) => i.ativo).length} ativas</p>
    </div>
  );
}
