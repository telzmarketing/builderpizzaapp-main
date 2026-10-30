import { useState, useMemo, useEffect, useId, type PointerEvent } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { ChevronLeft, Minus, Plus, AlertCircle, Check, Loader2, X, ZoomIn } from "lucide-react";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import CategorySeal from "@/components/CategorySeal";
import BestSellerSeal from "@/components/BestSellerSeal";
import { useApp, Pizza, PizzaFlavor, FlavorDivision, PricingRule, CartItemVariation, CartItemOptionSelection, type MultiFlavorsConfig } from "@/context/AppContext";
import { sizesApi, crustApi, productPromotionsApi, customerEventsApi, productsApi, ApiProductSize, ApiProductCrustType, ApiProductPriceQuote, ApiProductOptionGroup, getProductCategoryCapabilities, isAssetUrl, resolveAssetUrl, resolveOptimizedAssetUrl } from "@/lib/api";
import { isAllowedPizzaSize, isPizzaBroto, pizzaSizeDescription, pizzaSizeLabel, PIZZA_SIZE_LABELS } from "@/lib/pizzaSizes";
import { formatCrustAddition, isNapolitanaCrust, isNapolitanaCrustBlocked, normalizeCrustPriceAddition } from "@/lib/pricing";
import { firePixelEvent, trackEvent, getTrackingData } from "@/lib/tracking";

// ─── Add-ons ──────────────────────────────────────────────────────────────────

// ─── Helpers ──────────────────────────────────────────────────────────────────

const DIVISION_OPTIONS: { value: FlavorDivision; label: string; emoji: string }[] = [
  { value: 1, label: "Inteira", emoji: "🍕" },
  { value: 2, label: "Meio a Meio", emoji: "½" },
  { value: 3, label: "3 Sabores", emoji: "⅓" },
];

const PUBLIC_MAX_FLAVORS = 3;

const PRICING_LABELS: Record<PricingRule, string> = {
  most_expensive: "Preço do sabor mais caro",
  average: "Preço médio dos sabores",
  proportional: "Preço proporcional a cada parte",
};

const DRINK_PRODUCT_HINTS = [
  "agua",
  "bebida",
  "brahma",
  "budweiser",
  "cerveja",
  "chopp",
  "coca",
  "corona",
  "drink",
  "energetico",
  "fanta",
  "garrafa",
  "guarana",
  "h2o",
  "heineken",
  "lata",
  "litro",
  "long neck",
  "longneck",
  "mate",
  "ml",
  "monster",
  "pepsi",
  "refrigerante",
  "red bull",
  "skol",
  "sprite",
  "stella",
  "suco",
  "tonica",
];

const PIZZA_PRODUCT_HINTS = [
  "brotinho",
  "broto",
  "calzone",
  "doce",
  "doces",
  "especial",
  "especiais",
  "meio a meio",
  "napolitana",
  "pizza",
  "pizzas",
  "salgada",
  "salgadas",
  "tradicional",
  "tradicionais",
];

const SWEET_PRODUCT_HINTS = [
  "banana",
  "beijinho",
  "brigadeiro",
  "chocolate",
  "doce",
  "doces",
  "goiabada",
  "morango",
  "nutella",
  "prestigio",
  "romeu",
];

const normalizeProductText = (value?: string | null) =>
  String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();

const productSearchText = (candidate?: Pizza | null) =>
  normalizeProductText(
    [
      candidate?.name,
      candidate?.description,
      candidate?.category,
      candidate?.subcategory,
      candidate?.product_type,
    ].filter(Boolean).join(" ")
  );

const escapeRegExp = (value: string) =>
  value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const hasWordHint = (text: string, hints: string[]) =>
  hints.some((hint) => {
    const normalizedHint = normalizeProductText(hint);
    if (!normalizedHint) return false;
    return new RegExp(`(^|[^a-z0-9])${escapeRegExp(normalizedHint)}([^a-z0-9]|$)`, "i").test(text);
  });

const isSweetPizzaCandidate = (candidate?: Pizza | null) => {
  return hasWordHint(productSearchText(candidate), SWEET_PRODUCT_HINTS);
};

const productCategoryKeys = (candidate?: Pizza | null) =>
  [candidate?.category, candidate?.subcategory]
    .map((value) => normalizeProductText(value))
    .filter(Boolean);

const isFixedFlavorCombinationProduct = (candidate?: Pizza | null) =>
  productCategoryKeys(candidate).includes("combinacoes de sabores");

const matchesFlavorCategoryFilters = (candidate: Pizza, categoryFilters: string[] = []) => {
  const normalizedFilters = categoryFilters.map((value) => normalizeProductText(value)).filter(Boolean);
  if (normalizedFilters.length === 0) return false;
  const keys = productCategoryKeys(candidate);
  return keys.some((key) =>
    normalizedFilters.some((filter) => key === filter || key.includes(filter) || filter.includes(key))
  );
};

const isDrinkLikeCandidate = (candidate?: Pizza | null) => {
  if (!candidate) return false;
  const productType = normalizeProductText(candidate.product_type);
  if (["drink", "bebida", "beverage"].includes(productType)) return true;
  if (Array.isArray(candidate.drink_variants) && candidate.drink_variants.length > 0) return true;
  const searchableText = productSearchText(candidate);
  return hasWordHint(searchableText, DRINK_PRODUCT_HINTS) || /\b\d+\s*(ml|l|litro|litros)\b/.test(searchableText);
};

const isPizzaFlavorCandidate = (candidate?: Pizza | null, options: { allowSweet?: boolean; categoryFilters?: string[] } = {}) => {
  if (!candidate || candidate.active === false) return false;
  if (isFixedFlavorCombinationProduct(candidate)) return false;

  if (isDrinkLikeCandidate(candidate)) return false;

  const allowSweet = options.allowSweet ?? true;
  if (!allowSweet && isSweetPizzaCandidate(candidate)) return false;

  if (matchesFlavorCategoryFilters(candidate, options.categoryFilters)) return true;
  if ((options.categoryFilters ?? []).filter((value) => normalizeProductText(value)).length > 0) return false;

  const productType = normalizeProductText(candidate.product_type);
  if (productType) return productType === "pizza";

  return true;
};

function computeFlavorPrice(slots: (Pizza | null)[], division: number, rule: PricingRule): number {
  const filled = slots.slice(0, division).filter((f): f is Pizza => f !== null);
  if (filled.length === 0) return 0;
  if (rule === "most_expensive") return Math.max(...filled.map((f) => f.price));
  if (rule === "average") return filled.reduce((s, f) => s + f.price, 0) / filled.length;
  return filled.reduce((s, f) => s + f.price / division, 0);
}

// ─── SVG Pizza Diagram ────────────────────────────────────────────────────────

function SvgIcon({ icon, x, y, size }: { icon: string | undefined; x: number; y: number; size: number }) {
  if (!icon) return <text x={x} y={y} textAnchor="middle" dominantBaseline="middle" fontSize={size}>?</text>;
  if (isAssetUrl(icon)) {
    return (
      <image
        href={resolveOptimizedAssetUrl(icon, Math.ceil(size * 2))}
        x={x - size / 2}
        y={y - size / 2}
        width={size}
        height={size}
        preserveAspectRatio="xMidYMid slice"
      />
    );
  }
  return <text x={x} y={y} textAnchor="middle" dominantBaseline="middle" fontSize={size}>{icon}</text>;
}

