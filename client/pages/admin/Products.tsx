import { useState, useCallback, useEffect } from "react";
import { Plus, Trash2, Edit2, Settings2, Tag, Ruler, X, Check, Loader2, ChefHat, Droplets } from "lucide-react";
import { useApp, Pizza, PricingRule } from "@/context/AppContext";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";
import ImageUpload from "@/components/admin/ImageUpload";
import { sizesApi, crustApi, drinkVariantApi, categoriesApi, productPromotionsApi, ApiProductSize, ApiProductCrustType, ApiProductDrinkVariant, ApiProductCategory, ApiProductPromotion, ApiProductPromotionCombination, ProductPromotionDiscountType, isAssetUrl, resolveAssetUrl } from "@/lib/api";
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

type PTab = "produtos" | "categorias" | "config";

export default function AdminProducts() {
  const { products, addProduct, updateProduct, deleteProduct, multiFlavorsConfig, updateMultiFlavorsConfig } = useApp();
  const [activeTab, setActiveTab] = useState<PTab>("produtos");
  const [configSaved, setConfigSaved] = useState(false);
  const [catalogCategories, setCatalogCategories] = useState<ApiProductCategory[]>([]);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [newSubcategoryNames, setNewSubcategoryNames] = useState<Record<string, string>>({});
  const [categorySaving, setCategorySaving] = useState(false);
  const [editingCategoryId, setEditingCategoryId] = useState<string | null>(null);
  const [editingCategoryName, setEditingCategoryName] = useState("");
  const [editingCategoryParentId, setEditingCategoryParentId] = useState("");
  const [editingCategoryActive, setEditingCategoryActive] = useState(true);

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

  // ── Products CRUD ────────────────────────────────────────────────────────────
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<Partial<Pizza> & { product_type?: string }>({
    name: "", description: "", price: 0, icon: "🍕", category: "", rating: 4.5, product_type: "pizza",
  });

  const selectedCategoryId = activeCatalogCategories.find((cat) => cat.name === ((formData as any).category || ""))?.id ?? "";
  const availableSubcategories = activeSubcategories.filter((cat) => cat.parent_id === selectedCategoryId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name || !formData.description) {
      alert("Preencha todos os campos obrigatórios");
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
        await updateProduct(editingId, { ...formData, category: category || null, subcategory: subcategory || null } as any);
        setEditingId(null);
      } else {
        await addProduct({
          name: formData.name!, description: formData.description!,
          price: formData.price!, icon: formData.icon || "🍕",
          category: category || null,
          subcategory: subcategory || null,
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
      subcategory: (product as any).subcategory ?? "",
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

  const cls = "w-full bg-surface-03 border border-surface-03 rounded-lg px-4 py-2 text-cream placeholder-stone focus:outline-none focus:border-gold text-sm";

  const getTypeIcon = (type: string | null | undefined) => {
    if (type === "drink") return "🥤";
    if (type === "other") return "🍔";
    return "🍕";
  };

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
                  onClick={() => { setShowForm(!showForm); setEditingId(null); setFormData({ name: "", description: "", price: 0, icon: "🍕", category: "", rating: 4.5, product_type: "pizza" }); }}
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
            <div className="flex flex-wrap gap-2">
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
            {activeTab === "produtos" && (
              <button
                onClick={() => { setShowForm(!showForm); setEditingId(null); setFormData({ name: "", description: "", price: 0, icon: "ðŸ•", category: "", rating: 4.5, product_type: "pizza" }); }}
                className="flex items-center justify-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-4 rounded-lg transition-colors"
              >
                <Plus size={20} />
                Novo Produto
              </button>
            )}
          </div>

          <div className="p-8 pt-6">

            {/* ── TAB: PRODUTOS ── */}
            {activeTab === "produtos" && (
              <>
                {showForm && (
                  <div className="bg-surface-02 rounded-xl p-6 border border-surface-03 mb-8">
                    <h3 className="text-xl font-bold text-cream mb-4">{editingId ? "Editar Produto" : "Novo Produto"}</h3>
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
                              {(product as any).subcategory && (
                                <span className="inline-flex items-center gap-1 text-xs bg-emerald-500/15 text-emerald-300 border border-emerald-500/25 px-2 py-0.5 rounded-full">
                                  {(product as any).subcategory}
                                </span>
                              )}
                              <span className="inline-flex items-center gap-1 text-xs bg-surface-03 text-stone border border-surface-03 px-2 py-0.5 rounded-full">
                                {getTypeIcon(pType)} {pType === "drink" ? "Bebida" : pType === "other" ? "Outros" : "Pizza"}
                              </span>
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

                  {parentCategories.length === 0 ? (
                    <p className="text-stone text-sm text-center py-4">
                      Nenhuma categoria cadastrada.
                    </p>
                  ) : (
                    <div className="space-y-3">
                      {parentCategories.map((category) => {
                        const children = getSubcategoriesForCategory(category.id);
                        const draftName = newSubcategoryNames[category.id] || "";

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
                                children.map((subcategory) => (
                                  <div key={subcategory.id} className="flex items-center gap-2 rounded-lg bg-surface-03 px-3 py-2">
                                    <span className="w-1.5 h-1.5 rounded-full bg-gold/70 flex-shrink-0" />
                                    <div className="flex-1 min-w-0">
                                      <p className="text-parchment text-sm font-semibold">{subcategory.name}</p>
                                      <p className="text-stone text-xs">
                                        {subcategory.active ? "Ativa para selecao no produto" : "Inativa"}
                                      </p>
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
                                ))
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
              </div>
            )}

          </div>
        </div>
      </div>

      {/* ── Sizes Modal ───────────────────────────────────────────────────────── */}
      {promotionModalProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-surface-02 rounded-2xl border border-surface-03 w-full max-w-5xl max-h-[90vh] overflow-y-auto shadow-2xl">
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
