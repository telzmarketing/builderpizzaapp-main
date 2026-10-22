import { useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowUp, Loader2, Plus, Trash2, X } from "lucide-react";
import {
  inventoryApi, inventoryFoundationApi, productRecipesApi,
  type ApiProduct, type FoundationUnit, type InventoryItem,
  type OperationalRecipeInput, type OperationalRecipeVersion,
  type RecipeCompositionPreview,
  type RecipeCompositionCustomization,
} from "@/lib/api";

const input = "w-full rounded-lg border border-surface-03 bg-surface-01 p-2 text-sm text-cream disabled:opacity-50";
const button = "rounded-lg border border-surface-03 px-3 py-2 text-sm text-parchment disabled:opacity-50";
const decimal = (value: string) => value.trim().replace(",", ".");
type Ingredient = { inventory_item_id: string; entered_quantity: string; entered_unit_id: string; waste_percent: string; notes: string; public_name: string; show_public: boolean; allow_removal: boolean };
type Form = {
  component_role: OperationalRecipeVersion["component_role"]; reference_fraction: string;
  product_size_id: string; product_crust_type_id: string; product_drink_variant_id: string;
  complement_key: string; complement_name: string; active: boolean; notes: string;
  instructions: string; preparation_steps: string[]; reference_image_url: string;
  items: Ingredient[];
};
const emptyIngredient = (): Ingredient => ({ inventory_item_id: "", entered_quantity: "", entered_unit_id: "", waste_percent: "0", notes: "", public_name: "", show_public: false, allow_removal: false });
const emptyForm = (): Form => ({ component_role: "flavor", reference_fraction: "0.5", product_size_id: "", product_crust_type_id: "", product_drink_variant_id: "", complement_key: "", complement_name: "", active: true, notes: "", instructions: "", preparation_steps: [], reference_image_url: "", items: [emptyIngredient()] });

export function RecipePrivateImage({ url }: { url: string }) {
  const [source, setSource] = useState("");
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let alive = true;
    let local = "";
    setSource(""); setFailed(false);
    if (url) void productRecipesApi.imageBlob(url).then((blob) => {
      if (!alive) return;
      local = URL.createObjectURL(blob); setSource(local);
    }).catch(() => { if (alive) setFailed(true); });
    return () => { alive = false; if (local) URL.revokeObjectURL(local); };
  }, [url]);
  if (!url) return null;
  if (failed) return <p className="text-xs text-amber-300">Imagem indisponivel. A ficha permanece acessivel.</p>;
  return source ? <img src={source} alt="Referencia de montagem" className="max-h-48 rounded-lg object-contain" /> : <p className="text-xs text-stone">Carregando imagem privada…</p>;
}