function PizzaDiagram({ division, slots }: { division: FlavorDivision; slots: (Pizza | null)[] }) {
  const diagramId = useId().replace(/:/g, "");
  const S = 176;
  const cx = S / 2, cy = S / 2, r = S / 2 - 6;
  const filled = ["#f97316", "#ea580c", "#c2410c"];
  const empty = ["#1e293b", "#334155", "#475569"];
  const borderColor = "#0f172a";
  const imageBox = { x: cx - r, y: cy - r, size: r * 2 };
  const toRad = (d: number) => (d * Math.PI) / 180;
  const sectorPath = (start: number, end: number) => {
    const x1 = cx + r * Math.cos(toRad(start));
    const y1 = cy + r * Math.sin(toRad(start));
    const x2 = cx + r * Math.cos(toRad(end));
    const y2 = cy + r * Math.sin(toRad(end));
    const largeArc = Math.abs(end - start) > 180 ? 1 : 0;
    return `M ${cx} ${cy} L ${x1.toFixed(2)} ${y1.toFixed(2)} A ${r} ${r} 0 ${largeArc} 1 ${x2.toFixed(2)} ${y2.toFixed(2)} Z`;
  };
  const iconAt = (midDeg: number, dist = r * 0.58) => ({
    x: cx + dist * Math.cos(toRad(midDeg)),
    y: cy + dist * Math.sin(toRad(midDeg)),
  });

  if (division === 1) {
    const icon = slots[0]?.icon;
    const hasImage = isAssetUrl(icon);
    return (
      <svg width={S} height={S} viewBox={`0 0 ${S} ${S}`}>
        <defs>
          <clipPath id={`${diagramId}-full-flavor`}><circle cx={cx} cy={cy} r={r} /></clipPath>
        </defs>
        <circle cx={cx} cy={cy} r={r} fill={slots[0] ? filled[0] : empty[0]} />
        {hasImage && (
          <image
            href={resolveOptimizedAssetUrl(icon, 360)}
            x={imageBox.x}
            y={imageBox.y}
            width={imageBox.size}
            height={imageBox.size}
            preserveAspectRatio="xMidYMid slice"
            clipPath={`url(#${diagramId}-full-flavor)`}
          />
        )}
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={borderColor} strokeWidth="4" />
        {!hasImage && <SvgIcon icon={icon} x={cx} y={cy} size={60} />}
      </svg>
    );
  }

  if (division === 2) {
    const sectors = [
      { start: 90, end: 270, mid: 180 },
      { start: -90, end: 90, mid: 0 },
    ];
    return (
      <svg width={S} height={S} viewBox={`0 0 ${S} ${S}`}>
        <defs>
          {sectors.map((s, i) => (
            <clipPath key={i} id={`${diagramId}-half-flavor-${i}`}>
              <path d={sectorPath(s.start, s.end)} />
            </clipPath>
          ))}
        </defs>
        {sectors.map((s, i) => {
          const icon = slots[i]?.icon;
          const hasImage = isAssetUrl(icon);
          const pos = iconAt(s.mid);
          return (
            <g key={i}>
              <path d={sectorPath(s.start, s.end)} fill={slots[i] ? filled[i] : empty[i]} />
              {hasImage ? (
                <image
                  href={resolveOptimizedAssetUrl(icon, 360)}
                  x={imageBox.x}
                  y={imageBox.y}
                  width={imageBox.size}
                  height={imageBox.size}
                  preserveAspectRatio="xMidYMid slice"
                  clipPath={`url(#${diagramId}-half-flavor-${i})`}
                />
              ) : (
                <SvgIcon icon={icon} x={parseFloat(pos.x.toFixed(2))} y={parseFloat(pos.y.toFixed(2))} size={38} />
              )}
            </g>
          );
        })}
        <line x1={cx} y1={cy - r} x2={cx} y2={cy + r} stroke={borderColor} strokeWidth="4" />
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={borderColor} strokeWidth="4" />
      </svg>
    );
  }

  const sectors = [{ start: -90, end: 30 }, { start: 30, end: 150 }, { start: 150, end: 270 }];
  const divLines = [-90, 30, 150];

  return (
    <svg width={S} height={S} viewBox={`0 0 ${S} ${S}`}>
      <defs>
        {sectors.map((s, i) => (
          <clipPath key={i} id={`${diagramId}-third-flavor-${i}`}>
            <path d={sectorPath(s.start, s.end)} />
          </clipPath>
        ))}
      </defs>
      {sectors.map((s, i) => {
        const icon = slots[i]?.icon;
        const hasImage = isAssetUrl(icon);
        const mid = (s.start + s.end) / 2;
        const pos = iconAt(mid);
        return (
          <g key={i}>
            <path d={sectorPath(s.start, s.end)} fill={slots[i] ? filled[i] : empty[i]} />
            {hasImage ? (
              <image
                href={resolveOptimizedAssetUrl(icon, 360)}
                x={imageBox.x}
                y={imageBox.y}
                width={imageBox.size}
                height={imageBox.size}
                preserveAspectRatio="xMidYMid slice"
                clipPath={`url(#${diagramId}-third-flavor-${i})`}
              />
            ) : (
              <SvgIcon icon={icon} x={parseFloat(pos.x.toFixed(2))} y={parseFloat(pos.y.toFixed(2))} size={30} />
            )}
          </g>
        );
      })}
      {divLines.map((deg, i) => (
        <line key={i} x1={cx} y1={cy} x2={cx + r * Math.cos(toRad(deg))} y2={cy + r * Math.sin(toRad(deg))} stroke={borderColor} strokeWidth="4" />
      ))}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={borderColor} strokeWidth="4" />
    </svg>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export interface ProductConfiguratorProps {
  productId?: string;
  catalog?: Pizza[];
  embedded?: boolean;
  onBack?: () => void;
  onAdd?: ReturnType<typeof useApp>["addToCart"];
  flavorConfig?: MultiFlavorsConfig;
}

export default function Product({ productId, catalog, embedded = false, onBack, onAdd, flavorConfig }: ProductConfiguratorProps = {}) {
  const { id: routeId } = useParams<{ id: string }>();
  const id = productId ?? routeId;
  const navigate = useNavigate();
  const { products: storeProducts, addToCart: addStoreItem, multiFlavorsConfig: storeFlavorConfig, siteContent, loading: appLoading, customer } = useApp();
  const multiFlavorsConfig = flavorConfig ?? storeFlavorConfig;
  const products = catalog ?? storeProducts;
  const addToCart = onAdd ?? addStoreItem;
  const p = siteContent.pages.product;

  const product = products.find((p) => p.id === id);

  const [optionGroups, setOptionGroups] = useState<ApiProductOptionGroup[]>([]);
  const [optionGroupsLoading, setOptionGroupsLoading] = useState(false);
  const [selectedOptionState, setSelectedOptionState] = useState<Record<string, { selected: Record<string, number>; text: string }>>({});

  // Product type flags
  const productType = normalizeProductText(product?.product_type);
  const isDrink = isDrinkLikeCandidate(product);
  const categoryCapabilities = getProductCategoryCapabilities(product);
  const showProductOptions = categoryCapabilities?.enable_product_options !== false;
  const hasExplicitOptionGroups = showProductOptions && (optionGroups.length > 0 || Boolean(product?.option_groups?.length));
  const isPizza = !hasExplicitOptionGroups && !isDrink && (!productType || productType === "pizza");
  const isFixedFlavorCombination = isPizza && isFixedFlavorCombinationProduct(product);

  const [quantity, setQuantity] = useState(1);
  const [notes, setNotes] = useState("");
  const [division, setDivision] = useState<FlavorDivision>(1);
  const [flavorSlots, setFlavorSlots] = useState<(Pizza | null)[]>([product ?? null, null, null]);
  const [activeSlot, setActiveSlot] = useState<number | null>(null);
  const [cartError, setCartError] = useState(false);

  // Dynamic sizes from backend
  const [productSizes, setProductSizes] = useState<ApiProductSize[]>([]);
  const [selectedSizeObj, setSelectedSizeObj] = useState<ApiProductSize | null>(null);
  const [selectedSizeFallback, setSelectedSizeFallback] = useState("Pizza Grande");

  // Crust types (pizza only)
  const [productCrusts, setProductCrusts] = useState<ApiProductCrustType[]>([]);
  const [selectedCrust, setSelectedCrust] = useState<ApiProductCrustType | null>(null);
  const [selectedBorder, setSelectedBorder] = useState<ApiProductCrustType | null>(null);
  const [selectedDrinkVariantId, setSelectedDrinkVariantId] = useState("");
  const [optionsLoading, setOptionsLoading] = useState(true);
  const [optionsError, setOptionsError] = useState("");
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [quoteError, setQuoteError] = useState("");
  const [priceQuote, setPriceQuote] = useState<ApiProductPriceQuote | null>(null);

  const [imageZoomOpen, setImageZoomOpen] = useState(false);
  const [imageZoomScale, setImageZoomScale] = useState(1);
  const [imageZoomPosition, setImageZoomPosition] = useState({ x: 50, y: 50 });

  useEffect(() => {
    if (!product || embedded) return;
    const td = getTrackingData();
    customerEventsApi.register({
      event_type: "product_viewed",
      event_name: `Visualizou ${product.name}`,
      product_id: product.id,
      customer_id: customer?.id ?? null,
      session_id: td.session_id,
      page_url: window.location.href,
    }).catch(() => {});
    trackEvent("product_config_view", undefined, { product_id: product.id });
    trackEvent("product_viewed", undefined, { product_id: product.id });
    firePixelEvent("ViewContent", {
      value: product.current_price ?? product.price,
      content_name: product.name,
    });
  }, [product?.id]);

  useEffect(() => {
    if (!product) return;
    setQuantity(1);
    setNotes("");
    setDivision(1);
    setFlavorSlots([product, null, null]);
    setActiveSlot(null);
    setCartError(false);
    setSelectedCrust(null);
    setSelectedBorder(null);
    setSelectedDrinkVariantId((product.drink_variants ?? []).find((variant) => variant.active)?.id ?? "");
    setImageZoomOpen(false);
    setImageZoomScale(1);
    setImageZoomPosition({ x: 50, y: 50 });
    setOptionGroups(showProductOptions ? (product.option_groups ?? []).filter((group) => group.active) : []);
    setSelectedOptionState({});
  }, [product?.id, showProductOptions]);

  useEffect(() => {
    if (!product) return;
    if (!showProductOptions) {
      setOptionGroups([]);
      setOptionGroupsLoading(false);
      return;
    }
    let cancelled = false;
    setOptionGroupsLoading(true);
    productsApi.optionGroups.list(product.id, true).then((groups) => {
      if (!cancelled) setOptionGroups(groups.filter((group) => group.active));
    }).catch(() => {
      if (!cancelled) setOptionGroups(showProductOptions ? (product.option_groups ?? []).filter((group) => group.active) : []);
    }).finally(() => {
      if (!cancelled) setOptionGroupsLoading(false);
    });
    return () => { cancelled = true; };
  }, [product?.id, showProductOptions]);

  useEffect(() => {
    if (!product) {
      setProductSizes([]);
      setSelectedSizeObj(null);
      setProductCrusts([]);
      return;
    }
    setProductSizes([]);
    setSelectedSizeObj(null);
    setProductCrusts([]);

    let cancelled = false;
    setOptionsLoading(true);
    setOptionsError("");
    const showSizeOptions = categoryCapabilities?.enable_sizes ?? true;
    const showCrustOptions = categoryCapabilities?.enable_dough ?? (isPizza && product.show_crust_options !== false);
    const showBorderOptions = categoryCapabilities?.enable_border ?? (isPizza && product.show_crust_options !== false);
    setSelectedSizeFallback(showSizeOptions && isPizza ? "Pizza Grande" : "");
    const sizesRequest = hasExplicitOptionGroups || !showSizeOptions ? Promise.resolve() : sizesApi.list(product.id).then((sizes) => {
        if (cancelled) return;
        const activeSizes = sizes.filter((s) => s.active && (!isPizza || isAllowedPizzaSize(s.label)));
        setProductSizes(activeSizes);
        if (activeSizes.length > 0) {
          const def = activeSizes.find((s) => s.is_default) ?? activeSizes[0];
          setSelectedSizeObj(def);
        } else {
          setSelectedSizeObj(null);
          setSelectedSizeFallback(showSizeOptions && isPizza ? "Pizza Grande" : "");
        }
      }).catch(() => {
        if (!cancelled) setOptionsError("Nao foi possivel carregar as opcoes. Recarregue para tentar novamente.");
      });

    // Load crust types for pizza
    const crustRequest = (showCrustOptions || showBorderOptions) ? crustApi.list(product.id).then((crusts) => {
        if (cancelled) return;
        const activeCrusts = crusts.filter((c) => c.active);
        setProductCrusts(activeCrusts);
        setSelectedCrust(showCrustOptions ? activeCrusts.find((crust) => crust.option_kind === "dough") ?? null : null);
        setSelectedBorder(null);
      }).catch(() => { if (!cancelled) setOptionsError("Nao foi possivel carregar as massas e bordas."); }) : Promise.resolve();
    Promise.all([sizesRequest, crustRequest]).finally(() => { if (!cancelled) setOptionsLoading(false); });
    return () => { cancelled = true; };
  }, [product?.id, isPizza, isDrink, hasExplicitOptionGroups, categoryCapabilities?.enable_sizes, categoryCapabilities?.enable_dough, categoryCapabilities?.enable_border]);

  const selectedSize = selectedSizeObj ? selectedSizeObj.label : selectedSizeFallback;
  const isPizzaBrotoSelected = isPizza && isPizzaBroto(selectedSize);
  const productPrice = product?.delivery_price ?? product?.price ?? 0;
  const effectiveDivision: FlavorDivision = isFixedFlavorCombination ? 1 : division;
  const showSizeOptions = categoryCapabilities?.enable_sizes ?? true;
  const showCrustOptions = categoryCapabilities?.enable_dough ?? (isPizza && product?.show_crust_options !== false);
  const showBorderOptions = categoryCapabilities?.enable_border ?? (isPizza && product?.show_crust_options !== false);
  const showPromotions = categoryCapabilities?.enable_promotions !== false;

  // O recurso é compartilhado, mas o tipo persistido separa massas e bordas.
  const regularCrusts = productCrusts.filter((crust) => crust.option_kind === "dough");
  const borderCrusts = productCrusts.filter((crust) => crust.option_kind === "border");
  const borderAvailable = showBorderOptions && borderCrusts.length > 0 && !isNapolitanaCrust(selectedCrust?.name);

  const selectedOptionSelections = useMemo<CartItemOptionSelection[]>(() => optionGroups.flatMap((group) => {
    const state = selectedOptionState[group.id] ?? { selected: {}, text: "" };
    if (group.selection_type === "text") {
      return state.text.trim() ? [{ groupId: group.id, groupName: group.name, label: state.text.trim(), priceAddition: 0 }] : [];
    }
    return Object.entries(state.selected).filter(([, quantity]) => quantity > 0).flatMap(([optionId, quantity]) => {
      const option = group.options.find((candidate) => candidate.id === optionId);
      return option ? [{ groupId: group.id, groupName: group.name, optionId: option.id, label: option.name, quantity: group.selection_type === "quantity" ? quantity : 1, priceAddition: option.price_addition * (group.selection_type === "quantity" ? quantity : 1) }] : [];
    });
  }), [optionGroups, selectedOptionState]);

  const optionPriceAddition = selectedOptionSelections.reduce((sum, selection) => sum + selection.priceAddition, 0);
  const genericOptionsValid = optionGroups.every((group) => {
    const state = selectedOptionState[group.id] ?? { selected: {}, text: "" };
    if (group.selection_type === "text") return !group.required || state.text.trim().length > 0;
    const count = group.selection_type === "quantity"
      ? Object.values(state.selected).reduce((sum, quantity) => sum + quantity, 0)
      : Object.keys(state.selected).filter((optionId) => state.selected[optionId] > 0).length;
    const minimum = Math.max(group.required ? 1 : 0, group.min_selections || 0);
    return count >= minimum && (!group.max_selections || count <= group.max_selections);
  });

  const setOptionSelection = (group: ApiProductOptionGroup, optionId: string, quantity: number) => {
    setSelectedOptionState((current) => {
      const previous = current[group.id] ?? { selected: {}, text: "" };
      const selected = { ...previous.selected };
      if (quantity > 0) selected[optionId] = quantity;
      else delete selected[optionId];
      return { ...current, [group.id]: { ...previous, selected } };
    });
  };

  useEffect(() => {
    if (!isPizzaBrotoSelected || division === 1) return;
    setDivision(1);
    setActiveSlot(null);
    setCartError(false);
    setFlavorSlots((prev) => [prev[0] ?? product ?? null, null, null]);
  }, [isPizzaBrotoSelected, division, product?.id]);

  useEffect(() => {
    if (!product || !isFixedFlavorCombination) return;
    if (division !== 1) setDivision(1);
    setActiveSlot(null);
    setCartError(false);
    setFlavorSlots((prev) =>
      prev[0]?.id === product.id && prev[1] === null && prev[2] === null
        ? prev
        : [product, null, null]
    );
  }, [product?.id, isFixedFlavorCombination, division]);

  const selectedFlavorIdsKey = flavorSlots.slice(0, effectiveDivision).map((flavor) => flavor?.id ?? "").join("|");

  // Resetar borda se napolitana for selecionada
  useEffect(() => {
    if (isNapolitanaCrust(selectedCrust?.name)) setSelectedBorder(null);
  }, [selectedCrust?.id]);

  useEffect(() => {
    if (!isNapolitanaCrustBlocked(selectedCrust?.name, effectiveDivision)) return;
    setSelectedCrust(regularCrusts.find((crust) => !isNapolitanaCrust(crust.name)) ?? regularCrusts[0] ?? null);
    setSelectedBorder(null);
  }, [effectiveDivision, productCrusts, selectedCrust?.id]);

  useEffect(() => {
    if (!product || optionsLoading || optionsError || optionGroupsLoading) {
      setPriceQuote(null);
      return;
    }

    let cancelled = false;
    setQuoteLoading(true);
    setQuoteError("");
    setPriceQuote(null);
    if (hasExplicitOptionGroups) {
      const basePrice = product.delivery_price ?? product.price ?? 0;
      setPriceQuote({ standard_price: basePrice + optionPriceAddition, final_price: basePrice + optionPriceAddition, promotion_applied: false, promotion_id: null, promotion_name: null, discount_amount: 0, discount_type: null, free_shipping: false, gift_enabled: false, gift_product_id: null, gift_quantity: 1, gift_name: null, gift_icon: null, blocks_other_coupons: false, promotion_blocked: false, promotion_block_reason: null });
      setQuoteLoading(false);
      return;
    }
    const selectedFlavorIds = flavorSlots
      .slice(0, division)
      .map((flavor) => flavor?.id)
      .filter((id): id is string => Boolean(id));
    if (selectedFlavorIds.length !== effectiveDivision) { setQuoteLoading(false); return; }
    productPromotionsApi.quote(product.id, {
      size_id: selectedSizeObj?.id ?? null,
      crust_id: showCrustOptions ? selectedCrust?.id ?? null : null,
      border_id: showBorderOptions ? selectedBorder?.id ?? null : null,
      drink_variant_id: selectedDrinkVariantId || null,
      channel: "delivery",
      flavor_count: isDrink ? 1 : effectiveDivision,
      flavor_ids: selectedFlavorIds,
    }).then((quote) => {
      if (!cancelled) setPriceQuote(showPromotions ? quote : {
        ...quote,
        final_price: quote.standard_price,
        promotion_applied: false,
        promotion_id: null,
        promotion_name: null,
        discount_amount: 0,
        free_shipping: false,
        gift_enabled: false,
        gift_product_id: null,
        gift_quantity: 1,
        gift_name: null,
        gift_icon: null,
        blocks_other_coupons: false,
        promotion_blocked: false,
        promotion_block_reason: null,
      });
    }).catch(() => {
      if (!cancelled) { setPriceQuote(null); setQuoteError("Nao foi possivel confirmar o preco. Tente novamente."); }
    }).finally(() => {
      if (!cancelled) setQuoteLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [product?.id, isPizza, isDrink, hasExplicitOptionGroups, optionPriceAddition, optionGroupsLoading, selectedSizeObj?.id, selectedCrust?.id, selectedBorder?.id, selectedDrinkVariantId, effectiveDivision, selectedFlavorIdsKey, optionsLoading, optionsError, showCrustOptions, showBorderOptions, showPromotions]);

  // ── Computed values ──────────────────────────────────────────────────────────

  const activeFlavors = flavorSlots.slice(0, effectiveDivision);
  const allFilled = isFixedFlavorCombination || activeFlavors.every((f) => f !== null);
  const effectivePricingRule: PricingRule = multiFlavorsConfig.pricingRule;
  const flavorCategoryFilters = multiFlavorsConfig.flavorCategoryFilters ?? [];
  const selectedSizeLookup = normalizeProductText(selectedSizeObj?.label ?? selectedSize);

  const getFlavorDisplayPrice = (flavor?: Pizza | null) => {
    if (!flavor) return 0;
    if (isDrink) return selectedSizeObj?.price ?? flavor.price;

    if (selectedSizeLookup) {
      const matchingSize = flavor.sizes?.find(
        (size) => size.active && normalizeProductText(size.label) === selectedSizeLookup
      );
      if (matchingSize) return matchingSize.price;
      if (flavor.id === product?.id && selectedSizeObj) return selectedSizeObj.price;
    }

    return flavor.delivery_price ?? flavor.price;
  };

  const flavorPrice = useMemo(() => {
    if (isDrink) {
      // For drinks: price is the size price or product base price
      return selectedSizeObj?.price ?? productPrice;
    }

    const slotsWithDisplayPrice = activeFlavors.map((f) =>
      f ? { ...f, price: getFlavorDisplayPrice(f) } : null
    );
    return computeFlavorPrice(slotsWithDisplayPrice as (Pizza | null)[], effectiveDivision, effectivePricingRule);
  }, [activeFlavors, effectiveDivision, effectivePricingRule, selectedSizeLookup, selectedSizeObj, isDrink, productPrice, product?.id]);

  const variantPriceAddition = useMemo(() => {
    if (showCrustOptions && selectedCrust) return normalizeCrustPriceAddition(selectedCrust.price_addition, productPrice);
    return 0;
  }, [showCrustOptions, selectedCrust, productPrice]);

  const borderAddition = showBorderOptions && selectedBorder ? (selectedBorder.price_addition ?? 0) : 0;
  const localPricePerUnit = flavorPrice + variantPriceAddition;
  const pricePerUnit = priceQuote ? priceQuote.final_price : localPricePerUnit + borderAddition;
  const totalPrice = pricePerUnit * quantity;

  // ── Handlers ─────────────────────────────────────────────────────────────────

  const handleDivisionChange = (d: FlavorDivision) => {
    if (isFixedFlavorCombination) return;
    if (d > PUBLIC_MAX_FLAVORS) return;
    if (isPizzaBrotoSelected && d > 1) return;
    if (isNapolitanaCrustBlocked(selectedCrust?.name, d)) {
      setSelectedCrust(regularCrusts.find((crust) => !isNapolitanaCrust(crust.name)) ?? regularCrusts[0] ?? null);
      setSelectedBorder(null);
    }
    setDivision(d);
    setActiveSlot(null);
    setCartError(false);
    setFlavorSlots((prev) => {
      const next = [...prev];
      if (d === 1) { next[1] = null; next[2] = null; }
      if (d === 2) { next[2] = null; }
      return next;
    });
  };

  const handleSelectFlavor = (slotIndex: number, p: Pizza) => {
    if (isFixedFlavorCombination) return;
    if (!isPizzaFlavorCandidate(p, { allowSweet: division === 1, categoryFilters: flavorCategoryFilters })) return;

    setFlavorSlots((prev) => {
      const next = [...prev];
      next[slotIndex] = p;
      return next;
    });
    setActiveSlot(null);
    setCartError(false);
  };

  const handleSlotToggle = (i: number) => {
    if (isFixedFlavorCombination) return;
    setActiveSlot((prev) => (prev === i ? null : i));
    setCartError(false);
  };

  const updateImageZoomPosition = (event: PointerEvent<HTMLElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = Math.min(100, Math.max(0, ((event.clientX - rect.left) / rect.width) * 100));
    const y = Math.min(100, Math.max(0, ((event.clientY - rect.top) / rect.height) * 100));
    setImageZoomPosition({ x, y });
  };

  const openProductImageZoom = () => {
    setImageZoomPosition({ x: 50, y: 50 });
    setImageZoomScale(1.25);
    setImageZoomOpen(true);
  };

  const toggleProductImageZoom = () => {
    setImageZoomPosition({ x: 50, y: 50 });
    setImageZoomScale((value) => (value < 1.8 ? 2.15 : 1.25));
  };

  const handleAddToCart = () => {
    if (!product) return;
    if (optionsLoading || optionsError || quoteLoading || quoteError || !priceQuote) return;
    if (product.inventory_available === false) return;
    if (!isFixedFlavorCombination && isPizzaBrotoSelected && division > 1) {
      setDivision(1);
      setActiveSlot(null);
      setCartError(false);
      setFlavorSlots((prev) => [prev[0] ?? product, null, null]);
      return;
    }
    if (isNapolitanaCrustBlocked(selectedCrust?.name, effectiveDivision)) return;
    if (isPizza && !allFilled) {
      setCartError(true);
      return;
    }
    if (hasExplicitOptionGroups && !genericOptionsValid) return;

    let flavors: PizzaFlavor[];
    if (isFixedFlavorCombination) {
      flavors = [{ productId: product.id, name: product.name, price: getFlavorDisplayPrice(product), icon: product.icon }];
    } else if (isDrink) {
      // For drinks, the "flavor" is just the product itself at the computed price
      flavors = [{ productId: product.id, name: product.name, price: flavorPrice, icon: product.icon }];
    } else {
      // Use the size-adjusted price so backend validation passes with size-based pricing
      flavors = (activeFlavors as Pizza[]).map((p) => ({
        productId: p.id,
        name: p.name,
        price: getFlavorDisplayPrice(p),
        icon: p.icon,
      }));
    }

    const crustAddition = showCrustOptions && selectedCrust ? normalizeCrustPriceAddition(selectedCrust.price_addition, productPrice) : 0;
    const crustVariation: CartItemVariation | null = showCrustOptions && selectedCrust
      ? {
          id: selectedCrust.id,
          name: selectedCrust.name,
          priceAddition: crustAddition,
        }
      : null;

    addToCart(
      product,
      quantity,
      selectedSize,
      [],
      flavors,
      isDrink ? 1 : effectiveDivision,
      pricePerUnit,
      notes || undefined,
      crustVariation,
      selectedDrinkVariantId ? { id: selectedDrinkVariantId, name: product.drink_variants?.find((variant) => variant.id === selectedDrinkVariantId)?.name ?? "", priceAddition: product.drink_variants?.find((variant) => variant.id === selectedDrinkVariantId)?.price_addition ?? 0 } : null,
      selectedSizeObj?.id,
      showPromotions && priceQuote?.promotion_applied ? {
        applied: true,
        id: priceQuote.promotion_id,
        name: priceQuote.promotion_name,
        discount: priceQuote.discount_amount,
        freeShipping: priceQuote.free_shipping,
        giftEnabled: priceQuote.gift_enabled,
        giftProductId: priceQuote.gift_product_id,
        giftQuantity: priceQuote.gift_quantity,
        giftName: priceQuote.gift_name,
        giftIcon: priceQuote.gift_icon,
        blocksOtherCoupons: priceQuote.blocks_other_coupons,
      } : undefined,
      showBorderOptions && selectedBorder ? { id: selectedBorder.id, name: selectedBorder.name, priceAddition: borderAddition } : null,
      showProductOptions ? selectedOptionSelections : [],
    );
    if (!embedded) {
      trackEvent("add_to_cart", totalPrice, { product_id: product.id, quantity, selected_size: selectedSize });
      navigate("/cart");
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────────

  const divisionOptions = DIVISION_OPTIONS.filter(
    (opt) => opt.value <= Math.min(PUBLIC_MAX_FLAVORS, multiFlavorsConfig.maxFlavors ?? PUBLIC_MAX_FLAVORS)
  );

  const availableForSlot = (slotIndex: number) =>
    products.filter((p) => {
      if (slotIndex === 0) return p.id === product?.id;
      return p.inventory_available !== false && isPizzaFlavorCandidate(p, { allowSweet: division === 1, categoryFilters: flavorCategoryFilters }) && !flavorSlots.some((f, fi) => fi !== slotIndex && f?.id === p.id);
    });

  const productInventoryAvailable = !!product && product.inventory_available !== false;
  const canAddToCart = productInventoryAvailable && !optionGroupsLoading && !optionsLoading && !optionsError && !quoteLoading && !quoteError && !!priceQuote && (hasExplicitOptionGroups ? genericOptionsValid : (isDrink ? true : (allFilled && (!showCrustOptions || regularCrusts.length === 0 || selectedCrust !== null))));

  if (appLoading && !product) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-center">
          <Loader2 size={34} className="animate-spin text-gold" />
          <p className="text-cream text-base font-semibold">Carregando produto...</p>
        </div>
      </div>
    );
  }

  if (!product) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00 flex items-center justify-center px-6">
        <div className="text-center">
          <p className="text-cream text-xl font-bold">Produto não encontrado</p>
          <p className="text-stone text-sm mt-2">O item pode estar indisponível ou o cardápio ainda não foi atualizado.</p>
          <Link to="/" className="text-gold hover:text-gold-light mt-4 block font-semibold">Voltar ao início</Link>
        </div>
      </div>
    );
  }

  return (
    <div className={`${embedded ? "min-h-0" : "min-h-screen"} bg-gradient-to-br from-surface-01 to-surface-00`}>

      {/* Header */}
      <div className="bg-brand-dark px-4 py-3 flex justify-between items-center sticky top-0 z-30">
        <button type="button" onClick={() => embedded ? onBack?.() : navigate(-1)} aria-label={embedded ? "Voltar ao catálogo" : "Voltar"} className="text-parchment hover:text-cream transition-colors">
          <ChevronLeft size={24} />
        </button>
        {embedded ? <strong className="text-cream">Configurar produto</strong> : <button onClick={() => navigate("/")} aria-label="Ir para a home da loja">
          <MoschettieriLogo className="text-cream text-base scale-[1.31] origin-center" />
        </button>}
        <div className="w-6"></div>
      </div>

      {/* Content */}
      <div className="px-4 pt-6 pb-36 flex flex-col [&>*]:order-10">

        {/* ── Hero Product Image ───────────────────────────────────────────── */}
        <div className="flex flex-col items-center mb-6 order-0">
          <button
            type="button"
            onClick={openProductImageZoom}
            className="relative w-52 h-52 rounded-full bg-surface-02 border-4 border-surface-03 flex items-center justify-center text-8xl shadow-2xl shadow-black/40 transition-transform active:scale-95"
            aria-label="Ampliar imagem do produto"
          >
            <CategorySeal product={product} className="left-2 top-3" />
            <span className="absolute inset-0 z-0 rounded-full overflow-visible flex items-center justify-center">
              {isAssetUrl(product.icon)
                ? (
                  <img
                    src={resolveOptimizedAssetUrl(product.icon, 416)}
                    alt={product.name}
                    className="w-full h-full object-contain product-image-pulse-spin"
                    width={208}
                    height={208}
                    loading="eager"
                    decoding="async"
                    fetchPriority="high"
                  />
                )
                : (
                  <span>{product.icon || "🍕"}</span>
                )}
            </span>
            <span className="absolute bottom-4 right-4 z-30 h-9 w-9 rounded-full bg-surface-00/95 border border-surface-03 flex items-center justify-center text-gold shadow-lg">
              <ZoomIn size={17} />
            </span>
            <BestSellerSeal show={(product as any).show_best_seller_badge} />
          </button>
          <h1 className="text-cream text-2xl font-bold mt-4 text-center">{product.name}</h1>
          <div className="flex items-start gap-4 w-full mt-4">
            <p className="text-stone text-sm leading-relaxed flex-1">{product.description}</p>
            <div className="flex items-center gap-3 bg-surface-02 rounded-full px-4 py-2 flex-shrink-0 border border-surface-03">
              <button onClick={() => setQuantity(Math.max(1, quantity - 1))} className="text-parchment hover:text-cream transition-colors">
                <Minus size={16} />
              </button>
              <span className="text-cream font-bold w-5 text-center">{quantity}</span>
              <button onClick={() => setQuantity(quantity + 1)} className="text-gold hover:text-gold-light transition-colors">
                <Plus size={16} />
              </button>
            </div>
          </div>
        </div>

        {/* ── Pizza: Tipo de Massa ─────────────────────────────────────────── */}
        {showCrustOptions && regularCrusts.length > 0 && (
          <div className="mb-6 order-4">
            <h3 className="text-cream font-bold mb-3">Tipo de Massa</h3>
            <div className="flex gap-2 flex-wrap">
              {regularCrusts.map((crust) => {
                const effectiveAddition = normalizeCrustPriceAddition(crust.price_addition, product.price);
                const blockedByFlavorDivision = isNapolitanaCrustBlocked(crust.name, division);
                return (
                  <button
                    key={crust.id}
                    onClick={() => {
                      if (!blockedByFlavorDivision) {
                        setSelectedCrust(crust);
                        setSelectedBorder(null);
                      }
                    }}
                    disabled={blockedByFlavorDivision}
                    className={`flex-1 min-w-[80px] py-3 px-2 rounded-xl text-sm font-bold transition-all ${
                      selectedCrust?.id === crust.id
                        ? "bg-gold text-cream shadow-lg shadow-gold/30"
                        : blockedByFlavorDivision
                          ? "bg-surface-02/70 text-stone/60 border border-surface-03 cursor-not-allowed"
                        : "bg-surface-02 text-parchment hover:bg-surface-03 border border-surface-03"
                    }`}
                  >
                    <span className="block font-black text-xs">{crust.name}</span>
                    <span className={`block text-[10px] mt-0.5 ${selectedCrust?.id === crust.id ? "text-cream/80" : effectiveAddition > 0 ? "text-gold-light" : "opacity-70"}`}>
                      {formatCrustAddition(effectiveAddition)}
                    </span>
                  </button>
                );
              })}
            </div>
            {!isFixedFlavorCombination && effectiveDivision > 1 && regularCrusts.some((crust) => isNapolitanaCrust(crust.name)) && (
              <p className="text-stone/80 text-xs mt-2">Massa Napolitana indisponivel para pizzas com 2 ou 3 sabores.</p>
            )}
            {selectedCrust && (
              <p className="text-amber-400 text-xs mt-2">Massa {selectedCrust.name} selecionada - {formatCrustAddition(variantPriceAddition)}</p>
            )}
          </div>
        )}

        {/* ── Size Selector ───────────────────────────────────────────────── */}
        {(optionsLoading || optionsError || quoteError) && <div role="status" className="mb-4 rounded-xl bg-surface-02 p-4 text-sm text-amber-300">{optionsError || quoteError || "Carregando opcoes..."}{(optionsError || quoteError) && <button className="ml-3 underline" onClick={() => window.location.reload()}>Tentar novamente</button>}</div>}
         {hasExplicitOptionGroups && (
           <div className="order-2 space-y-5">
             {optionGroups.map((group) => {
               const state = selectedOptionState[group.id] ?? { selected: {}, text: "" };
               const selectedCount = group.selection_type === "quantity" ? Object.values(state.selected).reduce((sum, quantity) => sum + quantity, 0) : Object.keys(state.selected).length;
               return (
                 <section key={group.id} className="rounded-2xl border border-surface-03 bg-surface-02/60 p-4">
                   <div className="mb-3 flex items-start justify-between gap-3"><div><h3 className="font-bold text-cream">{group.name}{group.required ? " *" : ""}</h3><p className="text-xs text-stone">{group.selection_type === "single" ? "Escolha uma opcao" : group.selection_type === "multiple" ? "Escolha uma ou mais opcoes" : group.selection_type === "quantity" ? "Informe a quantidade" : "Digite uma observacao"}{group.max_selections ? ` · maximo ${group.max_selections}` : ""}</p></div>{group.selection_type !== "text" && <span className="text-xs text-stone">{selectedCount} selecionada(s)</span>}</div>
                   {group.selection_type === "text" ? (
                     <textarea value={state.text} onChange={(event) => setSelectedOptionState((current) => ({ ...current, [group.id]: { ...state, text: event.target.value } }))} rows={2} maxLength={300} className="w-full rounded-xl border border-surface-03 bg-surface-01 px-3 py-2 text-sm text-cream outline-none focus:border-gold" placeholder="Digite aqui" />
                   ) : (
                   <div className="space-y-2">{group.options.filter((option) => option.active).map((option) => { const currentQuantity = state.selected[option.id] ?? 0; const checked = currentQuantity > 0; return <div key={option.id} className="flex items-center gap-3 rounded-xl border border-surface-03 bg-surface-01 px-3 py-2">{group.selection_type === "quantity" ? <input type="number" min={0} max={group.max_selections || undefined} value={currentQuantity} onChange={(event) => setOptionSelection(group, option.id, Math.max(0, Number(event.target.value) || 0))} className="w-16 rounded-lg bg-surface-02 px-2 py-1 text-center text-sm text-cream" /> : <input type={group.selection_type === "single" ? "radio" : "checkbox"} name={`product-option-${group.id}`} checked={checked} onChange={() => { if (group.selection_type === "single") setSelectedOptionState((current) => ({ ...current, [group.id]: { ...state, selected: { [option.id]: 1 } } })); else setOptionSelection(group, option.id, checked ? 0 : 1); }} className="accent-gold" />}<span className="flex-1 text-sm text-parchment">{option.name}</span><span className="text-xs text-gold-light">{option.price_addition > 0 ? `+ R$ ${option.price_addition.toFixed(2)}` : ""}</span></div>; })}</div>
                   )}
                   {group.required && !genericOptionsValid && ((group.selection_type === "text" && !state.text.trim()) || (group.selection_type !== "text" && selectedCount < Math.max(1, group.min_selections || 0))) && <p className="mt-2 text-xs text-amber-300">Escolha uma opcao para continuar.</p>}
                 </section>
               );
             })}
           </div>
         )}
         {isDrink && (product.drink_variants ?? []).some((variant) => variant.active) && <label className="mb-6 block text-cream">Variante<select className="mt-2 block w-full rounded-xl bg-surface-02 p-3" value={selectedDrinkVariantId} onChange={(event) => setSelectedDrinkVariantId(event.target.value)}>{(product.drink_variants ?? []).filter((variant) => variant.active).map((variant) => <option key={variant.id} value={variant.id}>{variant.name}{variant.price_addition > 0 ? ` (+ R$ ${variant.price_addition.toFixed(2)})` : ""}</option>)}</select></label>}
         {!hasExplicitOptionGroups && showSizeOptions && (isPizza || productSizes.length > 0) && (
        <div className="mb-6 order-1">
          <h3 className="text-cream font-bold mb-3">
            {p.sizeLabel}
          </h3>
          <div className="flex gap-2 flex-wrap">
            {productSizes.length > 0 ? (
              productSizes.map((size) => (
                <button
                  key={size.id}
                  onClick={() => setSelectedSizeObj(size)}
                  className={`flex-1 min-w-[60px] py-3 rounded-xl text-sm font-bold transition-all ${
                    selectedSizeObj?.id === size.id
                      ? "bg-gold text-cream shadow-lg shadow-gold/30"
                      : "bg-surface-02 text-parchment hover:bg-surface-03 border border-surface-03"
                  }`}
                >
                  <span className="block font-black">{pizzaSizeLabel(size.label)}</span>
                  <span className="block text-[10px] opacity-70 font-normal">{pizzaSizeDescription(size.label, size.description)}</span>
                  <span className="block text-[10px] text-gold-light mt-0.5">R${size.price.toFixed(2)}</span>
                </button>
              ))
            ) : isPizza ? (
              PIZZA_SIZE_LABELS.map((size) => (
                <button
                  key={size}
                  onClick={() => setSelectedSizeFallback(size)}
                  className={`flex-1 py-3 rounded-xl text-sm font-bold transition-all ${
                    selectedSizeFallback === size
                      ? "bg-gold text-cream shadow-lg shadow-gold/30"
                      : "bg-surface-02 text-parchment hover:bg-surface-03 border border-surface-03"
                  }`}
                >
                  <span className="block font-black">{size}</span>
                  <span className="block text-[10px] opacity-70 font-normal">{pizzaSizeDescription(size)}</span>
                </button>
              ))
            ) : null}
          </div>
        </div>
        )}

        {/* ── Pizza: Division Selector ─────────────────────────────────────── */}
        {isPizza && !isFixedFlavorCombination && (
          <div className="mb-6 order-2">
            <h3 className="text-cream font-bold mb-3">{p.divisionLabel}</h3>
            <div className="flex gap-2">
              {divisionOptions.map(({ value, label, emoji }) => {
                const blockedBySize = isPizzaBrotoSelected && value > 1;
                return (
                  <button
                    key={value}
                    onClick={() => handleDivisionChange(value)}
                    disabled={blockedBySize}
                    className={`flex-1 py-3 rounded-xl text-xs font-bold transition-all ${
                      division === value
                        ? "bg-gold text-cream shadow-lg shadow-gold/30"
                        : blockedBySize
                          ? "bg-surface-02/70 text-stone/60 border border-surface-03 cursor-not-allowed"
                          : "bg-surface-02 text-parchment hover:bg-surface-03 border border-surface-03"
                    }`}
                  >
                    <span className="block text-base mb-0.5">{emoji}</span>
                    {label}
                    {blockedBySize && <span className="block text-[10px] font-normal mt-1">Somente Grande</span>}
                  </button>
                );
              })}
            </div>
            {isPizzaBrotoSelected && (
              <p className="text-stone/80 text-xs mt-2">Pizza Individual permite apenas 1 sabor.</p>
            )}
          </div>
        )}

        {/* ── Pizza: Flavor Slots ──────────────────────────────────────────── */}
        {isPizza && !isFixedFlavorCombination && (
          <div className="mb-6">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-cream font-bold">
                {division === 1 ? "Sabor da Pizza" : `Escolha os ${division} Sabores`}
              </h3>
              {cartError && (
                <span className="flex items-center gap-1 text-red-400 text-xs">
                  <AlertCircle size={12} />
                  Preencha todos os sabores
                </span>
              )}
            </div>

            <div className="space-y-3">
              {Array.from({ length: division }, (_, i) => {
                const flavor = flavorSlots[i];
                const isOpen = activeSlot === i;
                const slotLabel = division === 1 ? "Sabor único" : `Sabor ${i + 1} de ${division}`;

                return (
                  <div key={i}>
                    <button
                      onClick={() => handleSlotToggle(i)}
                      className={`w-full flex items-center gap-3 p-3 rounded-xl border transition-all ${
                        isOpen
                          ? "bg-surface-02 border-gold"
                          : flavor
                          ? "bg-surface-02 border-green-500/40"
                          : cartError
                          ? "bg-surface-02 border-red-500/60"
                          : "bg-surface-02 border-surface-03 hover:border-brand-mid"
                      }`}
                    >
                      <div className="w-12 h-12 rounded-full bg-surface-03 flex items-center justify-center text-2xl flex-shrink-0 overflow-hidden">
                        {isAssetUrl(flavor?.icon)
                          ? (
                            <img
                              src={resolveOptimizedAssetUrl(flavor?.icon, 96)}
                              alt=""
                              className="w-full h-full object-cover"
                              width={48}
                              height={48}
                              loading="lazy"
                              decoding="async"
                              fetchPriority="low"
                            />
                          )
                          : <span>{flavor?.icon ?? "?"}</span>}
                      </div>
                      <div className="flex-1 text-left">
                        <p className="text-stone text-xs">{slotLabel}</p>
                        <p className={`text-sm font-semibold ${flavor ? "text-cream" : "text-stone/70"}`}>
                          {flavor?.name ?? "Toque para escolher o sabor"}
                        </p>
                        {flavor && <p className="text-gold-light text-xs">R$ {getFlavorDisplayPrice(flavor).toFixed(2)}</p>}
                      </div>
                      <div className="flex-shrink-0">
                        {flavor ? (
                          <span className="flex items-center gap-1 text-xs text-green-400 bg-green-500/10 border border-green-500/30 px-2 py-1 rounded-full">
                            <Check size={11} />
                            {isOpen ? "Trocar" : "Ok"}
                          </span>
                        ) : (
                          <span className="text-xs text-gold-light bg-gold/10 border border-gold/30 px-2 py-1 rounded-full">Escolher</span>
                        )}
                      </div>
                    </button>

                    {isOpen && (
                      <div className="mt-2 bg-brand-dark rounded-xl p-3 border border-gold/30 animate-in slide-in-from-top-1">
                        <p className="text-stone text-xs mb-3">Selecione o sabor {i + 1}:</p>
                        <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                          {availableForSlot(i).map((p) => {
                            const isSelected = flavorSlots[i]?.id === p.id;
                            const displayPrice = getFlavorDisplayPrice(p);
                            return (
                              <button
                                key={p.id}
                                onClick={() => handleSelectFlavor(i, p)}
                                className={`w-full flex items-center gap-3 p-3 rounded-xl border text-left transition-all active:scale-[0.99] ${
                                  isSelected ? "bg-gold/20 border-gold shadow-sm" : "bg-surface-02 border-surface-03 hover:border-gold/40"
                                }`}
                              >
                                <div className="w-12 h-12 flex-shrink-0 flex items-center justify-center text-2xl overflow-hidden rounded-lg bg-surface-03">
                                  {isAssetUrl(p.icon)
                                    ? (
                                      <img
                                        src={resolveOptimizedAssetUrl(p.icon, 96)}
                                        alt=""
                                        className="w-full h-full object-cover"
                                        width={48}
                                        height={48}
                                        loading="lazy"
                                        decoding="async"
                                        fetchPriority="low"
                                      />
                                    )
                                    : <span>{p.icon || "🍕"}</span>}
                                </div>
                                <div className="min-w-0 flex-1">
                                  <p className="text-cream text-sm font-semibold leading-tight break-words">{p.name}</p>
                                  <p className="text-gold-light text-xs mt-1">R$ {displayPrice.toFixed(2)}</p>
                                </div>
                                {isSelected && (
                                  <span className="flex-shrink-0 text-[10px] bg-gold text-cream px-2 py-1 rounded-full">
                                    Selecionado
                                  </span>
                                )}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {effectiveDivision > 1 && activeFlavors.some((f) => f !== null) && (
              <div className="mt-3 p-3 rounded-xl bg-surface-02/60 border border-surface-03">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-stone">
                    {allFilled ? `${effectiveDivision === 2 ? "Meio a Meio" : "3 Sabores"}` : "Preço parcial"}
                  </span>
                  <span className="text-gold-light font-bold">R$ {flavorPrice.toFixed(2)}</span>
                </div>
                <div className="flex gap-1 mt-2 flex-wrap">
                  {activeFlavors.map((f, i) =>
                    f ? (
                      <span key={i} className="inline-flex items-center gap-1 text-xs bg-surface-03 text-parchment px-2 py-0.5 rounded-full">
                        {isAssetUrl(f.icon)
                          ? (
                            <img
                              src={resolveOptimizedAssetUrl(f.icon, 64)}
                              alt=""
                              className="w-4 h-4 rounded-full object-cover flex-shrink-0"
                              width={16}
                              height={16}
                              loading="lazy"
                              decoding="async"
                              fetchPriority="low"
                            />
                          )
                          : <span>{f.icon}</span>}
                        {f.name} — R${getFlavorDisplayPrice(f).toFixed(2)}
                      </span>
                    ) : (
                      <span key={i} className="text-xs bg-surface-03/50 text-stone/70 px-2 py-0.5 rounded-full border border-dashed border-brand-mid">
                        Sabor {i + 1} — ?
                      </span>
                    )
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Pizza: Borda (após divisão e sabores) ────────────────────────── */}
        {showBorderOptions && borderCrusts.length > 0 && (
          <div className="mb-6">
            <h3 className="text-cream font-bold mb-3">Borda</h3>
            {borderAvailable ? (
              <select
                aria-label="Selecionar borda"
                value={selectedBorder?.id ?? ""}
                onChange={(event) => setSelectedBorder(borderCrusts.find((border) => border.id === event.target.value) ?? null)}
                className="w-full rounded-xl bg-surface-02 border border-surface-03 px-4 py-3 text-cream font-semibold"
              >
                <option value="">Sem borda</option>
                {borderCrusts.map((border) => (
                  <option key={border.id} value={border.id}>
                    {border.name}{border.price_addition > 0 ? ` (+ R$ ${border.price_addition.toFixed(2)})` : ""}
                  </option>
                ))}
              </select>
            ) : (
              <p className="text-stone text-sm bg-surface-02 rounded-xl px-4 py-3 border border-surface-03">
                Borda disponível apenas com Massa Tradicional
              </p>
            )}
          </div>
        )}

        {/* ── Observações ─────────────────────────────────────────────────── */}
        {!isDrink && (
        <div className="mb-6">
          <h3 className="text-cream font-bold mb-3">Observações</h3>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Ex: sem cebola, ponto da massa, alergias..."
            rows={3}
            className="w-full bg-surface-02 border border-surface-03 focus:border-gold rounded-xl px-4 py-3 text-cream placeholder-stone/70 outline-none text-sm resize-none transition-colors"
            maxLength={200}
          />
          <p className="text-stone/60 text-xs mt-1 text-right">{notes.length}/200</p>
        </div>
        )}

        {/* ── Pizza Diagram ───────────────────────────────────────────────── */}
        {!productInventoryAvailable && (
          <div className="mb-5 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-center">
            <p className="text-sm font-bold text-amber-300">{product.inventory_unavailable_message || "Indisponivel no momento."}</p>
          </div>
        )}

        {isPizza && !isFixedFlavorCombination && effectiveDivision > 1 && (
          <div className="flex flex-col items-center mb-6 p-4 bg-surface-02/50 rounded-2xl border border-surface-03">
            <PizzaDiagram division={effectiveDivision} slots={flavorSlots} />
            <p className="text-stone/70 text-xs mt-2">
              💰 {PRICING_LABELS[effectivePricingRule]}
            </p>
          </div>
        )}
      </div>

      {/* ── Bottom Fixed Bar ────────────────────────────────────────────────── */}
      {imageZoomOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/95 flex flex-col items-center justify-center gap-5 p-6"
          onClick={() => setImageZoomOpen(false)}
        >
          {/* Close */}
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); setImageZoomOpen(false); }}
            className="absolute top-5 right-5 h-11 w-11 rounded-full bg-surface-00 border border-surface-03 text-cream flex items-center justify-center shadow-lg"
            aria-label="Fechar zoom"
          >
            <X size={20} />
          </button>

          {/* Product name */}
          <p className="text-cream text-base font-bold text-center select-none">{product.name}</p>

          {/* Image container — rect, object-contain, full pizza visible */}
          <div
            className="relative overflow-hidden rounded-2xl bg-surface-01 border border-surface-03/60 shadow-2xl shadow-black/60 flex items-center justify-center"
            style={{ width: "min(94vw, 640px)", height: "min(94vw, 640px)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <CategorySeal product={product} className="left-4 top-4" />
            {isAssetUrl(product.icon) ? (
              <img
                src={resolveOptimizedAssetUrl(product.icon, 1280)}
                alt={product.name}
                className="w-full h-full object-contain transition-transform duration-200 select-none"
                width={640}
                height={640}
                loading="lazy"
                decoding="async"
                fetchPriority="low"
                draggable={false}
                onPointerDown={updateImageZoomPosition}
                onPointerMove={updateImageZoomPosition}
                style={{
                  transform: `scale(${imageZoomScale})`,
                  transformOrigin: `${imageZoomPosition.x}% ${imageZoomPosition.y}%`,
                  cursor: imageZoomScale > 1 ? "grab" : "zoom-in",
                  willChange: "transform",
                  imageRendering: "high-quality" as React.CSSProperties["imageRendering"],
                }}
              />
            ) : (
              <span
                className="text-[9rem] transition-transform duration-200 select-none"
                onPointerDown={updateImageZoomPosition}
                onPointerMove={updateImageZoomPosition}
                style={{
                  transform: `scale(${imageZoomScale})`,
                  transformOrigin: `${imageZoomPosition.x}% ${imageZoomPosition.y}%`,
                }}
              >
                {product.icon || "🍕"}
              </span>
            )}
          </div>

          {/* Zoom controls */}
          <div
            className="flex items-center gap-3 rounded-full bg-surface-00 border border-surface-03 px-4 py-3 shadow-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              onClick={() => setImageZoomScale((v) => Math.max(1, Number((v - 0.25).toFixed(2))))}
              className="h-10 w-10 rounded-full bg-surface-03 text-parchment flex items-center justify-center disabled:opacity-40"
              disabled={imageZoomScale <= 1}
              aria-label="Diminuir zoom"
            >
              <Minus size={17} />
            </button>
            <span className="text-cream text-sm font-bold w-14 text-center">{Math.round(imageZoomScale * 100)}%</span>
            <button
              type="button"
              onClick={() => setImageZoomScale((v) => Math.min(4, Number((v + 0.25).toFixed(2))))}
              className="h-10 w-10 rounded-full bg-gold text-cream flex items-center justify-center disabled:opacity-40"
              disabled={imageZoomScale >= 4}
              aria-label="Aumentar zoom"
            >
              <Plus size={17} />
            </button>
          </div>

          <p className="text-stone/60 text-[11px] text-center -mt-2 select-none">
            Toque na imagem e arraste para explorar os detalhes
          </p>
        </div>
      )}

      <div className={`${embedded ? "sticky bottom-0 z-30" : "fixed bottom-0 left-0 right-0"} bg-surface-00 border-t border-surface-03 px-4 py-4 shadow-[0_-18px_40px_rgba(0,0,0,0.45)]`}>
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-stone text-xs">Total ({quantity}x)</p>
            <div className="flex items-end gap-2">
              <p className="text-gold text-2xl font-bold">R$ {totalPrice.toFixed(2)}</p>
              {showPromotions && priceQuote?.promotion_applied && (
                <p className="text-stone text-xs line-through mb-1">R$ {(priceQuote.standard_price * quantity).toFixed(2)}</p>
              )}
            </div>
            {showPromotions && priceQuote?.promotion_applied && (
              <p className="text-emerald-300 text-[11px] font-semibold mt-0.5">{priceQuote.promotion_name} aplicada</p>
            )}
            {showPromotions && priceQuote?.promotion_blocked && priceQuote.promotion_block_reason && (
              <p className="text-amber-300 text-[11px] font-semibold mt-0.5">{priceQuote.promotion_block_reason}.</p>
            )}
          </div>
          <div className="text-right">
            {isPizza && !isFixedFlavorCombination && effectiveDivision > 1 && allFilled && (
              <p className="text-stone text-xs">
                {effectiveDivision === 2 ? "Meio a Meio" : "3 Sabores"} · {selectedSize}
              </p>
            )}
            {showCrustOptions && selectedCrust && (
              <p className="text-stone text-xs">Massa: {selectedCrust.name}</p>
            )}
          </div>
        </div>
        <button
          onClick={handleAddToCart}
          disabled={!canAddToCart}
          className={`w-full font-bold py-3.5 px-4 rounded-full text-center transition-all text-base active:scale-95 ${
            canAddToCart
              ? "bg-gold hover:bg-gold/90 text-cream shadow-lg shadow-gold/30"
              : "bg-surface-03 text-stone/70 cursor-not-allowed"
          }`}
        >
          {canAddToCart
            ? `${embedded ? "Adicionar ao pedido" : p.addToCartButton} · R$ ${totalPrice.toFixed(2)}`
            : !productInventoryAvailable
            ? "Indisponivel no momento"
            : optionGroupsLoading || optionsLoading || quoteLoading ? "Confirmando opcoes e preco..."
            : optionsError || quoteError ? "Preco indisponivel - tente novamente"
            : hasExplicitOptionGroups ? "Preencha as opcoes obrigatorias"
            : `Escolha ${activeFlavors.filter((f) => !f).length} sabor(es) restante(s)`}
        </button>
      </div>
    </div>
  );
}
