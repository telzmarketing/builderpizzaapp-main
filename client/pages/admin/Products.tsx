import { useState, useCallback, useEffect } from "react";
import { Plus, Trash2, Edit2, Settings2, Tag, Ruler, X, Check, Loader2, ChefHat, Droplets, Gift, Search, ChevronUp, ChevronDown } from "lucide-react";
import { useApp, Pizza, PricingRule } from "@/context/AppContext";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";
import ImageUpload from "@/components/admin/ImageUpload";
import { productsApi, sizesApi, crustApi, drinkVariantApi, categoriesApi, productPromotionsApi, ApiProduct, ApiProductSize, ApiProductCrustType, ApiProductDrinkVariant, ApiProductCategory, ApiProductPromotion, ApiProductPromotionCombination, ProductPromotionDiscountType, ApiBestSellerConfig, isAssetUrl, resolveAssetUrl } from "@/lib/api";
import { pizzaSizeDescription, pizzaSizeLabel } from "@/lib/pizzaSizes";
import { normalizeCrustPriceAddition } from "@/lib/pricing";

const PRICING_OPTIONS: { value: PricingRule; label: string; description: string }[] = [
  { value: "most_expensive", label: "Mais Caro", description: "Cliente paga pelo sabor mais caro (padrão iFood)" },
  { value: "average", label: "Média", description: "Preço é a média aritmética dos sabores" },
  { value: "proportional", label: "Proporcional", description: "Cada parte paga sua fração do sabor" },
];

const WEEKDAYS = [
  { value: 0, label: "Seg" },
  { value: 1, label: "Ter" },
  { value: 2, label: "Qua" },
  { value: 3, label: "Qui" },
  { value: 4, label: "Sex" },
  { value: 5, label: "Sab" },
  { value: 6, label: "Dom" },
];

const DISCOUNT_LABELS: Record<ProductPromotionDiscountType, string> = {
  fixed_price: "Preço fixo promocional",
  amount_off: "Desconto em reais",
  percent_off: "Desconto percentual",
};

const CATUPIRY_CRUST_NAME = "Borda com Catupiry";

const isCatupiryCrust = (name?: string | null) =>
  (name || "").trim().toLowerCase().includes("catupiry");

const productHasCatupiryCrust = (product: Pizza) =>
  (((product as any).crust_types ?? []) as ApiProductCrustType[]).some((crust) => crust.active && isCatupiryCrust(crust.name));

const PIZZA_ICON = "\u{1F355}";
const DRINK_ICON = "\u{1F964}";
const OTHER_ICON = "\u{1F354}";

const getTypeIcon = (type: string | null | undefined) => {
  if (type === "drink") return DRINK_ICON;
  if (type === "other") return OTHER_ICON;
  return PIZZA_ICON;
};

const isBrokenIconValue = (value?: string | null) => {
  const trimmed = (value || "").trim();
  return !trimmed || trimmed.includes("ðŸ") || trimmed.includes("�");
};

function ProductIconPreview({ icon, name, type }: { icon?: string | null; name: string; type?: string | null }) {
  const [imageFailed, setImageFailed] = useState(false);
  const cleanIcon = (icon || "").trim();
  const canRenderImage = cleanIcon && !isBrokenIconValue(cleanIcon) && isAssetUrl(cleanIcon) && !imageFailed;

  if (canRenderImage) {
    return (
      <img
        src={resolveAssetUrl(cleanIcon)}
        alt={name}
        className="w-full h-full object-contain"
        onError={() => setImageFailed(true)}
      />
    );
  }

  return <span className="text-3xl">{isBrokenIconValue(cleanIcon) ? getTypeIcon(type) : cleanIcon}</span>;
}

type PromotionFormState = {
  name: string;
  active: boolean;
  valid_weekdays: number[];
  start_time: string;
  end_time: string;
  start_date: string;
  end_date: string;
  discount_type: ProductPromotionDiscountType;
  default_value: number | null;
  timezone: string;
};

const emptyPromotionForm = (): PromotionFormState => ({
  name: "",
  active: true,
  valid_weekdays: [],
  start_time: "",
  end_time: "",
  start_date: "",
  end_date: "",
  discount_type: "fixed_price",
  default_value: null,
  timezone: "America/Sao_Paulo",
});

type PTab = "produtos" | "brindes" | "categorias" | "config";
type ProductSortMode = "recent" | "date" | "name" | "type";

const PRODUCT_SORT_LABELS: Record<ProductSortMode, string> = {
  recent: "Recente",
  date: "Por data",
  name: "Nome",
  type: "Tipo",
};

