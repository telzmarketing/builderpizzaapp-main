import { useState, useCallback, useEffect } from "react";
import { Plus, Trash2, Edit2, Settings2, Tag, Ruler, X, Check, Loader2, ChefHat, Droplets } from "lucide-react";
import { useApp, Pizza, PricingRule } from "@/context/AppContext";
import AdminSidebar from "@/components/AdminSidebar";
import ImageUpload from "@/components/admin/ImageUpload";
import { sizesApi, crustApi, drinkVariantApi, categoriesApi, ApiProductSize, ApiProductCrustType, ApiProductDrinkVariant, ApiProductCategory, isAssetUrl, resolveAssetUrl } from "@/lib/api";
import { normalizeCrustPriceAddition } from "@/lib/pricing";

const PRICING_OPTIONS: { value: PricingRule; label: string; description: string }[] = [
  { value: "most_expensive", label: "Mais Caro", description: "Cliente paga pelo sabor mais caro (padrão iFood)" },
  { value: "average", label: "Média", description: "Preço é a média aritmética dos sabores" },
  { value: "proportional", label: "Proporcional", description: "Cada parte paga sua fração do sabor" },
];

type PTab = "produtos" | "categorias" | "config";

export default function AdminProducts() {
  const { products, addProduct, updateProduct, deleteProduct, multiFlavorsConfig, updateMultiFlavorsConfig } = useApp();
  const [activeTab, setActiveTab] = useState<PTab>("produtos");
  const [configSaved, setConfigSaved] = useState(false);
  const [catalogCategories, setCatalogCategories] = useState<ApiProductCategory[]>([]);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [categorySaving, setCategorySaving] = useState(false);

  const sortedCatalogCategories = [...catalogCategories].sort((a, b) => {
    if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order;
    return a.name.localeCompare(b.name);
  });
  const activeCatalogCategories = sortedCatalogCategories.filter((cat) => cat.active);
  const catalogCategoryNames = sortedCatalogCategories.map((cat) => cat.name);
  const legacyProductCategories = [...new Set(
    products
      .map((p) => (p.category || "").trim())
      .filter((cat) => cat && !catalogCategoryNames.includes(cat))
  )].sort();

  useEffect(() => {
    categoriesApi.list().then(setCatalogCategories).catch(() => setCatalogCategories([]));
  }, []);

  const handleAddCategory = async () => {
    const name = newCategoryName.trim();
    if (!name) return;
    setCategorySaving(true);
    try {
      const created = await categoriesApi.create({
        name,
        active: true,
        sort_order: catalogCategories.length,
      });
      setCatalogCategories((prev) => [...prev, created]);
      setNewCategoryName("");
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao criar categoria.");
    } finally {
      setCategorySaving(false);
    }
  };

  const handleDeleteCategory = async (category: ApiProductCategory) => {
    if (!confirm(`Remover a categoria "${category.name}"?`)) return;
    try {
      await categoriesApi.remove(category.id);
      setCatalogCategories((prev) => prev.filter((cat) => cat.id !== category.id));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao remover categoria.");
    }
  };

  // ── Products CRUD ────────────────────────────────────────────────────────────
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<Partial<Pizza> & { product_type?: string }>({
    name: "", description: "", price: 0, icon: "🍕", category: "", rating: 4.5, product_type: "pizza",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name || !formData.description || !formData.price) {
      alert("Preencha todos os campos obrigatórios");
      return;
    }
    const category = ((formData as any).category || "").trim();
    if (category && !catalogCategoryNames.includes(category)) {
      alert("Selecione uma categoria cadastrada na aba Categorias.");
      return;
    }
    try {
      if (editingId) {
        await updateProduct(editingId, { ...formData, category: category || null } as any);
        setEditingId(null);
      } else {
        await addProduct({
          name: formData.name!, description: formData.description!,
          price: formData.price!, icon: formData.icon || "🍕",
          category: category || null,
          product_type: formData.product_type || "pizza",
          rating: formData.rating || 4.5, active: true,
        } as any);
      }
      setFormData({ name: "", description: "", price: 0, icon: "🍕", category: "", rating: 4.5, product_type: "pizza" });
      setShowForm(false);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao salvar produto.");
    }
  };

  const handleEdit = (product: Pizza) => {
    setFormData({
      ...product,
      category: (product as any).category ?? "",
      product_type: (product as any).product_type ?? "pizza",
    });
    setEditingId(product.id);
    setShowForm(true);
  };

  const handleConfigSave = async () => {
    try {
      await updateMultiFlavorsConfig(multiFlavorsConfig);
      setConfigSaved(true);
      setTimeout(() => setConfigSaved(false), 2000);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao salvar configuração.");
    }
  };

  // ── Sizes modal ──────────────────────────────────────────────────────────────
  const [sizesModalProduct, setSizesModalProduct] = useState<Pizza | null>(null);
  const [productSizes, setProductSizes] = useState<ApiProductSize[]>([]);
  const [sizesLoading, setSizesLoading] = useState(false);
  const [sizeForm, setSizeForm] = useState({ label: "", description: "", price: "", is_default: false });
  const [savingSizeId, setSavingSizeId] = useState<string | null>(null);

  const openSizesModal = useCallback(async (product: Pizza) => {
    setSizesModalProduct(product);
    setSizesLoading(true);
    try {
      const sizes = await sizesApi.list(product.id);
      setProductSizes(sizes);
    } catch {
      setProductSizes([]);
    } finally {
      setSizesLoading(false);
    }
  }, []);

  const closeSizesModal = () => {
    setSizesModalProduct(null);
    setProductSizes([]);
    setSizeForm({ label: "", description: "", price: "", is_default: false });
  };

  const handleAddSize = async () => {
    if (!sizesModalProduct || !sizeForm.label.trim() || !sizeForm.price) return;
    const price = parseFloat(sizeForm.price);
    if (isNaN(price) || price <= 0) { alert("Preço inválido."); return; }
    try {
      const created = await sizesApi.create(sizesModalProduct.id, {
        label: sizeForm.label.trim(),
        description: sizeForm.description.trim() || null,
        price,
        is_default: sizeForm.is_default,
        sort_order: productSizes.length,
        active: true,
      } as any);
      setProductSizes((prev) => [...prev, created]);
      setSizeForm({ label: "", description: "", price: "", is_default: false });
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao adicionar tamanho.");
    }
  };

  const handleToggleSizeField = async (size: ApiProductSize, field: "is_default" | "active") => {
    if (!sizesModalProduct) return;
    setSavingSizeId(size.id);
    try {
      const updated = await sizesApi.update(sizesModalProduct.id, size.id, { [field]: !size[field] });
      setProductSizes((prev) => prev.map((s) => (s.id === size.id ? updated : s)));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao atualizar tamanho.");
    } finally {
      setSavingSizeId(null);
    }
  };

  const handleUpdateSizePrice = async (size: ApiProductSize, value: string) => {
    if (!sizesModalProduct) return;
    const price = parseFloat(value);
    if (isNaN(price) || price <= 0) {
      alert("Preco invalido.");
      return;
    }
    if (Math.abs(price - size.price) < 0.001) return;
    setSavingSizeId(size.id);
    try {
      const updated = await sizesApi.update(sizesModalProduct.id, size.id, { price });
      setProductSizes((prev) => prev.map((s) => (s.id === size.id ? updated : s)));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao atualizar preco.");
    } finally {
      setSavingSizeId(null);
    }
  };

  const handleDeleteSize = async (sizeId: string) => {
    if (!sizesModalProduct) return;
    if (!confirm("Remover este tamanho?")) return;
    try {
      await sizesApi.remove(sizesModalProduct.id, sizeId);
      setProductSizes((prev) => prev.filter((s) => s.id !== sizeId));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao remover tamanho.");
    }
  };

  // ── Crust modal (pizza) ───────────────────────────────────────────────────────
  const [crustModalProduct, setCrustModalProduct] = useState<Pizza | null>(null);
  const [productCrusts, setProductCrusts] = useState<ApiProductCrustType[]>([]);
  const [crustsLoading, setCrustsLoading] = useState(false);
  const [crustForm, setCrustForm] = useState({ name: "", price_addition: "" });
  const [savingCrustId, setSavingCrustId] = useState<string | null>(null);

  const openCrustModal = useCallback(async (product: Pizza) => {
    setCrustModalProduct(product);
    setCrustsLoading(true);
    try {
      const crusts = await crustApi.list(product.id);
      setProductCrusts(crusts);
    } catch {
      setProductCrusts([]);
    } finally {
      setCrustsLoading(false);
    }
  }, []);

  const closeCrustModal = () => {
    setCrustModalProduct(null);
    setProductCrusts([]);
    setCrustForm({ name: "", price_addition: "" });
  };

  const handleAddCrust = async () => {
    if (!crustModalProduct || !crustForm.name.trim()) return;
    const priceAdd = parseFloat(crustForm.price_addition || "0");
    try {
      const created = await crustApi.create(crustModalProduct.id, {
        name: crustForm.name.trim(),
        price_addition: isNaN(priceAdd) ? 0 : priceAdd,
        active: true,
        sort_order: productCrusts.length,
      } as any);
      setProductCrusts((prev) => [...prev, created]);
      setCrustForm({ name: "", price_addition: "" });
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao adicionar tipo de massa.");
    }
  };

  const handleToggleCrustActive = async (crust: ApiProductCrustType) => {
    if (!crustModalProduct) return;
    setSavingCrustId(crust.id);
    try {
      const updated = await crustApi.update(crustModalProduct.id, crust.id, { active: !crust.active });
      setProductCrusts((prev) => prev.map((c) => (c.id === crust.id ? updated : c)));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao atualizar massa.");
    } finally {
      setSavingCrustId(null);
    }
  };

  const handleUpdateCrustPrice = async (crust: ApiProductCrustType, value: string) => {
    if (!crustModalProduct) return;
    const priceAddition = parseFloat(value || "0");
    if (isNaN(priceAddition) || priceAddition < 0) {
      alert("Preco invalido.");
      return;
    }
    if (Math.abs(priceAddition - crust.price_addition) < 0.001) return;
    setSavingCrustId(crust.id);
    try {
      const updated = await crustApi.update(crustModalProduct.id, crust.id, { price_addition: priceAddition });
      setProductCrusts((prev) => prev.map((c) => (c.id === crust.id ? updated : c)));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao atualizar adicional da massa.");
    } finally {
      setSavingCrustId(null);
    }
  };

  const handleDeleteCrust = async (crustId: string) => {
    if (!crustModalProduct) return;
    if (!confirm("Remover este tipo de massa?")) return;
    try {
      await crustApi.remove(crustModalProduct.id, crustId);
      setProductCrusts((prev) => prev.filter((c) => c.id !== crustId));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao remover massa.");
    }
  };

  // ── Drink variants modal ──────────────────────────────────────────────────────
  const [drinkModalProduct, setDrinkModalProduct] = useState<Pizza | null>(null);
  const [productDrinkVariants, setProductDrinkVariants] = useState<ApiProductDrinkVariant[]>([]);
  const [drinkLoading, setDrinkLoading] = useState(false);
  const [drinkForm, setDrinkForm] = useState({ name: "", price_addition: "" });
  const [savingDrinkId, setSavingDrinkId] = useState<string | null>(null);

  const openDrinkModal = useCallback(async (product: Pizza) => {
    setDrinkModalProduct(product);
    setDrinkLoading(true);
    try {
      const variants = await drinkVariantApi.list(product.id);
      setProductDrinkVariants(variants);
    } catch {
      setProductDrinkVariants([]);
    } finally {
      setDrinkLoading(false);
    }
  }, []);

  const closeDrinkModal = () => {
    setDrinkModalProduct(null);
    setProductDrinkVariants([]);
    setDrinkForm({ name: "", price_addition: "" });
  };

  const handleAddDrinkVariant = async () => {
    if (!drinkModalProduct || !drinkForm.name.trim()) return;
    const priceAdd = parseFloat(drinkForm.price_addition || "0");
    try {
      const created = await drinkVariantApi.create(drinkModalProduct.id, {
        name: drinkForm.name.trim(),
        price_addition: isNaN(priceAdd) ? 0 : priceAdd,
        active: true,
        sort_order: productDrinkVariants.length,
      } as any);
      setProductDrinkVariants((prev) => [...prev, created]);
      setDrinkForm({ name: "", price_addition: "" });
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao adicionar variante.");
    }
  };

  const handleToggleDrinkActive = async (variant: ApiProductDrinkVariant) => {
    if (!drinkModalProduct) return;
    setSavingDrinkId(variant.id);
    try {
      const updated = await drinkVariantApi.update(drinkModalProduct.id, variant.id, { active: !variant.active });
      setProductDrinkVariants((prev) => prev.map((v) => (v.id === variant.id ? updated : v)));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao atualizar variante.");
    } finally {
      setSavingDrinkId(null);
    }
  };

  const handleDeleteDrinkVariant = async (variantId: string) => {
    if (!drinkModalProduct) return;
    if (!confirm("Remover esta variante?")) return;
    try {
      await drinkVariantApi.remove(drinkModalProduct.id, variantId);
      setProductDrinkVariants((prev) => prev.filter((v) => v.id !== variantId));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao remover variante.");
    }
  };

  // ── Presets ───────────────────────────────────────────────────────────────────
  const SIZE_PRESETS = [
    { label: "Brotinho", description: "Individual" },
    { label: "Pizza Grande", description: "Grande" },
  ];

  const CRUST_PRESETS = [
    { name: "Napolitana", price_addition: "0" },
    { name: "Tradicional", price_addition: "0" },
  ];

  const DRINK_SIZE_PRESETS = [
    { label: "Lata", description: "350ml" },
    { label: "600ml", description: "" },
    { label: "1 Litro", description: "" },
    { label: "2 Litros", description: "" },
  ];

  const DRINK_VARIANT_PRESETS = [
    { name: "Normal", price_addition: "0" },
    { name: "Zero", price_addition: "0" },
    { name: "Sem Açúcar", price_addition: "0" },
  ];

  const cls = "w-full bg-surface-03 border border-surface-03 rounded-lg px-4 py-2 text-cream placeholder-stone focus:outline-none focus:border-gold text-sm";

  const getTypeIcon = (type: string | null | undefined) => {
    if (type === "drink") return "🥤";
    if (type === "other") return "🍔";
    return "🍕";
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-00 to-surface-00">
      <div className="flex h-screen">
        <AdminSidebar />
        <div className="flex-1 overflow-auto">

          {/* Header */}
          <div className="bg-surface-02 px-8 py-4 border-b border-surface-03 flex justify-between items-center sticky top-0 z-20">
            <div>
              <h2 className="text-2xl font-bold text-cream">Produtos</h2>
              <p className="text-stone text-sm">{products.length} produtos · {sortedCatalogCategories.length} categorias cadastradas</p>
            </div>
            {activeTab === "produtos" && (
              <button
                onClick={() => { setShowForm(!showForm); setEditingId(null); setFormData({ name: "", description: "", price: 0, icon: "🍕", category: "", rating: 4.5, product_type: "pizza" }); }}
                className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-4 rounded-lg transition-colors"
              >
                <Plus size={20} />
                Novo Produto
              </button>
            )}
          </div>

          {/* Tabs */}
          <div className="px-8 pt-4 flex gap-2">
            {([
              { key: "produtos", label: "Produtos" },
              { key: "categorias", label: "Categorias" },
              { key: "config", label: "Configurações" },
            ] as { key: PTab; label: string }[]).map(({ key, label }) => (
              <button key={key} onClick={() => setActiveTab(key)}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${activeTab === key ? "bg-gold text-cream" : "bg-surface-02 text-parchment hover:bg-surface-03 border border-surface-03"}`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="p-8">

            {/* ── TAB: PRODUTOS ── */}
            {activeTab === "produtos" && (
              <>
                {showForm && (
                  <div className="bg-surface-02 rounded-xl p-6 border border-surface-03 mb-8">
                    <h3 className="text-xl font-bold text-cream mb-4">{editingId ? "Editar Produto" : "Novo Produto"}</h3>
                    <form onSubmit={handleSubmit} className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-parchment text-sm font-medium mb-2">Nome do Produto *</label>
                          <input type="text" value={formData.name || ""} onChange={(e) => setFormData({ ...formData, name: e.target.value })} className={cls} placeholder="Ex: Pizza Pepperoni" />
                        </div>
                        <div>
                          <label className="block text-parchment text-sm font-medium mb-2">Preço (R$) *</label>
                          <input type="number" value={formData.price || ""} onChange={(e) => setFormData({ ...formData, price: parseFloat(e.target.value) })} className={cls} placeholder="12.99" step="0.01" />
                        </div>
                      </div>
                      <div>
                        <label className="block text-parchment text-sm font-medium mb-2">Descrição *</label>
                        <textarea value={formData.description || ""} onChange={(e) => setFormData({ ...formData, description: e.target.value })} className={`${cls} resize-none`} placeholder="Descreva o produto..." rows={3} />
                      </div>
                      <div>
                        <div className="flex items-center justify-between gap-3 mb-2">
                          <label className="block text-parchment text-sm font-medium">Categoria</label>
                          <button
                            type="button"
                            onClick={() => setActiveTab("categorias")}
                            className="text-xs text-gold hover:text-gold-light font-semibold"
                          >
                            Gerenciar categorias
                          </button>
                        </div>
                        <select
                          value={(formData as any).category || ""}
                          onChange={(e) => setFormData({ ...formData, category: e.target.value } as any)}
                          className={cls}
                          disabled={activeCatalogCategories.length === 0}
                        >
                          <option value="">
                            {activeCatalogCategories.length === 0 ? "Cadastre uma categoria na aba Categorias" : "Selecione uma categoria"}
                          </option>
                          {activeCatalogCategories.map((cat) => (
                            <option key={cat.id} value={cat.name}>{cat.name}</option>
                          ))}
                          {(formData as any).category && !catalogCategoryNames.includes((formData as any).category) && (
                            <option value={(formData as any).category}>Categoria atual nao cadastrada: {(formData as any).category}</option>
                          )}
                        </select>
                        {(formData as any).category && !catalogCategoryNames.includes((formData as any).category) && (
                          <p className="text-amber-400 text-xs mt-2">
                            Esta categoria veio de um produto antigo. Crie ela na aba Categorias ou selecione uma categoria cadastrada.
                          </p>
                        )}
                      </div>
                      <div className="grid grid-cols-2 gap-4 items-start">
                        <ImageUpload
                          value={formData.icon || ""}
                          onChange={(v) => setFormData({ ...formData, icon: v })}
                          label="Ícone / Imagem do produto"
                          sizeGuide="Tamanho recomendado: 200×200px, máx. 512KB"
                          hint="Faça upload de uma imagem ou use um emoji 🍕"
                          maxKB={512}
                        />
                        <div>
                          <label className="block text-parchment text-sm font-medium mb-2">Avaliação (1–5)</label>
                          <input type="number" value={formData.rating || ""} onChange={(e) => setFormData({ ...formData, rating: parseFloat(e.target.value) })} className={cls} placeholder="4.5" min="1" max="5" step="0.1" />
                        </div>
                      </div>

                      {/* Dica de próximos passos */}
                      {!editingId && (
                        <div className="bg-surface-03/60 rounded-lg p-3 text-stone text-xs">
                          {(formData.product_type || "pizza") === "pizza" && (
                            <span>💡 Após criar a pizza, use <strong className="text-parchment">Gerenciar Tamanhos</strong> e <strong className="text-parchment">Gerenciar Massas</strong> no card do produto.</span>
                          )}
                          {formData.product_type === "drink" && (
                            <span>💡 Após criar a bebida, use <strong className="text-parchment">Gerenciar Tamanhos</strong> e <strong className="text-parchment">Gerenciar Variantes</strong> no card do produto.</span>
                          )}
                          {formData.product_type === "other" && (
                            <span>💡 Após criar o produto, use <strong className="text-parchment">Gerenciar Tamanhos</strong> para configurar variações de tamanho e preço.</span>
                          )}
                        </div>
                      )}

                      <div className="flex gap-3 pt-4">
                        <button type="submit" className="flex-1 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-4 rounded-lg transition-colors">
                          {editingId ? "Salvar Alterações" : "Adicionar Produto"}
                        </button>
                        <button type="button" onClick={() => { setShowForm(false); setEditingId(null); }} className="flex-1 bg-surface-03 hover:bg-brand-mid text-cream font-bold py-2 px-4 rounded-lg transition-colors">
                          Cancelar
                        </button>
                      </div>
                    </form>
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {products.map((product) => {
                    const pType = (product as any).product_type as string | null | undefined;
                    const isPizza = !pType || pType === "pizza";
                    const isDrink = pType === "drink";
                    return (
                      <div key={product.id} className="bg-surface-02 rounded-xl p-6 border border-surface-03">
                        <div className="flex items-start gap-3 mb-3">
                          <div className="w-14 h-14 rounded-xl bg-surface-03 flex items-center justify-center flex-shrink-0 overflow-hidden">
                            {isAssetUrl(product.icon) ? (
                              <img src={resolveAssetUrl(product.icon)} alt={product.name} className="w-full h-full object-contain" />
                            ) : (
                              <span className="text-3xl">{product.icon || getTypeIcon(pType)}</span>
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <h3 className="text-lg font-bold text-cream leading-tight">{product.name}</h3>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {(product as any).category && (
                                <span className="inline-flex items-center gap-1 text-xs bg-gold/20 text-gold border border-gold/30 px-2 py-0.5 rounded-full">
                                  <Tag size={10} />
                                  {(product as any).category}
                                </span>
                              )}
                              <span className="inline-flex items-center gap-1 text-xs bg-surface-03 text-stone border border-surface-03 px-2 py-0.5 rounded-full">
                                {getTypeIcon(pType)} {pType === "drink" ? "Bebida" : pType === "other" ? "Outros" : "Pizza"}
                              </span>
                            </div>
                          </div>
                        </div>

                        <p className="text-stone text-sm mb-3 line-clamp-2">{product.description}</p>
                        <div className="flex justify-between items-center mb-4">
                          <span className="text-gold font-bold">R$ {product.price.toFixed(2)}</span>
                          <span className="text-stone text-sm">⭐ {product.rating}</span>
                        </div>

                        <div className="flex gap-2 mb-2">
                          <button onClick={() => handleEdit(product)} className="flex-1 flex items-center justify-center gap-2 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 font-medium py-2 px-3 rounded-lg transition-colors">
                            <Edit2 size={16} />
                            Editar
                          </button>
                          <button onClick={() => deleteProduct(product.id)} className="flex items-center justify-center gap-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 font-medium py-2 px-3 rounded-lg transition-colors">
                            <Trash2 size={16} />
                          </button>
                        </div>

                        <button onClick={() => openSizesModal(product)} className="w-full flex items-center justify-center gap-2 bg-surface-03 hover:bg-gold/10 hover:border-gold/40 text-parchment hover:text-gold font-medium py-2 px-3 rounded-lg transition-colors border border-surface-03 text-sm mb-2">
                          <Ruler size={15} />
                          Gerenciar Tamanhos
                          {(product as any).sizes && (product as any).sizes.length > 0 && (
                            <span className="ml-auto text-xs bg-gold/20 text-gold px-1.5 py-0.5 rounded-full">{(product as any).sizes.length}</span>
                          )}
                        </button>

                        {isPizza && (
                          <button onClick={() => openCrustModal(product)} className="w-full flex items-center justify-center gap-2 bg-surface-03 hover:bg-amber-500/10 hover:border-amber-500/40 text-parchment hover:text-amber-400 font-medium py-2 px-3 rounded-lg transition-colors border border-surface-03 text-sm mb-2">
                            <ChefHat size={15} />
                            Gerenciar Massas
                            {(product as any).crust_types && (product as any).crust_types.length > 0 && (
                              <span className="ml-auto text-xs bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded-full">{(product as any).crust_types.length}</span>
                            )}
                          </button>
                        )}

                        {isDrink && (
                          <button onClick={() => openDrinkModal(product)} className="w-full flex items-center justify-center gap-2 bg-surface-03 hover:bg-blue-500/10 hover:border-blue-500/40 text-parchment hover:text-blue-400 font-medium py-2 px-3 rounded-lg transition-colors border border-surface-03 text-sm">
                            <Droplets size={15} />
                            Gerenciar Variantes (Normal/Zero)
                            {(product as any).drink_variants && (product as any).drink_variants.length > 0 && (
                              <span className="ml-auto text-xs bg-blue-500/20 text-blue-400 px-1.5 py-0.5 rounded-full">{(product as any).drink_variants.length}</span>
                            )}
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>

                {products.length === 0 && (
                  <div className="text-center py-12">
                    <p className="text-stone text-lg">Nenhum produto cadastrado</p>
                    <button onClick={() => setShowForm(true)} className="mt-4 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-6 rounded-lg transition-colors inline-flex items-center gap-2">
                      <Plus size={20} /> Adicionar Primeiro Produto
                    </button>
                  </div>
                )}
              </>
            )}

            {/* ── TAB: CATEGORIAS ── */}
            {activeTab === "categorias" && (
              <div className="max-w-xl space-y-4">
                <div className="bg-surface-02 rounded-xl p-6 border border-surface-03 space-y-4">
                  <div className="flex items-center gap-3 pb-3 border-b border-surface-03">
                    <Tag size={18} className="text-gold" />
                    <div>
                      <h3 className="text-cream font-bold">Categorias do Cardapio</h3>
                      <p className="text-stone text-sm">Crie categorias para usar no cadastro dos produtos.</p>
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newCategoryName}
                      onChange={(e) => setNewCategoryName(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); handleAddCategory(); } }}
                      className={cls}
                      placeholder="Ex: Pizzas, Bebidas, Sobremesas..."
                      maxLength={100}
                    />
                    <button
                      type="button"
                      onClick={handleAddCategory}
                      disabled={categorySaving || !newCategoryName.trim()}
                      className="flex items-center gap-2 bg-gold hover:bg-gold/90 disabled:opacity-50 disabled:cursor-not-allowed text-cream font-bold py-2 px-4 rounded-lg transition-colors"
                    >
                      {categorySaving ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
                      Criar
                    </button>
                  </div>

                  {sortedCatalogCategories.length === 0 ? (
                    <p className="text-stone text-sm text-center py-4">
                      Nenhuma categoria cadastrada.
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {sortedCatalogCategories.map((category) => (
                        <div key={category.id} className="flex items-center gap-3 bg-surface-03 rounded-xl px-4 py-3">
                          <Tag size={14} className="text-gold flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="text-cream text-sm font-bold">{category.name}</p>
                            <p className="text-stone text-xs">
                              {category.active ? "Ativa para seleção no produto" : "Inativa"}
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleDeleteCategory(category)}
                            className="text-stone hover:text-red-400 transition-colors p-1.5"
                            title="Remover categoria"
                          >
                            <X size={14} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  {legacyProductCategories.length > 0 && (
                    <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 text-amber-300 text-xs leading-relaxed">
                      Categorias antigas encontradas em produtos: {legacyProductCategories.join(", ")}. Para usar no cadastro, crie essas categorias aqui na aba Categorias.
                    </div>
                  )}

                  <div className="bg-surface-03 rounded-lg p-3 text-stone text-xs leading-relaxed">
                    Depois de criar a categoria, selecione ela no campo <strong className="text-parchment">Categoria</strong> do produto. Categorias sem produto ficam disponiveis no painel, mas so aparecem na loja quando houver produto ativo vinculado.
                  </div>
                </div>
              </div>
            )}

            {/* ── TAB: CONFIG ── */}
            {activeTab === "config" && (
              <div className="max-w-xl">
                <div className="bg-surface-02 rounded-xl p-6 border border-surface-03 space-y-4">
                  <div className="flex items-center gap-3 pb-3 border-b border-surface-03">
                    <Settings2 size={18} className="text-gold" />
                    <div>
                      <h3 className="text-cream font-bold">Configuração de Multi-Sabores</h3>
                      <p className="text-stone text-sm">Define como pizzas meio-a-meio são precificadas</p>
                    </div>
                  </div>

                  <div>
                    <label className="block text-parchment text-sm font-medium mb-2">Máximo de sabores por pizza</label>
                    <div className="flex gap-3">
                      {[2, 3].map((n) => (
                        <button
                          key={n}
                          onClick={() => updateMultiFlavorsConfig({ ...multiFlavorsConfig, maxFlavors: n as 2 | 3 })}
                          className={`flex-1 py-3 rounded-xl border-2 font-bold transition-all ${multiFlavorsConfig.maxFlavors === n ? "border-gold bg-gold/10 text-gold" : "border-surface-03 text-stone hover:border-gold/50"}`}
                        >
                          {n} sabores
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="block text-parchment text-sm font-medium mb-3">Regra de precificação</label>
                    <div className="space-y-2">
                      {PRICING_OPTIONS.map((opt) => (
                        <button
                          key={opt.value}
                          onClick={() => updateMultiFlavorsConfig({ ...multiFlavorsConfig, pricingRule: opt.value })}
                          className={`w-full text-left p-3 rounded-xl border-2 transition-all ${multiFlavorsConfig.pricingRule === opt.value ? "border-gold bg-gold/10" : "border-surface-03 hover:border-gold/50"}`}
                        >
                          <p className={`font-bold text-sm ${multiFlavorsConfig.pricingRule === opt.value ? "text-gold" : "text-cream"}`}>{opt.label}</p>
                          <p className="text-stone text-xs mt-0.5">{opt.description}</p>
                        </button>
                      ))}
                    </div>
                  </div>

                  <button
                    onClick={handleConfigSave}
                    className={`w-full py-3 rounded-xl font-bold text-sm transition-colors ${configSaved ? "bg-green-500 text-white" : "bg-gold hover:bg-gold/90 text-cream"}`}
                  >
                    {configSaved ? "✓ Salvo!" : "Salvar Configurações"}
                  </button>
                </div>
              </div>
            )}

          </div>
        </div>
      </div>

      {/* ── Sizes Modal ───────────────────────────────────────────────────────── */}
      {sizesModalProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-surface-02 rounded-2xl border border-surface-03 w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-2xl">
            <div className="flex items-center justify-between px-6 py-4 border-b border-surface-03 sticky top-0 bg-surface-02 z-10">
              <div className="flex items-center gap-3">
                <Ruler size={18} className="text-gold" />
                <div>
                  <h3 className="text-cream font-bold">Tamanhos</h3>
                  <p className="text-stone text-xs">{sizesModalProduct.name}</p>
                </div>
              </div>
              <button onClick={closeSizesModal} className="text-stone hover:text-cream transition-colors">
                <X size={20} />
              </button>
            </div>

            <div className="p-6 space-y-6">
              <div>
                <h4 className="text-parchment text-sm font-semibold mb-3">Tamanhos cadastrados</h4>
                {sizesLoading ? (
                  <div className="flex items-center justify-center py-6 text-stone gap-2">
                    <Loader2 size={16} className="animate-spin" />
                    <span className="text-sm">Carregando...</span>
                  </div>
                ) : productSizes.length === 0 ? (
                  <p className="text-stone text-sm text-center py-4">Nenhum tamanho cadastrado. Este produto usará os tamanhos padrão.</p>
                ) : (
                  <div className="space-y-2">
                    {productSizes.map((size) => (
                      <div key={size.id} className="flex items-center gap-3 bg-surface-03 rounded-xl px-4 py-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-cream font-bold text-sm">{size.label}</span>
                            {size.is_default && <span className="text-[10px] bg-gold/20 text-gold border border-gold/30 px-1.5 py-0.5 rounded-full">padrão</span>}
                            {!size.active && <span className="text-[10px] bg-red-500/20 text-red-400 border border-red-500/30 px-1.5 py-0.5 rounded-full">inativo</span>}
                          </div>
                          {size.description && <p className="text-stone text-xs mt-0.5">{size.description}</p>}
                        </div>
                        <input
                          type="number"
                          defaultValue={size.price.toFixed(2)}
                          onBlur={(e) => handleUpdateSizePrice(size, e.target.value)}
                          disabled={savingSizeId === size.id}
                          className="w-24 bg-surface-02 border border-surface-03 rounded-lg px-2 py-1 text-gold font-bold text-sm outline-none focus:border-gold"
                          step="0.01"
                          min="0.01"
                          title="Preco deste tamanho"
                        />
                        <div className="flex items-center gap-1 flex-shrink-0">
                          <button onClick={() => handleToggleSizeField(size, "is_default")} disabled={savingSizeId === size.id} title={size.is_default ? "Remover como padrão" : "Marcar como padrão"} className={`p-1.5 rounded-lg transition-colors ${size.is_default ? "bg-gold/20 text-gold" : "text-stone hover:text-gold"}`}>
                            {savingSizeId === size.id ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
                          </button>
                          <button onClick={() => handleToggleSizeField(size, "active")} disabled={savingSizeId === size.id} title={size.active ? "Desativar" : "Ativar"} className={`p-1.5 rounded-lg transition-colors ${size.active ? "text-green-400 hover:text-red-400" : "text-red-400 hover:text-green-400"}`}>
                            <Settings2 size={13} />
                          </button>
                          <button onClick={() => handleDeleteSize(size.id)} className="p-1.5 rounded-lg text-stone hover:text-red-400 transition-colors">
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="border-t border-surface-03 pt-5">
                <h4 className="text-parchment text-sm font-semibold mb-3">Adicionar Tamanho</h4>
                <div className="mb-3">
                  <p className="text-stone text-xs mb-2">Atalhos rápidos:</p>
                  <div className="flex gap-2 flex-wrap">
                    {((sizesModalProduct as any).product_type === "drink" ? DRINK_SIZE_PRESETS : SIZE_PRESETS).map((preset) => (
                      <button key={preset.label} onClick={() => setSizeForm((f) => ({ ...f, label: preset.label, description: preset.description }))} className="text-xs bg-surface-03 hover:bg-gold/10 hover:text-gold text-parchment border border-surface-03 hover:border-gold/30 px-3 py-1.5 rounded-full transition-colors">
                        {preset.label}{preset.description ? ` / ${preset.description}` : ""}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-parchment text-xs font-medium mb-1">Rótulo *</label>
                      <input type="text" value={sizeForm.label} onChange={(e) => setSizeForm((f) => ({ ...f, label: e.target.value }))} className={cls} placeholder={(sizesModalProduct as any).product_type === "drink" ? 'Ex: "600ml"' : 'Ex: "Brotinho"'} maxLength={50} />
                    </div>
                    <div>
                      <label className="block text-parchment text-xs font-medium mb-1">Preço (R$) *</label>
                      <input type="number" value={sizeForm.price} onChange={(e) => setSizeForm((f) => ({ ...f, price: e.target.value }))} className={cls} placeholder="29.90" step="0.01" min="0.01" />
                    </div>
                  </div>
                  <div>
                    <label className="block text-parchment text-xs font-medium mb-1">Descrição (opcional)</label>
                    <input type="text" value={sizeForm.description} onChange={(e) => setSizeForm((f) => ({ ...f, description: e.target.value }))} className={cls} placeholder='Ex: "Serve 2 pessoas"' maxLength={100} />
                  </div>
                  <div className="flex items-center gap-2">
                    <input type="checkbox" id="size-default" checked={sizeForm.is_default} onChange={(e) => setSizeForm((f) => ({ ...f, is_default: e.target.checked }))} className="accent-gold" />
                    <label htmlFor="size-default" className="text-parchment text-xs cursor-pointer">Marcar como tamanho padrão</label>
                  </div>
                  <button onClick={handleAddSize} className="w-full flex items-center justify-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2.5 rounded-xl transition-colors text-sm">
                    <Plus size={15} /> Adicionar Tamanho
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Crust Modal (Pizza) ──────────────────────────────────────────────── */}
      {crustModalProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-surface-02 rounded-2xl border border-surface-03 w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-2xl">
            <div className="flex items-center justify-between px-6 py-4 border-b border-surface-03 sticky top-0 bg-surface-02 z-10">
              <div className="flex items-center gap-3">
                <ChefHat size={18} className="text-amber-400" />
                <div>
                  <h3 className="text-cream font-bold">Tipos de Massa</h3>
                  <p className="text-stone text-xs">{crustModalProduct.name}</p>
                </div>
              </div>
              <button onClick={closeCrustModal} className="text-stone hover:text-cream transition-colors">
                <X size={20} />
              </button>
            </div>

            <div className="p-6 space-y-6">
              <div>
                <h4 className="text-parchment text-sm font-semibold mb-3">Massas cadastradas</h4>
                {crustsLoading ? (
                  <div className="flex items-center justify-center py-6 text-stone gap-2">
                    <Loader2 size={16} className="animate-spin" />
                    <span className="text-sm">Carregando...</span>
                  </div>
                ) : productCrusts.length === 0 ? (
                  <p className="text-stone text-sm text-center py-4">Nenhum tipo de massa cadastrado. O cliente não verá opção de massa.</p>
                ) : (
                  <div className="space-y-2">
                    {productCrusts.map((crust) => {
                      const effectiveAddition = normalizeCrustPriceAddition(crust.price_addition, crustModalProduct.price);
                      const isLegacyDuplicate = crust.price_addition > 0 && effectiveAddition === 0;
                      return (
                      <div key={crust.id} className="flex items-center gap-3 bg-surface-03 rounded-xl px-4 py-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-cream font-bold text-sm">{crust.name}</span>
                            {!crust.active && <span className="text-[10px] bg-red-500/20 text-red-400 border border-red-500/30 px-1.5 py-0.5 rounded-full">inativo</span>}
                          </div>
                          {isLegacyDuplicate && (
                            <p className="text-amber-400 text-[11px] mt-1">Valor antigo igual ao preco da pizza: tratado como sem adicional.</p>
                          )}
                        </div>
                        <input
                          type="number"
                          defaultValue={effectiveAddition.toFixed(2)}
                          onBlur={(e) => handleUpdateCrustPrice(crust, e.target.value)}
                          disabled={savingCrustId === crust.id}
                          className="w-24 bg-surface-02 border border-surface-03 rounded-lg px-2 py-1 text-amber-400 font-bold text-sm outline-none focus:border-amber-400"
                          step="0.01"
                          min="0"
                          title="Adicional da massa"
                        />
                        <div className="flex items-center gap-1 flex-shrink-0">
                          <button onClick={() => handleToggleCrustActive(crust)} disabled={savingCrustId === crust.id} title={crust.active ? "Desativar" : "Ativar"} className={`p-1.5 rounded-lg transition-colors ${crust.active ? "text-green-400 hover:text-red-400" : "text-red-400 hover:text-green-400"}`}>
                            {savingCrustId === crust.id ? <Loader2 size={13} className="animate-spin" /> : <Settings2 size={13} />}
                          </button>
                          <button onClick={() => handleDeleteCrust(crust.id)} className="p-1.5 rounded-lg text-stone hover:text-red-400 transition-colors">
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </div>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className="border-t border-surface-03 pt-5">
                <h4 className="text-parchment text-sm font-semibold mb-3">Adicionar Tipo de Massa</h4>
                <div className="mb-3">
                  <p className="text-stone text-xs mb-2">Atalhos rápidos:</p>
                  <div className="flex gap-2 flex-wrap">
                    {CRUST_PRESETS.map((preset) => (
                      <button key={preset.name} onClick={() => setCrustForm({ name: preset.name, price_addition: preset.price_addition })} className="text-xs bg-surface-03 hover:bg-amber-500/10 hover:text-amber-400 text-parchment border border-surface-03 hover:border-amber-500/30 px-3 py-1.5 rounded-full transition-colors">
                        {preset.name}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-parchment text-xs font-medium mb-1">Nome *</label>
                      <input type="text" value={crustForm.name} onChange={(e) => setCrustForm((f) => ({ ...f, name: e.target.value }))} className={cls} placeholder='Ex: "Tradicional"' maxLength={100} />
                    </div>
                    <div>
                      <label className="block text-parchment text-xs font-medium mb-1">Adicional da massa (R$)</label>
                      <input type="number" value={crustForm.price_addition} onChange={(e) => setCrustForm((f) => ({ ...f, price_addition: e.target.value }))} className={cls} placeholder="0.00" step="0.01" min="0" />
                    </div>
                  </div>
                  <button onClick={handleAddCrust} className="w-full flex items-center justify-center gap-2 bg-amber-500 hover:bg-amber-500/90 text-white font-bold py-2.5 rounded-xl transition-colors text-sm">
                    <Plus size={15} /> Adicionar Massa
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Drink Variants Modal ─────────────────────────────────────────────── */}
      {drinkModalProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-surface-02 rounded-2xl border border-surface-03 w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-2xl">
            <div className="flex items-center justify-between px-6 py-4 border-b border-surface-03 sticky top-0 bg-surface-02 z-10">
              <div className="flex items-center gap-3">
                <Droplets size={18} className="text-blue-400" />
                <div>
                  <h3 className="text-cream font-bold">Variantes da Bebida</h3>
                  <p className="text-stone text-xs">{drinkModalProduct.name}</p>
                </div>
              </div>
              <button onClick={closeDrinkModal} className="text-stone hover:text-cream transition-colors">
                <X size={20} />
              </button>
            </div>

            <div className="p-6 space-y-6">
              <div>
                <h4 className="text-parchment text-sm font-semibold mb-3">Variantes cadastradas</h4>
                {drinkLoading ? (
                  <div className="flex items-center justify-center py-6 text-stone gap-2">
                    <Loader2 size={16} className="animate-spin" />
                    <span className="text-sm">Carregando...</span>
                  </div>
                ) : productDrinkVariants.length === 0 ? (
                  <p className="text-stone text-sm text-center py-4">Nenhuma variante cadastrada. O cliente verá apenas o produto sem opções de tipo.</p>
                ) : (
                  <div className="space-y-2">
                    {productDrinkVariants.map((variant) => (
                      <div key={variant.id} className="flex items-center gap-3 bg-surface-03 rounded-xl px-4 py-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-cream font-bold text-sm">{variant.name}</span>
                            {!variant.active && <span className="text-[10px] bg-red-500/20 text-red-400 border border-red-500/30 px-1.5 py-0.5 rounded-full">inativo</span>}
                          </div>
                        </div>
                        <span className={`text-sm font-bold flex-shrink-0 ${variant.price_addition > 0 ? "text-blue-400" : "text-stone"}`}>
                          {variant.price_addition > 0 ? `+R$ ${variant.price_addition.toFixed(2)}` : "Mesmo preço"}
                        </span>
                        <div className="flex items-center gap-1 flex-shrink-0">
                          <button onClick={() => handleToggleDrinkActive(variant)} disabled={savingDrinkId === variant.id} title={variant.active ? "Desativar" : "Ativar"} className={`p-1.5 rounded-lg transition-colors ${variant.active ? "text-green-400 hover:text-red-400" : "text-red-400 hover:text-green-400"}`}>
                            {savingDrinkId === variant.id ? <Loader2 size={13} className="animate-spin" /> : <Settings2 size={13} />}
                          </button>
                          <button onClick={() => handleDeleteDrinkVariant(variant.id)} className="p-1.5 rounded-lg text-stone hover:text-red-400 transition-colors">
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="border-t border-surface-03 pt-5">
                <h4 className="text-parchment text-sm font-semibold mb-3">Adicionar Variante</h4>
                <div className="mb-3">
                  <p className="text-stone text-xs mb-2">Atalhos rápidos:</p>
                  <div className="flex gap-2 flex-wrap">
                    {DRINK_VARIANT_PRESETS.map((preset) => (
                      <button key={preset.name} onClick={() => setDrinkForm({ name: preset.name, price_addition: preset.price_addition })} className="text-xs bg-surface-03 hover:bg-blue-500/10 hover:text-blue-400 text-parchment border border-surface-03 hover:border-blue-500/30 px-3 py-1.5 rounded-full transition-colors">
                        {preset.name}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-parchment text-xs font-medium mb-1">Nome *</label>
                      <input type="text" value={drinkForm.name} onChange={(e) => setDrinkForm((f) => ({ ...f, name: e.target.value }))} className={cls} placeholder='Ex: "Normal" ou "Zero"' maxLength={100} />
                    </div>
                    <div>
                      <label className="block text-parchment text-xs font-medium mb-1">Acréscimo (R$)</label>
                      <input type="number" value={drinkForm.price_addition} onChange={(e) => setDrinkForm((f) => ({ ...f, price_addition: e.target.value }))} className={cls} placeholder="0.00" step="0.01" min="0" />
                    </div>
                  </div>
                  <button onClick={handleAddDrinkVariant} className="w-full flex items-center justify-center gap-2 bg-blue-500 hover:bg-blue-500/90 text-white font-bold py-2.5 rounded-xl transition-colors text-sm">
                    <Plus size={15} /> Adicionar Variante
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
