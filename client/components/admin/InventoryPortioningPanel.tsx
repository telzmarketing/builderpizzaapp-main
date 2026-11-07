import { useEffect, useState } from "react";
import { Loader2, Plus, RefreshCw, X } from "lucide-react";
import { inventoryApi, type InventoryItem, type InventoryOverview, type InventoryPortionConfig } from "@/lib/api";

const input = "w-full rounded-lg border border-surface-03 bg-surface-01 px-3 py-2 text-sm text-cream outline-none placeholder:text-stone/70 focus:border-gold";
const button = "inline-flex items-center justify-center gap-2 rounded-lg bg-gold px-3 py-2 text-sm font-black text-black disabled:cursor-not-allowed disabled:opacity-60";
const ghost = "inline-flex items-center justify-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm font-bold text-stone hover:bg-surface-03 hover:text-cream";

function key(prefix: string) {
  return `${prefix}:${crypto.randomUUID()}`;
}

export default function InventoryPortioningPanel() {
  const [overview, setOverview] = useState<InventoryOverview | null>(null);
  const [configs, setConfigs] = useState<InventoryPortionConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [form, setForm] = useState({ source_item_id: "", usage: "mandatory" as InventoryPortionConfig["usage"], portion_weight: "", unit_id: "", reference_fraction: "0.5", size: "", min_stock: "0", target_stock: "0", shelf_life_days: "", yield_percent: "100", loss_percent: "0" });

  async function load() {
    setLoading(true); setError("");
    try {
      const [nextOverview, nextConfigs] = await Promise.all([inventoryApi.overview(), inventoryApi.portionConfigs(true)]);
      setOverview(nextOverview); setConfigs(nextConfigs);
      if (!form.unit_id && nextOverview.units[0]) setForm((current) => ({ ...current, unit_id: nextOverview.units[0].id }));
    } catch (err) { setError(err instanceof Error ? err.message : "Falha ao carregar porcionamentos."); }
    finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, []);

  async function save() {
    setSaving(true); setMessage(""); setError("");
    try {
      if (!form.source_item_id || !form.portion_weight || !form.unit_id) throw new Error("Informe insumo, peso e unidade.");
      const min = Number(form.min_stock); const target = Number(form.target_stock);
      if (target < min) throw new Error("O estoque-alvo deve ser maior ou igual ao mínimo.");
      await inventoryApi.createPortionConfig({ source_item_id: form.source_item_id, usage: form.usage, portion_weight: Number(form.portion_weight), unit_id: form.unit_id, reference_fraction: Number(form.reference_fraction), size: form.size || null, min_stock: min, target_stock: target, shelf_life_days: form.shelf_life_days ? Number(form.shelf_life_days) : null, yield_percent: Number(form.yield_percent), loss_percent: Number(form.loss_percent), active: true }, key("create-portion"));
      setMessage("Configuração de porcionamento cadastrada.");
      setForm((current) => ({ ...current, source_item_id: "", portion_weight: "", size: "", min_stock: "0", target_stock: "0", shelf_life_days: "" }));
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Não foi possível cadastrar a configuração."); }
    finally { setSaving(false); }
  }

  async function deactivate(config: InventoryPortionConfig) {
    if (!window.confirm(`Desativar ${config.output_item_name || "esta configuração"}? O histórico será preservado.`)) return;
    setSaving(true); setMessage(""); setError("");
    try { await inventoryApi.deactivatePortionConfig(config.id, key(`deactivate-portion:${config.id}`)); setMessage("Configuração desativada."); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : "Não foi possível desativar."); }
    finally { setSaving(false); }
  }

  if (loading) return <div className="flex min-h-40 items-center justify-center text-stone"><Loader2 size={18} className="mr-2 animate-spin" />Carregando porcionamentos...</div>;
  const rawItems = (overview?.items ?? []).filter((item: InventoryItem) => item.active && item.item_type !== "finished_good");

  return <section className="space-y-5 rounded-lg border border-surface-03 bg-surface-02 p-5">
    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"><div><h2 className="text-lg font-black text-cream">Cadastro de Porcionamento</h2><p className="mt-1 text-sm text-stone">Configure a transformação de um insumo existente em produto porcionado. O cadastro não movimenta estoque.</p></div><button type="button" className={ghost} onClick={() => void load()}><RefreshCw size={15} /> Atualizar</button></div>
    <div className="grid gap-5 xl:grid-cols-[24rem_minmax(0,1fr)]">
      <div className="rounded-lg border border-surface-03 bg-surface-01 p-4"><h3 className="font-black text-cream">Nova configuração</h3><div className="mt-4 space-y-3">
        <label className="block text-xs text-stone">Insumo de origem<select className={input} value={form.source_item_id} onChange={(e) => setForm({ ...form, source_item_id: e.target.value })}><option value="">Selecione o insumo</option>{rawItems.map((item) => <option key={item.id} value={item.id}>{item.name}{item.unit_symbol ? ` (${item.unit_symbol})` : ""}</option>)}</select></label>
        <label className="block text-xs text-stone">Uso operacional<select className={input} value={form.usage} onChange={(e) => setForm({ ...form, usage: e.target.value as InventoryPortionConfig["usage"] })}><option value="mandatory">Porcionamento obrigatório</option><option value="optional">Porcionamento opcional</option><option value="direct">Utilização direta</option></select></label>
        <div className="grid grid-cols-2 gap-3"><label className="block text-xs text-stone">Peso padrão<input className={input} type="number" min="0.000001" step="0.000001" value={form.portion_weight} onChange={(e) => setForm({ ...form, portion_weight: e.target.value })} /></label><label className="block text-xs text-stone">Unidade<select className={input} value={form.unit_id} onChange={(e) => setForm({ ...form, unit_id: e.target.value })}>{(overview?.units ?? []).map((unit) => <option key={unit.id} value={unit.id}>{unit.name} ({unit.symbol})</option>)}</select></label></div>
        <div className="grid grid-cols-2 gap-3"><label className="block text-xs text-stone">Referência<select className={input} value={form.reference_fraction} onChange={(e) => setForm({ ...form, reference_fraction: e.target.value })}><option value="0.5">Meia pizza</option><option value="1">Pizza inteira</option></select></label><label className="block text-xs text-stone">Tamanho<input className={input} placeholder="Ex.: Grande" value={form.size} onChange={(e) => setForm({ ...form, size: e.target.value })} /></label></div>
        <div className="grid grid-cols-2 gap-3"><label className="block text-xs text-stone">Estoque mínimo<input className={input} type="number" min="0" step="0.001" value={form.min_stock} onChange={(e) => setForm({ ...form, min_stock: e.target.value })} /></label><label className="block text-xs text-stone">Estoque-alvo<input className={input} type="number" min="0" step="0.001" value={form.target_stock} onChange={(e) => setForm({ ...form, target_stock: e.target.value })} /></label></div>
        <div className="grid grid-cols-3 gap-3"><label className="block text-xs text-stone">Validade (dias)<input className={input} type="number" min="0" value={form.shelf_life_days} onChange={(e) => setForm({ ...form, shelf_life_days: e.target.value })} /></label><label className="block text-xs text-stone">Rendimento %<input className={input} type="number" min="0.01" max="100" step="0.01" value={form.yield_percent} onChange={(e) => setForm({ ...form, yield_percent: e.target.value })} /></label><label className="block text-xs text-stone">Perda %<input className={input} type="number" min="0" max="99.99" step="0.01" value={form.loss_percent} onChange={(e) => setForm({ ...form, loss_percent: e.target.value })} /></label></div>
        <button type="button" className={button} disabled={saving || !rawItems.length} onClick={() => void save()}><Plus size={15} /> Cadastrar porcionamento</button>
      </div></div>
      <div className="overflow-x-auto rounded-lg border border-surface-03"><div className="grid min-w-[900px] grid-cols-[1.4fr_1.4fr_.8fr_.8fr_1fr_.8fr_auto] gap-3 bg-surface-01 px-4 py-3 text-xs font-black uppercase tracking-wide text-stone"><span>Porção</span><span>Matéria-prima</span><span>Peso</span><span>Referência</span><span>Uso</span><span>Estoque</span><span /></div>{configs.map((config) => <div key={config.id} className="grid min-w-[900px] grid-cols-[1.4fr_1.4fr_.8fr_.8fr_1fr_.8fr_auto] items-center gap-3 border-t border-surface-03 bg-surface-01 px-4 py-3 text-sm"><span className="font-bold text-cream">{config.output_item_name}<small className="block text-stone">{config.output_item_sku || ""}</small></span><span className="text-stone">{config.source_item_name}</span><span className="text-stone">{config.portion_weight} {config.unit_symbol || ""}</span><span className="text-stone">{config.reference_fraction === 0.5 ? "Meia pizza" : "Inteira"}{config.size ? ` · ${config.size}` : ""}</span><span className="text-stone">{config.usage === "mandatory" ? "Obrigatório" : config.usage === "optional" ? "Opcional" : "Direto"}</span><span className="text-stone">{config.min_stock} / {config.target_stock}</span><button type="button" className="text-stone hover:text-red-300" disabled={saving} onClick={() => void deactivate(config)} aria-label="Desativar configuração"><X size={16} /></button></div>)}{!configs.length && <p className="px-4 py-10 text-center text-sm text-stone">Nenhuma configuração de porcionamento cadastrada.</p>}</div>
    </div>
    {message && <p className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">{message}</p>}{error && <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</p>}
  </section>;
}
