import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, BarChart3, CheckCircle2, ChevronDown, ChevronRight, ClipboardList, Gauge, Loader2, RefreshCw, Settings } from "lucide-react";
import { AdminPageTabs, type AdminPageTab } from "@/components/admin/AdminPageChrome";
import AdminGestao from "./AdminGestao";
import { cmvApi, type CmvOverview, type CmvProductCost } from "@/lib/api";

type CmvSection = "settings" | "overview" | "products";

const sections: AdminPageTab<CmvSection>[] = [
  { id: "settings", label: "Configuracoes", icon: Settings },
  { id: "overview", label: "Indicadores", icon: Gauge },
  { id: "products", label: "Produtos e fichas", icon: ClipboardList },
];

const panelClass = "rounded-lg border border-surface-03 bg-surface-02 p-5";
const mutedPanelClass = "rounded-lg border border-surface-03 bg-surface-01 p-4";

function currency(value: number) {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value || 0);
}

function percent(value?: number | null) {
  return value === null || value === undefined ? "-" : `${value.toFixed(2)}%`;
}

function statusLabel(product: CmvProductCost) {
  if (product.status === "missing_recipe") return "Sem ficha";
  if (product.status === "missing_cost") return "Sem custo";
  return "Calculado";
}

function statusClass(product: CmvProductCost) {
  if (product.status === "ok") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
  return "border-amber-500/30 bg-amber-500/10 text-amber-300";
}

function dreComplete(status: string) {
  return status === "complete_with_cmv" || status === "complete_with_operational_cmv";
}

export default function GestaoCmv() {
  const [section, setSection] = useState<CmvSection>("settings");

  return (
    <AdminGestao
      moduleKey="cmv"
      showSettings={section === "settings"}
      moduleTabs={<AdminPageTabs<CmvSection> tabs={sections} active={section} onChange={setSection} />}
    >
      {section !== "settings" && <CmvAnalytics section={section} />}
    </AdminGestao>
  );
}

