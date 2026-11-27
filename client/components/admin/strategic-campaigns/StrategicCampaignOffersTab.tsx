import { useEffect, useMemo, useState } from "react";
import {
  Archive,
  ArrowDown,
  ArrowUp,
  Copy,
  Edit3,
  Loader2,
  PackagePlus,
  Plus,
  Save,
  Search,
  Trash2,
  X,
} from "lucide-react";
import MediaUpload from "@/components/admin/MediaUpload";
import {
  campaignsApi,
  categoriesApi,
  productsApi,
  strategicCampaignsApi,
  type ApiProduct,
  type ApiProductCategory,
  type ApiPromotionalKit,
  type ApiStrategicCampaign,
  type ApiStrategicOffer,
  type ApiStrategicOfferConfig,
  type StrategicOfferComponent,
  type StrategicOfferPricingStrategy,
  type StrategicOfferReferenceType,
} from "@/lib/api";

type SourceType = StrategicOfferReferenceType;

type ComponentDraft = {
  subcategoryId: string;
  quantity: string;
  allowRepeatedProducts?: boolean;
  restrictions?: Record<string, unknown> | null;
};

type OfferDraft = {
  code: string;
  title: string;
  description: string;
  sourceType: SourceType;
  sourceId: string;
  components: ComponentDraft[];
  selectionQuantity: string;
  pricingStrategy: StrategicOfferPricingStrategy;
  pricingValue: string;
  priceOriginal: string;
  pricePromotional: string;
  quantityLimit: string;
  maxPerCustomer: string;
  salesStartsAt: string;
  salesEndsAt: string;
  buttonText: string;
  badgeText: string;
  imageDesktopUrl: string;
  imageMobileUrl: string;
  highlighted: boolean;
  active: boolean;
  showWhenSoldOut: boolean;
};

const inputClass =
  "mt-1 w-full rounded-xl border border-surface-03 bg-surface-02 px-3 py-2.5 text-sm text-cream outline-none focus:border-gold";
const sourceTypeLabels: Record<SourceType, string> = {
  product: "Produto",
  kit: "Combo",
  subcategory: "Subcategoria",
  mixed_subcategories: "Mesclar subcategorias",
};
const pricingStrategyLabels: Record<StrategicOfferPricingStrategy, string> = {
  catalog: "Preço de catálogo",
  percentage: "Desconto percentual",
  fixed_discount: "Desconto fixo",
  fixed_price: "Preço promocional fixo",
};

function emptyDraft(campaign: ApiStrategicCampaign): OfferDraft {
  const next = campaign.offers.length + 1;
  return {
    code: `${campaign.slug.toUpperCase().replace(/-/g, "_")}-${String(next).padStart(3, "0")}`,
    title: "",
    description: "",
    sourceType: "product",
    sourceId: "",
    components: [],
    selectionQuantity: "",
    pricingStrategy: "fixed_price",
    pricingValue: "",
    priceOriginal: "",
    pricePromotional: "",
    quantityLimit: "",
    maxPerCustomer: "",
    salesStartsAt: toLocalDateTime(campaign.starts_at),
    salesEndsAt: toLocalDateTime(campaign.ends_at),
    buttonText: "Comprar agora",
    badgeText: "",
    imageDesktopUrl: "",
    imageMobileUrl: "",
    highlighted: false,
    active: true,
    showWhenSoldOut: true,
  };
}

export function getStrategicOfferReferenceType(
  offer: Pick<
    ApiStrategicOffer,
    "product_id" | "kit_id" | "reference_type" | "config"
  >,
): SourceType {
  const configured = offer.reference_type ?? offer.config?.reference_type;
  if (
    configured === "product" ||
    configured === "kit" ||
    configured === "subcategory" ||
    configured === "mixed_subcategories"
  )
    return configured;
  return offer.kit_id ? "kit" : "product";
}

export function getStrategicOfferComponents(
  offer: Pick<ApiStrategicOffer, "components" | "config"> | null | undefined,
): StrategicOfferComponent[] {
  const components = Array.isArray(offer?.components)
    ? offer.components
    : offer?.config?.components;
  if (!Array.isArray(components)) return [];
  return components
    .filter(
      (component) =>
        component &&
        typeof component.subcategory_id === "string" &&
        Number(component.quantity) > 0,
    )
    .map((component) => ({
      subcategory_id: component.subcategory_id,
      quantity: Math.max(1, Math.trunc(Number(component.quantity))),
      allow_repeated_products: component.allow_repeated_products ?? true,
      restrictions: component.restrictions ?? null,
    }));
}

export function buildStrategicOfferConfig(
  draft: Pick<
    OfferDraft,
    | "sourceType"
    | "components"
    | "selectionQuantity"
    | "pricingStrategy"
    | "pricingValue"
  >,
): ApiStrategicOfferConfig {
  const value = Number(draft.pricingValue);
  const config: ApiStrategicOfferConfig = {
    reference_type: draft.sourceType,
    pricing_strategy: draft.pricingStrategy,
    selection_quantity:
      draft.sourceType === "mixed_subcategories"
        ? Math.max(1, Math.trunc(Number(draft.selectionQuantity) || 1))
        : undefined,
  };
  if (
    draft.sourceType === "subcategory" ||
    draft.sourceType === "mixed_subcategories"
  ) {
    config.components = draft.components.map((component) => ({
      subcategory_id: component.subcategoryId,
      quantity: Math.max(1, Math.trunc(Number(component.quantity))),
      allow_repeated_products: component.allowRepeatedProducts ?? true,
      restrictions: component.restrictions ?? null,
    }));
  }
  if (draft.pricingStrategy === "percentage") config.discount_percent = value;
  if (draft.pricingStrategy === "fixed_discount")
    config.discount_amount = value;
  if (draft.pricingStrategy === "fixed_price")
    config.fixed_promotional_price = value;
  return config;
}

