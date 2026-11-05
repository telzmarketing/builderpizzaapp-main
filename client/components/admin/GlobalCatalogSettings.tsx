import { useEffect, useMemo, useState } from "react";
import { Check, Loader2, Plus, X } from "lucide-react";
import { globalCatalogApi, ApiGlobalCatalogItem } from "@/lib/api";

type Kind = "sizes" | "doughTypes" | "crusts";
const labels: Record<Kind, string> = { sizes: "Tamanhos de pizza", doughTypes: "Tipos de massa", crusts: "Bordas de pizza" };

export default function GlobalCatalogSettings() {
  const [kind, setKind] = useState<Kind>("sizes");
  const [items, setItems] = useState<ApiGlobalCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", price_addition: "", sort_order: "0", is_default: false });
  const api = globalCatalogApi[kind];

  const load = async () => {
    setLoading(true); setError("");
    try { setItems(await api.list()); } catch (e) { setError(e instanceof Error ? e.message : "Nao foi possivel carregar as configuracoes."); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, [kind]);
  const hasPrice = kind !== "sizes";
  const canSave = form.name.trim().length > 0 && (!hasPrice || Number(form.price_addition) >= 0);
  const create = async () => {
    if (!canSave) return;
    setSaving(true); setError(""); setSaved(false);
    try {
      const data = { name: form.name.trim(), description: form.description.trim() || null, sort_order: Number(form.sort_order) || 0, active: true, ...(hasPrice ? { price_addition: Number(form.price_addition) || 0 } : { is_default: form.is_default }) };
      const created = await api.create(data as never);
      setItems((current) => [...current, created].sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name)));
      setForm({ name: "", description: "", price_addition: "", sort_order: "0", is_default: false }); setSaved(true);
    } catch (e) { setError(e instanceof Error ? e.message : "Nao foi possivel salvar."); }
    finally { setSaving(false); }
  };
  const toggle = async (item: ApiGlobalCatalogItem) => {
    try { const updated = await api.update(item.id, { active: !item.active } as never); setItems((current) => current.map((x) => x.id === item.id ? updated : x)); }
    catch (e) { setError(e instanceof Error ? e.message : "Nao foi possivel atualizar."); }
  };
  const title = useMemo(() => labels[kind], [kind]);
  return <section className="mt-6 rounded-xl border border-surface-03 bg-surface-02 p-5 space-y-4">
    <div><h3 className="text-cream font-bold">Configurações Gerais do Catálogo</h3><p className="text-stone text-sm">Cadastros globais reutilizáveis por pizzas, sem alterar produtos ou pedidos existentes.</p></div>
    <div className="flex flex-wrap gap-2">{(Object.keys(labels) as Kind[]).map((value) => <button key={value} type="button" onClick={() => setKind(value)} className={`rounded-lg px-3 py-2 text-sm font-bold ${kind === value ? "bg-gold text-cream" : "bg-surface-03 text-stone"}`}>{labels[value]}</button>)}</div>
    <div className="grid gap-2 md:grid-cols-[1fr,1fr,120px,auto]">
      <input className="rounded-lg bg-surface-03 px-3 py-2 text-cream" placeholder={`Nome de ${title.toLowerCase()}`} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
      <input className="rounded-lg bg-surface-03 px-3 py-2 text-cream" placeholder="Descrição opcional" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
      {hasPrice ? <input className="rounded-lg bg-surface-03 px-3 py-2 text-cream" type="number" min="0" step="0.01" placeholder="Adicional" value={form.price_addition} onChange={(e) => setForm({ ...form, price_addition: e.target.value })} /> : <input className="rounded-lg bg-surface-03 px-3 py-2 text-cream" type="number" min="0" placeholder="Ordem" value={form.sort_order} onChange={(e) => setForm({ ...form, sort_order: e.target.value })} />}
      <button type="button" disabled={!canSave || saving} onClick={() => void create()} className="flex items-center justify-center gap-2 rounded-lg bg-gold px-4 py-2 font-bold text-cream disabled:opacity-50">{saving ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}Adicionar</button>
    </div>
    {kind === "sizes" && <label className="flex items-center gap-2 text-sm text-parchment"><input type="checkbox" checked={form.is_default} onChange={(e) => setForm({ ...form, is_default: e.target.checked })} /> Definir como tamanho padrão</label>}
    {error && <div role="alert" className="rounded-lg border border-red-400/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</div>}
    {saved && <div role="status" className="flex items-center gap-2 text-sm text-emerald-300"><Check size={15} /> Cadastro salvo.</div>}
    {loading ? <div className="flex items-center gap-2 text-stone"><Loader2 size={16} className="animate-spin" /> Carregando...</div> : items.length === 0 ? <p className="text-sm text-stone">Nenhum cadastro global ainda.</p> : <div className="space-y-2">{items.map((item) => <div key={item.id} className="flex items-center gap-3 rounded-lg border border-surface-03 bg-surface-01 p-3"><div className="min-w-0 flex-1"><p className={`font-bold ${item.active ? "text-cream" : "text-stone line-through"}`}>{item.name}</p><p className="text-xs text-stone">{item.description || "Sem descrição"}{kind !== "sizes" ? ` · + R$ ${(item.price_addition || 0).toFixed(2)}` : item.is_default ? " · padrão" : ""}</p></div><button type="button" onClick={() => void toggle(item)} className="text-xs text-stone hover:text-gold">{item.active ? "Inativar" : "Ativar"}</button><X size={14} className="text-stone/40" /></div>)}</div>}
  </section>;
}
