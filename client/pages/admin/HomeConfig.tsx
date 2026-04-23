import { useState, useEffect } from "react";
import { Home, Save, Loader2, Check, List, Tag, Package, Eye, EyeOff } from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import { homeCatalogApi, isAssetUrl, resolveAssetUrl } from "@/lib/api";
import { useApp } from "@/context/AppContext";

type CatalogMode = "all" | "categories" | "products";

export default function AdminHomeConfig() {
  const { products } = useApp();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const [mode, setMode] = useState<CatalogMode>("all");
  const [showPromotions, setShowPromotions] = useState(true);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [selectedProductIds, setSelectedProductIds] = useState<string[]>([]);

  const allCategories = [...new Set(
    products.filter(p => p.active && p.category).map(p => p.category as string)
  )].sort();

  const activeProducts = products.filter(p => p.active);

  useEffect(() => {
    homeCatalogApi.get()
      .then((config) => {
        setMode(config.mode as CatalogMode);
        setShowPromotions(config.show_promotions);
        try { setSelectedCategories(JSON.parse(config.selected_categories || "[]")); } catch { /* ignore */ }
        try { setSelectedProductIds(JSON.parse(config.selected_product_ids || "[]")); } catch { /* ignore */ }
      })
      .catch(() => setError("Erro ao carregar configuração."))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setError("");
    try {
      await homeCatalogApi.update({
        mode,
        show_promotions: showPromotions,
        selected_categories: mode === "categories" ? selectedCategories : [],
        selected_product_ids: mode === "products" ? selectedProductIds : [],
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar configuração.");
    } finally {
      setSaving(false);
    }
  };

  const toggleCategory = (cat: string) =>
    setSelectedCategories(prev =>
      prev.includes(cat) ? prev.filter(c => c !== cat) : [...prev, cat]
    );

  const toggleProduct = (id: string) =>
    setSelectedProductIds(prev =>
      prev.includes(id) ? prev.filter(p => p !== id) : [...prev, id]
    );

  const selectAllProducts = () => setSelectedProductIds(activeProducts.map(p => p.id));
  const clearProductSelection = () => setSelectedProductIds([]);

  const modeOptions: { value: CatalogMode; label: string; description: string; icon: React.ReactNode }[] = [
    {
      value: "all",
      label: "Todos os produtos",
      description: "Exibe todos os produtos ativos do cardápio",
      icon: <List size={16} />,
    },
    {
      value: "categories",
      label: "Categorias específicas",
      description: "Exibe apenas produtos das categorias selecionadas",
      icon: <Tag size={16} />,
    },
    {
      value: "products",
      label: "Produtos específicos",
      description: "Exibe apenas os produtos escolhidos manualmente",
      icon: <Package size={16} />,
    },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-00 to-surface-00">
      <div className="flex h-screen">
        <AdminSidebar />
        <div className="flex-1 overflow-auto">

          {/* Header */}
          <div className="bg-surface-02 px-8 py-4 border-b border-surface-03 flex justify-between items-center sticky top-0 z-20">
            <div>
              <h2 className="text-2xl font-bold text-cream">Catálogo da Home</h2>
              <p className="text-stone text-sm">Controle o que é exibido na vitrine principal da loja</p>
            </div>
            <button
              onClick={handleSave}
              disabled={saving || loading}
              className={`flex items-center gap-2 font-bold py-2 px-5 rounded-lg transition-colors ${
                saved
                  ? "bg-green-500 text-white"
                  : saving
                  ? "bg-gold/50 text-cream cursor-not-allowed"
                  : "bg-gold hover:bg-gold/90 text-cream"
              }`}
            >
              {saving ? <Loader2 size={16} className="animate-spin" /> : saved ? <Check size={16} /> : <Save size={16} />}
              {saved ? "Salvo!" : saving ? "Salvando..." : "Salvar Configuração"}
            </button>
          </div>

          <div className="p-8 max-w-3xl space-y-6">
            {loading ? (
              <div className="flex items-center justify-center py-20 text-stone gap-3">
                <Loader2 size={22} className="animate-spin" />
                <span>Carregando configuração...</span>
              </div>
            ) : (
              <>
                {error && (
                  <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400 text-sm">
                    {error}
                  </div>
                )}

                {/* Banner de Promoções */}
                <div className="bg-surface-02 rounded-xl p-6 border border-surface-03">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-gold/10 flex items-center justify-center">
                        <Home size={18} className="text-gold" />
                      </div>
                      <div>
                        <h3 className="text-cream font-bold">Banner de Promoções</h3>
                        <p className="text-stone text-sm">Exibir o carrossel de promoções no topo da home</p>
                      </div>
                    </div>
                    <button
                      onClick={() => setShowPromotions(p => !p)}
                      className={`flex items-center gap-2 px-4 py-2 rounded-xl border-2 font-medium text-sm transition-all ${
                        showPromotions
                          ? "border-gold bg-gold/10 text-gold"
                          : "border-surface-03 text-stone hover:border-gold/40"
                      }`}
                    >
                      {showPromotions ? <Eye size={15} /> : <EyeOff size={15} />}
                      {showPromotions ? "Visível" : "Oculto"}
                    </button>
                  </div>
                  <p className="text-stone text-xs mt-3 pl-13">
                    {showPromotions
                      ? "✓ Banner ativo — as promoções cadastradas serão exibidas no topo da home."
                      : "✗ Banner oculto — nenhuma promoção será exibida no topo da home."}
                  </p>
                </div>

                {/* Modo do Catálogo */}
                <div className="bg-surface-02 rounded-xl p-6 border border-surface-03">
                  <div className="flex items-center gap-3 pb-4 border-b border-surface-03 mb-5">
                    <div className="w-10 h-10 rounded-xl bg-gold/10 flex items-center justify-center">
                      <List size={18} className="text-gold" />
                    </div>
                    <div>
                      <h3 className="text-cream font-bold">Modo do Catálogo</h3>
                      <p className="text-stone text-sm">Define o que será exibido no catálogo principal</p>
                    </div>
                  </div>

                  <div className="space-y-3">
                    {modeOptions.map((opt) => (
                      <button
                        key={opt.value}
                        onClick={() => setMode(opt.value)}
                        className={`w-full text-left p-4 rounded-xl border-2 transition-all ${
                          mode === opt.value
                            ? "border-gold bg-gold/10"
                            : "border-surface-03 hover:border-gold/40 hover:bg-surface-03/50"
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <span className={`${mode === opt.value ? "text-gold" : "text-stone"}`}>
                            {opt.icon}
                          </span>
                          <div>
                            <p className={`font-bold text-sm ${mode === opt.value ? "text-gold" : "text-cream"}`}>
                              {opt.label}
                            </p>
                            <p className="text-stone text-xs mt-0.5">{opt.description}</p>
                          </div>
                          {mode === opt.value && (
                            <Check size={16} className="text-gold ml-auto flex-shrink-0" />
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Seleção de Categorias */}
                {mode === "categories" && (
                  <div className="bg-surface-02 rounded-xl p-6 border border-surface-03">
                    <div className="flex items-center gap-3 pb-4 border-b border-surface-03 mb-5">
                      <div className="w-10 h-10 rounded-xl bg-gold/10 flex items-center justify-center">
                        <Tag size={18} className="text-gold" />
                      </div>
                      <div>
                        <h3 className="text-cream font-bold">Categorias Exibidas</h3>
                        <p className="text-stone text-sm">Selecione as categorias que aparecerão na vitrine</p>
                      </div>
                    </div>

                    {allCategories.length === 0 ? (
                      <div className="text-center py-6">
                        <p className="text-stone text-sm">Nenhuma categoria encontrada.</p>
                        <p className="text-stone text-xs mt-1">Cadastre produtos com categoria em <strong className="text-parchment">Produtos</strong>.</p>
                      </div>
                    ) : (
                      <>
                        <div className="flex flex-wrap gap-2 mb-3">
                          {allCategories.map(cat => (
                            <button
                              key={cat}
                              onClick={() => toggleCategory(cat)}
                              className={`px-4 py-2 rounded-full text-sm font-medium transition-all border-2 flex items-center gap-1.5 ${
                                selectedCategories.includes(cat)
                                  ? "bg-gold border-gold text-cream shadow-sm"
                                  : "bg-surface-03 border-surface-03 text-parchment hover:border-gold/40"
                              }`}
                            >
                              {selectedCategories.includes(cat) && <Check size={12} />}
                              {cat}
                            </button>
                          ))}
                        </div>
                        <p className="text-stone text-xs">
                          {selectedCategories.length === 0
                            ? "Nenhuma categoria selecionada — todos os produtos serão exibidos."
                            : `${selectedCategories.length} categoria(s) selecionada(s) — apenas produtos dessas categorias aparecerão na home.`}
                        </p>
                      </>
                    )}
                  </div>
                )}

                {/* Seleção de Produtos */}
                {mode === "products" && (
                  <div className="bg-surface-02 rounded-xl p-6 border border-surface-03">
                    <div className="flex items-center justify-between pb-4 border-b border-surface-03 mb-5">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gold/10 flex items-center justify-center">
                          <Package size={18} className="text-gold" />
                        </div>
                        <div>
                          <h3 className="text-cream font-bold">Produtos Exibidos</h3>
                          <p className="text-stone text-sm">Selecione os produtos que aparecerão na vitrine</p>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <button onClick={selectAllProducts} className="text-xs text-gold hover:text-gold/80 transition-colors px-2 py-1 rounded border border-gold/30 hover:border-gold/60">
                          Todos
                        </button>
                        <button onClick={clearProductSelection} className="text-xs text-stone hover:text-parchment transition-colors px-2 py-1 rounded border border-surface-03 hover:border-stone/40">
                          Limpar
                        </button>
                      </div>
                    </div>

                    {activeProducts.length === 0 ? (
                      <p className="text-stone text-sm text-center py-6">Nenhum produto ativo encontrado.</p>
                    ) : (
                      <>
                        <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
                          {activeProducts.map(p => {
                            const isSelected = selectedProductIds.includes(p.id);
                            return (
                              <button
                                key={p.id}
                                onClick={() => toggleProduct(p.id)}
                                className={`w-full flex items-center gap-3 p-3 rounded-xl border-2 transition-all text-left ${
                                  isSelected
                                    ? "border-gold bg-gold/10"
                                    : "border-surface-03 hover:border-gold/40 hover:bg-surface-03/50"
                                }`}
                              >
                                <div className="w-11 h-11 rounded-xl bg-surface-03 flex items-center justify-center flex-shrink-0 overflow-hidden">
                                  {isAssetUrl(p.icon)
                                    ? <img src={resolveAssetUrl(p.icon)} alt="" className="w-full h-full object-contain" />
                                    : <span className="text-xl">{p.icon || "🍕"}</span>}
                                </div>
                                <div className="flex-1 min-w-0">
                                  <p className={`text-sm font-semibold truncate ${isSelected ? "text-gold" : "text-cream"}`}>
                                    {p.name}
                                  </p>
                                  {p.category && (
                                    <p className="text-stone text-xs">{p.category}</p>
                                  )}
                                </div>
                                <span className={`text-sm font-bold flex-shrink-0 ${isSelected ? "text-gold" : "text-stone"}`}>
                                  R$ {p.price.toFixed(2)}
                                </span>
                                {isSelected && <Check size={15} className="text-gold flex-shrink-0" />}
                              </button>
                            );
                          })}
                        </div>
                        <p className="text-stone text-xs mt-3">
                          {selectedProductIds.length === 0
                            ? "Nenhum produto selecionado — selecione ao menos um produto."
                            : `${selectedProductIds.length} de ${activeProducts.length} produto(s) selecionado(s).`}
                        </p>
                      </>
                    )}
                  </div>
                )}

                {/* Resumo da configuração */}
                <div className="bg-surface-03/40 rounded-xl p-4 border border-surface-03 text-stone text-xs space-y-1">
                  <p className="text-parchment font-semibold text-sm mb-2">Resumo da Configuração Atual</p>
                  <p>• Banner de promoções: <span className={showPromotions ? "text-green-400" : "text-red-400"}>{showPromotions ? "Visível" : "Oculto"}</span></p>
                  <p>• Modo do catálogo: <span className="text-parchment">
                    {mode === "all" && "Todos os produtos"}
                    {mode === "categories" && `Categorias específicas (${selectedCategories.length} selecionada${selectedCategories.length !== 1 ? "s" : ""})`}
                    {mode === "products" && `Produtos específicos (${selectedProductIds.length} selecionado${selectedProductIds.length !== 1 ? "s" : ""})`}
                  </span></p>
                  <p className="text-stone/60 pt-1">Clique em <strong className="text-parchment">Salvar Configuração</strong> para aplicar as mudanças na loja.</p>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