export function buildStrategicOfferCommercialContract(
  draft: Pick<
    OfferDraft,
    | "sourceType"
    | "components"
    | "selectionQuantity"
    | "pricingStrategy"
    | "pricingValue"
  >,
) {
  const pricingValue = Number(draft.pricingValue);
  const components =
    draft.sourceType === "subcategory" ||
    draft.sourceType === "mixed_subcategories"
      ? draft.components.map((component) => ({
          subcategory_id: component.subcategoryId,
          quantity: Math.max(1, Math.trunc(Number(component.quantity))),
          allow_repeated_products: component.allowRepeatedProducts ?? true,
          restrictions: component.restrictions ?? null,
        }))
      : [];
  return {
    reference_type: draft.sourceType,
    selection_quantity:
      draft.sourceType === "mixed_subcategories"
        ? Math.max(1, Math.trunc(Number(draft.selectionQuantity) || 1))
        : null,
    components,
    pricing_strategy: draft.pricingStrategy,
    discount_percent:
      draft.pricingStrategy === "percentage" ? pricingValue : null,
    discount_amount:
      draft.pricingStrategy === "fixed_discount" ? pricingValue : null,
    fixed_promotional_price:
      draft.pricingStrategy === "fixed_price" ? pricingValue : null,
    config: buildStrategicOfferConfig(draft),
  };
}

export function calculateStrategicOfferPriceRange(
  draft: Pick<
    OfferDraft,
    | "sourceType"
    | "sourceId"
    | "components"
    | "pricingStrategy"
    | "pricingValue"
    | "priceOriginal"
  >,
  products: ApiProduct[],
  kits: ApiPromotionalKit[],
) {
  let minimum = 0;
  let maximum = 0;
  if (draft.sourceType === "product") {
    const price = Number(
      products.find((product) => product.id === draft.sourceId)?.price ??
        draft.priceOriginal ??
        0,
    );
    minimum = maximum = price;
  } else if (draft.sourceType === "kit") {
    const kit = kits.find((item) => item.id === draft.sourceId);
    minimum = maximum = Number(kit?.price_original ?? draft.priceOriginal ?? 0);
  } else {
    const hasExplicitSelectionQuantity =
      draft.sourceType === "mixed_subcategories" &&
      Number(draft.selectionQuantity) >= 1;
    const multiplier =
      draft.sourceType === "mixed_subcategories"
        ? Number.isFinite(Number(draft.selectionQuantity)) && Number(draft.selectionQuantity) >= 1
          ? Math.trunc(Number(draft.selectionQuantity))
          : draft.components.reduce((total, component) => total + Math.max(1, Math.trunc(Number(component.quantity) || 1)), 0)
        : 1;
    for (const component of draft.components) {
      const eligiblePrices = products
        .filter((product) => product.subcategory_id === component.subcategoryId)
        .map((product) => Number(product.price))
        .filter((price) => Number.isFinite(price) && price >= 0);
      if (!eligiblePrices.length) continue;
      const quantity = Math.max(1, Math.trunc(Number(component.quantity) || 1));
      if (hasExplicitSelectionQuantity) continue;
      minimum += Math.min(...eligiblePrices) * quantity;
      maximum += Math.max(...eligiblePrices) * quantity;
    }
    if (hasExplicitSelectionQuantity) {
      const eligiblePrices = products
        .filter((product) => draft.components.some((component) => product.subcategory_id === component.subcategoryId))
        .map((product) => Number(product.price))
        .filter((price) => Number.isFinite(price) && price >= 0);
      if (eligiblePrices.length) {
        minimum = Math.min(...eligiblePrices) * multiplier;
        maximum = Math.max(...eligiblePrices) * multiplier;
      }
    }
  }
  const value = Math.max(0, Number(draft.pricingValue) || 0);
  const apply = (amount: number) => {
    if (draft.pricingStrategy === "catalog") return amount;
    if (draft.pricingStrategy === "percentage")
      return Math.max(0, amount * (1 - value / 100));
    if (draft.pricingStrategy === "fixed_discount")
      return Math.max(0, amount - value);
    return value;
  };
  return {
    originalMinimum: minimum,
    originalMaximum: maximum,
    promotionalMinimum: apply(minimum),
    promotionalMaximum: apply(maximum),
  };
}