export default function AdminProducts() {
  const { products, addProduct, updateProduct, deleteProduct, multiFlavorsConfig, updateMultiFlavorsConfig } = useApp();
  const [activeTab, setActiveTab] = useState<PTab>("produtos");
  const [tabSearch, setTabSearch] = useState("");
  const [productSort, setProductSort] = useState<ProductSortMode>("recent");
  const [configSaved, setConfigSaved] = useState(false);
  const [catalogCategories, setCatalogCategories] = useState<ApiProductCategory[]>([]);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [newSubcategoryNames, setNewSubcategoryNames] = useState<Record<string, string>>({});
  const [categorySaving, setCategorySaving] = useState(false);
  const [editingCategoryId, setEditingCategoryId] = useState<string | null>(null);
  const [editingCategoryName, setEditingCategoryName] = useState("");
  const [editingCategoryParentId, setEditingCategoryParentId] = useState("");
  const [editingCategoryActive, setEditingCategoryActive] = useState(true);
  const [categoryReorderingId, setCategoryReorderingId] = useState<string | null>(null);

  const sortedCatalogCategories = [...catalogCategories].sort((a, b) => {
    if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order;
    return a.name.localeCompare(b.name);
  });
  const parentCategories = sortedCatalogCategories.filter((cat) => !cat.parent_id);
  const activeCatalogCategories = parentCategories.filter((cat) => cat.active);
  const subcategories = sortedCatalogCategories.filter((cat) => !!cat.parent_id);
  const activeSubcategories = subcategories.filter((cat) => cat.active);
  const catalogCategoryNames = parentCategories.map((cat) => cat.name);
  const catalogSubcategoryNames = subcategories.map((cat) => cat.name);
  const getSubcategoriesForCategory = (parentId: string) =>
    subcategories.filter((cat) => cat.parent_id === parentId);
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
        parent_id: null,
        name,
        active: true,
        sort_order: parentCategories.length,
      });
      setCatalogCategories((prev) => [...prev, created]);
      setNewCategoryName("");
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao criar categoria.");
    } finally {
      setCategorySaving(false);
    }
  };

  const handleAddSubcategory = async (parentId: string) => {
    const name = (newSubcategoryNames[parentId] || "").trim();
    if (!name || !parentId) return;
    setCategorySaving(true);
    try {
      const created = await categoriesApi.create({
        parent_id: parentId,
        name,
        active: true,
        sort_order: getSubcategoriesForCategory(parentId).length,
      });
      setCatalogCategories((prev) => [...prev, created]);
      setNewSubcategoryNames((prev) => ({ ...prev, [parentId]: "" }));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao criar subcategoria.");
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

  const handleMoveCategory = async (category: ApiProductCategory, direction: -1 | 1) => {
    const siblings = category.parent_id ? getSubcategoriesForCategory(category.parent_id) : parentCategories;
    const currentIndex = siblings.findIndex((item) => item.id === category.id);
    const targetIndex = currentIndex + direction;
    if (currentIndex < 0 || targetIndex < 0 || targetIndex >= siblings.length) return;

    const reordered = [...siblings];
    [reordered[currentIndex], reordered[targetIndex]] = [reordered[targetIndex], reordered[currentIndex]];
    setCategoryReorderingId(category.id);
    try {
      const updatedCategories = await Promise.all(
        reordered.map((item, index) => categoriesApi.update(item.id, { sort_order: index }))
      );
      setCatalogCategories((prev) =>
        prev.map((item) => updatedCategories.find((updated) => updated.id === item.id) ?? item)
      );
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao alterar ordem da categoria.");
    } finally {
      setCategoryReorderingId(null);
    }
  };

  const startEditCategory = (category: ApiProductCategory) => {
    setEditingCategoryId(category.id);
    setEditingCategoryName(category.name);
    setEditingCategoryParentId(category.parent_id ?? "");
    setEditingCategoryActive(category.active);
  };

  const cancelEditCategory = () => {
    setEditingCategoryId(null);
    setEditingCategoryName("");
    setEditingCategoryParentId("");
    setEditingCategoryActive(true);
  };

  const handleSaveCategory = async (category: ApiProductCategory) => {
    const name = editingCategoryName.trim();
    if (!name) return;
    setCategorySaving(true);
    try {
      const updated = await categoriesApi.update(category.id, {
        name,
        parent_id: editingCategoryParentId || null,
        active: editingCategoryActive,
        sort_order: category.sort_order,
      });
      setCatalogCategories((prev) => prev.map((cat) => cat.id === updated.id ? updated : cat));
      cancelEditCategory();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao atualizar categoria.");
    } finally {
      setCategorySaving(false);
    }
  };

  // ── Brindes CRUD ─────────────────────────────────────────────────────────────
  const [brindes, setBrindes] = useState<ApiProduct[]>([]);
  const [brindesLoading, setBrindesLoading] = useState(false);
  const [showBrindeForm, setShowBrindeForm] = useState(false);
  const [editingBrindeId, setEditingBrindeId] = useState<string | null>(null);
  const [brindeForm, setBrindeForm] = useState({ name: "", description: "", icon: "🎁", active: true });
  const [brindeSaving, setBrindeSaving] = useState(false);

  const loadBrindes = useCallback(async () => {
    setBrindesLoading(true);
    try {
      const all = await productsApi.listGifts();
      setBrindes(all);
    } catch {
      setBrindes([]);
    } finally {
      setBrindesLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === "brindes") loadBrindes();
  }, [activeTab, loadBrindes]);

  const openNewBrindeForm = () => {
    setEditingBrindeId(null);
    setBrindeForm({ name: "", description: "", icon: "🎁", active: true });
    setShowBrindeForm(true);
  };

  const openEditBrindeForm = (b: ApiProduct) => {
    setEditingBrindeId(b.id);
    setBrindeForm({ name: b.name, description: b.description, icon: (b as any).icon || "🎁", active: (b as any).active ?? true });
    setShowBrindeForm(true);
  };

  const handleBrindeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!brindeForm.name.trim() || !brindeForm.description.trim()) {
      alert("Preencha nome e descrição do brinde.");
      return;
    }
    setBrindeSaving(true);
    try {
      if (editingBrindeId) {
        const updated = await productsApi.update(editingBrindeId, {
          name: brindeForm.name.trim(),
          description: brindeForm.description.trim(),
          icon: brindeForm.icon,
          active: brindeForm.active,
        } as any);
        setBrindes((prev) => prev.map((b) => b.id === editingBrindeId ? updated : b));
      } else {
        const created = await productsApi.create({
          name: brindeForm.name.trim(),
          description: brindeForm.description.trim(),
          icon: brindeForm.icon,
          price: 0,
          product_type: "brinde",
          rating: 5.0,
          active: brindeForm.active,
        } as any);
        setBrindes((prev) => [...prev, created]);
      }
      setShowBrindeForm(false);
      setEditingBrindeId(null);
      setBrindeForm({ name: "", description: "", icon: "🎁", active: true });
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao salvar brinde.");
    } finally {
      setBrindeSaving(false);
    }
  };

  const handleDeleteBrinde = async (b: ApiProduct) => {
    if (!confirm(`Remover o brinde "${b.name}"?`)) return;
    try {
      await productsApi.remove(b.id);
      setBrindes((prev) => prev.filter((x) => x.id !== b.id));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao remover brinde.");
    }
  };

  // ── Products CRUD ────────────────────────────────────────────────────────────
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<Partial<Pizza> & { product_type?: string }>({
    name: "", description: "", price: 0, icon: PIZZA_ICON, category: "", rating: 4.5, product_type: "pizza",
  });

  const selectedCategoryId = activeCatalogCategories.find((cat) => cat.name === ((formData as any).category || ""))?.id ?? "";
  const availableSubcategories = activeSubcategories.filter((cat) => cat.parent_id === selectedCategoryId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name || !formData.description) {
      alert("Preencha todos os campos obrigatórios");
      return;
    }
    const price = Number(formData.price || 0);
    if (!Number.isFinite(price) || price <= 0) {
      alert("Informe um preco base maior que zero.");
      return;
    }
    const category = ((formData as any).category || "").trim();
    const subcategory = ((formData as any).subcategory || "").trim();
    if (category && !catalogCategoryNames.includes(category)) {
      alert("Selecione uma categoria cadastrada na aba Categorias.");
      return;
    }
    if (subcategory && !catalogSubcategoryNames.includes(subcategory)) {
      alert("Selecione uma subcategoria cadastrada na aba Categorias.");
      return;
    }
    try {
      if (editingId) {
        await updateProduct(editingId, { ...formData, price, category: category || null, subcategory: subcategory || null } as any);
        setEditingId(null);
      } else {
        await addProduct({
          name: formData.name!, description: formData.description!,
          price, icon: formData.icon || PIZZA_ICON,
          category: category || null,
          subcategory: subcategory || null,
          product_type: formData.product_type || "pizza",
          rating: formData.rating || 4.5, active: true,
        } as any);
      }
      setFormData({ name: "", description: "", price: 0, icon: PIZZA_ICON, category: "", rating: 4.5, product_type: "pizza" });
      setShowForm(false);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao salvar produto.");
    }
  };

  const handleEdit = (product: Pizza) => {
    setFormData({
      ...product,
      category: (product as any).category ?? "",
      subcategory: (product as any).subcategory ?? "",
      product_type: (product as any).product_type ?? "pizza",
      best_seller_badge_mode: (product as any).best_seller_badge_mode ?? "off",
    } as any);
    setEditingId(product.id);
    setShowForm(true);
  };

  const handleDeleteProduct = async (product: Pizza) => {
    if (!confirm(`Remover "${product.name}" do catalogo?`)) return;
    try {
      await deleteProduct(product.id);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao remover produto do catalogo.");
    }
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

  const [bestSellerConfig, setBestSellerConfig] = useState<ApiBestSellerConfig | null>(null);
  const [bestSellerSaving, setBestSellerSaving] = useState(false);
  const [bestSellerSaved, setBestSellerSaved] = useState(false);

  useEffect(() => {
    if (activeTab === "config") {
      productsApi.getBestSellerConfig().then(setBestSellerConfig).catch(() => {});
    }
  }, [activeTab]);

  const handleBestSellerSave = async () => {
    if (!bestSellerConfig) return;
    setBestSellerSaving(true);
    try {
      const updated = await productsApi.updateBestSellerConfig({
        period_days: bestSellerConfig.period_days,
        top_count: bestSellerConfig.top_count,
      });
      setBestSellerConfig(updated);
      setBestSellerSaved(true);
      setTimeout(() => setBestSellerSaved(false), 2000);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao salvar configuração do selo.");
    } finally {
      setBestSellerSaving(false);
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
      const sizes = await sizesApi.list(product.id, false);
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
      const crusts = await crustApi.list(product.id, false);
      setProductCrusts(crusts.filter((crust) => !isCatupiryCrust(crust.name)));
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

  const [borderModalProduct, setBorderModalProduct] = useState<Pizza | null>(null);
  const [productBorders, setProductBorders] = useState<ApiProductCrustType[]>([]);
  const [bordersLoading, setBordersLoading] = useState(false);
  const [borderForm, setBorderForm] = useState({ price_addition: "" });
  const [savingBorderId, setSavingBorderId] = useState<string | null>(null);

  const openBorderModal = useCallback(async (product: Pizza) => {
    setBorderModalProduct(product);
    setBordersLoading(true);
    try {
      const crusts = await crustApi.list(product.id, false);
      setProductBorders(crusts.filter((crust) => isCatupiryCrust(crust.name)));
    } catch {
      setProductBorders([]);
    } finally {
      setBordersLoading(false);
    }
  }, []);

  const closeBorderModal = () => {
    setBorderModalProduct(null);
    setProductBorders([]);
    setBorderForm({ price_addition: "" });
  };

  const handleAddCatupiryBorder = async () => {
    if (!borderModalProduct) return;
    const priceAdd = parseFloat(borderForm.price_addition || "0");
    const priceAddition = isNaN(priceAdd) || priceAdd < 0 ? 0 : priceAdd;
    const existing = productBorders.find((border) => isCatupiryCrust(border.name));
    try {
      if (existing) {
        const updated = await crustApi.update(borderModalProduct.id, existing.id, {
          name: CATUPIRY_CRUST_NAME,
          price_addition: priceAddition,
          active: true,
        } as any);
        setProductBorders((prev) => prev.map((border) => border.id === updated.id ? updated : border));
      } else {
        const allCrusts = await crustApi.list(borderModalProduct.id, false);
        const created = await crustApi.create(borderModalProduct.id, {
          name: CATUPIRY_CRUST_NAME,
          price_addition: priceAddition,
          active: true,
          sort_order: allCrusts.length,
        } as any);
        setProductBorders((prev) => [...prev, created]);
      }
      setBorderForm({ price_addition: "" });
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao adicionar borda.");
    }
  };

  const handleToggleBorderActive = async (border: ApiProductCrustType) => {
    if (!borderModalProduct) return;
    setSavingBorderId(border.id);
    try {
      const updated = await crustApi.update(borderModalProduct.id, border.id, { active: !border.active });
      setProductBorders((prev) => prev.map((item) => item.id === border.id ? updated : item));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao atualizar borda.");
    } finally {
      setSavingBorderId(null);
    }
  };

  const handleUpdateBorderPrice = async (border: ApiProductCrustType, value: string) => {
    if (!borderModalProduct) return;
    const priceAddition = parseFloat(value || "0");
    if (isNaN(priceAddition) || priceAddition < 0) {
      alert("Preco invalido.");
      return;
    }
    if (Math.abs(priceAddition - border.price_addition) < 0.001) return;
    setSavingBorderId(border.id);
    try {
      const updated = await crustApi.update(borderModalProduct.id, border.id, { price_addition: priceAddition });
      setProductBorders((prev) => prev.map((item) => item.id === border.id ? updated : item));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao atualizar adicional da borda.");
    } finally {
      setSavingBorderId(null);
    }
  };

  const handleDeleteBorder = async (borderId: string) => {
    if (!borderModalProduct) return;
    if (!confirm("Remover esta borda?")) return;
    try {
      await crustApi.remove(borderModalProduct.id, borderId);
      setProductBorders((prev) => prev.filter((border) => border.id !== borderId));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao remover borda.");
    }
  };

  const handleAddCrust = async () => {
    if (!crustModalProduct || !crustForm.name.trim()) return;
    if (isCatupiryCrust(crustForm.name)) {
      alert("Use o botao Gerenciar Bordas para adicionar borda com Catupiry.");
      return;
    }
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
  // Product promotions modal (pizza)
  const [promotionModalProduct, setPromotionModalProduct] = useState<Pizza | null>(null);
  const [productPromotions, setProductPromotions] = useState<ApiProductPromotion[]>([]);
  const [promoSizes, setPromoSizes] = useState<ApiProductSize[]>([]);
  const [promoCrusts, setPromoCrusts] = useState<ApiProductCrustType[]>([]);
  const [promoCombinations, setPromoCombinations] = useState<ApiProductPromotionCombination[]>([]);
  const [promoLoading, setPromoLoading] = useState(false);
  const [promoSaving, setPromoSaving] = useState(false);
  const [editingPromotionId, setEditingPromotionId] = useState<string | null>(null);
  const [promotionForm, setPromotionForm] = useState<PromotionFormState>(emptyPromotionForm());

  const buildPromotionCombinations = (
    sizes: ApiProductSize[],
    crusts: ApiProductCrustType[],
    existing: ApiProductPromotionCombination[] = [],
  ): ApiProductPromotionCombination[] => {
    const sizeRows = sizes.filter((size) => size.active);
    const crustRows: (ApiProductCrustType | null)[] = crusts.filter((crust) => crust.active);
    const rows = crustRows.length > 0 ? crustRows : [null];
    return sizeRows.flatMap((size) => rows.map((crust) => {
      const current = existing.find((combo) =>
        combo.product_size_id === size.id &&
        (combo.product_crust_type_id ?? null) === (crust?.id ?? null)
      );
      return {
        product_size_id: size.id,
        product_crust_type_id: crust?.id ?? null,
        active: current?.active ?? true,
        promotional_value: current?.promotional_value ?? null,
      };
    }));
  };

  const openPromotionModal = useCallback(async (product: Pizza) => {
    setPromotionModalProduct(product);
    setPromoLoading(true);
    setEditingPromotionId(null);
    setPromotionForm(emptyPromotionForm());
    try {
      const [promotions, sizes, crusts] = await Promise.all([
        productPromotionsApi.list(product.id),
        sizesApi.list(product.id, false),
        crustApi.list(product.id, false),
      ]);
      setProductPromotions(promotions);
      setPromoSizes(sizes);
      setPromoCrusts(crusts);
      setPromoCombinations(buildPromotionCombinations(sizes, crusts));
    } catch (err: unknown) {
      setProductPromotions([]);
      setPromoSizes([]);
      setPromoCrusts([]);
      setPromoCombinations([]);
      alert(err instanceof Error ? err.message : "Erro ao carregar promocoes.");
    } finally {
      setPromoLoading(false);
    }
  }, []);

  const closePromotionModal = () => {
    setPromotionModalProduct(null);
    setProductPromotions([]);
    setPromoSizes([]);
    setPromoCrusts([]);
    setPromoCombinations([]);
    setEditingPromotionId(null);
    setPromotionForm(emptyPromotionForm());
  };

  const handleEditPromotion = (promotion: ApiProductPromotion) => {
    setEditingPromotionId(promotion.id);
    setPromotionForm({
      name: promotion.name,
      active: promotion.active,
      valid_weekdays: promotion.valid_weekdays,
      start_time: promotion.start_time ?? "",
      end_time: promotion.end_time ?? "",
      start_date: promotion.start_date ?? "",
      end_date: promotion.end_date ?? "",
      discount_type: promotion.discount_type,
      default_value: promotion.default_value,
      timezone: promotion.timezone || "America/Sao_Paulo",
    });
    setPromoCombinations(buildPromotionCombinations(promoSizes, promoCrusts, promotion.combinations));
  };

  const handleNewPromotion = () => {
    setEditingPromotionId(null);
    setPromotionForm(emptyPromotionForm());
    setPromoCombinations(buildPromotionCombinations(promoSizes, promoCrusts));
  };

  const handleTogglePromotionWeekday = (day: number) => {
    setPromotionForm((form) => {
      const exists = form.valid_weekdays.includes(day);
      return {
        ...form,
        valid_weekdays: exists
          ? form.valid_weekdays.filter((item) => item !== day)
          : [...form.valid_weekdays, day].sort(),
      };
    });
  };

  const updatePromoCombination = (index: number, patch: Partial<ApiProductPromotionCombination>) => {
    setPromoCombinations((prev) => prev.map((combo, i) => i === index ? { ...combo, ...patch } : combo));
  };

  const handleSavePromotion = async () => {
    if (!promotionModalProduct || !promotionForm.name.trim()) {
      alert("Informe o nome da promocao.");
      return;
    }
    if (promotionForm.valid_weekdays.length === 0) {
      alert("Selecione pelo menos um dia da semana.");
      return;
    }
    const combinations = promoCombinations.map((combo) => ({
      product_size_id: combo.product_size_id,
      product_crust_type_id: combo.product_crust_type_id,
      active: combo.active,
      promotional_value: combo.promotional_value,
    }));
    if (combinations.every((combo) => !combo.active)) {
      alert("Ative pelo menos uma combinacao da promocao.");
      return;
    }

    setPromoSaving(true);
    const payload = {
      ...promotionForm,
      name: promotionForm.name.trim(),
      start_time: promotionForm.start_time || null,
      end_time: promotionForm.end_time || null,
      start_date: promotionForm.start_date || null,
      end_date: promotionForm.end_date || null,
      combinations,
    };
    try {
      const saved = editingPromotionId
        ? await productPromotionsApi.update(promotionModalProduct.id, editingPromotionId, payload)
        : await productPromotionsApi.create(promotionModalProduct.id, payload);
      setProductPromotions((prev) => editingPromotionId
        ? prev.map((promotion) => promotion.id === saved.id ? saved : promotion)
        : [saved, ...prev]
      );
      handleEditPromotion(saved);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao salvar promocao.");
    } finally {
      setPromoSaving(false);
    }
  };

  const handleDeletePromotion = async (promotion: ApiProductPromotion) => {
    if (!promotionModalProduct) return;
    if (!confirm(`Excluir a promocao "${promotion.name}"?`)) return;
    try {
      await productPromotionsApi.remove(promotionModalProduct.id, promotion.id);
      setProductPromotions((prev) => prev.filter((item) => item.id !== promotion.id));
      if (editingPromotionId === promotion.id) handleNewPromotion();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao excluir promocao.");
    }
  };

  const [drinkModalProduct, setDrinkModalProduct] = useState<Pizza | null>(null);
  const [productDrinkVariants, setProductDrinkVariants] = useState<ApiProductDrinkVariant[]>([]);
  const [drinkLoading, setDrinkLoading] = useState(false);
  const [drinkForm, setDrinkForm] = useState({ name: "", price_addition: "" });
  const [savingDrinkId, setSavingDrinkId] = useState<string | null>(null);

  const openDrinkModal = useCallback(async (product: Pizza) => {
    setDrinkModalProduct(product);
    setDrinkLoading(true);
    try {
      const variants = await drinkVariantApi.list(product.id, false);
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
    { label: "Pizza Broto", description: "25cm - 4 pedaços" },
    { label: "Pizza Grande", description: "35cm - 8 pedaços" },
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

  const searchTerm = tabSearch.trim().toLowerCase();
  const searchDisabled = activeTab === "config";
  const searchPlaceholder: Record<PTab, string> = {
    produtos: "Pesquisar produtos...",
    brindes: "Pesquisar brindes...",
    categorias: "Pesquisar categorias...",
    config: "Busca indisponivel nesta aba",
  };
  const matchesSearch = (...values: Array<string | number | boolean | null | undefined>) => {
    if (!searchTerm) return true;
    return values.some((value) => String(value ?? "").toLowerCase().includes(searchTerm));
  };
  const productTypeLabel = (type?: string | null) =>
    type === "drink" ? "Bebida" : type === "other" ? "Outros" : type === "brinde" ? "Brinde" : "Pizza";
  const filteredProducts = products
    .filter((product) =>
      matchesSearch(
        product.name,
        product.description,
        (product as any).category,
        (product as any).subcategory,
        (product as any).product_type,
        productTypeLabel((product as any).product_type),
        product.price,
        product.rating,
      )
    )
    .sort((a, b) => {
      if (productSort === "name") return a.name.localeCompare(b.name);
      if (productSort === "type") {
        const typeCompare = productTypeLabel((a as any).product_type).localeCompare(productTypeLabel((b as any).product_type));
        return typeCompare || a.name.localeCompare(b.name);
      }
      const aDate = new Date(productSort === "date" ? a.updated_at : a.created_at).getTime();
      const bDate = new Date(productSort === "date" ? b.updated_at : b.created_at).getTime();
      return bDate - aDate;
    });
  const filteredBrindes = brindes.filter((brinde) =>
    matchesSearch(
      brinde.name,
      brinde.description,
      (brinde as any).active ? "ativo" : "inativo",
    )
  );
  const categoryMatchesSearch = (category: ApiProductCategory) =>
    matchesSearch(category.name, category.active ? "ativa" : "inativa");
  const filteredParentCategories = parentCategories.filter((category) => {
    if (categoryMatchesSearch(category)) return true;
    return getSubcategoriesForCategory(category.id).some((subcategory) => categoryMatchesSearch(subcategory));
  });
  const getVisibleSubcategoriesForCategory = (category: ApiProductCategory) => {
    const children = getSubcategoriesForCategory(category.id);
    if (!searchTerm || categoryMatchesSearch(category)) return children;
    return children.filter((subcategory) => categoryMatchesSearch(subcategory));
  };

  const cls = "w-full bg-surface-03 border border-surface-03 rounded-lg px-4 py-2 text-cream placeholder-stone focus:outline-none focus:border-gold text-sm";

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-00 to-surface-00">
      <div className="flex flex-col md:flex-row min-h-screen md:h-screen">
        <AdminSidebar />
        <div className="flex-1 overflow-auto">

          {/* Header */}
          <div className="hidden">
            <div>
              <h2 className="text-2xl font-bold text-cream">Produtos</h2>
              <p className="text-stone text-sm">{products.length} produtos · {sortedCatalogCategories.length} categorias cadastradas</p>
            </div>
            <div className="flex items-center gap-3">
              {activeTab === "produtos" && (
                <button
                  onClick={() => { setShowForm(!showForm); setEditingId(null); setFormData({ name: "", description: "", price: 0, icon: PIZZA_ICON, category: "", rating: 4.5, product_type: "pizza" }); }}
                  className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-4 rounded-lg transition-colors"
                >
                  <Plus size={20} />
                  Novo Produto
                </button>
              )}
              <AdminTopActions />
            </div>
          </div>

          {/* Tabs */}
          <div className="px-8 pt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:flex-1">
              <div className="flex flex-wrap gap-2">
            {([
              { key: "produtos", label: "Produtos" },
              { key: "brindes", label: "Brindes" },
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
              <div className="relative w-full lg:max-w-xs">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone" />
                <input
                  type="search"
                  value={tabSearch}
                  onChange={(event) => setTabSearch(event.target.value)}
                  disabled={searchDisabled}
                  placeholder={searchPlaceholder[activeTab]}
                  className="w-full bg-surface-02 border border-surface-03 rounded-full py-2 pl-9 pr-9 text-sm text-cream placeholder-stone focus:outline-none focus:border-gold disabled:cursor-not-allowed disabled:opacity-60"
                />
                {tabSearch && !searchDisabled && (
                  <button
                    type="button"
                    onClick={() => setTabSearch("")}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-stone hover:text-gold transition-colors"
                    title="Limpar busca"
                  >
                    <X size={14} />
                  </button>
                )}
              </div>
            </div>
            {activeTab === "produtos" && (
              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={productSort}
                  onChange={(event) => setProductSort(event.target.value as ProductSortMode)}
                  className="h-10 rounded-lg border border-surface-03 bg-surface-02 px-3 text-sm font-medium text-parchment outline-none transition-colors focus:border-gold"
                  title="Organizar produtos"
                >
                  {(Object.keys(PRODUCT_SORT_LABELS) as ProductSortMode[]).map((mode) => (
                    <option key={mode} value={mode}>{PRODUCT_SORT_LABELS[mode]}</option>
                  ))}
                </select>
                <button
                  onClick={() => { setShowForm(true); setEditingId(null); setFormData({ name: "", description: "", price: 0, icon: PIZZA_ICON, category: "", rating: 4.5, product_type: "pizza" }); }}
                  className="flex items-center justify-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-4 rounded-lg transition-colors"
                >
                  <Plus size={20} />
                  Novo Produto
                </button>
              </div>
            )}
            {activeTab === "brindes" && (
              <button
                onClick={openNewBrindeForm}
                className="flex items-center justify-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-4 rounded-lg transition-colors"
              >
                <Plus size={20} />
                Novo Brinde
              </button>
            )}
          </div>

          <div className="p-8 pt-6">

            {/* ── TAB: PRODUTOS ── */}
            {activeTab === "produtos" && (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {filteredProducts.map((product) => {
                    const pType = (product as any).product_type as string | null | undefined;
                    const isPizza = !pType || pType === "pizza";
                    const isDrink = pType === "drink";
                    return (
                      <div key={product.id} className="bg-surface-02 rounded-xl p-6 border border-surface-03">
                        <div className="flex items-start gap-3 mb-3">
                          <div className="w-14 h-14 rounded-xl bg-surface-03 flex items-center justify-center flex-shrink-0 overflow-hidden">
                            <ProductIconPreview icon={product.icon} name={product.name} type={pType} />
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
                              {(product as any).subcategory && (
                                <span className="inline-flex items-center gap-1 text-xs bg-emerald-500/15 text-emerald-300 border border-emerald-500/25 px-2 py-0.5 rounded-full">
                                  {(product as any).subcategory}
                                </span>
                              )}
                              <span className="inline-flex items-center gap-1 text-xs bg-surface-03 text-stone border border-surface-03 px-2 py-0.5 rounded-full">
                                {getTypeIcon(pType)} {pType === "drink" ? "Bebida" : pType === "other" ? "Outros" : "Pizza"}
                              </span>
                              {isPizza && productHasCatupiryCrust(product) && (
                                <span className="inline-flex items-center gap-1 text-xs bg-amber-500/20 text-amber-300 border border-amber-500/30 px-2 py-0.5 rounded-full">
                                  Borda Catupiry
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        <p className="text-stone text-sm mb-3 line-clamp-2">{product.description}</p>
                        <div className="flex justify-end items-center mb-4">
                          <span className="text-stone text-sm">⭐ {product.rating}</span>
                        </div>

                        <div className="flex gap-2 mb-2">
                          <button onClick={() => handleEdit(product)} className="flex-1 flex items-center justify-center gap-2 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 font-medium py-2 px-3 rounded-lg transition-colors">
                            <Edit2 size={16} />
                            Editar
                          </button>
                          <button onClick={() => handleDeleteProduct(product)} className="flex items-center justify-center gap-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 font-medium py-2 px-3 rounded-lg transition-colors">
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
                            {(((product as any).crust_types ?? []) as ApiProductCrustType[]).filter((crust) => !isCatupiryCrust(crust.name)).length > 0 && (
                              <span className="ml-auto text-xs bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded-full">
                                {(((product as any).crust_types ?? []) as ApiProductCrustType[]).filter((crust) => !isCatupiryCrust(crust.name)).length}
                              </span>
                            )}
                          </button>
                        )}

                        {isPizza && (
                          <button onClick={() => openBorderModal(product)} className="w-full flex items-center justify-center gap-2 bg-surface-03 hover:bg-orange-500/10 hover:border-orange-500/40 text-parchment hover:text-orange-300 font-medium py-2 px-3 rounded-lg transition-colors border border-surface-03 text-sm mb-2">
                            <Tag size={15} />
                            Gerenciar Bordas
                            {productHasCatupiryCrust(product) && (
                              <span className="ml-auto text-xs bg-orange-500/20 text-orange-300 px-1.5 py-0.5 rounded-full">1</span>
                            )}
                          </button>
                        )}

                        {isPizza && (
                          <button onClick={() => openPromotionModal(product)} className="w-full flex items-center justify-center gap-2 bg-surface-03 hover:bg-emerald-500/10 hover:border-emerald-500/40 text-parchment hover:text-emerald-300 font-medium py-2 px-3 rounded-lg transition-colors border border-surface-03 text-sm mb-2">
                            <Tag size={15} />
                            Gerenciar Promoções
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

                {filteredProducts.length === 0 && (
                  <div className="text-center py-12">
                    <p className="text-stone text-lg">
                      {products.length === 0 ? "Nenhum produto cadastrado" : "Nenhum produto encontrado para esta busca"}
                    </p>
                    {products.length === 0 && (
                      <button onClick={() => setShowForm(true)} className="mt-4 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-6 rounded-lg transition-colors inline-flex items-center gap-2">
                        <Plus size={20} /> Adicionar Primeiro Produto
                      </button>
                    )}
                  </div>
                )}
              </>
            )}

            {/* ── TAB: BRINDES ── */}
            {activeTab === "brindes" && (
              <div className="space-y-6">
                {brindesLoading ? (
                  <div className="flex justify-center py-12">
                    <Loader2 size={32} className="animate-spin text-gold" />
                  </div>
                ) : filteredBrindes.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-16 text-center">
                    <Gift size={48} className="text-stone mb-4" />
                    <p className="text-parchment font-semibold">{brindes.length === 0 ? "Nenhum brinde cadastrado" : "Nenhum brinde encontrado para esta busca"}</p>
                    {brindes.length === 0 && (
                      <p className="text-stone text-sm mt-1">Clique em "Novo Brinde" para começar.</p>
                    )}
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {filteredBrindes.map((b) => (
                      <div key={b.id} className="bg-surface-02 rounded-xl border border-surface-03 overflow-hidden flex flex-col">
                        <div className="h-36 bg-surface-03 flex items-center justify-center overflow-hidden">
                          {(b as any).icon && isAssetUrl((b as any).icon) ? (
                            <img
                              src={resolveAssetUrl((b as any).icon)}
                              alt={b.name}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <span className="text-5xl">{(b as any).icon || "🎁"}</span>
                          )}
                        </div>
                        <div className="p-4 flex flex-col gap-2 flex-1">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <p className="text-cream font-bold truncate">{b.name}</p>
                              <p className="text-stone text-xs mt-0.5 line-clamp-2">{b.description}</p>
                            </div>
                            <span className={`shrink-0 text-xs px-2 py-0.5 rounded-full font-medium ${(b as any).active ? "bg-green-500/15 text-green-400" : "bg-stone/15 text-stone"}`}>
                              {(b as any).active ? "Ativo" : "Inativo"}
                            </span>
                          </div>
                          <div className="flex gap-2 mt-auto pt-2">
                            <button
                              onClick={() => openEditBrindeForm(b)}
                              className="flex-1 flex items-center justify-center gap-1.5 bg-surface-03 hover:bg-surface-03/70 text-parchment text-sm py-1.5 rounded-lg transition-colors"
                            >
                              <Edit2 size={14} /> Editar
                            </button>
                            <button
                              onClick={() => handleDeleteBrinde(b)}
                              className="flex items-center justify-center gap-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 text-sm px-3 py-1.5 rounded-lg transition-colors"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* ── TAB: CATEGORIAS ── */}
            {activeTab === "categorias" && (
              <div className="max-w-4xl space-y-4">
                <div className="bg-surface-02 rounded-xl p-6 border border-surface-03 space-y-4">
                  <div className="flex items-center gap-3 pb-3 border-b border-surface-03">
                    <Tag size={18} className="text-gold" />
                    <div>
                      <h3 className="text-cream font-bold">Categorias do Cardapio</h3>
                      <p className="text-stone text-sm">Crie categorias principais e adicione diversas subcategorias dentro de cada uma.</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-[1fr,auto] gap-2">
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

                  {editingCategoryId && (
                    <div className="rounded-xl border border-gold/30 bg-gold/10 p-4 space-y-3">
                      <p className="text-parchment text-sm font-bold">
                        Editar {catalogCategories.find((cat) => cat.id === editingCategoryId)?.parent_id ? "subcategoria" : "categoria"}
                      </p>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        <input
                          value={editingCategoryName}
                          onChange={(e) => setEditingCategoryName(e.target.value)}
                          className={cls}
                          placeholder="Nome da categoria"
                          maxLength={100}
                        />
                        {catalogCategories.find((cat) => cat.id === editingCategoryId)?.parent_id ? (
                          <select
                            value={editingCategoryParentId}
                            onChange={(e) => setEditingCategoryParentId(e.target.value)}
                            className={cls}
                          >
                            {parentCategories.map((cat) => (
                              <option key={cat.id} value={cat.id}>Subcategoria de {cat.name}</option>
                            ))}
                          </select>
                        ) : (
                          <div className="rounded-lg border border-surface-03 bg-surface-01 px-3 py-2 text-stone text-sm">
                            Categoria principal
                          </div>
                        )}
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <label className="flex items-center gap-2 text-parchment text-xs">
                          <input
                            type="checkbox"
                            checked={editingCategoryActive}
                            onChange={(e) => setEditingCategoryActive(e.target.checked)}
                            className="accent-gold"
                          />
                          Ativa
                        </label>
                        <button
                          type="button"
                          onClick={() => {
                            const category = catalogCategories.find((cat) => cat.id === editingCategoryId);
                            if (category) handleSaveCategory(category);
                          }}
                          disabled={categorySaving || !editingCategoryName.trim()}
                          className="bg-gold hover:bg-gold/90 disabled:opacity-50 text-cream text-xs font-bold px-3 py-1.5 rounded-lg"
                        >
                          Salvar
                        </button>
                        <button
                          type="button"
                          onClick={cancelEditCategory}
                          className="bg-surface-03 hover:bg-brand-mid text-parchment text-xs font-bold px-3 py-1.5 rounded-lg"
                        >
                          Cancelar
                        </button>
                      </div>
                    </div>
                  )}

                  {filteredParentCategories.length === 0 ? (
                    <p className="text-stone text-sm text-center py-4">
                      {parentCategories.length === 0 ? "Nenhuma categoria cadastrada." : "Nenhuma categoria encontrada para esta busca."}
                    </p>
                  ) : (
                    <div className="space-y-3">
                      {filteredParentCategories.map((category) => {
                        const children = getVisibleSubcategoriesForCategory(category);
                        const draftName = newSubcategoryNames[category.id] || "";
                        const categoryIndex = parentCategories.findIndex((item) => item.id === category.id);
                        const categoryIsReordering = categoryReorderingId === category.id;

                        return (
                          <div key={category.id} className="rounded-xl border border-surface-03 bg-surface-01 p-4 space-y-3">
                            <div className="flex items-center gap-3">
                              <Tag size={14} className="text-gold flex-shrink-0" />
                              <div className="flex-1 min-w-0">
                                <p className="text-cream text-sm font-bold">{category.name}</p>
                                <p className="text-stone text-xs">
                                  {category.active ? "Categoria ativa" : "Categoria inativa"} - {children.length} subcategoria{children.length === 1 ? "" : "s"}
                                </p>
                              </div>
                              <div className="flex items-center gap-1">
                                <button
                                  type="button"
                                  onClick={() => handleMoveCategory(category, -1)}
                                  disabled={categoryIsReordering || categoryIndex <= 0}
                                  className="text-stone hover:text-gold transition-colors p-1.5 disabled:opacity-30 disabled:cursor-not-allowed"
                                  title="Mover categoria para cima"
                                >
                                  <ChevronUp size={14} />
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleMoveCategory(category, 1)}
                                  disabled={categoryIsReordering || categoryIndex < 0 || categoryIndex >= parentCategories.length - 1}
                                  className="text-stone hover:text-gold transition-colors p-1.5 disabled:opacity-30 disabled:cursor-not-allowed"
                                  title="Mover categoria para baixo"
                                >
                                  <ChevronDown size={14} />
                                </button>
                              </div>
                              <button
                                type="button"
                                onClick={() => startEditCategory(category)}
                                className="text-stone hover:text-gold transition-colors p-1.5"
                                title="Editar categoria"
                              >
                                <Edit2 size={14} />
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDeleteCategory(category)}
                                className="text-stone hover:text-red-400 transition-colors p-1.5"
                                title="Remover categoria"
                              >
                                <X size={14} />
                              </button>
                            </div>

                            <div className="pl-0 md:pl-8 space-y-2">
                              {children.length === 0 ? (
                                <p className="text-stone text-xs rounded-lg border border-dashed border-surface-03 px-3 py-2">
                                  Nenhuma subcategoria criada para esta categoria.
                                </p>
                              ) : (
                                children.map((subcategory) => {
                                  const subcategorySiblings = getSubcategoriesForCategory(category.id);
                                  const subcategoryIndex = subcategorySiblings.findIndex((item) => item.id === subcategory.id);
                                  const subcategoryIsReordering = categoryReorderingId === subcategory.id;

                                  return (
                                    <div key={subcategory.id} className="flex items-center gap-2 rounded-lg bg-surface-03 px-3 py-2">
                                      <span className="w-1.5 h-1.5 rounded-full bg-gold/70 flex-shrink-0" />
                                      <div className="flex-1 min-w-0">
                                        <p className="text-parchment text-sm font-semibold">{subcategory.name}</p>
                                        <p className="text-stone text-xs">
                                          {subcategory.active ? "Ativa para selecao no produto" : "Inativa"}
                                        </p>
                                      </div>
                                      <div className="flex items-center gap-1">
                                        <button
                                          type="button"
                                          onClick={() => handleMoveCategory(subcategory, -1)}
                                          disabled={subcategoryIsReordering || subcategoryIndex <= 0}
                                          className="text-stone hover:text-gold transition-colors p-1 disabled:opacity-30 disabled:cursor-not-allowed"
                                          title="Mover subcategoria para cima"
                                        >
                                          <ChevronUp size={13} />
                                        </button>
                                        <button
                                          type="button"
                                          onClick={() => handleMoveCategory(subcategory, 1)}
                                          disabled={subcategoryIsReordering || subcategoryIndex < 0 || subcategoryIndex >= subcategorySiblings.length - 1}
                                          className="text-stone hover:text-gold transition-colors p-1 disabled:opacity-30 disabled:cursor-not-allowed"
                                          title="Mover subcategoria para baixo"
                                        >
                                          <ChevronDown size={13} />
                                        </button>
                                      </div>
                                      <button
                                        type="button"
                                        onClick={() => startEditCategory(subcategory)}
                                        className="text-stone hover:text-gold transition-colors p-1.5"
                                        title="Editar subcategoria"
                                      >
                                        <Edit2 size={13} />
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() => handleDeleteCategory(subcategory)}
                                        className="text-stone hover:text-red-400 transition-colors p-1.5"
                                        title="Remover subcategoria"
                                      >
                                        <X size={13} />
                                      </button>
                                    </div>
                                  );
                                })
                              )}

                              <div className="grid grid-cols-1 md:grid-cols-[1fr,auto] gap-2 pt-1">
                                <input
                                  type="text"
                                  value={draftName}
                                  onChange={(e) => setNewSubcategoryNames((prev) => ({ ...prev, [category.id]: e.target.value }))}
                                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); handleAddSubcategory(category.id); } }}
                                  className={cls}
                                  placeholder={`Nova subcategoria de ${category.name}`}
                                  maxLength={100}
                                />
                                <button
                                  type="button"
                                  onClick={() => handleAddSubcategory(category.id)}
                                  disabled={categorySaving || !draftName.trim()}
                                  className="flex items-center justify-center gap-2 bg-surface-03 hover:bg-brand-mid disabled:opacity-50 disabled:cursor-not-allowed text-cream font-bold py-2 px-4 rounded-lg transition-colors"
                                >
                                  {categorySaving ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
                                  Adicionar subcategoria
                                </button>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {subcategories.length > 0 && (
                    <div className="bg-emerald-500/10 border border-emerald-500/25 rounded-lg p-3 text-emerald-200 text-xs leading-relaxed">
                      As subcategorias ativas aparecem automaticamente no catalogo da Home e na pagina Cardapio quando houver produto ativo vinculado a elas.
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

                {/* Best Seller Config */}
                <div className="bg-surface-02 rounded-xl p-6 border border-surface-03 space-y-4 mt-6">
                  <div className="flex items-center gap-3 pb-3 border-b border-surface-03">
                    <span className="text-lg">🔥</span>
                    <div>
                      <h3 className="text-cream font-bold">Selo "Mais Pedida" — Automático</h3>
                      <p className="text-stone text-sm">Configura o cálculo automático por volume de vendas</p>
                    </div>
                  </div>

                  {!bestSellerConfig ? (
                    <div className="flex items-center gap-2 text-stone text-sm py-2">
                      <Loader2 size={14} className="animate-spin" />
                      Carregando...
                    </div>
                  ) : (
                    <>
                      <div>
                        <label className="block text-parchment text-sm font-medium mb-2">Período de análise</label>
                        <select
                          value={bestSellerConfig.period_days}
                          onChange={(e) => setBestSellerConfig({ ...bestSellerConfig, period_days: Number(e.target.value) })}
                          className={cls}
                        >
                          <option value={7}>Últimos 7 dias</option>
                          <option value={15}>Últimos 15 dias</option>
                          <option value={30}>Últimos 30 dias</option>
                          <option value={0}>Todos os tempos</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-parchment text-sm font-medium mb-2">Quantidade máxima com selo automático</label>
                        <select
                          value={bestSellerConfig.top_count}
                          onChange={(e) => setBestSellerConfig({ ...bestSellerConfig, top_count: Number(e.target.value) })}
                          className={cls}
                        >
                          <option value={3}>Top 3 produtos</option>
                          <option value={5}>Top 5 produtos</option>
                          <option value={10}>Top 10 produtos</option>
                        </select>
                      </div>
                      <p className="text-stone text-xs">Considera apenas pedidos pagos e concluídos. Produtos com modo "Manual" têm prioridade sobre o automático.</p>
                      <button
                        onClick={handleBestSellerSave}
                        disabled={bestSellerSaving}
                        className={`w-full py-3 rounded-xl font-bold text-sm transition-colors ${bestSellerSaved ? "bg-green-500 text-white" : "bg-gold hover:bg-gold/90 text-cream"} disabled:opacity-60`}
                      >
                        {bestSellerSaved ? "✓ Salvo!" : bestSellerSaving ? "Salvando..." : "Salvar Configuração do Selo"}
                      </button>
                    </>
                  )}
                </div>
              </div>
            )}

          </div>
        </div>
      </div>

      {/* ── Product Form Modal ───────────────────────────────────────────────── */}
      {showForm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
          onClick={() => { setShowForm(false); setEditingId(null); }}
        >
          <div
            className="bg-surface-02 rounded-2xl border border-surface-03 w-full max-w-xl max-h-[90vh] overflow-y-auto shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-surface-03 sticky top-0 bg-surface-02 z-10">
              <h3 className="text-xl font-bold text-cream">{editingId ? "Editar Produto" : "Novo Produto"}</h3>
              <button onClick={() => { setShowForm(false); setEditingId(null); }} className="text-stone hover:text-cream transition-colors">
                <X size={20} />
              </button>
            </div>
            <div className="p-6">
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-parchment text-sm font-medium mb-2">Nome do Produto *</label>
                  <input type="text" value={formData.name || ""} onChange={(e) => setFormData({ ...formData, name: e.target.value })} className={cls} placeholder="Ex: Pizza Pepperoni" />
                </div>
                <div>
                  <label className="block text-parchment text-sm font-medium mb-2">Descrição *</label>
                  <textarea value={formData.description || ""} onChange={(e) => setFormData({ ...formData, description: e.target.value })} className={`${cls} resize-none`} placeholder="Descreva o produto..." rows={3} />
                </div>
                <div>
                  <label className="block text-parchment text-sm font-medium mb-2">Preco base *</label>
                  <input
                    type="number"
                    value={formData.price ?? ""}
                    onChange={(e) => setFormData({ ...formData, price: parseFloat(e.target.value) || 0 })}
                    className={cls}
                    placeholder="Ex: 39.90"
                    min="0.01"
                    step="0.01"
                  />
                  <p className="text-stone text-xs mt-1">Usado como preco inicial e fallback. Tamanhos podem ser configurados depois no card do produto.</p>
                </div>
                <div>
                  <div className="flex items-center justify-between gap-3 mb-2">
                    <label className="block text-parchment text-sm font-medium">Categoria</label>
                    <button
                      type="button"
                      onClick={() => { setShowForm(false); setEditingId(null); setActiveTab("categorias"); }}
                      className="text-xs text-gold hover:text-gold-light font-semibold"
                    >
                      Gerenciar categorias
                    </button>
                  </div>
                  <select
                    value={(formData as any).category || ""}
                    onChange={(e) => setFormData({ ...formData, category: e.target.value, subcategory: "" } as any)}
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
                <div>
                  <label className="block text-parchment text-sm font-medium mb-2">Subcategoria</label>
                  <select
                    value={(formData as any).subcategory || ""}
                    onChange={(e) => setFormData({ ...formData, subcategory: e.target.value } as any)}
                    className={cls}
                    disabled={!selectedCategoryId || availableSubcategories.length === 0}
                  >
                    <option value="">
                      {!selectedCategoryId ? "Selecione uma categoria primeiro" : availableSubcategories.length === 0 ? "Sem subcategorias cadastradas" : "Selecione uma subcategoria"}
                    </option>
                    {availableSubcategories.map((cat) => (
                      <option key={cat.id} value={cat.name}>{cat.name}</option>
                    ))}
                    {(formData as any).subcategory && !catalogSubcategoryNames.includes((formData as any).subcategory) && (
                      <option value={(formData as any).subcategory}>Subcategoria atual nao cadastrada: {(formData as any).subcategory}</option>
                    )}
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-4 items-start">
                  <ImageUpload
                    value={formData.icon || ""}
                    onChange={(v) => setFormData({ ...formData, icon: v })}
                    label="Ícone / Imagem do produto"
                    sizeGuide="Tamanho recomendado: 800×800px ou maior, máx. 2MB"
                    hint="Faça upload de uma imagem ou use um emoji 🍕"
                    maxKB={2048}
                  />
                  <div>
                    <label className="block text-parchment text-sm font-medium mb-2">Avaliação (1–5)</label>
                    <input type="number" value={formData.rating || ""} onChange={(e) => setFormData({ ...formData, rating: parseFloat(e.target.value) })} className={cls} placeholder="4.5" min="1" max="5" step="0.1" />
                  </div>
                </div>
                <div>
                  <label className="block text-parchment text-sm font-medium mb-2">Selo "Mais Pedida"</label>
                  <select
                    value={(formData as any).best_seller_badge_mode || "off"}
                    onChange={(e) => setFormData({ ...formData, best_seller_badge_mode: e.target.value } as any)}
                    className={cls}
                  >
                    <option value="off">Não exibir</option>
                    <option value="manual">Manual — exibir sempre neste produto</option>
                    <option value="auto">Automático — conforme volume de vendas</option>
                  </select>
                  <p className="text-stone text-xs mt-1">Manual tem prioridade. Automático considera apenas pedidos pagos/concluídos.</p>
                </div>

                {!editingId && (
                  <div className="bg-surface-03/60 rounded-lg p-3 text-stone text-xs">
                    {(formData.product_type || "pizza") === "pizza" && (
                      <span>💡 Após criar a pizza, use <strong className="text-parchment">Gerenciar Tamanhos</strong>, <strong className="text-parchment">Gerenciar Massas</strong> e <strong className="text-parchment">Gerenciar Bordas</strong> no card do produto.</span>
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
          </div>
        </div>
      )}

      {/* ── Sizes Modal ───────────────────────────────────────────────────────── */}
      {promotionModalProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={closePromotionModal}>
          <div className="bg-surface-02 rounded-2xl border border-surface-03 w-full max-w-5xl max-h-[90vh] overflow-y-auto shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-surface-03 sticky top-0 bg-surface-02 z-10">
              <div className="flex items-center gap-3">
                <Tag size={18} className="text-emerald-300" />
                <div>
                  <h3 className="text-cream font-bold">Promoções</h3>
                  <p className="text-stone text-xs">{promotionModalProduct.name}</p>
                </div>
              </div>
              <button onClick={closePromotionModal} className="text-stone hover:text-cream transition-colors">
                <X size={20} />
              </button>
            </div>

            <div className="p-6 grid grid-cols-1 lg:grid-cols-[260px,1fr] gap-5">
              <aside className="space-y-3">
                <button onClick={handleNewPromotion} className="w-full flex items-center justify-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2.5 rounded-xl transition-colors text-sm">
                  <Plus size={15} /> Nova Promoção
                </button>
                {promoLoading ? (
                  <div className="flex items-center justify-center py-6 text-stone gap-2">
                    <Loader2 size={16} className="animate-spin" />
                    <span className="text-sm">Carregando...</span>
                  </div>
                ) : productPromotions.length === 0 ? (
                  <p className="text-stone text-sm bg-surface-03 rounded-xl p-4">Nenhuma promoção cadastrada para esta pizza.</p>
                ) : (
                  <div className="space-y-2">
                    {productPromotions.map((promotion) => (
                      <button
                        key={promotion.id}
                        onClick={() => handleEditPromotion(promotion)}
                        className={`w-full text-left rounded-xl border px-4 py-3 transition-colors ${
                          editingPromotionId === promotion.id
                            ? "bg-emerald-500/10 border-emerald-500/40"
                            : "bg-surface-03 border-surface-03 hover:border-emerald-500/30"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-cream font-bold text-sm line-clamp-1">{promotion.name}</span>
                          <span className={`text-[10px] px-2 py-0.5 rounded-full ${promotion.active ? "bg-emerald-500/20 text-emerald-300" : "bg-red-500/20 text-red-300"}`}>
                            {promotion.active ? "ativa" : "inativa"}
                          </span>
                        </div>
                        <p className="text-stone text-xs mt-1">{promotion.valid_weekdays.map((day) => WEEKDAYS.find((item) => item.value === day)?.label).filter(Boolean).join(", ") || "Sem dias"}</p>
                      </button>
                    ))}
                  </div>
                )}
              </aside>

              <section className="space-y-5">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-parchment text-xs font-medium mb-1">Nome da promoção *</label>
                    <input value={promotionForm.name} onChange={(e) => setPromotionForm((form) => ({ ...form, name: e.target.value }))} className={cls} placeholder="Ex: Terça da Pizza" maxLength={200} />
                  </div>
                  <div>
                    <label className="block text-parchment text-xs font-medium mb-1">Tipo de desconto</label>
                    <select value={promotionForm.discount_type} onChange={(e) => setPromotionForm((form) => ({ ...form, discount_type: e.target.value as ProductPromotionDiscountType }))} className={cls}>
                      {(Object.keys(DISCOUNT_LABELS) as ProductPromotionDiscountType[]).map((type) => (
                        <option key={type} value={type}>{DISCOUNT_LABELS[type]}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <label className="inline-flex items-center gap-2 text-parchment text-sm">
                    <input type="checkbox" checked={promotionForm.active} onChange={(e) => setPromotionForm((form) => ({ ...form, active: e.target.checked }))} className="accent-gold" />
                    Promoção ativa
                  </label>
                  <span className="text-stone text-xs">Timezone: America/Sao_Paulo</span>
                </div>

                <div>
                  <label className="block text-parchment text-xs font-medium mb-2">Dias válidos</label>
                  <div className="flex gap-2 flex-wrap">
                    {WEEKDAYS.map((day) => (
                      <button
                        key={day.value}
                        type="button"
                        onClick={() => handleTogglePromotionWeekday(day.value)}
                        className={`px-3 py-2 rounded-lg text-xs font-bold border transition-colors ${
                          promotionForm.valid_weekdays.includes(day.value)
                            ? "bg-gold text-cream border-gold"
                            : "bg-surface-03 text-stone border-surface-03 hover:text-cream"
                        }`}
                      >
                        {day.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div>
                    <label className="block text-parchment text-xs font-medium mb-1">Data inicial</label>
                    <input type="date" value={promotionForm.start_date} onChange={(e) => setPromotionForm((form) => ({ ...form, start_date: e.target.value }))} className={cls} />
                  </div>
                  <div>
                    <label className="block text-parchment text-xs font-medium mb-1">Data final</label>
                    <input type="date" value={promotionForm.end_date} onChange={(e) => setPromotionForm((form) => ({ ...form, end_date: e.target.value }))} className={cls} />
                  </div>
                  <div>
                    <label className="block text-parchment text-xs font-medium mb-1">Hora inicial</label>
                    <input type="time" value={promotionForm.start_time} onChange={(e) => setPromotionForm((form) => ({ ...form, start_time: e.target.value }))} className={cls} />
                  </div>
                  <div>
                    <label className="block text-parchment text-xs font-medium mb-1">Hora final</label>
                    <input type="time" value={promotionForm.end_time} onChange={(e) => setPromotionForm((form) => ({ ...form, end_time: e.target.value }))} className={cls} />
                  </div>
                </div>

                <div className="overflow-x-auto rounded-xl border border-surface-03">
                  <table className="w-full min-w-[720px] text-sm">
                    <thead className="bg-surface-03 text-stone">
                      <tr>
                        <th className="text-left px-4 py-3">Tamanho</th>
                        <th className="text-left px-4 py-3">Massa</th>
                        <th className="text-left px-4 py-3">Preço padrão</th>
                        <th className="text-left px-4 py-3">{promotionForm.discount_type === "fixed_price" ? "Preço promocional" : "Valor do desconto"}</th>
                        <th className="text-left px-4 py-3">Ativar</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-03">
                      {promoCombinations.map((combo, index) => {
                        const size = promoSizes.find((item) => item.id === combo.product_size_id);
                        const crust = promoCrusts.find((item) => item.id === combo.product_crust_type_id);
                        const standardPrice = (size?.price ?? promotionModalProduct.price) + (crust ? normalizeCrustPriceAddition(crust.price_addition, promotionModalProduct.price) : 0);
                        return (
                          <tr key={`${combo.product_size_id}-${combo.product_crust_type_id ?? "none"}`} className="bg-surface-02">
                            <td className="px-4 py-3 text-cream font-semibold">{size ? pizzaSizeLabel(size.label) : "Padrão"}</td>
                            <td className="px-4 py-3 text-parchment">{crust?.name ?? "Sem massa"}</td>
                            <td className="px-4 py-3 text-gold font-bold">R$ {standardPrice.toFixed(2)}</td>
                            <td className="px-4 py-3">
                              <input
                                type="number"
                                value={combo.promotional_value ?? ""}
                                onChange={(e) => updatePromoCombination(index, { promotional_value: e.target.value === "" ? null : Number(e.target.value) })}
                                className="w-32 bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream outline-none focus:border-gold"
                                placeholder={promotionForm.discount_type === "percent_off" ? "10" : "39.90"}
                                step="0.01"
                                min="0"
                              />
                            </td>
                            <td className="px-4 py-3">
                              <input type="checkbox" checked={combo.active} onChange={(e) => updatePromoCombination(index, { active: e.target.checked })} className="accent-gold" />
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                <div className="flex flex-col sm:flex-row gap-3">
                  <button onClick={handleSavePromotion} disabled={promoSaving || promoLoading} className="flex-1 flex items-center justify-center gap-2 bg-gold hover:bg-gold/90 disabled:opacity-60 text-cream font-bold py-3 rounded-xl transition-colors text-sm">
                    {promoSaving ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
                    {editingPromotionId ? "Salvar Promoção" : "Criar Promoção"}
                  </button>
                  {editingPromotionId && (
                    <button
                      onClick={() => {
                        const promotion = productPromotions.find((item) => item.id === editingPromotionId);
                        if (promotion) handleDeletePromotion(promotion);
                      }}
                      className="flex items-center justify-center gap-2 bg-red-500/20 hover:bg-red-500/30 text-red-300 font-bold py-3 px-5 rounded-xl transition-colors text-sm"
                    >
                      <Trash2 size={16} /> Excluir
                    </button>
                  )}
                </div>
              </section>
            </div>
          </div>
        </div>
      )}

      {sizesModalProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={closeSizesModal}>
          <div className="bg-surface-02 rounded-2xl border border-surface-03 w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-2xl" onClick={(e) => e.stopPropagation()}>
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
                            <span className="text-cream font-bold text-sm">{pizzaSizeLabel(size.label)}</span>
                            {size.is_default && <span className="text-[10px] bg-gold/20 text-gold border border-gold/30 px-1.5 py-0.5 rounded-full">padrão</span>}
                            {!size.active && <span className="text-[10px] bg-red-500/20 text-red-400 border border-red-500/30 px-1.5 py-0.5 rounded-full">inativo</span>}
                          </div>
                          {pizzaSizeDescription(size.label, size.description) && (
                            <p className="text-stone text-xs mt-0.5">{pizzaSizeDescription(size.label, size.description)}</p>
                          )}
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
                      <input type="text" value={sizeForm.label} onChange={(e) => setSizeForm((f) => ({ ...f, label: e.target.value }))} className={cls} placeholder={(sizesModalProduct as any).product_type === "drink" ? 'Ex: "600ml"' : 'Ex: "Pizza Broto"'} maxLength={50} />
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={closeCrustModal}>
          <div className="bg-surface-02 rounded-2xl border border-surface-03 w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-2xl" onClick={(e) => e.stopPropagation()}>
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
      {borderModalProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={closeBorderModal}>
          <div className="bg-surface-02 rounded-2xl border border-surface-03 w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-surface-03 sticky top-0 bg-surface-02 z-10">
              <div className="flex items-center gap-3">
                <Tag size={18} className="text-orange-300" />
                <div>
                  <h3 className="text-cream font-bold">Bordas</h3>
                  <p className="text-stone text-xs">{borderModalProduct.name}</p>
                </div>
              </div>
              <button onClick={closeBorderModal} className="text-stone hover:text-cream transition-colors">
                <X size={20} />
              </button>
            </div>

            <div className="p-6 space-y-6">
              <div>
                <h4 className="text-parchment text-sm font-semibold mb-3">Bordas cadastradas</h4>
                {bordersLoading ? (
                  <div className="flex items-center justify-center py-6 text-stone gap-2">
                    <Loader2 size={16} className="animate-spin" />
                    <span className="text-sm">Carregando...</span>
                  </div>
                ) : productBorders.length === 0 ? (
                  <p className="text-stone text-sm text-center py-4">Nenhuma borda cadastrada para esta pizza.</p>
                ) : (
                  <div className="space-y-2">
                    {productBorders.map((border) => (
                      <div key={border.id} className="flex items-center gap-3 bg-surface-03 rounded-xl px-4 py-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-cream font-bold text-sm">{CATUPIRY_CRUST_NAME}</span>
                            {!border.active && <span className="text-[10px] bg-red-500/20 text-red-400 border border-red-500/30 px-1.5 py-0.5 rounded-full">inativa</span>}
                          </div>
                        </div>
                        <input
                          type="number"
                          defaultValue={border.price_addition.toFixed(2)}
                          onBlur={(e) => handleUpdateBorderPrice(border, e.target.value)}
                          disabled={savingBorderId === border.id}
                          className="w-24 bg-surface-02 border border-surface-03 rounded-lg px-2 py-1 text-orange-300 font-bold text-sm outline-none focus:border-orange-300"
                          step="0.01"
                          min="0"
                          title="Adicional da borda"
                        />
                        <div className="flex items-center gap-1 flex-shrink-0">
                          <button onClick={() => handleToggleBorderActive(border)} disabled={savingBorderId === border.id} title={border.active ? "Desativar" : "Ativar"} className={`p-1.5 rounded-lg transition-colors ${border.active ? "text-green-400 hover:text-red-400" : "text-red-400 hover:text-green-400"}`}>
                            {savingBorderId === border.id ? <Loader2 size={13} className="animate-spin" /> : <Settings2 size={13} />}
                          </button>
                          <button onClick={() => handleDeleteBorder(border.id)} className="p-1.5 rounded-lg text-stone hover:text-red-400 transition-colors">
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="border-t border-surface-03 pt-5">
                <h4 className="text-parchment text-sm font-semibold mb-3">Adicionar Borda com Catupiry</h4>
                <div className="space-y-3">
                  <div>
                    <label className="block text-parchment text-xs font-medium mb-1">Adicional da borda (R$)</label>
                    <input
                      type="number"
                      value={borderForm.price_addition}
                      onChange={(e) => setBorderForm({ price_addition: e.target.value })}
                      className={cls}
                      placeholder="0.00"
                      step="0.01"
                      min="0"
                    />
                  </div>
                  <button onClick={handleAddCatupiryBorder} className="w-full flex items-center justify-center gap-2 bg-orange-500 hover:bg-orange-500/90 text-white font-bold py-2.5 rounded-xl transition-colors text-sm">
                    <Plus size={15} /> Adicionar Borda
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {drinkModalProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={closeDrinkModal}>
          <div className="bg-surface-02 rounded-2xl border border-surface-03 w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-2xl" onClick={(e) => e.stopPropagation()}>
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

      {/* ── Brinde Form Modal ────────────────────────────────────────────────── */}
      {showBrindeForm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
          onClick={() => { setShowBrindeForm(false); setEditingBrindeId(null); }}
        >
          <div
            className="bg-surface-02 rounded-2xl border border-surface-03 w-full max-w-xl max-h-[90vh] overflow-y-auto shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-surface-03 sticky top-0 bg-surface-02 z-10">
              <h3 className="text-xl font-bold text-cream">{editingBrindeId ? "Editar Brinde" : "Novo Brinde"}</h3>
              <button onClick={() => { setShowBrindeForm(false); setEditingBrindeId(null); }} className="text-stone hover:text-cream transition-colors">
                <X size={20} />
              </button>
            </div>
            <div className="p-6">
              <form onSubmit={handleBrindeSubmit} className="space-y-4">
                <div>
                  <label className="block text-parchment text-sm font-medium mb-2">Nome do Brinde *</label>
                  <input
                    type="text"
                    value={brindeForm.name}
                    onChange={(e) => setBrindeForm((f) => ({ ...f, name: e.target.value }))}
                    className={cls}
                    placeholder="Ex: Refrigerante Lata, Sobremesa..."
                    maxLength={200}
                  />
                </div>
                <div>
                  <label className="block text-parchment text-sm font-medium mb-2">Descrição *</label>
                  <textarea
                    value={brindeForm.description}
                    onChange={(e) => setBrindeForm((f) => ({ ...f, description: e.target.value }))}
                    className={`${cls} resize-none`}
                    placeholder="Descreva o brinde..."
                    rows={3}
                  />
                </div>
                <div>
                  <label className="block text-parchment text-sm font-medium mb-2">Foto do Brinde</label>
                  <ImageUpload
                    value={brindeForm.icon}
                    onChange={(url) => setBrindeForm((f) => ({ ...f, icon: url }))}
                    label="Foto do Brinde"
                    previewRounded={false}
                    maxKB={1024}
                    sizeGuide="Recomendado: 400×400px, JPEG ou PNG, máx. 1MB"
                  />
                </div>
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => setBrindeForm((f) => ({ ...f, active: !f.active }))}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${brindeForm.active ? "bg-gold" : "bg-surface-03"}`}
                  >
                    <span className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${brindeForm.active ? "translate-x-6" : "translate-x-1"}`} />
                  </button>
                  <span className="text-parchment text-sm">{brindeForm.active ? "Ativo" : "Inativo"}</span>
                </div>
                <div className="flex gap-3 pt-2">
                  <button
                    type="submit"
                    disabled={brindeSaving}
                    className="flex items-center gap-2 bg-gold hover:bg-gold/90 disabled:opacity-50 text-cream font-bold py-2 px-6 rounded-lg transition-colors"
                  >
                    {brindeSaving ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
                    {editingBrindeId ? "Salvar" : "Criar Brinde"}
                  </button>
                  <button
                    type="button"
                    onClick={() => { setShowBrindeForm(false); setEditingBrindeId(null); }}
                    className="flex items-center gap-2 bg-surface-03 hover:bg-surface-03/80 text-parchment font-bold py-2 px-6 rounded-lg transition-colors"
                  >
                    <X size={16} /> Cancelar
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
