import { useEffect, useState } from "react";
import { Plus, Pencil, Trash2, Save, X, ToggleLeft, ToggleRight } from "lucide-react";
import { chatbotAdminApi, type ChatbotAutomation } from "@/lib/chatbotApi";

const TRIGGERS: { value: ChatbotAutomation["gatilho"]; label: string; hint: string }[] = [
  { value: "tempo_na_pagina",    label: "Tempo na página",       hint: "Dispara após X segundos na página" },
  { value: "pagina_especifica",  label: "Página específica",     hint: "Dispara quando visita uma URL" },
  { value: "carrinho_abandonado",label: "Carrinho abandonado",   hint: "Dispara quando tem itens no carrinho há muito tempo" },
  { value: "produto_visualizado",label: "Produto visualizado",   hint: "Dispara quando visualiza um produto específico" },
];

interface ModalProps {
  auto: Partial<ChatbotAutomation> | null;
  onClose: () => void;
  onSave: (d: Partial<ChatbotAutomation>) => Promise<void>;
}

function AutoModal({ auto, onClose, onSave }: ModalProps) {
  const [form, setForm] = useState<Partial<ChatbotAutomation>>({
    nome: "", gatilho: "tempo_na_pagina", condicao: "", mensagem: "", ativo: true, prioridade: 0, ...auto,
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const upd = (k: keyof ChatbotAutomation, v: unknown) => setForm((p) => ({ ...p, [k]: v }));

  const submit = async () => {
    if (!form.nome?.trim() || !form.mensagem?.trim()) { setErr("Preencha nome e mensagem."); return; }
    setSaving(true); setErr("");
    try { await onSave(form); } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Erro."); setSaving(false); }
  };

  const trigger = TRIGGERS.find((t) => t.value === form.gatilho);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
      <div className="bg-surface-01 border border-surface-03 rounded-2xl w-full max-w-lg space-y-4 p-6">
        <div className="flex items-center justify-between">
          <h4 className="text-cream font-bold">{auto?.id ? "Editar automação" : "Nova automação"}</h4>
          <button onClick={onClose} className="text-stone hover:text-cream"><X size={18} /></button>
        </div>

        <div>
          <label className="block text-parchment text-xs font-medium mb-1">Nome</label>
          <input value={form.nome ?? ""} onChange={(e) => upd("nome", e.target.value)}
            className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold"
            placeholder="Ex: Oferta após 30s" />
        </div>

        <div>
          <label className="block text-parchment text-xs font-medium mb-1">Gatilho</label>
          <div className="grid grid-cols-2 gap-2">
            {TRIGGERS.map((t) => (
              <button key={t.value} onClick={() => upd("gatilho", t.value)}
                className={`text-left px-3 py-2 rounded-lg border text-xs transition-colors ${
                  form.gatilho === t.value ? "bg-gold/20 border-gold text-gold" : "bg-surface-03 border-surface-03 text-stone hover:text-parchment"
                }`}>
                <p className="font-medium">{t.label}</p>
                <p className="opacity-70">{t.hint}</p>
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-parchment text-xs font-medium mb-1">
            Condição
            {trigger && <span className="text-stone font-normal ml-2">— {trigger.hint}</span>}
          </label>
          <input value={form.condicao ?? ""} onChange={(e) => upd("condicao", e.target.value)}
            className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold"
            placeholder={form.gatilho === "tempo_na_pagina" ? "30" : form.gatilho === "pagina_especifica" ? "/cardapio" : ""} />
        </div>

        <div>
          <label className="block text-parchment text-xs font-medium mb-1">Mensagem do bot</label>
          <textarea value={form.mensagem ?? ""} onChange={(e) => upd("mensagem", e.target.value)}
            rows={3}
            className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold resize-none"
            placeholder="Oi! Posso te ajudar a escolher uma pizza? 🍕" />
        </div>

        <div className="grid grid-cols-2 gap-3 items-center">
          <div>
            <label className="block text-parchment text-xs font-medium mb-1">Prioridade</label>
            <input type="number" min={0} max={100}
              value={form.prioridade ?? 0} onChange={(e) => upd("prioridade", Number(e.target.value))}
              className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold" />
          </div>
          <div className="flex items-center gap-3 pt-5">
            <button onClick={() => upd("ativo", !form.ativo)}
              className={`relative w-11 h-6 rounded-full transition-colors ${form.ativo ? "bg-gold" : "bg-surface-03"}`}>
              <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${form.ativo ? "translate-x-6" : "translate-x-1"}`} />
            </button>
            <span className="text-parchment text-sm">{form.ativo ? "Ativo" : "Inativo"}</span>
          </div>
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

export default function ChatbotAutomations() {
  const [items, setItems] = useState<ChatbotAutomation[]>([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<Partial<ChatbotAutomation> | null | false>(false);

  const load = () => chatbotAdminApi.listAutomations().then(setItems).finally(() => setLoading(false));
  useEffect(() => { load(); }, []);

  const save = async (data: Partial<ChatbotAutomation>) => {
    if (data.id) await chatbotAdminApi.updateAutomation(data.id, data);
    else         await chatbotAdminApi.createAutomation(data);
    await load();
    setModal(false);
  };

  const del = async (id: string) => {
    if (!confirm("Excluir automação?")) return;
    await chatbotAdminApi.deleteAutomation(id);
    setItems((p) => p.filter((x) => x.id !== id));
  };

  const toggle = async (item: ChatbotAutomation) => {
    const updated = await chatbotAdminApi.updateAutomation(item.id, { ativo: !item.ativo });
    setItems((p) => p.map((x) => x.id === item.id ? updated : x));
  };

  if (loading) return <div className="text-stone text-center py-16">Carregando...</div>;

  return (
    <div className="max-w-4xl space-y-5">
      {modal !== false && (
        <AutoModal auto={modal} onClose={() => setModal(false)} onSave={save} />
      )}

      <div className="flex items-center justify-between">
        <h3 className="text-cream font-bold text-base">Automações</h3>
        <button onClick={() => setModal(null)}
          className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-4 rounded-lg text-sm">
          <Plus size={14} /> Nova automação
        </button>
      </div>

      <p className="text-stone text-xs">Automações disparam mensagens proativas no widget baseadas no comportamento do visitante.</p>

      {items.length === 0 ? (
        <p className="text-stone text-sm text-center py-12">Nenhuma automação configurada.</p>
      ) : (
        <div className="space-y-2">
          {items.map((item) => {
            const trigger = TRIGGERS.find((t) => t.value === item.gatilho);
            return (
              <div key={item.id} className="bg-surface-02 rounded-xl px-4 py-3 border border-surface-03 flex gap-3 items-start">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <p className={`text-sm font-medium ${item.ativo ? "text-cream" : "text-stone"}`}>{item.nome}</p>
                    {item.prioridade > 0 && <span className="bg-gold/10 text-gold text-xs px-2 py-0.5 rounded-full">P{item.prioridade}</span>}
                  </div>
                  <div className="flex gap-2 items-center">
                    <span className="bg-surface-03 text-stone text-xs px-2 py-0.5 rounded-full">{trigger?.label ?? item.gatilho}</span>
                    {item.condicao && <span className="text-stone text-xs">{item.condicao}</span>}
                  </div>
                  <p className="text-stone text-xs mt-1 line-clamp-1">{item.mensagem}</p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button onClick={() => toggle(item)} className="text-stone hover:text-parchment">
                    {item.ativo ? <ToggleRight size={18} className="text-gold" /> : <ToggleLeft size={18} />}
                  </button>
                  <button onClick={() => setModal(item)} className="text-stone hover:text-parchment">
                    <Pencil size={15} />
                  </button>
                  <button onClick={() => del(item.id)} className="text-stone hover:text-red-400">
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