function CmvAnalytics({ section }: { section: Exclude<CmvSection, "settings"> }) {
  const [data, setData] = useState<CmvOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const load = () => {
    setLoading(true);
    setError("");
    cmvApi.overview()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Nao foi possivel carregar CMV."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const sortedProducts = useMemo(() => {
    return [...(data?.products ?? [])].sort((a, b) => {
      const rank = { missing_recipe: 0, missing_cost: 1, ok: 2 } as Record<string, number>;
      return (rank[a.status] ?? 3) - (rank[b.status] ?? 3) || a.product_name.localeCompare(b.product_name);
    });
  }, [data]);

  return (
    <section className="space-y-5">
      <div className={panelClass}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-lg font-black text-cream">CMV operacional</h3>
            <p className="text-sm text-stone">Snapshot por venda, ficha tecnica, custo medio e margem.</p>
          </div>
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm font-bold text-stone transition hover:bg-surface-03 hover:text-cream disabled:opacity-60"
          >
            {loading ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
            Atualizar
          </button>
        </div>
      </div>

      {loading && (
        <div className="flex min-h-48 items-center justify-center rounded-lg border border-surface-03 bg-surface-02 text-stone">
          <Loader2 size={18} className="mr-2 animate-spin" /> Carregando CMV...
        </div>
      )}

      {!loading && error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-5 text-red-200">
          <div className="flex items-center gap-2 font-bold">
            <AlertTriangle size={18} /> Erro ao carregar
          </div>
          <p className="mt-2 text-sm">{error}</p>
        </div>
      )}

      {!loading && data && (
        <>
          {section === "overview" && (
            <>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <Metric title="DRE" value={data.dre_label} tone={dreComplete(data.dre_status) ? "success" : "warn"} />
                <Metric title="CMV vendas" value={percent(data.operational_cmv_percent)} />
                <Metric title="Vendas com snapshot" value={String(data.operational_snapshot_count)} tone={data.operational_snapshot_count ? "success" : "warn"} />
                <Metric title="Pendencias" value={String(data.operational_pending_count + data.products_missing_recipe + data.products_missing_cost)} tone={data.operational_pending_count || data.products_missing_recipe || data.products_missing_cost ? "warn" : "success"} />
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <Metric title="Receita snapshot" value={currency(data.operational_sale_total)} />
                <Metric title="Custo snapshot" value={currency(data.operational_cost_total)} />
                <Metric title="CMV medio catalogo" value={percent(data.average_cmv_percent)} />
              </div>
            </>
          )}

          {section === "products" && <div className={panelClass}>
            <div className="mb-4 flex items-center gap-2">
              <BarChart3 size={18} className="text-gold" />
              <h3 className="text-sm font-black uppercase tracking-wide text-parchment">Produtos</h3>
            </div>
            <div className="space-y-3">
              {sortedProducts.map((product) => {
                const open = !!expanded[product.product_id];
                return (
                  <div key={product.product_id} className={mutedPanelClass}>
                    <button
                      type="button"
                      onClick={() => setExpanded((value) => ({ ...value, [product.product_id]: !open }))}
                      className="flex w-full items-start justify-between gap-3 text-left"
                    >
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          {open ? <ChevronDown size={15} className="text-stone" /> : <ChevronRight size={15} className="text-stone" />}
                          <h4 className="font-bold text-cream">{product.product_name}</h4>
                          <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${statusClass(product)}`}>
                            {statusLabel(product)}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-stone">
                          Venda {currency(product.sale_price)} · Custo {currency(product.cost_min)} a {currency(product.cost_max)}
                        </p>
                      </div>
                      <div className="shrink-0 text-right text-sm">
                        <p className="font-black text-gold">{percent(product.cmv_percent_max)}</p>
                        <p className="text-xs text-stone">Margem {currency(product.margin_min)}</p>
                      </div>
                    </button>

                    {open && (
                      <div className="mt-4 space-y-3 border-t border-surface-03 pt-4">
                        {product.recipes.length === 0 && (
                          <p className="rounded-lg border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-sm text-amber-300">
                            Cadastre a ficha tecnica deste produto para calcular o CMV.
                          </p>
                        )}
                        {product.recipes.map((recipe) => (
                          <div key={recipe.recipe_id} className="rounded-lg border border-surface-03 bg-surface-02 p-3">
                            <div className="flex items-center justify-between gap-3">
                              <p className="text-sm font-bold text-cream">{recipe.scope_label} · v{recipe.version_number}</p>
                              <p className="text-sm font-black text-gold">{currency(recipe.cost_total)}</p>
                            </div>
                            <div className="mt-3 space-y-2">
                              {recipe.ingredients.map((ingredient) => (
                                <div key={`${recipe.recipe_id}-${ingredient.inventory_item_id}`} className="grid gap-2 rounded-lg bg-surface-01 px-3 py-2 text-xs text-stone sm:grid-cols-[1fr_.7fr_.7fr_.7fr]">
                                  <span className="font-semibold text-parchment">{ingredient.inventory_item_name || ingredient.inventory_item_id}</span>
                                  <span>{ingredient.quantity} {ingredient.unit_symbol || ""}</span>
                                  <span>{currency(ingredient.unit_cost)}</span>
                                  <span className={ingredient.missing_cost ? "font-bold text-amber-300" : "text-gold"}>{currency(ingredient.total_cost)}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
              {sortedProducts.length === 0 && (
                <div className="rounded-lg border border-surface-03 bg-surface-01 p-8 text-center text-sm text-stone">
                  Nenhum produto ativo para calcular.
                </div>
              )}
            </div>
          </div>}
        </>
      )}
    </section>
  );
}

function Metric({ title, value, tone = "default" }: { title: string; value: string; tone?: "default" | "success" | "warn" }) {
  const toneClass = tone === "success" ? "text-emerald-300" : tone === "warn" ? "text-amber-300" : "text-gold";
  return (
    <div className={panelClass}>
      <div className="mb-2 flex items-center gap-2 text-xs font-black uppercase tracking-wide text-stone">
        {tone === "success" && <CheckCircle2 size={14} className="text-emerald-300" />}
        {tone === "warn" && <AlertTriangle size={14} className="text-amber-300" />}
        <span>{title}</span>
      </div>
      <p className={`text-xl font-black ${toneClass}`}>{value}</p>
    </div>
  );
}
