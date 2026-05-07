import { useEffect, useMemo, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  BarChart2,
  CheckCircle2,
  Loader2,
  Pause,
  Pencil,
  Play,
  Plus,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import {
  productsApi,
  upsellsApi,
  type ApiProduct,
  type ApiUpsell,
  type ApiUpsellInput,
  type UpsellTriggerType,
} from "@/lib/api";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";

const IC = "w-full rounded-xl border border-surface-03 bg-surface-03 px-3 py-2 text-sm text-cream outline-none transition-colors focus:border-gold";
const LB = "block text-xs text-stone mb-1";
const WEEKDAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"];

const TRIGGER_LABELS: Record<UpsellTriggerType, string> = {
  product_in_cart: "Produto no carrinho",
  category: "Categoria no carrinho",
  min_value: "Valor mínimo",
  min_quantity: "Quantidade mínima",
};

type View = "list" | "metrics";

function emptyForm(): ApiUpsellInput {
  return {
    internal_name: "",
    product_id: "",
    image_url: null,
    main_text: "",
    secondary_text: null,
    promotional_price: null,
    trigger_type: "min_value",
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
  return str
    .split("")
    .map(Number)
    .filter((n) => !isNaN(n) && n >= 0 && n <= 6);
}

function buildWeekdaysString(days: number[]): string {
  return [...new Set(days)].sort().join("");
}

function fmtCurrency(v: number) {
  return `R$ ${v.toFixed(2)}`;
}

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
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const activeProducts = useMemo(() => products.filter((p) => p.active), [products]);

  async function loadAll() {
    setLoading(true);
    try {
      const [u, p] = await Promise.all([upsellsApi.list(), productsApi.getAll()]);
      setUpsells(u);
      setProducts(p);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erro ao carregar dados.");
    } finally {
      setLoading(false);
    }
  }

  async function loadMetrics() {
    try {
      setMetrics(await upsellsApi.metrics());
    } catch {}
  }

  useEffect(() => {
    loadAll();
  }, []);

  useEffect(() => {
    if (view === "metrics") loadMetrics();
  }, [view]);

  function openCreate() {
    setEditId(null);
    setForm(emptyForm());
    setSelectedWeekdays([0, 1, 2, 3, 4, 5, 6]);
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
      trigger_type: u.trigger_type as UpsellTriggerType,
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
    setError("");
    setShowForm(true);
  }

  async function handleSave() {
    if (!form.internal_name.trim() || !form.product_id || !form.main_text.trim()) {
      setError("Preencha nome interno, produto e texto principal.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const payload: ApiUpsellInput = {
        ...form,
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

  const triggerNeedsProduct = form.trigger_type === "product_in_cart";
  const triggerNeedsCategory = form.trigger_type === "category";
  const triggerNeedsMinValue = form.trigger_type === "min_value";
  const triggerNeedsMinQty = form.trigger_type === "min_quantity";

  return (
    <div className="flex h-full">
      <AdminSidebar />
      <div className="flex-1 overflow-auto">
        <AdminTopActions title="Gestao de Upsell" />

        <div className="p-6 space-y-6 max-w-5xl mx-auto">
          {/* Header */}
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
                Metricas
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

          {/* Error banner */}
          {error && !showForm && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3 text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* ─── List view ─────────────────────────────────────────────────── */}
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
                  {upsells.map((u, idx) => (
                    <div
                      key={u.id}
                      className={`bg-surface-02 rounded-xl border p-4 flex items-center gap-4 transition-colors ${
                        u.active ? "border-surface-03" : "border-surface-03 opacity-60"
                      }`}
                    >
                      {/* Priority controls */}
                      <div className="flex flex-col gap-1">
                        <button
                          onClick={() => handleMoveUp(idx)}
                          disabled={idx === 0}
                          className="text-stone hover:text-cream disabled:opacity-20 transition-colors"
                        >
                          <ArrowUp size={14} />
                        </button>
                        <button
                          onClick={() => handleMoveDown(idx)}
                          disabled={idx === upsells.length - 1}
                          className="text-stone hover:text-cream disabled:opacity-20 transition-colors"
                        >
                          <ArrowDown size={14} />
                        </button>
                      </div>

                      {/* Icon */}
                      <div className="w-10 h-10 rounded-xl bg-surface-03 flex-shrink-0 flex items-center justify-center text-lg overflow-hidden">
                        {u.product?.icon ? (
                          u.product.icon.startsWith("http") || u.product.icon.startsWith("/") || u.product.icon.startsWith("uploads") ? (
                            <img src={u.product.icon.startsWith("http") ? u.product.icon : `${import.meta.env.VITE_API_URL ?? "http://localhost:8000"}/${u.product.icon}`} alt="" className="w-full h-full object-cover" />
                          ) : (
                            <span>{u.product.icon}</span>
                          )
                        ) : (
                          <span>🍕</span>
                        )}
                      </div>

                      {/* Info */}
                      <div className="flex-1 min-w-0">
                        <p className="text-cream font-semibold text-sm truncate">{u.internal_name}</p>
                        <p className="text-stone text-xs truncate">{u.product?.name ?? "Produto removido"}</p>
                        <div className="flex flex-wrap items-center gap-2 mt-1">
                          <span className="bg-surface-03 text-stone text-[10px] px-2 py-0.5 rounded-full">
                            {TRIGGER_LABELS[u.trigger_type as UpsellTriggerType] ?? u.trigger_type}
                          </span>
                          {u.promotional_price !== null && (
                            <span className="bg-gold/10 text-gold text-[10px] px-2 py-0.5 rounded-full font-bold">
                              {fmtCurrency(u.promotional_price)}
                            </span>
                          )}
                          {u.metrics && u.metrics.views > 0 && (
                            <span className="text-stone text-[10px]">
                              {u.metrics.accepts}/{u.metrics.views} aceites
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <button
                          onClick={() => handleToggle(u.id)}
                          title={u.active ? "Pausar" : "Ativar"}
                          className="p-2 rounded-lg bg-surface-03 text-stone hover:text-cream transition-colors"
                        >
                          {u.active ? <Pause size={14} /> : <Play size={14} />}
                        </button>
                        <button
                          onClick={() => openEdit(u)}
                          className="p-2 rounded-lg bg-surface-03 text-stone hover:text-cream transition-colors"
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          onClick={() => setConfirmDelete(u.id)}
                          className="p-2 rounded-lg bg-surface-03 text-red-400 hover:bg-red-500/20 transition-colors"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {/* ─── Metrics view ──────────────────────────────────────────────── */}
          {view === "metrics" && (
            <>
              {metrics ? (
                <div className="space-y-6">
                  {/* Summary cards */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {[
                      { label: "Visualizações", value: metrics.total_views, color: "text-blue-400" },
                      { label: "Aceites", value: metrics.total_accepts, color: "text-green-400" },
                      { label: "Recusas", value: metrics.total_rejects, color: "text-red-400" },
                      { label: "Receita", value: fmtCurrency(metrics.total_revenue), color: "text-gold" },
                    ].map((card) => (
                      <div key={card.label} className="bg-surface-02 rounded-xl p-4 border border-surface-03">
                        <p className="text-stone text-xs">{card.label}</p>
                        <p className={`font-bold text-xl mt-1 ${card.color}`}>{card.value}</p>
                      </div>
                    ))}
                  </div>

                  {/* Per-upsell table */}
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
                          <tr>
                            <td colSpan={5} className="px-4 py-8 text-center text-stone text-xs">
                              Nenhum dado disponivel ainda.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-center py-16 text-stone gap-2">
                  <Loader2 size={20} className="animate-spin" />
                  Carregando metricas...
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* ─── Form modal ──────────────────────────────────────────────────────── */}
      {showForm && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-end md:items-center justify-center p-4">
          <div className="bg-surface-01 rounded-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto shadow-2xl">
            <div className="flex items-center justify-between p-6 border-b border-surface-03">
              <h2 className="text-cream font-bold text-lg">
                {editId ? "Editar Upsell" : "Novo Upsell"}
              </h2>
              <button onClick={() => setShowForm(false)} className="text-stone hover:text-cream transition-colors">
                <X size={20} />
              </button>
            </div>

            <div className="p-6 space-y-4">
              {error && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3 text-red-400 text-sm">
                  {error}
                </div>
              )}

              {/* Nome interno */}
              <div>
                <label className={LB}>Nome interno *</label>
                <input
                  className={IC}
                  placeholder="Ex: Upsell Bebida Gelada"
                  value={form.internal_name}
                  onChange={(e) => setForm((f) => ({ ...f, internal_name: e.target.value }))}
                />
              </div>

              {/* Produto ofertado */}
              <div>
                <label className={LB}>Produto ofertado *</label>
                <select
                  className={IC}
                  value={form.product_id}
                  onChange={(e) => setForm((f) => ({ ...f, product_id: e.target.value }))}
                >
                  <option value="">Selecione...</option>
                  {activeProducts.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Imagem (URL) */}
              <div>
                <label className={LB}>Imagem (URL opcional)</label>
                <input
                  className={IC}
                  placeholder="https://... ou uploads/foto.jpg"
                  value={form.image_url ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, image_url: e.target.value || null }))}
                />
              </div>

              {/* Texto principal */}
              <div>
                <label className={LB}>Texto principal *</label>
                <input
                  className={IC}
                  placeholder='Ex: "Adicione uma bebida gelada por apenas..."'
                  value={form.main_text}
                  onChange={(e) => setForm((f) => ({ ...f, main_text: e.target.value }))}
                />
              </div>

              {/* Texto secundário */}
              <div>
                <label className={LB}>Texto secundário</label>
                <input
                  className={IC}
                  placeholder="Detalhe extra (opcional)"
                  value={form.secondary_text ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, secondary_text: e.target.value || null }))}
                />
              </div>

              {/* Preço promocional */}
              <div>
                <label className={LB}>Preço promocional (R$)</label>
                <input
                  className={IC}
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="Deixe vazio para usar o preço normal"
                  value={form.promotional_price ?? ""}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, promotional_price: e.target.value ? parseFloat(e.target.value) : null }))
                  }
                />
              </div>

              {/* Tipo de gatilho */}
              <div>
                <label className={LB}>Tipo de gatilho *</label>
                <select
                  className={IC}
                  value={form.trigger_type}
                  onChange={(e) => setForm((f) => ({ ...f, trigger_type: e.target.value as UpsellTriggerType }))}
                >
                  {(Object.entries(TRIGGER_LABELS) as [UpsellTriggerType, string][]).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </div>

              {/* Gatilho: produto no carrinho */}
              {triggerNeedsProduct && (
                <div>
                  <label className={LB}>Produto gatilho</label>
                  <select
                    className={IC}
                    value={form.trigger_product_id ?? ""}
                    onChange={(e) => setForm((f) => ({ ...f, trigger_product_id: e.target.value || null }))}
                  >
                    <option value="">Qualquer produto</option>
                    {activeProducts.map((p) => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                </div>
              )}

              {/* Gatilho: categoria */}
              {triggerNeedsCategory && (
                <div>
                  <label className={LB}>Categoria gatilho</label>
                  <input
                    className={IC}
                    placeholder="Ex: pizzas, bebidas"
                    value={form.trigger_category ?? ""}
                    onChange={(e) => setForm((f) => ({ ...f, trigger_category: e.target.value || null }))}
                  />
                </div>
              )}

              {/* Gatilho: valor mínimo */}
              {triggerNeedsMinValue && (
                <div>
                  <label className={LB}>Valor mínimo do carrinho (R$)</label>
                  <input
                    className={IC}
                    type="number"
                    min="0"
                    step="0.01"
                    value={form.trigger_min_value ?? ""}
                    onChange={(e) => setForm((f) => ({ ...f, trigger_min_value: parseFloat(e.target.value) || 0 }))}
                  />
                </div>
              )}

              {/* Gatilho: quantidade mínima */}
              {triggerNeedsMinQty && (
                <div>
                  <label className={LB}>Quantidade mínima de itens</label>
                  <input
                    className={IC}
                    type="number"
                    min="1"
                    step="1"
                    value={form.trigger_min_quantity ?? ""}
                    onChange={(e) => setForm((f) => ({ ...f, trigger_min_quantity: parseInt(e.target.value) || 1 }))}
                  />
                </div>
              )}

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
                        selectedWeekdays.includes(idx)
                          ? "bg-gold text-cream"
                          : "bg-surface-03 text-stone hover:text-cream"
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
                  <input
                    className={IC}
                    type="time"
                    value={form.start_time ?? ""}
                    onChange={(e) => setForm((f) => ({ ...f, start_time: e.target.value || null }))}
                  />
                </div>
                <div>
                  <label className={LB}>Horário final</label>
                  <input
                    className={IC}
                    type="time"
                    value={form.end_time ?? ""}
                    onChange={(e) => setForm((f) => ({ ...f, end_time: e.target.value || null }))}
                  />
                </div>
              </div>

              {/* Prioridade + limite */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={LB}>Prioridade (maior = primeiro)</label>
                  <input
                    className={IC}
                    type="number"
                    min="0"
                    value={form.priority ?? 0}
                    onChange={(e) => setForm((f) => ({ ...f, priority: parseInt(e.target.value) || 0 }))}
                  />
                </div>
                <div>
                  <label className={LB}>Limite de exibição</label>
                  <input
                    className={IC}
                    type="number"
                    min="1"
                    value={form.display_limit ?? 1}
                    onChange={(e) => setForm((f) => ({ ...f, display_limit: parseInt(e.target.value) || 1 }))}
                  />
                </div>
              </div>

              {/* Ativo */}
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, active: !f.active }))}
                  className={`w-10 h-6 rounded-full transition-colors flex items-center ${
                    form.active ? "bg-gold justify-end" : "bg-surface-03 justify-start"
                  }`}
                >
                  <span className="w-5 h-5 rounded-full bg-white shadow mx-0.5 block" />
                </button>
                <span className="text-sm text-stone">{form.active ? "Ativo" : "Inativo"}</span>
              </div>
            </div>

            {/* Form footer */}
            <div className="p-6 border-t border-surface-03 flex gap-3">
              <button
                onClick={() => setShowForm(false)}
                className="flex-1 py-3 rounded-xl border border-surface-03 text-stone hover:text-cream text-sm font-semibold transition-colors"
              >
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

      {/* ─── Delete confirm ───────────────────────────────────────────────────── */}
      {confirmDelete && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
          <div className="bg-surface-01 rounded-2xl p-6 max-w-sm w-full text-center shadow-2xl">
            <Trash2 size={32} className="text-red-400 mx-auto mb-3" />
            <h3 className="text-cream font-bold text-lg mb-2">Excluir upsell?</h3>
            <p className="text-stone text-sm mb-6">Essa ação não pode ser desfeita. O histórico de métricas será perdido.</p>
            <div className="flex gap-3">
              <button
                onClick={() => setConfirmDelete(null)}
                className="flex-1 py-3 rounded-xl border border-surface-03 text-stone hover:text-cream text-sm font-semibold transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={() => handleDelete(confirmDelete)}
                className="flex-1 py-3 rounded-xl bg-red-500 hover:bg-red-600 text-white font-bold text-sm transition-colors"
              >
                Excluir
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
