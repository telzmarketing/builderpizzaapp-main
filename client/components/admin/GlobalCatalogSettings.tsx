import { useEffect, useMemo, useState } from "react";
import { Check, Loader2, Pencil, Plus, X } from "lucide-react";
import { globalCatalogApi, ApiGlobalCatalogItem } from "@/lib/api";

type Kind = "sizes" | "doughTypes" | "crusts";
const labels: Record<Kind, string> = { sizes: "Tamanhos de pizza", doughTypes: "Tipos de massa", crusts: "Bordas de pizza" };
type Form = { name: string; description: string; price_addition: string; sort_order: string; is_default: boolean };
const emptyForm = (): Form => ({ name: "", description: "", price_addition: "", sort_order: "0", is_default: false });

export default function GlobalCatalogSettings() {
  const [kind, setKind] = useState<Kind>("sizes");
  const [items, setItems] = useState<ApiGlobalCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<Form>(emptyForm());
  const [editForm, setEditForm] = useState<Form>(emptyForm());
  const api = globalCatalogApi[kind];
  const hasPrice = kind !== "sizes";

  const load = async () => {
    setLoading(true); setError("");
    try { setItems(await api.list()); } catch (e) { setError(e instanceof Error ? e.message : "Nao foi possivel carregar as configuracoes."); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); setEditingId(null); }, [kind]);

  const toPayload = (value: Form) => ({
    name: value.name.trim(), description: value.description.trim() || null,
    sort_order: Number(value.sort_order) || 0, active: true,
    ...(hasPrice ? { price_addition: Number(value.price_addition) || 0 } : { is_default: value.is_default }),
  });
  const canSave = form.name.trim().length > 0 && (!hasPrice || Number(form.price_addition) >= 0);
  const create = async () => {
    if (!canSave) return;
    setSaving(true); setError(""); setSaved(false);
    try {
      const created = await api.create(toPayload(form) as never);
      setItems((current) => [...current, created].sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name)));
      setForm(emptyForm()); setSaved(true);
    } catch (e) { setError(e instanceof Error ? e.message : "Nao foi possivel salvar."); }
    finally { setSaving(false); }
  };
  const startEdit = (item: ApiGlobalCatalogItem) => {
    setEditingId(item.id); setError("");
    setEditForm({ name: item.name, description: item.description || "", price_addition: String(item.price_addition ?? 0), sort_order: String(item.sort_order), is_default: Boolean(item.is_default) });
  };
  const saveEdit = async (item: ApiGlobalCatalogItem) => {
    if (!editForm.name.trim()) return;
    setSaving(true); setError("");
    try {
      const updated = await api.update(item.id, { name: editForm.name.trim(), description: editForm.description.trim() || null, sort_order: Number(editForm.sort_order) || 0, ...(hasPrice ? { price_addition: Number(editForm.price_addition) || 0 } : { is_default: editForm.is_default }) } as never);
      setItems((current) => current.map((x) => x.id === item.id ? updated : x)); setEditingId(null);
    } catch (e) { setError(e instanceof Error ? e.message : "Nao foi possivel editar."); }
    finally { setSaving(false); }
  };
  const toggle = async (item: ApiGlobalCatalogItem) => {
    try { const updated = await api.update(item.id, { active: !item.active } as never); setItems((current) => current.map((x) => x.id === item.id ? updated : x)); }
    catch (e) { setError(e instanceof Error ? e.message : "Nao foi possivel atualizar."); }
  };
  const remove = async (item: ApiGlobalCatalogItem) => {
    if (!window.confirm(`Excluir ${item.name} definitivamente do banco?`)) return;
    setDeletingId(item.id); setError("");
    try { await api.remove(item.id); setItems((current) => current.filter((x) => x.id !== item.id)); }
    catch (e) { setError(e instanceof Error ? e.message : "Nao foi possivel excluir. A borda pode estar vinculada a um produto."); }
    finally { setDeletingId(null); }
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
    {loading ? <div className="flex items-center gap-2 text-stone"><Loader2 size={16} className="animate-spin" /> Carregando...</div> : items.length === 0 ? <p className="text-sm text-stone">Nenhum cadastro global ainda.</p> : <div className="space-y-2">{items.map((item) => editingId === item.id ? <div key={item.id} className="rounded-lg border border-gold/50 bg-surface-01 p-3 space-y-2"><div className="grid gap-2 md:grid-cols-2"><input className="rounded-lg bg-surface-03 px-3 py-2 text-cream" aria-label="Nome da borda" value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} /><input className="rounded-lg bg-surface-03 px-3 py-2 text-cream" aria-label="Descrição da borda" value={editForm.description} onChange={(e) => setEditForm({ ...editForm, description: e.target.value })} />{hasPrice && <input className="rounded-lg bg-surface-03 px-3 py-2 text-cream" type="number" min="0" step="0.01" aria-label="Adicional da borda" value={editForm.price_addition} onChange={(e) => setEditForm({ ...editForm, price_addition: e.target.value })} />}<input className="rounded-lg bg-surface-03 px-3 py-2 text-cream" type="number" min="0" aria-label="Ordem" value={editForm.sort_order} onChange={(e) => setEditForm({ ...editForm, sort_order: e.target.value })} /></div><div className="flex gap-2"><button type="button" onClick={() => void saveEdit(item)} disabled={saving || !editForm.name.trim()} className="rounded-lg bg-gold px-3 py-2 text-sm font-bold text-cream">Salvar</button><button type="button" onClick={() => setEditingId(null)} className="rounded-lg bg-surface-03 px-3 py-2 text-sm text-stone">Cancelar</button></div></div> : <div key={item.id} className="flex items-center gap-3 rounded-lg border border-surface-03 bg-surface-01 p-3"><div className="min-w-0 flex-1"><p className={`font-bold ${item.active ? "text-cream" : "text-stone line-through"}`}>{item.name}</p><p className="text-xs text-stone">{item.description || "Sem descrição"}{kind !== "sizes" ? ` · + R$ ${(item.price_addition || 0).toFixed(2)}` : item.is_default ? " · padrão" : ""}</p></div><button type="button" onClick={() => startEdit(item)} aria-label={`Editar ${item.name}`} className="text-stone hover:text-gold"><Pencil size={14} /></button><button type="button" onClick={() => void toggle(item)} className="text-xs text-stone hover:text-gold">{item.active ? "Inativar" : "Ativar"}</button><button type="button" aria-label={`Excluir ${item.name}`} disabled={deletingId === item.id} onClick={() => void remove(item)} className="text-stone/60 hover:text-red-300 disabled:opacity-50"><X size={14} /></button></div>)}</div>}
  </section>;
}