export default function ProductRecipeEditor({ product, catalog, onClose }: { product: ApiProduct; catalog: ApiProduct[]; onClose: () => void }) {
  const [recipes, setRecipes] = useState<OperationalRecipeVersion[]>([]);
  const [latestVersion, setLatestVersion] = useState(0);
  const [ingredients, setIngredients] = useState<InventoryItem[]>([]);
  const [units, setUnits] = useState<FoundationUnit[]>([]);
  const [form, setForm] = useState<Form>(emptyForm);
  const [editing, setEditing] = useState<OperationalRecipeVersion | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [preview, setPreview] = useState<RecipeCompositionPreview | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewQuantity, setPreviewQuantity] = useState(1);
  const [flavors, setFlavors] = useState([product.id]);
  const [previewSize, setPreviewSize] = useState("");
  const [previewCrust, setPreviewCrust] = useState("");
  const [previewBorder, setPreviewBorder] = useState("");
  const [previewVariant, setPreviewVariant] = useState("");
  const [previewExtras, setPreviewExtras] = useState<string[]>([]);
  const [customizations, setCustomizations] = useState<RecipeCompositionCustomization[]>([]);
  const mounted = useRef(true);
  const saving = useRef(false);
  const keys = useRef(new Map<string, string>());

  async function load() {
    setLoading(true); setError("");
    try {
      const [history, overview, unitList] = await Promise.all([productRecipesApi.list(product.id), inventoryApi.overview(), inventoryFoundationApi.units()]);
      if (!mounted.current) return;
      setRecipes(history.items); setLatestVersion(history.latest_version); setIngredients(overview.items ?? []); setUnits(unitList.items ?? []);
    } catch (e) { if (mounted.current) setError(e instanceof Error ? e.message : "Falha ao carregar fichas."); }
    finally { if (mounted.current) setLoading(false); }
  }
  useEffect(() => { mounted.current = true; void load(); return () => { mounted.current = false; }; }, [product.id]);
  const patch = (values: Partial<Form>) => { setForm((current) => ({ ...current, ...values })); setMessage(""); };
  const updateIngredient = (index: number, values: Partial<Ingredient>) => setForm((current) => ({ ...current, items: current.items.map((row, position) => position === index ? { ...row, ...values } : row) }));
  const move = (index: number, direction: number) => setForm((current) => {
    const rows = [...current.items]; const other = index + direction;
    if (other < 0 || other >= rows.length) return current;
    [rows[index], rows[other]] = [rows[other], rows[index]];
    return { ...current, items: rows };
  });
  function edit(recipe: OperationalRecipeVersion) {
    setEditing(recipe.active ? recipe : null); setError(""); setMessage("");
    setForm({ component_role: recipe.component_role, reference_fraction: String(recipe.reference_fraction),
      product_size_id: recipe.product_size_id ?? "", product_crust_type_id: recipe.product_crust_type_id ?? "", product_drink_variant_id: recipe.product_drink_variant_id ?? "",
      complement_key: recipe.complement_key ?? "", complement_name: recipe.complement_name ?? "", active: recipe.active,
      notes: recipe.notes ?? "", instructions: recipe.instructions ?? "", preparation_steps: [...(recipe.preparation_steps ?? [])], reference_image_url: recipe.reference_image_url ?? "",
      items: [...(recipe.items ?? [])].sort((a, b) => a.position - b.position).map((row) => ({ inventory_item_id: row.inventory_item_id,
        entered_quantity: String(row.entered_quantity ?? row.quantity), entered_unit_id: row.entered_unit_id ?? row.unit_id ?? ingredients.find((item) => item.id === row.inventory_item_id)?.unit_id ?? "",
        waste_percent: String(row.waste_percent ?? "0"), notes: row.notes ?? "", public_name: row.public_name ?? "", show_public: row.show_public ?? false, allow_removal: row.allow_removal ?? false })) });
  }
  function payload(): OperationalRecipeInput {
    if (!form.items.length || form.items.some((row) => !row.inventory_item_id || !row.entered_quantity.trim() || !row.entered_unit_id)) throw new Error("Preencha todos os insumos, quantidades e unidades. Nenhuma linha sera descartada ao salvar.");
    if (form.preparation_steps.some((step) => !step.trim())) throw new Error("Preencha ou remova as etapas vazias.");
    return { expected_version: editing?.version_number ?? latestVersion,
      component_role: form.component_role, reference_fraction: decimal(form.reference_fraction), product_size_id: form.product_size_id || null,
      product_crust_type_id: form.product_crust_type_id || null, product_drink_variant_id: form.product_drink_variant_id || null,
      complement_key: form.complement_key.trim() || null, complement_name: form.complement_name.trim() || null, active: form.active,
      notes: form.notes.trim() || null, instructions: form.instructions.trim() || null, preparation_steps: form.preparation_steps.map((step) => step.trim()),
      reference_image_url: form.reference_image_url || null,
      items: form.items.map((row, position) => ({ inventory_item_id: row.inventory_item_id,
        // The backend derives base quantity/unit from these explicit entered values.
        unit_id: ingredients.find((item) => item.id === row.inventory_item_id)?.unit_id ?? null,
        entered_quantity: decimal(row.entered_quantity), entered_unit_id: row.entered_unit_id,
        waste_percent: decimal(row.waste_percent || "0"), position, notes: row.notes.trim() || null,
        public_name: row.public_name.trim() || null, show_public: row.show_public, allow_removal: row.allow_removal })) };
  }
  async function save() {
    if (saving.current) return;
    setError(""); setMessage("");
    let body: OperationalRecipeInput;
    try { body = payload(); } catch (e) { setError((e as Error).message); return; }
    const identity = JSON.stringify([editing?.id ?? "new", body]);
    const key = keys.current.get(identity) ?? crypto.randomUUID(); keys.current.set(identity, key);
    saving.current = true; setBusy(true);
    try {
      if (editing) await productRecipesApi.update(product.id, editing.id, body, key);
      else await productRecipesApi.create(product.id, body, key);
      if (!mounted.current) return;
      // Read authoritative activation/history after publishing; no scope rules in React.
      setEditing(null); setForm(emptyForm()); setPreview(null); await load(); setMessage("Nova versao publicada. O historico anterior foi preservado.");
    } catch (e) { if (mounted.current) setError(e instanceof Error ? e.message : "Falha ao publicar ficha. Repetir reutiliza a mesma chave."); }
    finally { saving.current = false; if (mounted.current) setBusy(false); }
  }
  async function upload(file?: File) {
    if (!file) return;
    setUploading(true); setError("");
    try { const image = await productRecipesApi.uploadImage(file); if (mounted.current) patch({ reference_image_url: image.url }); }
    catch (e) { if (mounted.current) setError(e instanceof Error ? e.message : "Falha no envio da imagem."); }
    finally { if (mounted.current) setUploading(false); }
  }
  async function archive(recipe: OperationalRecipeVersion) {
    if (saving.current || !window.confirm(`Arquivar v${recipe.version_number}? O historico sera preservado.`)) return;
    const identity = `archive:${recipe.id}:${recipe.version_number}`;
    const key = keys.current.get(identity) ?? crypto.randomUUID(); keys.current.set(identity, key);
    saving.current = true; setBusy(true); setError("");
    try {
      await productRecipesApi.archive(product.id, recipe.id, recipe.version_number, key);
      if (!mounted.current) return;
      if (editing?.id === recipe.id) { setEditing(null); setForm(emptyForm()); }
      setPreview(null); await load(); setMessage("Versao arquivada; historico preservado.");
    } catch (e) { if (mounted.current) setError(e instanceof Error ? e.message : "Falha ao arquivar."); }
    finally { saving.current = false; if (mounted.current) setBusy(false); }
  }
  async function simulate() {
    setPreviewBusy(true); setError(""); setPreview(null);
    try {
      const result = await productRecipesApi.preview({ product_id: product.id, quantity: previewQuantity,
        selected_size_id: previewSize || null, selected_crust_type_id: previewCrust || null,
        selected_border_id: previewBorder || null,
        selected_drink_variant_id: previewVariant || null,
        flavors: flavors.filter(Boolean).map((product_id) => ({ product_id })),
        add_ons: previewExtras, customizations });
      if (mounted.current) setPreview(result);
    } catch (e) { if (mounted.current) setError(e instanceof Error ? e.message : "Falha na simulacao."); }
    finally { if (mounted.current) setPreviewBusy(false); }
  }

  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-2 sm:p-4" role="dialog" aria-modal="true" aria-labelledby="recipe-title">
    <div className="flex max-h-[96dvh] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-surface-03 bg-surface-02 text-parchment">
      <header className="flex items-center justify-between border-b border-surface-03 p-4"><div><h2 id="recipe-title" className="font-bold text-cream">Ficha tecnica — {product.name}</h2><p className="text-xs text-stone">Receitas vinculadas ao cadastro comercial. Alteracoes publicam uma nova versao.</p></div><button className={button} onClick={onClose} disabled={busy || uploading} aria-label="Fechar ficha tecnica"><X size={20} /></button></header>
      <div className="overflow-y-auto p-4">
        {error && <div role="alert" className="mb-3 rounded border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">{error}<button className={`${button} ml-3`} onClick={() => void load()} disabled={busy}>Atualizar dados</button></div>}
        {message && <p role="status" className="mb-3 text-sm text-emerald-300">{message}</p>}
        {loading ? <p className="flex items-center gap-2 py-10"><Loader2 className="animate-spin" size={18} />Carregando fichas, insumos e unidades…</p> : <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
          <section className="min-w-0 space-y-4">
            <fieldset disabled={busy || uploading} className="space-y-4">
              <legend className="mb-2 font-bold">{editing ? `Nova versao a partir de v${editing.version_number}` : "Nova ficha"}</legend>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="text-xs">Componente<select className={input} value={form.component_role} onChange={(e) => patch({ component_role: e.target.value as Form["component_role"] })}><option value="flavor">Sabor</option><option value="base">Base</option><option value="crust">Massa / borda</option><option value="addon">Adicional</option><option value="packaging">Embalagem</option></select></label>
                <label className="text-xs">Referencia das quantidades<select className={input} value={form.reference_fraction} onChange={(e) => patch({ reference_fraction: e.target.value })}><option value="0.5">Meia pizza (1/2)</option><option value="1">Uma unidade inteira</option>{!["0.5", "1"].includes(form.reference_fraction) && <option value={form.reference_fraction}>{form.reference_fraction} da unidade (historico)</option>}</select></label>
                <label className="text-xs">Tamanho<select className={input} value={form.product_size_id} onChange={(e) => patch({ product_size_id: e.target.value })}><option value="">Sem tamanho especifico</option>{product.sizes?.map((row) => <option key={row.id} value={row.id}>{row.label}</option>)}</select></label>
                <label className="text-xs">Massa / borda<select className={input} value={form.product_crust_type_id} onChange={(e) => patch({ product_crust_type_id: e.target.value })}><option value="">Sem opcao especifica</option>{product.crust_types?.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
                <label className="text-xs">Variante<select className={input} value={form.product_drink_variant_id} onChange={(e) => patch({ product_drink_variant_id: e.target.value })}><option value="">Sem variante especifica</option>{product.drink_variants?.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
                <label className="text-xs">Chave do adicional<input className={input} value={form.complement_key} onChange={(e) => patch({ complement_key: e.target.value })} /></label>
                <label className="text-xs">Nome do adicional<input className={input} value={form.complement_name} onChange={(e) => patch({ complement_name: e.target.value })} /></label>
              </div>
              <p className="text-xs text-stone">Base e embalagem usam referencia de unidade inteira. Confirmar a referencia faz parte da ficha; os valores nao sao alterados automaticamente.</p>
              <div className="flex items-center justify-between"><h3 className="font-bold">Insumos na ordem de montagem</h3><button type="button" className={button} onClick={() => patch({ items: [...form.items, emptyIngredient()] })}><Plus size={14} className="inline" /> Insumo</button></div>
              {!ingredients.some((row) => row.active) && <p className="text-amber-300">Cadastre insumos e classifique suas unidades em Gestao → Estoque.</p>}
              {form.items.map((row, index) => {
                const selected = ingredients.find((item) => item.id === row.inventory_item_id);
                return <div key={index} className="space-y-2 rounded-lg border border-surface-03 bg-surface-01 p-3">
                  <div className="flex items-center justify-between"><span className="text-xs">Ingrediente {index + 1}</span><div className="flex gap-1"><button type="button" className={button} disabled={index === 0} onClick={() => move(index, -1)} aria-label={`Subir ingrediente ${index + 1}`}><ArrowUp size={14} /></button><button type="button" className={button} disabled={index === form.items.length - 1} onClick={() => move(index, 1)} aria-label={`Descer ingrediente ${index + 1}`}><ArrowDown size={14} /></button><button type="button" className={button} onClick={() => patch({ items: form.items.filter((_, position) => position !== index) })} aria-label={`Remover ingrediente ${index + 1}`}><Trash2 size={14} /></button></div></div>
                  <div className="grid gap-2 sm:grid-cols-2"><label className="text-xs">Insumo<select className={input} value={row.inventory_item_id} onChange={(e) => updateIngredient(index, { inventory_item_id: e.target.value, entered_unit_id: ingredients.find((item) => item.id === e.target.value)?.unit_id ?? "", entered_quantity: "" })}><option value="">Selecione</option>{ingredients.filter((item) => item.active || item.id === row.inventory_item_id).map((item) => <option key={item.id} value={item.id}>{item.name}{!item.active ? " (inativo)" : ""}</option>)}</select></label>
                  <label className="text-xs">Quantidade informada<input className={input} value={row.entered_quantity} onChange={(e) => updateIngredient(index, { entered_quantity: e.target.value })} inputMode="decimal" /></label>
                  <label className="text-xs">Unidade informada<select className={input} value={row.entered_unit_id} onChange={(e) => updateIngredient(index, { entered_unit_id: e.target.value })}><option value="">Selecione unidade confirmada</option>{units.filter((unit) => (unit.active && unit.dimension) || unit.id === row.entered_unit_id).map((unit) => <option key={unit.id} value={unit.id}>{unit.name} ({unit.symbol}){!unit.dimension ? " — classificar no estoque" : ""}</option>)}</select></label>
                  <label className="text-xs">Perda tecnica (%)<input className={input} value={row.waste_percent} onChange={(e) => updateIngredient(index, { waste_percent: e.target.value })} inputMode="decimal" /></label></div>
                  <p className="text-xs text-stone">Unidade base: {selected?.unit_symbol ?? "nao definida"}. A conversao e validada no servidor ao publicar.</p>
                  <label className="block text-xs">Observacao do ingrediente<input className={input} value={row.notes} onChange={(e) => updateIngredient(index, { notes: e.target.value })} /></label>
                  <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={row.show_public} onChange={(e) => updateIngredient(index, { show_public: e.target.checked })} />Exibir nome comercial no catalogo</label>
                  <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={row.allow_removal} onChange={(e) => updateIngredient(index, { allow_removal: e.target.checked })} />Permitir retirada / substituicao deste ingrediente</label>
                  {row.show_public && <label className="block text-xs">Nome publico do ingrediente<input className={input} value={row.public_name} onChange={(e) => updateIngredient(index, { public_name: e.target.value })} maxLength={180} /></label>}
                </div>;
              })}
              <label className="block text-xs">Instrucoes de montagem<textarea className={input} rows={3} value={form.instructions} onChange={(e) => patch({ instructions: e.target.value })} /></label>
              <div className="space-y-2"><div className="flex justify-between"><h3 className="font-bold">Etapas</h3><button className={button} type="button" onClick={() => patch({ preparation_steps: [...form.preparation_steps, ""] })}>Adicionar etapa</button></div>{form.preparation_steps.map((step, index) => <div key={index} className="flex gap-2"><label className="flex-1 text-xs">Etapa {index + 1}<textarea className={input} value={step} onChange={(e) => patch({ preparation_steps: form.preparation_steps.map((text, position) => position === index ? e.target.value : text) })} /></label><button className={button} type="button" aria-label={`Remover etapa ${index + 1}`} onClick={() => patch({ preparation_steps: form.preparation_steps.filter((_, position) => position !== index) })}><Trash2 size={14} /></button></div>)}</div>
              <label className="block text-xs">Observacao interna<textarea className={input} value={form.notes} onChange={(e) => patch({ notes: e.target.value })} /></label>
              <div className="space-y-2"><label className="block text-xs">Imagem privada de referencia<input className={input} type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => { void upload(e.target.files?.[0]); e.target.value = ""; }} /></label>{form.reference_image_url && <><RecipePrivateImage url={form.reference_image_url} /><button type="button" className={button} onClick={() => patch({ reference_image_url: "" })}>Remover referencia desta nova versao</button></>}{uploading && <p role="status">Enviando imagem…</p>}</div>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.active} onChange={(e) => patch({ active: e.target.checked })} />Publicar ativa</label>
              <div className="flex flex-wrap gap-2"><button type="button" className={`${button} bg-gold text-black`} onClick={() => void save()} disabled={loading || !ingredients.length}>{busy ? "Publicando…" : "Publicar nova versao"}</button><button type="button" className={button} onClick={() => { setEditing(null); setForm(emptyForm()); }}>Limpar formulario</button></div>
            </fieldset>
            <section className="space-y-3 rounded-lg border border-surface-03 p-3" aria-label="Simulacao de composicao">
              <h3 className="font-bold">Simular composicao publicada</h3><p className="text-xs text-stone">Consulta fichas ativas no servidor. O formulario nao publicado nao participa desta simulacao. Nenhum estoque e movimentado.</p>
              <div className="grid gap-2 sm:grid-cols-2"><label className="text-xs">Quantidade de unidades<input className={input} type="number" min={1} max={1000} step={1} value={previewQuantity} onChange={(e) => { setPreviewQuantity(e.target.valueAsNumber); setPreview(null); }} /></label>
              <label className="text-xs">Tamanho<select className={input} value={previewSize} onChange={(e) => { setPreviewSize(e.target.value); setPreview(null); }}><option value="">Sem tamanho</option>{product.sizes?.map((row) => <option key={row.id} value={row.id}>{row.label}</option>)}</select></label>
              <label className="text-xs">Massa<select className={input} value={previewCrust} onChange={(e) => { setPreviewCrust(e.target.value); setPreview(null); }}><option value="">Sem opcao</option>{product.crust_types?.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
              <label className="text-xs">Borda<select className={input} value={previewBorder} onChange={(e) => { setPreviewBorder(e.target.value); setPreview(null); }}><option value="">Sem opcao</option>{product.crust_types?.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
              <label className="text-xs">Variante<select className={input} value={previewVariant} onChange={(e) => { setPreviewVariant(e.target.value); setPreview(null); }}><option value="">Sem variante</option>{product.drink_variants?.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label></div>
              {flavors.map((value, index) => <label key={index} className="block text-xs">Sabor {index + 1}<select className={input} value={value} onChange={(e) => { setFlavors((current) => current.map((id, position) => position === index ? e.target.value : id)); setPreview(null); }}>{catalog.filter((row) => row.product_type === "pizza" || row.id === product.id || row.id === value).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>)}
              <div className="flex gap-2"><button className={button} disabled={flavors.length >= 3} onClick={() => { setFlavors([...flavors, product.id]); setPreview(null); }}>Adicionar sabor</button><button className={button} disabled={flavors.length <= 1} onClick={() => { setFlavors(flavors.slice(0, -1)); setPreview(null); }}>Remover ultimo sabor</button></div>
              <fieldset className="space-y-1"><legend className="text-xs">Adicionais cadastrados para simulacao</legend>{recipes.filter((row) => row.active && row.component_role === "addon" && row.complement_key).map((row) => <label key={row.id} className="flex gap-2 text-xs"><input type="checkbox" checked={previewExtras.includes(row.complement_key!)} onChange={(e) => { setPreviewExtras((current) => e.target.checked ? [...new Set([...current, row.complement_key!])] : current.filter((key) => key !== row.complement_key)); setCustomizations((current) => current.map((change) => change.replacement_recipe_id === row.id ? { ...change, replacement_recipe_id: null } : change)); setPreview(null); }} />{row.complement_name || row.complement_key} (v{row.version_number})</label>)}{!recipes.some((row) => row.active && row.component_role === "addon" && row.complement_key) && <p className="text-xs text-stone">Nenhuma ficha de adicional ativa com chave cadastrada.</p>}</fieldset>
              <div className="space-y-2"><div className="flex justify-between"><h4 className="text-sm font-bold">Remocoes e substituicoes</h4><button className={button} onClick={() => { setCustomizations([...customizations, { action: "remove", inventory_item_id: "" }]); setPreview(null); }}>Adicionar alteracao</button></div>
              {customizations.map((change, index) => {
                const update = (values: Partial<RecipeCompositionCustomization>) => { setCustomizations((current) => current.map((row, position) => position === index ? { ...row, ...values } : row)); setPreview(null); };
                return <div key={index} className="space-y-2 rounded border border-surface-03 p-2"><div className="grid gap-2 sm:grid-cols-2"><label className="text-xs">Acao<select className={input} value={change.action} onChange={(e) => update({ action: e.target.value as RecipeCompositionCustomization["action"], replacement_recipe_id: null })}><option value="remove">Remover ingrediente</option><option value="substitute">Substituir com ficha de adicional</option></select></label>
                <label className="text-xs">Ingrediente<select className={input} value={change.inventory_item_id} onChange={(e) => update({ inventory_item_id: e.target.value })}><option value="">Selecione</option>{ingredients.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
                <label className="text-xs">Escopo por sabor<select className={input} value={change.scope_product_id ?? ""} onChange={(e) => update({ scope_product_id: e.target.value || null })}><option value="">Todos os sabores/componentes</option>{catalog.filter((row) => flavors.includes(row.id)).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
                <label className="text-xs">Escopo por componente<select className={input} value={change.scope_component_role ?? ""} onChange={(e) => update({ scope_component_role: (e.target.value || null) as RecipeCompositionCustomization["scope_component_role"] })}><option value="">Todos os componentes</option><option value="flavor">Sabor</option><option value="base">Base</option><option value="crust">Massa / borda</option><option value="addon">Adicional</option><option value="packaging">Embalagem</option></select></label>
                {change.action === "substitute" && <label className="text-xs">Ficha do adicional substituto<select className={input} value={change.replacement_recipe_id ?? ""} onChange={(e) => update({ replacement_recipe_id: e.target.value || null })}><option value="">Selecione adicional com opcao comercial marcada</option>{recipes.filter((row) => row.active && row.component_role === "addon" && (!row.complement_key || previewExtras.includes(row.complement_key)) && ((row.product_crust_type_id && [previewCrust, previewBorder].includes(row.product_crust_type_id)) || (row.product_drink_variant_id && row.product_drink_variant_id === previewVariant))).map((row) => <option key={row.id} value={row.id}>{row.complement_name || row.complement_key || row.id} — v{row.version_number}</option>)}</select><span className="text-stone">Exige ficha vinculada a massa/borda/variante selecionada; o servidor valida permissao e preco.</span></label>}</div><button className={button} onClick={() => { setCustomizations((current) => current.filter((_, position) => position !== index)); setPreview(null); }}>Remover alteracao {index + 1}</button></div>;
              })}</div>
              <button className={button} disabled={previewBusy || busy || !Number.isInteger(previewQuantity) || previewQuantity < 1} onClick={() => void simulate()}>{previewBusy ? "Consultando…" : "Calcular no servidor"}</button>
              {preview && <RecipeCompositionResult result={preview} />}
            </section>
          </section>
          <aside className="min-w-0 space-y-4"><h3 className="font-bold">Historico</h3>{!recipes.length && <p className="text-sm text-stone">Nenhuma ficha cadastrada. O cadastro comercial permanece disponivel.</p>}{recipes.map((recipe) => <article key={recipe.id} className="space-y-2 rounded-lg border border-surface-03 bg-surface-01 p-3"><div className="flex justify-between"><strong>v{recipe.version_number}</strong><span className="text-xs">{recipe.active ? "Ativa" : "Arquivada"}</span></div><p className="text-xs text-stone">{[recipe.component_role, recipe.product_size_label, recipe.product_crust_type_name, recipe.complement_name].filter(Boolean).join(" · ")}</p>{recipe.items?.map((row, index) => <p key={row.id ?? index} className="text-xs">{row.inventory_item_name ?? "Insumo"}: {row.quantity} {row.unit_symbol ?? ""}</p>)}{recipe.instructions && <p className="whitespace-pre-wrap text-xs">{recipe.instructions}</p>}{recipe.preparation_steps?.length > 0 && <ol className="list-inside list-decimal text-xs">{recipe.preparation_steps.map((step, index) => <li key={index}>{step}</li>)}</ol>}<RecipePrivateImage url={recipe.reference_image_url ?? ""} /><button className={button} disabled={busy} onClick={() => edit(recipe)}>Usar v{recipe.version_number} como referencia</button>{recipe.active && <button className={button} disabled={busy} onClick={() => void archive(recipe)}>Arquivar v{recipe.version_number}</button>}</article>)}</aside>
        </div>}
      </div>
    </div>
  </div>;
}

export function RecipeCompositionResult({ result }: { result: RecipeCompositionPreview }) {
  const rows = (items: RecipeCompositionPreview["ingredients"]) => <ul className="space-y-1 text-sm">{items.map((row, index) => <li key={`${row.inventory_item_id}:${index}`}>{row.name}: <strong>{row.quantity} {row.unit_symbol ?? ""}</strong></li>)}</ul>;
  return <div className="space-y-3 rounded-lg bg-surface-01 p-3" role="status">
    <p className={result.complete ? "text-emerald-300" : "text-amber-300"}>{result.complete ? "Composicao completa" : "Composicao incompleta — nao utilizar como receita completa"}</p>
    {!result.complete && <ul className="text-xs text-amber-300">{result.missing.map((value) => <li key={value}>{value}</li>)}</ul>}
    <h4 className="font-bold">Componentes comuns</h4>{rows(result.common_components)}
    {result.flavors.map((flavor, index) => <section key={index}><h4 className="font-bold">{flavor.name} — fracao {flavor.fraction}</h4>{rows(flavor.ingredients)}</section>)}
    <h4 className="font-bold">Total consolidado ({result.quantity} unidade(s))</h4>{rows(result.ingredients)}
    {result.removed_ingredients.length > 0 && <section><h4 className="font-bold text-amber-300">Ingredientes removidos</h4>{rows(result.removed_ingredients)}</section>}
    {result.substitutions.length > 0 && <p className="text-xs text-amber-300">Substituicoes aplicadas: {result.substitutions.length}. As quantidades acima foram calculadas pelas fichas cadastradas.</p>}
    {result.methods.map((method) => <section key={method.recipe_version_id}><p className="whitespace-pre-wrap text-sm">{method.instructions}</p><ol className="list-inside list-decimal text-sm">{method.preparation_steps.map((step, index) => <li key={index}>{step}</li>)}</ol><RecipePrivateImage url={method.reference_image_url ?? ""} /></section>)}
  </div>;
}
