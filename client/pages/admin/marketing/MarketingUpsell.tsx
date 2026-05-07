import { useEffect, useMemo, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  BarChart2,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Loader2,
  Pause,
  Pencil,
  Play,
  Plus,
  Search,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import {
  productsApi,
  resolveAssetUrl,
  isAssetUrl,
  upsellsApi,
  type ApiProduct,
  type ApiUpsell,
  type ApiUpsellInput,
} from "@/lib/api";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";

const IC = "w-full rounded-xl border border-surface-03 bg-surface-03 px-3 py-2 text-sm text-cream outline-none transition-colors focus:border-gold";
const LB = "block text-xs text-stone mb-1.5";
const WEEKDAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"];

type View = "list" | "metrics";

function emptyForm(): ApiUpsellInput {
  return {
    internal_name: "",
    product_id: "",
    image_url: null,
    main_text: "",
    secondary_text: null,
    promotional_price: null,
    trigger_type: "product_in_cart",
    trigger_product_id: null,
    trigger_category: null,
    trigger_min_value: 0,
    trigger_min_quantity: 1,
    allowed_weekdays: "0123456",
    start_time: null,
    end_time: null,
    priority: 0,
    display_limit: 1,
    active: true,
  };
}

function parseWeekdaysString(str: string | null | undefined): number[] {
  if (!str) return [0, 1, 2, 3, 4, 5, 6];
  return str.split("").map(Number).filter((n) => !isNaN(n) && n >= 0 && n <= 6);
}

function buildWeekdaysString(days: number[]): string {
  return [...new Set(days)].sort().join("");
}

function fmtCurrency(v: number) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

// ── Seletor de produto com busca e preview ────────────────────────────────────

interface ProductPickerProps {
  label: string;
  value: string;
  products: ApiProduct[];
  onChange: (id: string) => void;
  placeholder?: string;
}

function ProductPicker({ label, value, products, onChange, placeholder }: ProductPickerProps) {
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);

  const selected = products.find((p) => p.id === value) ?? null;

  const filtered = useMemo(() => {
    if (!search.trim()) return products;
    const q = search.toLowerCase();
    return products.filter((p) => p.name.toLowerCase().includes(q));
  }, [products, search]);

  function select(p: ApiProduct) {
    onChange(p.id);
    setSearch("");
    setOpen(false);
  }

  return (
    <div className="relative">
      <label className={LB}>{label}</label>

      {/* Trigger button */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 rounded-xl border border-surface-03 bg-surface-03 px-3 py-2.5 text-sm text-left transition-colors focus:border-gold outline-none hover:border-gold/50"
      >
        {selected ? (
          <>
            <div className="w-8 h-8 rounded-lg bg-surface-01 flex-shrink-0 flex items-center justify-center text-base overflow-hidden">
              {isAssetUrl(selected.icon)
                ? <img src={resolveAssetUrl(selected.icon)} alt="" className="w-full h-full object-cover" />
                : <span>{selected.icon || "🍕"}</span>}
            </div>
            <span className="flex-1 text-cream truncate">{selected.name}</span>
            <span className="text-stone text-xs flex-shrink-0">{fmtCurrency(selected.price)}</span>
          </>
        ) : (
          <span className="flex-1 text-stone">{placeholder ?? "Selecione um produto..."}</span>
        )}
        <ChevronDown size={15} className={`text-stone flex-shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute z-50 mt-1 w-full bg-surface-01 border border-surface-03 rounded-xl shadow-2xl overflow-hidden">
          <div className="p-2 border-b border-surface-03">
            <div className="flex items-center gap-2 bg-surface-03 rounded-lg px-3 py-2">
              <Search size={14} className="text-stone flex-shrink-0" />
              <input
                autoFocus
                className="flex-1 bg-transparent text-sm text-cream placeholder-stone/60 outline-none"
                placeholder="Buscar produto..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>
          <div className="max-h-56 overflow-y-auto">
            {filtered.length === 0 ? (
              <p className="px-4 py-6 text-center text-stone text-xs">Nenhum produto encontrado.</p>
            ) : (
              filtered.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => select(p)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 text-left text-sm hover:bg-surface-03 transition-colors ${
                    p.id === value ? "bg-gold/10 text-gold" : "text-cream"
                  }`}
                >
                  <div className="w-8 h-8 rounded-lg bg-surface-03 flex-shrink-0 flex items-center justify-center text-base overflow-hidden">
                    {isAssetUrl(p.icon)
                      ? <img src={resolveAssetUrl(p.icon)} alt="" className="w-full h-full object-cover" />
                      : <span>{p.icon || "🍕"}</span>}
                  </div>
                  <span className="flex-1 truncate">{p.name}</span>
                  <span className="text-stone text-xs flex-shrink-0">{fmtCurrency(p.price)}</span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Preview do produto ofertado no upsell ─────────────────────────────────────

interface UpsellPreviewProps {
  product: ApiProduct | null;
  mainText: string;
  secondaryText: string;
  promotionalPrice: number | null;
}

function UpsellPreview({ product, mainText, secondaryText, promotionalPrice }: UpsellPreviewProps) {
  if (!product && !mainText) return null;

  const price = promotionalPrice ?? product?.price ?? 0;
  const original = product?.price ?? 0;
  const hasDiscount = promotionalPrice !== null && product !== null && promotionalPrice < original;

  return (
    <div className="rounded-2xl border border-gold/30 bg-surface-03/40 overflow-hidden">
      <p className="text-[10px] text-gold font-bold uppercase tracking-wider px-4 pt-3 pb-1">
        Preview — como aparece no checkout
      </p>
      <div className="flex items-center gap-4 px-4 pb-4">
        <div className="w-16 h-16 rounded-xl bg-surface-03 flex-shrink-0 flex items-center justify-center text-2xl overflow-hidden">
          {product && isAssetUrl(product.icon)
            ? <img src={resolveAssetUrl(product.icon)} alt={product.name} className="w-full h-full object-cover" />
            : <span>{product?.icon || "🍕"}</span>}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-cream font-bold text-sm leading-snug">
            {mainText || <span className="text-stone italic">Texto principal aqui...</span>}
          </p>
          {secondaryText && (
            <p className="text-stone text-xs mt-0.5">{secondaryText}</p>
          )}
          <div className="flex items-baseline gap-2 mt-1.5">
            {product || promotionalPrice ? (
              <>
                <span className="text-gold font-bold text-base">{fmtCurrency(price)}</span>
                {hasDiscount && (
                  <span className="text-stone text-xs line-through">{fmtCurrency(original)}</span>
                )}
              </>
            ) : null}
          </div>
        </div>
      </div>
      <div className="grid grid-cols-2 border-t border-surface-03">
        <div className="flex items-center justify-center gap-2 py-2.5 text-stone text-xs font-medium">
          <X size={13} /> Não, obrigado
        </div>
        <div className="flex items-center justify-center gap-2 py-2.5 text-gold text-xs font-bold border-l border-surface-03">
          Adicionar
        </div>
      </div>
    </div>
  );
}

// ── Componente principal ──────────────────────────────────────────────────────

export default function MarketingUpsell() {
  const [view, setView] = useState<View>("list");
  const [upsells, setUpsells] = useState<ApiUpsell[]>([]);
  const [metrics, setMetrics] = useState<Awaited<ReturnType<typeof upsellsApi.metrics>> | null>(null);
  const [products, setProducts] = useState<ApiProduct[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState<ApiUpsellInput>(emptyForm());
  const [selectedWeekdays, setSelectedWeekdays] = useState<number[]>([0, 1, 2, 3, 4, 5, 6]);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const activeProducts = useMemo(() => products.filter((p) => p.active), [products]);

  const selectedTriggerProduct = activeProducts.find((p) => p.id === form.trigger_product_id) ?? null;
  const selectedUpsellProduct = activeProducts.find((p) => p.id === form.product_id) ?? null;

  async function loadAll() {
    setLoading(true);
    try {
      const [u, p] = await Promise.all([upsellsApi.list(), productsApi.list(false)]);
      setUpsells(u);
      setProducts(p);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erro ao carregar.");
    } finally {
      setLoading(false);
    }
  }

  async function loadMetrics() {
    try {
      setMetrics(await upsellsApi.metrics());
    } catch {}
  }

  useEffect(() => { loadAll(); }, []);
  useEffect(() => { if (view === "metrics") loadMetrics(); }, [view]);

  function openCreate() {
    setEditId(null);
    setForm(emptyForm());
    setSelectedWeekdays([0, 1, 2, 3, 4, 5, 6]);
    setShowAdvanced(false);
    setError("");
    setShowForm(true);
  }

  function openEdit(u: ApiUpsell) {
    setEditId(u.id);
    setForm({
      internal_name: u.internal_name,
      product_id: u.product_id,
      image_url: u.image_url,
      main_text: u.main_text,
      secondary_text: u.secondary_text,
      promotional_price: u.promotional_price,
      trigger_type: "product_in_cart",
      trigger_product_id: u.trigger_product_id,
      trigger_category: u.trigger_category,
      trigger_min_value: u.trigger_min_value,
      trigger_min_quantity: u.trigger_min_quantity,
      allowed_weekdays: u.allowed_weekdays,
      start_time: u.start_time,
      end_time: u.end_time,
      priority: u.priority,
      display_limit: u.display_limit,
      active: u.active,
    });
    setSelectedWeekdays(parseWeekdaysString(u.allowed_weekdays));
    setShowAdvanced(false);
    setError("");
    setShowForm(true);
  }

  async function handleSave() {
    if (!form.product_id) {
      setError("Selecione o produto a ser ofertado no upsell.");
      return;
    }
    if (!form.main_text.trim()) {
      setError("Preencha o texto principal do upsell.");
      return;
    }
    // Auto-generate internal_name if empty
    const internalName = form.internal_name.trim() ||
      `${selectedTriggerProduct?.name ?? "Geral"} → ${selectedUpsellProduct?.name ?? form.product_id}`;

    setSaving(true);
    setError("");
    try {
      const payload: ApiUpsellInput = {
        ...form,
        internal_name: internalName,
        trigger_type: form.trigger_product_id ? "product_in_cart" : "min_value",
        allowed_weekdays: buildWeekdaysString(selectedWeekdays),
      };
      if (editId) {
        const updated = await upsellsApi.update(editId, payload);
        setUpsells((prev) => prev.map((u) => (u.id === editId ? updated : u)));
      } else {
        const created = await upsellsApi.create(payload);
        setUpsells((prev) => [created, ...prev]);
      }
      setShowForm(false);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle(id: string) {
    try {
      const updated = await upsellsApi.toggle(id);
      setUpsells((prev) => prev.map((u) => (u.id === id ? updated : u)));
    } catch {}
  }

  async function handleDelete(id: string) {
    try {
      await upsellsApi.remove(id);
      setUpsells((prev) => prev.filter((u) => u.id !== id));
    } catch {}
    setConfirmDelete(null);
  }

  async function handleMoveUp(idx: number) {
    if (idx === 0) return;
    const next = [...upsells];
    [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]];
    setUpsells(next);
    await upsellsApi.reorder(next.map((u) => u.id)).catch(() => {});
  }

  async function handleMoveDown(idx: number) {
    if (idx === upsells.length - 1) return;
    const next = [...upsells];
    [next[idx], next[idx + 1]] = [next[idx + 1], next[idx]];
    setUpsells(next);
    await upsellsApi.reorder(next.map((u) => u.id)).catch(() => {});
  }

  function toggleWeekday(day: number) {
    setSelectedWeekdays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day],
    );
  }

  return (
    <div className="flex h-full">
      <AdminSidebar />
      <div className="flex-1 overflow-auto">
        <AdminTopActions />

        <div className="p-6 space-y-6 max-w-5xl mx-auto">

          {/* ── Header ──────────────────────────────────────────────────── */}
          <div className="flex items-center justify-between gap-4">
            <div className="flex gap-2">
              <button
                onClick={() => setView("list")}
                className={`px-4 py-2 rounded-xl text-sm font-semibold transition-colors ${
                  view === "list" ? "bg-gold text-cream" : "bg-surface-02 text-stone hover:text-cream"
                }`}
              >
                Upsells
              </button>
              <button
                onClick={() => setView("metrics")}
                className={`px-4 py-2 rounded-xl text-sm font-semibold transition-colors flex items-center gap-2 ${
                  view === "metrics" ? "bg-gold text-cream" : "bg-surface-02 text-stone hover:text-cream"
                }`}
              >
                <BarChart2 size={15} />
                Métricas
              </button>
            </div>
            {view === "list" && (
              <button
                onClick={openCreate}
                className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold px-4 py-2 rounded-xl text-sm transition-colors"
              >
                <Plus size={16} />
                Novo Upsell
              </button>
            )}
          </div>

          {error && !showForm && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3 text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* ── Lista ────────────────────────────────────────────────────── */}
          {view === "list" && (
            <>
              {loading ? (
                <div className="flex items-center justify-center py-16 text-stone gap-2">
                  <Loader2 size={20} className="animate-spin" />
                  Carregando...
                </div>
              ) : upsells.length === 0 ? (
                <div className="text-center py-16 text-stone">
                  <Sparkles size={40} className="mx-auto mb-4 opacity-30" />
                  <p className="font-semibold">Nenhum upsell cadastrado</p>
                  <p className="text-xs mt-1">Crie seu primeiro upsell para aumentar o ticket médio.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {upsells.map((u, idx) => {
                    const triggerProd = products.find((p) => p.id === u.trigger_product_id);
                    const offeredProd = products.find((p) => p.id === u.product_id) ?? u.product;
                    return (
                      <div
                        key={u.id}
                        className={`bg-surface-02 rounded-xl border p-4 flex items-center gap-4 ${
                          u.active ? "border-surface-03" : "border-surface-03 opacity-55"
                        }`}
                      >
                        {/* Ordenação */}
                        <div className="flex flex-col gap-1">
                          <button onClick={() => handleMoveUp(idx)} disabled={idx === 0} className="text-stone hover:text-cream disabled:opacity-20">
                            <ArrowUp size={14} />
                          </button>
                          <button onClick={() => handleMoveDown(idx)} disabled={idx === upsells.length - 1} className="text-stone hover:text-cream disabled:opacity-20">
                            <ArrowDown size={14} />
                          </button>
                        </div>

                        {/* Produto principal (gatilho) */}
                        <div className="flex items-center gap-2 min-w-0 flex-1">
                          {triggerProd ? (
                            <div className="flex items-center gap-2">
                              <div className="w-9 h-9 rounded-lg bg-surface-03 flex-shrink-0 flex items-center justify-center text-base overflow-hidden">
                                {isAssetUrl(triggerProd.icon)
                                  ? <img src={resolveAssetUrl(triggerProd.icon)} alt="" className="w-full h-full object-cover" />
                                  : <span>{triggerProd.icon || "🍕"}</span>}
                              </div>
                              <div className="min-w-0">
                                <p className="text-stone text-[10px] uppercase tracking-wide">Produto principal</p>
                                <p className="text-cream text-xs font-medium truncate">{triggerProd.name}</p>
                              </div>
                            </div>
                          ) : (
                            <div className="text-stone text-xs">Qualquer produto</div>
                          )}
                        </div>

                        {/* Seta */}
                        <span className="text-stone text-lg flex-shrink-0">→</span>

                        {/* Produto ofertado */}
                        <div className="flex items-center gap-2 flex-1 min-w-0">
                          {offeredProd && (
                            <>
                              <div className="w-9 h-9 rounded-lg bg-surface-03 flex-shrink-0 flex items-center justify-center text-base overflow-hidden">
                                {isAssetUrl(offeredProd.icon)
                                  ? <img src={resolveAssetUrl(offeredProd.icon)} alt="" className="w-full h-full object-cover" />
                                  : <span>{offeredProd.icon || "🍕"}</span>}
                              </div>
                              <div className="min-w-0">
                                <p className="text-stone text-[10px] uppercase tracking-wide">Produto ofertado</p>
                                <p className="text-cream text-xs font-medium truncate">{offeredProd.name}</p>
                                <p className="text-gold text-xs font-bold">
                                  {fmtCurrency(u.promotional_price ?? offeredProd.price)}
                                </p>
                              </div>
                            </>
                          )}
                        </div>

                        {/* Texto */}
                        <div className="flex-1 min-w-0 hidden md:block">
                          <p className="text-cream text-xs truncate">{u.main_text}</p>
                          {u.secondary_text && <p className="text-stone text-[11px] truncate">{u.secondary_text}</p>}
                        </div>

                        {/* Métricas rápidas */}
                        {u.metrics && u.metrics.views > 0 && (
                          <div className="text-center flex-shrink-0 hidden lg:block">
                            <p className="text-gold font-bold text-sm">{u.metrics.accepts}</p>
                            <p className="text-stone text-[10px]">aceites</p>
                          </div>
                        )}

                        {/* Ações */}
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <button onClick={() => handleToggle(u.id)} title={u.active ? "Pausar" : "Ativar"} className="p-2 rounded-lg bg-surface-03 text-stone hover:text-cream transition-colors">
                            {u.active ? <Pause size={14} /> : <Play size={14} />}
                          </button>
                          <button onClick={() => openEdit(u)} className="p-2 rounded-lg bg-surface-03 text-stone hover:text-cream transition-colors">
                            <Pencil size={14} />
                          </button>
                          <button onClick={() => setConfirmDelete(u.id)} className="p-2 rounded-lg bg-surface-03 text-red-400 hover:bg-red-500/20 transition-colors">
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}

          {/* ── Métricas ─────────────────────────────────────────────────── */}
          {view === "metrics" && (
            <>
              {metrics ? (
                <div className="space-y-6">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {[
                      { label: "Visualizações", value: metrics.total_views, color: "text-blue-400" },
                      { label: "Aceites", value: metrics.total_accepts, color: "text-green-400" },
                      { label: "Recusas", value: metrics.total_rejects, color: "text-red-400" },
                      { label: "Receita gerada", value: fmtCurrency(metrics.total_revenue), color: "text-gold" },
                    ].map((c) => (
                      <div key={c.label} className="bg-surface-02 rounded-xl p-4 border border-surface-03">
                        <p className="text-stone text-xs">{c.label}</p>
                        <p className={`font-bold text-xl mt-1 ${c.color}`}>{c.value}</p>
                      </div>
                    ))}
                  </div>
                  <div className="bg-surface-02 rounded-xl border border-surface-03 overflow-hidden">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-surface-03 text-stone text-xs">
                          <th className="text-left px-4 py-3">Upsell</th>
                          <th className="text-center px-4 py-3">Views</th>
                          <th className="text-center px-4 py-3">Aceites</th>
                          <th className="text-center px-4 py-3">Conversão</th>
                          <th className="text-right px-4 py-3">Receita</th>
                        </tr>
                      </thead>
                      <tbody>
                        {metrics.items.map((item) => (
                          <tr key={item.upsell_id} className="border-b border-surface-03 last:border-0">
                            <td className="px-4 py-3">
                              <p className="text-cream font-medium">{item.internal_name}</p>
                              <p className="text-stone text-xs">{item.product_name}</p>
                            </td>
                            <td className="px-4 py-3 text-center text-stone">{item.views}</td>
                            <td className="px-4 py-3 text-center text-green-400 font-semibold">{item.accepts}</td>
                            <td className="px-4 py-3 text-center">
                              <span className={`font-bold ${item.conversion_rate >= 20 ? "text-green-400" : item.conversion_rate >= 10 ? "text-yellow-400" : "text-stone"}`}>
                                {item.conversion_rate}%
                              </span>
                            </td>
                            <td className="px-4 py-3 text-right text-gold font-bold">{fmtCurrency(item.revenue)}</td>
                          </tr>
                        ))}
                        {metrics.items.length === 0 && (
                          <tr><td colSpan={5} className="px-4 py-8 text-center text-stone text-xs">Nenhum dado disponível ainda.</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-center py-16 text-stone gap-2">
                  <Loader2 size={20} className="animate-spin" />
                  Carregando métricas...
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* ── Modal de formulário ───────────────────────────────────────────────── */}
      {showForm && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-end md:items-center justify-center p-4">
          <div className="bg-surface-01 rounded-2xl w-full max-w-lg max-h-[92vh] overflow-y-auto shadow-2xl">

            <div className="flex items-center justify-between p-5 border-b border-surface-03">
              <h2 className="text-cream font-bold text-lg">
                {editId ? "Editar Upsell" : "Novo Upsell"}
              </h2>
              <button onClick={() => setShowForm(false)} className="text-stone hover:text-cream transition-colors">
                <X size={20} />
              </button>
            </div>

            <div className="p-5 space-y-5">
              {error && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3 text-red-400 text-sm">
                  {error}
                </div>
              )}

              {/* 1. Produto principal (gatilho) */}
              <div>
                <ProductPicker
                  label="Produto principal (quando estiver no carrinho, o upsell aparece)"
                  value={form.trigger_product_id ?? ""}
                  products={activeProducts}
                  onChange={(id) => setForm((f) => ({ ...f, trigger_product_id: id || null }))}
                  placeholder="Selecione o produto que aciona o upsell..."
                />
                {selectedTriggerProduct && (
                  <button
                    type="button"
                    onClick={() => setForm((f) => ({ ...f, trigger_product_id: null }))}
                    className="mt-1.5 text-xs text-stone hover:text-red-400 transition-colors flex items-center gap-1"
                  >
                    <X size={11} /> Remover (upsell aparece para qualquer carrinho)
                  </button>
                )}
              </div>

              {/* Divisor visual */}
              <div className="flex items-center gap-3">
                <div className="flex-1 h-px bg-surface-03" />
                <span className="text-stone text-xs">oferecer</span>
                <div className="flex-1 h-px bg-surface-03" />
              </div>

              {/* 2. Produto ofertado */}
              <div>
                <ProductPicker
                  label="Produto a ser oferecido no upsell *"
                  value={form.product_id}
                  products={activeProducts}
                  onChange={(id) => setForm((f) => ({ ...f, product_id: id }))}
                  placeholder="Selecione o produto a oferecer..."
                />
              </div>

              {/* 3. Texto principal */}
              <div>
                <label className={LB}>Texto principal do upsell *</label>
                <input
                  className={IC}
                  placeholder='Ex: "Adicione uma bebida gelada por apenas R$ 7,90!"'
                  value={form.main_text}
                  onChange={(e) => setForm((f) => ({ ...f, main_text: e.target.value }))}
                />
              </div>

              {/* 4. Texto secundário */}
              <div>
                <label className={LB}>Texto secundário (opcional)</label>
                <input
                  className={IC}
                  placeholder='Ex: "Perfeito para acompanhar sua pizza"'
                  value={form.secondary_text ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, secondary_text: e.target.value || null }))}
                />
              </div>

              {/* Preview */}
              <UpsellPreview
                product={selectedUpsellProduct}
                mainText={form.main_text}
                secondaryText={form.secondary_text ?? ""}
                promotionalPrice={form.promotional_price}
              />

              {/* ── Configurações avançadas (colapsável) ─────────────────── */}
              <button
                type="button"
                onClick={() => setShowAdvanced((v) => !v)}
                className="w-full flex items-center justify-between py-2 text-stone hover:text-cream text-sm font-medium transition-colors"
              >
                <span>Configurações avançadas</span>
                {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </button>

              {showAdvanced && (
                <div className="space-y-4 pt-1 border-t border-surface-03">

                  {/* Preço promocional */}
                  <div>
                    <label className={LB}>Preço promocional (R$) — deixe vazio para usar o preço do produto</label>
                    <input
                      className={IC}
                      type="number"
                      min="0"
                      step="0.01"
                      placeholder="Ex: 7.90"
                      value={form.promotional_price ?? ""}
                      onChange={(e) => setForm((f) => ({ ...f, promotional_price: e.target.value ? parseFloat(e.target.value) : null }))}
                    />
                  </div>

                  {/* Dias da semana */}
                  <div>
                    <label className={LB}>Dias da semana</label>
                    <div className="flex gap-1.5 flex-wrap">
                      {WEEKDAYS.map((label, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => toggleWeekday(idx)}
                          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                            selectedWeekdays.includes(idx) ? "bg-gold text-cream" : "bg-surface-03 text-stone hover:text-cream"
                          }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Horário */}
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className={LB}>Horário inicial</label>
                      <input className={IC} type="time" value={form.start_time ?? ""} onChange={(e) => setForm((f) => ({ ...f, start_time: e.target.value || null }))} />
                    </div>
                    <div>
                      <label className={LB}>Horário final</label>
                      <input className={IC} type="time" value={form.end_time ?? ""} onChange={(e) => setForm((f) => ({ ...f, end_time: e.target.value || null }))} />
                    </div>
                  </div>

                  {/* Prioridade + limite */}
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className={LB}>Prioridade (maior = primeiro)</label>
                      <input className={IC} type="number" min="0" value={form.priority ?? 0} onChange={(e) => setForm((f) => ({ ...f, priority: parseInt(e.target.value) || 0 }))} />
                    </div>
                    <div>
                      <label className={LB}>Limite de exibição</label>
                      <input className={IC} type="number" min="1" value={form.display_limit ?? 1} onChange={(e) => setForm((f) => ({ ...f, display_limit: parseInt(e.target.value) || 1 }))} />
                    </div>
                  </div>

                  {/* Ativo */}
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => setForm((f) => ({ ...f, active: !f.active }))}
                      className={`w-10 h-6 rounded-full transition-colors flex items-center ${form.active ? "bg-gold justify-end" : "bg-surface-03 justify-start"}`}
                    >
                      <span className="w-5 h-5 rounded-full bg-white shadow mx-0.5 block" />
                    </button>
                    <span className="text-sm text-stone">{form.active ? "Ativo" : "Inativo"}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="p-5 border-t border-surface-03 flex gap-3">
              <button onClick={() => setShowForm(false)} className="flex-1 py-3 rounded-xl border border-surface-03 text-stone hover:text-cream text-sm font-semibold transition-colors">
                Cancelar
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex-1 py-3 rounded-xl bg-gold hover:bg-gold/90 text-cream font-bold text-sm transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {saving ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
                {saving ? "Salvando..." : editId ? "Salvar alterações" : "Criar upsell"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Confirmar exclusão ─────────────────────────────────────────────── */}
      {confirmDelete && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
          <div className="bg-surface-01 rounded-2xl p-6 max-w-sm w-full text-center shadow-2xl">
            <Trash2 size={32} className="text-red-400 mx-auto mb-3" />
            <h3 className="text-cream font-bold text-lg mb-2">Excluir upsell?</h3>
            <p className="text-stone text-sm mb-6">Essa ação não pode ser desfeita.</p>
            <div className="flex gap-3">
              <button onClick={() => setConfirmDelete(null)} className="flex-1 py-3 rounded-xl border border-surface-03 text-stone hover:text-cream text-sm font-semibold transition-colors">
                Cancelar
              </button>
              <button onClick={() => handleDelete(confirmDelete)} className="flex-1 py-3 rounded-xl bg-red-500 hover:bg-red-600 text-white font-bold text-sm transition-colors">
                Excluir
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