function offerDraft(offer: ApiStrategicOffer): OfferDraft {
  const sourceType = getStrategicOfferReferenceType(offer);
  const components = getStrategicOfferComponents(offer).map((component) => ({
    subcategoryId: component.subcategory_id,
    quantity: String(component.quantity),
    allowRepeatedProducts: component.allow_repeated_products ?? true,
    restrictions: component.restrictions ?? null,
  }));
  const pricingStrategy =
    offer.pricing_strategy ?? offer.config?.pricing_strategy ?? "fixed_price";
  const pricingValue =
    pricingStrategy === "percentage"
      ? (offer.discount_percent ?? offer.config.discount_percent)
      : pricingStrategy === "fixed_discount"
        ? (offer.discount_amount ?? offer.config.discount_amount)
        : (offer.fixed_promotional_price ??
          offer.config.fixed_promotional_price ??
          offer.price_promotional);
  return {
    code: offer.code,
    title: offer.title,
    description: offer.description ?? "",
    sourceType,
    sourceId: offer.kit_id ?? offer.product_id ?? "",
    components:
      sourceType === "subcategory" && components.length === 0
        ? [{ subcategoryId: "", quantity: "1" }]
        : components,
    selectionQuantity:
      offer.selection_quantity == null ? "" : String(offer.selection_quantity),
    pricingStrategy,
    pricingValue: String(pricingValue ?? ""),
    priceOriginal: String(offer.price_original),
    pricePromotional: String(offer.price_promotional),
    quantityLimit:
      offer.quantity_limit == null ? "" : String(offer.quantity_limit),
    maxPerCustomer:
      offer.max_per_customer == null ? "" : String(offer.max_per_customer),
    salesStartsAt: toLocalDateTime(offer.sales_starts_at),
    salesEndsAt: toLocalDateTime(offer.sales_ends_at),
    buttonText: offer.button_text ?? "Comprar agora",
    badgeText: offer.badge_text ?? "",
    imageDesktopUrl: offer.image_desktop_url ?? "",
    imageMobileUrl: offer.image_mobile_url ?? "",
    highlighted: offer.highlighted,
    active: offer.active,
    showWhenSoldOut: offer.show_when_sold_out,
  };
}

function toIso(value: string) {
  return value ? new Date(value).toISOString() : null;
}

function toLocalDateTime(value: string | null | undefined) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return shifted.toISOString().slice(0, 16);
}

export default function StrategicCampaignOffersTab({
  campaign,
  onChanged,
}: {
  campaign: ApiStrategicCampaign;
  onChanged: (campaign: ApiStrategicCampaign) => void;
}) {
  const [products, setProducts] = useState<ApiProduct[]>([]);
  const [kits, setKits] = useState<ApiPromotionalKit[]>([]);
  const [categories, setCategories] = useState<ApiProductCategory[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState("");
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<ApiStrategicOffer | null>(null);
  const [draft, setDraft] = useState<OfferDraft>(() => emptyDraft(campaign));
  const [formOpen, setFormOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    setCatalogLoading(true);
    Promise.all([
      productsApi.list(true),
      campaignsApi.listKits(true),
      categoriesApi.list(true),
    ])
      .then(([productRows, kitRows, categoryRows]) => {
        setProducts(productRows);
        setKits(kitRows);
        setCategories(categoryRows);
        setCatalogError("");
      })
      .catch((error) =>
        setCatalogError(
          error instanceof Error
            ? error.message
            : "Não foi possível carregar o catálogo.",
        ),
      )
      .finally(() => setCatalogLoading(false));
  }, []);

  useEffect(() => {
    if (!formOpen) setDraft(emptyDraft(campaign));
  }, [campaign, formOpen]);

  const sources = useMemo(() => {
    const term = search.trim().toLocaleLowerCase("pt-BR");
    const rows =
      draft.sourceType === "product"
        ? products.map((item) => ({
            id: item.id,
            name: item.name,
            price: item.price,
            detail: item.product_type || "Produto",
          }))
        : kits.map((item) => ({
            id: item.id,
            name: item.name,
            price: item.price_promotional,
            detail: "Combo",
          }));
    return term
      ? rows.filter((item) =>
          item.name.toLocaleLowerCase("pt-BR").includes(term),
        )
      : rows;
  }, [draft.sourceType, kits, products, search]);

  const subcategories = useMemo(
    () =>
      categories
        .filter((category) => category.active && category.parent_id)
        .sort(
          (left, right) =>
            left.sort_order - right.sort_order ||
            left.name.localeCompare(right.name, "pt-BR"),
        ),
    [categories],
  );

  const priceRange = useMemo(
    () => calculateStrategicOfferPriceRange(draft, products, kits),
    [draft, kits, products],
  );

  const openCreate = () => {
    setEditing(null);
    setDraft(emptyDraft(campaign));
    setSearch("");
    setMessage("");
    setFormOpen(true);
  };

  const openEdit = (offer: ApiStrategicOffer) => {
    setEditing(offer);
    setDraft(offerDraft(offer));
    setSearch("");
    setMessage("");
    setFormOpen(true);
  };

  const reloadCampaign = async () =>
    onChanged(await strategicCampaignsApi.get(campaign.id));

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (
      (draft.sourceType === "product" || draft.sourceType === "kit") &&
      !draft.sourceId
    ) {
      setMessage("Selecione um produto ou combo do catálogo.");
      return;
    }
    const composition = draft.components.filter(
      (component) => component.subcategoryId,
    );
    if (draft.sourceType === "subcategory" && composition.length !== 1) {
      setMessage("Selecione uma subcategoria e informe a quantidade.");
      return;
    }
    if (draft.sourceType === "mixed_subcategories" && composition.length < 2) {
      setMessage("Adicione pelo menos duas subcategorias para criar a mescla.");
      return;
    }
    if (
      draft.sourceType === "mixed_subcategories" &&
      (!Number.isInteger(Number(draft.selectionQuantity)) ||
        Number(draft.selectionQuantity) < 1)
    ) {
      setMessage("Informe quantos produtos o cliente poderá escolher no total.");
      return;
    }
    if (
      composition.some(
        (component) =>
          !Number.isInteger(Number(component.quantity)) ||
          Number(component.quantity) < 1,
      )
    ) {
      setMessage(
        "A quantidade de cada subcategoria deve ser um número inteiro positivo.",
      );
      return;
    }
    if (
      new Set(composition.map((component) => component.subcategoryId)).size !==
      composition.length
    ) {
      setMessage(
        "Uma subcategoria não pode aparecer mais de uma vez na oferta.",
      );
      return;
    }
    const pricingValue = Number(draft.pricingValue);
    if (
      (draft.pricingStrategy !== "catalog" && !Number.isFinite(pricingValue)) ||
      pricingValue < 0 ||
      (draft.pricingStrategy === "percentage" &&
        (pricingValue <= 0 || pricingValue > 100)) ||
      (draft.pricingStrategy === "fixed_discount" && pricingValue <= 0)
    ) {
      setMessage(
        draft.pricingStrategy === "percentage"
          ? "Informe um percentual maior que 0 e menor ou igual a 100."
          : "Informe um valor comercial válido.",
      );
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      const common = {
        title: draft.title.trim(),
        description: draft.description.trim() || null,
        price_original: Math.max(
          priceRange.originalMaximum,
          priceRange.promotionalMaximum,
        ),
        price_promotional: priceRange.promotionalMinimum,
        quantity_limit: draft.quantityLimit
          ? Number(draft.quantityLimit)
          : null,
        selection_quantity:
          draft.sourceType === "mixed_subcategories"
            ? Number(draft.selectionQuantity)
            : null,
        max_per_customer: draft.maxPerCustomer
          ? Number(draft.maxPerCustomer)
          : null,
        sales_starts_at: toIso(draft.salesStartsAt),
        sales_ends_at: toIso(draft.salesEndsAt),
        show_when_sold_out: draft.showWhenSoldOut,
        button_text: draft.buttonText.trim() || null,
        image_desktop_url: draft.imageDesktopUrl || null,
        image_mobile_url: draft.imageMobileUrl || null,
        badge_text: draft.badgeText.trim() || null,
        highlighted: draft.highlighted,
        display_order: editing?.display_order ?? campaign.offers.length,
        product_id: draft.sourceType === "product" ? draft.sourceId : null,
        kit_id: draft.sourceType === "kit" ? draft.sourceId : null,
        ...buildStrategicOfferCommercialContract({
          ...draft,
          components: composition,
        }),
      };
      if (editing) {
        await strategicCampaignsApi.updateOffer(editing.id, {
          ...common,
          active: draft.active,
        });
      } else {
        await strategicCampaignsApi.addOffer(campaign.id, {
          ...common,
          code: draft.code.trim(),
        });
      }
      await reloadCampaign();
      setFormOpen(false);
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Não foi possível salvar a oferta.",
      );
    } finally {
      setSaving(false);
    }
  };

  const toggle = async (offer: ApiStrategicOffer) => {
    setSaving(true);
    try {
      await strategicCampaignsApi.updateOffer(offer.id, {
        active: !offer.active,
      });
      await reloadCampaign();
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Não foi possível alterar a oferta.",
      );
    } finally {
      setSaving(false);
    }
  };

  const duplicate = async (offer: ApiStrategicOffer) => {
    setSaving(true);
    setMessage("");
    try {
      await strategicCampaignsApi.duplicateOffer(offer.id);
      await reloadCampaign();
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Não foi possível duplicar a oferta.",
      );
    } finally {
      setSaving(false);
    }
  };

  const archive = async (offer: ApiStrategicOffer) => {
    if (
      !window.confirm(
        `Arquivar a oferta “${offer.title}”? O histórico comercial será preservado.`,
      )
    )
      return;
    setSaving(true);
    setMessage("");
    try {
      await strategicCampaignsApi.archiveOffer(offer.id);
      await reloadCampaign();
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Não foi possível arquivar a oferta.",
      );
    } finally {
      setSaving(false);
    }
  };

  const move = async (offerId: string, direction: -1 | 1) => {
    const ordered = [...campaign.offers]
      .filter((item) => !item.archived_at)
      .sort((a, b) => a.display_order - b.display_order);
    const index = ordered.findIndex((item) => item.id === offerId);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= ordered.length) return;
    [ordered[index], ordered[target]] = [ordered[target], ordered[index]];
    setSaving(true);
    setMessage("");
    try {
      await strategicCampaignsApi.reorderOffers(
        campaign.id,
        ordered.map((item) => item.id),
      );
      await reloadCampaign();
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Não foi possível reordenar as ofertas.",
      );
    } finally {
      setSaving(false);
    }
  };

  const pricePreview =
    priceRange.promotionalMinimum === priceRange.promotionalMaximum
      ? `R$ ${priceRange.promotionalMinimum.toFixed(2)}`
      : `R$ ${priceRange.promotionalMinimum.toFixed(2)} a R$ ${priceRange.promotionalMaximum.toFixed(2)}`;
  const totalProducts = draft.sourceType === "product" || draft.sourceType === "kit"
    ? 1
    : draft.sourceType === "mixed_subcategories"
      ? Number(draft.selectionQuantity) >= 1
        ? Math.trunc(Number(draft.selectionQuantity))
        : draft.components.reduce((total, component) => total + Math.max(0, Math.trunc(Number(component.quantity) || 0)), 0)
      : draft.components.reduce((total, component) => total + Math.max(0, Math.trunc(Number(component.quantity) || 0)), 0);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-bold text-cream">Ofertas da campanha</h2>
          <p className="text-sm text-stone">
            Use produtos, combos e subcategorias existentes. Nenhum item é
            duplicado no catálogo.
          </p>
        </div>
        <button
          type="button"
          onClick={openCreate}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-gold px-4 py-2.5 text-sm font-bold text-cream"
        >
          <Plus size={16} /> Adicionar oferta
        </button>
      </div>

      {message && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
          {message}
        </div>
      )}

      {campaign.offers.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-surface-03 bg-surface-01 px-6 py-12 text-center">
          <PackagePlus className="mx-auto text-gold" size={34} />
          <h3 className="mt-3 font-bold text-cream">
            Nenhuma oferta cadastrada
          </h3>
          <p className="mt-1 text-sm text-stone">
            Cadastre a primeira oferta diretamente pela interface
            administrativa.
          </p>
          <button
            type="button"
            onClick={openCreate}
            className="mt-4 rounded-xl bg-gold px-4 py-2 text-sm font-bold text-cream"
          >
            Adicionar oferta
          </button>
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {[...campaign.offers]
            .filter((offer) => !offer.archived_at)
            .sort((a, b) => a.display_order - b.display_order)
            .map((offer, index, ordered) => (
              <article
                key={offer.id}
                className="overflow-hidden rounded-2xl border border-surface-03 bg-surface-01"
              >
                {offer.image_desktop_url ? (
                  <img
                    src={offer.image_desktop_url}
                    alt=""
                    className="h-40 w-full object-cover"
                  />
                ) : (
                  <div className="flex h-28 items-center justify-center bg-surface-02 text-sm text-stone">
                    Sem imagem comercial
                  </div>
                )}
                <div className="space-y-3 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wider text-gold">
                        {offer.code}
                      </p>
                      <h3 className="font-bold text-cream">{offer.title}</h3>
                    </div>
                    <span
                      className={`rounded-full px-2 py-1 text-xs font-semibold ${offer.active ? "bg-emerald-500/15 text-emerald-300" : "bg-surface-03 text-stone"}`}
                    >
                      {offer.active ? "Ativa" : "Inativa"}
                    </span>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <strong className="text-xl text-gold">
                      R$ {offer.price_promotional.toFixed(2)}
                    </strong>
                    {offer.price_original > offer.price_promotional && (
                      <span className="text-sm text-stone line-through">
                        R$ {offer.price_original.toFixed(2)}
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => openEdit(offer)}
                      className="inline-flex items-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm font-semibold text-parchment"
                    >
                      <Edit3 size={14} /> Editar
                    </button>
                    <button
                      type="button"
                      disabled={saving}
                      onClick={() => void toggle(offer)}
                      className="rounded-lg border border-surface-03 px-3 py-2 text-sm font-semibold text-parchment"
                    >
                      {offer.active ? "Desativar" : "Ativar"}
                    </button>
                    <button
                      type="button"
                      disabled={saving}
                      onClick={() => void duplicate(offer)}
                      className="inline-flex items-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm font-semibold text-parchment"
                    >
                      <Copy size={14} /> Duplicar
                    </button>
                    <button
                      type="button"
                      disabled={saving || index === 0}
                      onClick={() => void move(offer.id, -1)}
                      aria-label="Mover oferta para cima"
                      className="rounded-lg border border-surface-03 p-2 text-parchment disabled:opacity-30"
                    >
                      <ArrowUp size={14} />
                    </button>
                    <button
                      type="button"
                      disabled={saving || index === ordered.length - 1}
                      onClick={() => void move(offer.id, 1)}
                      aria-label="Mover oferta para baixo"
                      className="rounded-lg border border-surface-03 p-2 text-parchment disabled:opacity-30"
                    >
                      <ArrowDown size={14} />
                    </button>
                    <button
                      type="button"
                      disabled={saving}
                      onClick={() => void archive(offer)}
                      className="inline-flex items-center gap-2 rounded-lg border border-red-500/30 px-3 py-2 text-sm font-semibold text-red-300"
                    >
                      <Archive size={14} /> Arquivar
                    </button>
                  </div>
                </div>
              </article>
            ))}
        </div>
      )}

      {formOpen && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 p-0 backdrop-blur-sm sm:items-center sm:p-5"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setFormOpen(false);
          }}
        >
          <form
            onSubmit={save}
            className="max-h-[95vh] w-full max-w-5xl overflow-y-auto rounded-t-2xl border border-surface-03 bg-surface-00 p-5 shadow-2xl sm:rounded-2xl"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-cream">
                  {editing ? "Editar oferta" : "Adicionar oferta"}
                </h2>
                <p className="text-sm text-stone">
                  Configuração comercial e apresentação visual individual.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setFormOpen(false)}
                className="rounded-lg p-2 text-stone hover:bg-surface-02 hover:text-cream"
                aria-label="Fechar"
              >
                <X />
              </button>
            </div>

            <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_.9fr]">
              <div className="space-y-5">
                <section className="space-y-4 rounded-2xl border border-surface-03 bg-surface-01 p-4">
                  <h3 className="font-bold text-cream">
                    Referência do catálogo
                  </h3>
                  <div className="grid grid-cols-2 gap-2">
                    {(
                      [
                        "product",
                        "kit",
                        "subcategory",
                        "mixed_subcategories",
                      ] as SourceType[]
                    ).map((type) => (
                      <button
                        key={type}
                        type="button"
                        disabled={Boolean(editing)}
                        onClick={() =>
                          setDraft((current) => ({
                            ...current,
                            sourceType: type,
                            sourceId: "",
                            components:
                              type === "subcategory"
                                ? [{ subcategoryId: "", quantity: "1" }]
                                : type === "mixed_subcategories"
                                  ? [
                                      { subcategoryId: "", quantity: "1" },
                                      { subcategoryId: "", quantity: "1" },
                                    ]
                                  : [],
                          }))
                        }
                        className={`rounded-xl border px-3 py-2 text-sm font-semibold ${draft.sourceType === type ? "border-gold bg-gold/15 text-gold" : "border-surface-03 text-parchment"}`}
                      >
                        {sourceTypeLabels[type]}
                      </button>
                    ))}
                  </div>
                  {(draft.sourceType === "product" ||
                    draft.sourceType === "kit") && (
                    <>
                      <label className="block text-xs font-medium text-parchment">
                        Pesquisar no catálogo
                        <div className="relative">
                          <Search
                            className="absolute left-3 top-3.5 text-stone"
                            size={15}
                          />
                          <input
                            value={search}
                            onChange={(event) => setSearch(event.target.value)}
                            className={`${inputClass} pl-9`}
                            placeholder="Nome do produto ou combo"
                          />
                        </div>
                      </label>
                      {catalogLoading ? (
                        <Loader2 className="animate-spin text-gold" />
                      ) : catalogError ? (
                        <p className="text-sm text-red-300">{catalogError}</p>
                      ) : (
                        <div className="max-h-56 space-y-2 overflow-y-auto">
                          {sources.map((source) => (
                            <button
                              key={source.id}
                              type="button"
                              disabled={Boolean(editing)}
                              onClick={() =>
                                setDraft((current) => ({
                                  ...current,
                                  sourceId: source.id,
                                  title: current.title || source.name,
                                  priceOriginal: String(source.price),
                                  pricingValue:
                                    current.pricingValue ||
                                    String(source.price),
                                }))
                              }
                              className={`flex w-full items-center justify-between rounded-xl border p-3 text-left ${draft.sourceId === source.id ? "border-gold bg-gold/10" : "border-surface-03 bg-surface-02"}`}
                            >
                              <span>
                                <strong className="block text-sm text-cream">
                                  {source.name}
                                </strong>
                                <small className="text-stone">
                                  {source.detail}
                                </small>
                              </span>
                              <span className="text-sm font-semibold text-gold">
                                R$ {Number(source.price).toFixed(2)}
                              </span>
                            </button>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                  {(draft.sourceType === "subcategory" ||
                    draft.sourceType === "mixed_subcategories") &&
                    (catalogLoading ? (
                      <Loader2 className="animate-spin text-gold" />
                    ) : catalogError ? (
                      <p className="text-sm text-red-300">{catalogError}</p>
                    ) : (
                      <div className="space-y-3">
                        {draft.components.map((component, index) => (
                          <div
                            key={`${index}-${component.subcategoryId}`}
                            className="rounded-xl border border-surface-03 bg-surface-02 p-3"
                          >
                            <div className="grid gap-3 sm:grid-cols-[1fr_6rem_auto] sm:items-end">
                              <label className="text-xs text-parchment">
                                Subcategoria
                                <select
                                  value={component.subcategoryId}
                                  onChange={(event) =>
                                    setDraft((current) => ({
                                      ...current,
                                      components: current.components.map(
                                        (item, itemIndex) =>
                                          itemIndex === index
                                            ? {
                                                ...item,
                                                subcategoryId:
                                                  event.target.value,
                                              }
                                            : item,
                                      ),
                                    }))
                                  }
                                  className={inputClass}
                                >
                                  <option value="">Selecione</option>
                                  {subcategories.map((subcategory) => (
                                    <option
                                      key={subcategory.id}
                                      value={subcategory.id}
                                      disabled={draft.components.some(
                                        (item, itemIndex) =>
                                          itemIndex !== index &&
                                          item.subcategoryId === subcategory.id,
                                      )}
                                    >
                                      {subcategory.name}
                                    </option>
                                  ))}
                                </select>
                              </label>
                              <label className="text-xs text-parchment">
                                Quantidade
                                <input
                                  required
                                  min="1"
                                  step="1"
                                  type="number"
                                  value={component.quantity}
                                  onChange={(event) =>
                                    setDraft((current) => ({
                                      ...current,
                                      components: current.components.map(
                                        (item, itemIndex) =>
                                          itemIndex === index
                                            ? {
                                                ...item,
                                                quantity: event.target.value,
                                              }
                                            : item,
                                      ),
                                    }))
                                  }
                                  className={inputClass}
                                />
                              </label>
                              {draft.sourceType === "mixed_subcategories" && (
                                <div className="flex gap-1">
                                  <button
                                    type="button"
                                    aria-label={`Mover subcategoria ${index + 1} para cima`}
                                    disabled={index === 0}
                                    onClick={() =>
                                      setDraft((current) => {
                                        const components = [
                                          ...current.components,
                                        ];
                                        [
                                          components[index - 1],
                                          components[index],
                                        ] = [
                                          components[index],
                                          components[index - 1],
                                        ];
                                        return { ...current, components };
                                      })
                                    }
                                    className="rounded-lg border border-surface-03 p-2 text-parchment disabled:opacity-30"
                                  >
                                    <ArrowUp size={14} />
                                  </button>
                                  <button
                                    type="button"
                                    aria-label={`Mover subcategoria ${index + 1} para baixo`}
                                    disabled={
                                      index === draft.components.length - 1
                                    }
                                    onClick={() =>
                                      setDraft((current) => {
                                        const components = [
                                          ...current.components,
                                        ];
                                        [
                                          components[index],
                                          components[index + 1],
                                        ] = [
                                          components[index + 1],
                                          components[index],
                                        ];
                                        return { ...current, components };
                                      })
                                    }
                                    className="rounded-lg border border-surface-03 p-2 text-parchment disabled:opacity-30"
                                  >
                                    <ArrowDown size={14} />
                                  </button>
                                  <button
                                    type="button"
                                    aria-label={`Remover subcategoria ${index + 1}`}
                                    disabled={draft.components.length <= 2}
                                    onClick={() =>
                                      setDraft((current) => ({
                                        ...current,
                                        components: current.components.filter(
                                          (_, itemIndex) => itemIndex !== index,
                                        ),
                                      }))
                                    }
                                    className="rounded-lg border border-red-500/30 p-2 text-red-300 disabled:opacity-30"
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                </div>
                              )}
                            </div>
                            {component.subcategoryId && (
                              <p className="mt-2 text-xs text-stone">
                                {
                                  products.filter(
                                    (product) =>
                                      product.subcategory_id ===
                                      component.subcategoryId,
                                  ).length
                                }{" "}
                                produto(s) ativo(s) disponível(is).
                              </p>
                            )}
                          </div>
                        ))}
                        {draft.sourceType === "mixed_subcategories" && (
                          <label className="block rounded-xl border border-gold/25 bg-gold/10 p-3 text-sm text-parchment">
                            Quantidade total de produtos escolhíveis
                            <input
                              required
                              min="1"
                              max="100"
                              step="1"
                              type="number"
                              value={draft.selectionQuantity}
                              onChange={(event) =>
                                setDraft({ ...draft, selectionQuantity: event.target.value })
                              }
                              className={inputClass}
                            />
                            <span className="mt-1 block text-xs text-stone">
                              O cliente escolherá essa quantidade entre todas as subcategorias acima.
                            </span>
                          </label>
                        )}
                        {draft.sourceType === "mixed_subcategories" && (
                          <button
                            type="button"
                            onClick={() =>
                              setDraft((current) => ({
                                ...current,
                                components: [
                                  ...current.components,
                                  { subcategoryId: "", quantity: "1" },
                                ],
                              }))
                            }
                            className="inline-flex items-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm font-semibold text-parchment"
                          >
                            <Plus size={14} /> Adicionar subcategoria
                          </button>
                        )}
                        <p className="rounded-xl border border-gold/25 bg-gold/10 p-3 text-sm font-bold text-gold">
                          Quantidade total de produtos: {totalProducts}
                        </p>
                        {subcategories.length === 0 && (
                          <p className="text-sm text-amber-300">
                            Nenhuma subcategoria ativa foi encontrada no
                            catálogo.
                          </p>
                        )}
                      </div>
                    ))}
                </section>

                <section className="grid gap-4 rounded-2xl border border-surface-03 bg-surface-01 p-4 sm:grid-cols-2">
                  <h3 className="sm:col-span-2 font-bold text-cream">
                    Condições comerciais
                  </h3>
                  <label className="text-xs text-parchment">
                    Código exclusivo
                    <input
                      required
                      disabled={Boolean(editing)}
                      value={draft.code}
                      onChange={(event) =>
                        setDraft({ ...draft, code: event.target.value })
                      }
                      className={inputClass}
                    />
                  </label>
                  <label className="text-xs text-parchment">
                    Título comercial
                    <input
                      required
                      value={draft.title}
                      onChange={(event) =>
                        setDraft({ ...draft, title: event.target.value })
                      }
                      className={inputClass}
                    />
                  </label>
                  <label className="text-xs text-parchment sm:col-span-2">
                    Descrição
                    <textarea
                      value={draft.description}
                      onChange={(event) =>
                        setDraft({ ...draft, description: event.target.value })
                      }
                      className={`${inputClass} min-h-20`}
                    />
                  </label>
                  <label className="text-xs text-parchment">
                    Estratégia de preço
                    <select
                      value={draft.pricingStrategy}
                      onChange={(event) =>
                        setDraft({
                          ...draft,
                          pricingStrategy: event.target
                            .value as StrategicOfferPricingStrategy,
                          pricingValue:
                            event.target.value === "catalog"
                              ? ""
                              : draft.pricingValue,
                        })
                      }
                      className={inputClass}
                    >
                      {(
                        [
                          "percentage",
                          "fixed_discount",
                          "fixed_price",
                          "catalog",
                        ] as StrategicOfferPricingStrategy[]
                      ).map((strategy) => (
                        <option key={strategy} value={strategy}>
                          {pricingStrategyLabels[strategy]}
                        </option>
                      ))}
                    </select>
                  </label>
                  {draft.pricingStrategy !== "catalog" && (
                    <label className="text-xs text-parchment">
                      {draft.pricingStrategy === "percentage"
                        ? "Percentual (%)"
                        : draft.pricingStrategy === "fixed_discount"
                          ? "Valor do desconto"
                          : "Preço promocional"}
                      <input
                        required
                        min={
                          draft.pricingStrategy === "fixed_price" ? "0" : "0.01"
                        }
                        max={
                          draft.pricingStrategy === "percentage"
                            ? "100"
                            : undefined
                        }
                        step="0.01"
                        type="number"
                        value={draft.pricingValue}
                        onChange={(event) =>
                          setDraft({
                            ...draft,
                            pricingValue: event.target.value,
                          })
                        }
                        className={inputClass}
                      />
                    </label>
                  )}
                  <div className="rounded-xl border border-gold/25 bg-gold/10 p-3 text-xs text-parchment sm:col-span-2">
                    <strong className="block text-gold">
                      Prévia comercial: {pricePreview}
                    </strong>
                    <span>
                      Faixa original calculada pelo catálogo: R${" "}
                      {priceRange.originalMinimum.toFixed(2)} a R${" "}
                      {priceRange.originalMaximum.toFixed(2)}. O backend
                      confirma o valor final.
                    </span>
                  </div>
                  <label className="text-xs text-parchment">
                    Quantidade máxima
                    <input
                      min="0"
                      type="number"
                      value={draft.quantityLimit}
                      onChange={(event) =>
                        setDraft({
                          ...draft,
                          quantityLimit: event.target.value,
                        })
                      }
                      className={inputClass}
                    />
                  </label>
                  <label className="text-xs text-parchment">
                    Limite por cliente
                    <input
                      min="1"
                      type="number"
                      value={draft.maxPerCustomer}
                      onChange={(event) =>
                        setDraft({
                          ...draft,
                          maxPerCustomer: event.target.value,
                        })
                      }
                      className={inputClass}
                    />
                  </label>
                  <label className="text-xs text-parchment">
                    Início da oferta
                    <input
                      type="datetime-local"
                      value={draft.salesStartsAt}
                      onChange={(event) =>
                        setDraft({
                          ...draft,
                          salesStartsAt: event.target.value,
                        })
                      }
                      className={inputClass}
                    />
                  </label>
                  <label className="text-xs text-parchment">
                    Encerramento da oferta
                    <input
                      type="datetime-local"
                      value={draft.salesEndsAt}
                      onChange={(event) =>
                        setDraft({ ...draft, salesEndsAt: event.target.value })
                      }
                      className={inputClass}
                    />
                  </label>
                </section>
              </div>

              <section className="space-y-5 rounded-2xl border border-surface-03 bg-surface-01 p-4">
                <h3 className="font-bold text-cream">Apresentação visual</h3>
                <MediaUpload
                  mediaType="image"
                  label="Imagem desktop"
                  value={draft.imageDesktopUrl}
                  onChange={(value) =>
                    setDraft((current) => ({
                      ...current,
                      imageDesktopUrl: value,
                    }))
                  }
                  sizeGuide="Recomendado: 1200 × 800 px, WebP/JPG/PNG."
                />
                <MediaUpload
                  mediaType="image"
                  label="Imagem smartphone"
                  value={draft.imageMobileUrl}
                  onChange={(value) =>
                    setDraft((current) => ({
                      ...current,
                      imageMobileUrl: value,
                    }))
                  }
                  sizeGuide="Recomendado: 800 × 800 px, WebP/JPG/PNG."
                />
                <label className="block text-xs text-parchment">
                  Texto do botão
                  <input
                    value={draft.buttonText}
                    onChange={(event) =>
                      setDraft({ ...draft, buttonText: event.target.value })
                    }
                    className={inputClass}
                  />
                </label>
                <label className="block text-xs text-parchment">
                  Selo promocional
                  <input
                    value={draft.badgeText}
                    onChange={(event) =>
                      setDraft({ ...draft, badgeText: event.target.value })
                    }
                    className={inputClass}
                    placeholder="Ex.: Mais vendida"
                  />
                </label>
                <label className="flex items-center gap-3 rounded-xl border border-surface-03 bg-surface-02 p-3 text-sm text-parchment">
                  <input
                    type="checkbox"
                    checked={draft.highlighted}
                    onChange={(event) =>
                      setDraft({ ...draft, highlighted: event.target.checked })
                    }
                    className="accent-gold"
                  />{" "}
                  Destacar visualmente esta oferta
                </label>
                <label className="flex items-center gap-3 rounded-xl border border-surface-03 bg-surface-02 p-3 text-sm text-parchment">
                  <input
                    type="checkbox"
                    checked={draft.showWhenSoldOut}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        showWhenSoldOut: event.target.checked,
                      })
                    }
                    className="accent-gold"
                  />{" "}
                  Manter visível quando esgotada
                </label>
                {editing && (
                  <label className="flex items-center gap-3 rounded-xl border border-surface-03 bg-surface-02 p-3 text-sm text-parchment">
                    <input
                      type="checkbox"
                      checked={draft.active}
                      onChange={(event) =>
                        setDraft({ ...draft, active: event.target.checked })
                      }
                      className="accent-gold"
                    />{" "}
                    Oferta ativa
                  </label>
                )}
              </section>
            </div>

            <div className="mt-6 flex flex-col-reverse gap-2 border-t border-surface-03 pt-4 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={() => setFormOpen(false)}
                className="rounded-xl border border-surface-03 px-4 py-2.5 text-sm font-semibold text-parchment"
              >
                Cancelar
              </button>
              <button
                disabled={saving || catalogLoading}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-gold px-5 py-2.5 text-sm font-bold text-cream disabled:opacity-60"
              >
                {saving ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Save size={16} />
                )}{" "}
                Salvar oferta
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
