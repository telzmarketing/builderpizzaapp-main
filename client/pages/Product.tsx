import { useState, useMemo, useEffect } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { ChevronLeft, Star, Minus, Plus, AlertCircle, Check } from "lucide-react";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import { useApp, Pizza, PizzaFlavor, FlavorDivision, PricingRule, CartItemVariation } from "@/context/AppContext";
import { sizesApi, crustApi, drinkVariantApi, ApiProductSize, ApiProductCrustType, ApiProductDrinkVariant, isAssetUrl, resolveAssetUrl } from "@/lib/api";
import { isAllowedPizzaSize, pizzaSizeDescription, pizzaSizeLabel, PIZZA_SIZE_LABELS } from "@/lib/pizzaSizes";
import { formatCrustAddition, normalizeCrustPriceAddition } from "@/lib/pricing";
import { trackEvent } from "@/lib/tracking";

// ─── Add-ons ──────────────────────────────────────────────────────────────────

// ─── Helpers ──────────────────────────────────────────────────────────────────

const DIVISION_OPTIONS: { value: FlavorDivision; label: string; emoji: string }[] = [
  { value: 1, label: "Inteira", emoji: "🍕" },
  { value: 2, label: "Meio a Meio", emoji: "½" },
  { value: 3, label: "3 Sabores", emoji: "⅓" },
];

const PRICING_LABELS: Record<PricingRule, string> = {
  most_expensive: "Preço do sabor mais caro",
  average: "Preço médio dos sabores",
  proportional: "Preço proporcional a cada parte",
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
    return <image href={resolveAssetUrl(icon)} x={x - size / 2} y={y - size / 2} width={size} height={size} />;
  }
  return <text x={x} y={y} textAnchor="middle" dominantBaseline="middle" fontSize={size}>{icon}</text>;
}

function PizzaDiagram({ division, slots }: { division: FlavorDivision; slots: (Pizza | null)[] }) {
  const S = 176;
  const cx = S / 2, cy = S / 2, r = S / 2 - 6;
  const filled = ["#f97316", "#ea580c", "#c2410c"];
  const empty = ["#1e293b", "#334155", "#475569"];
  const borderColor = "#0f172a";

  if (division === 1) {
    return (
      <svg width={S} height={S} viewBox={`0 0 ${S} ${S}`}>
        <circle cx={cx} cy={cy} r={r} fill={slots[0] ? filled[0] : empty[0]} />
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={borderColor} strokeWidth="4" />
        <SvgIcon icon={slots[0]?.icon} x={cx} y={cy} size={60} />
      </svg>
    );
  }

  if (division === 2) {
    return (
      <svg width={S} height={S} viewBox={`0 0 ${S} ${S}`}>
        <defs>
          <clipPath id="left-half"><rect x="0" y="0" width={cx} height={S} /></clipPath>
          <clipPath id="right-half"><rect x={cx} y="0" width={cx} height={S} /></clipPath>
        </defs>
        <circle cx={cx} cy={cy} r={r} fill={slots[0] ? filled[0] : empty[0]} clipPath="url(#left-half)" />
        <circle cx={cx} cy={cy} r={r} fill={slots[1] ? filled[1] : empty[1]} clipPath="url(#right-half)" />
        <line x1={cx} y1={cy - r} x2={cx} y2={cy + r} stroke={borderColor} strokeWidth="4" />
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={borderColor} strokeWidth="4" />
        <SvgIcon icon={slots[0]?.icon} x={cx / 2} y={cy} size={38} />
        <SvgIcon icon={slots[1]?.icon} x={cx + cx / 2} y={cy} size={38} />
      </svg>
    );
  }

  const toRad = (d: number) => (d * Math.PI) / 180;
  const sectorPath = (start: number, end: number) => {
    const x1 = cx + r * Math.cos(toRad(start));
    const y1 = cy + r * Math.sin(toRad(start));
    const x2 = cx + r * Math.cos(toRad(end));
    const y2 = cy + r * Math.sin(toRad(end));
    return `M ${cx} ${cy} L ${x1.toFixed(2)} ${y1.toFixed(2)} A ${r} ${r} 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)} Z`;
  };
  const sectors = [{ start: -90, end: 30 }, { start: 30, end: 150 }, { start: 150, end: 270 }];
  const divLines = [-90, 30, 150];
  const iconAt = (midDeg: number, dist = r * 0.58) => ({
    x: cx + dist * Math.cos(toRad(midDeg)),
    y: cy + dist * Math.sin(toRad(midDeg)),
  });

  return (
    <svg width={S} height={S} viewBox={`0 0 ${S} ${S}`}>
      {sectors.map((s, i) => (
        <path key={i} d={sectorPath(s.start, s.end)} fill={slots[i] ? filled[i] : empty[i]} />
      ))}
      {divLines.map((deg, i) => (
        <line key={i} x1={cx} y1={cy} x2={cx + r * Math.cos(toRad(deg))} y2={cy + r * Math.sin(toRad(deg))} stroke={borderColor} strokeWidth="4" />
      ))}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={borderColor} strokeWidth="4" />
      {sectors.map((s, i) => {
        const mid = (s.start + s.end) / 2;
        const pos = iconAt(mid);
        return <SvgIcon key={i} icon={slots[i]?.icon} x={parseFloat(pos.x.toFixed(2))} y={parseFloat(pos.y.toFixed(2))} size={30} />;
      })}
    </svg>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function Product() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { products, addToCart, multiFlavorsConfig, siteContent } = useApp();
  const p = siteContent.pages.product;

  const product = products.find((p) => p.id === id);

  // Product type flags
  const productType = (product as any)?.product_type as string | null | undefined;
  const isPizza = !productType || productType === "pizza";
  const isDrink = productType === "drink";

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

  // Drink variants (drink only)
  const [productDrinkVariants, setProductDrinkVariants] = useState<ApiProductDrinkVariant[]>([]);
  const [selectedDrinkVariant, setSelectedDrinkVariant] = useState<ApiProductDrinkVariant | null>(null);

  useEffect(() => {
    if (!product) return;

    // Load sizes for all product types
    sizesApi.list(product.id).then((sizes) => {
      const activeSizes = sizes.filter((s) => s.active && (!isPizza || isAllowedPizzaSize(s.label)));
      setProductSizes(activeSizes);
      if (activeSizes.length > 0) {
        const def = activeSizes.find((s) => s.is_default) ?? activeSizes[0];
        setSelectedSizeObj(def);
      } else {
        setSelectedSizeObj(null);
        setSelectedSizeFallback(isPizza ? "Pizza Grande" : "");
      }
    }).catch(() => {
      setProductSizes([]);
      setSelectedSizeObj(null);
      setSelectedSizeFallback(isPizza ? "Pizza Grande" : "");
    });

    // Load crust types for pizza
    if (isPizza) {
      crustApi.list(product.id).then((crusts) => {
        const activeCrusts = crusts.filter((c) => c.active);
        setProductCrusts(activeCrusts);
        // Don't auto-select — make it an explicit choice
      }).catch(() => setProductCrusts([]));
    }

    // Load drink variants for drinks
    if (isDrink) {
      drinkVariantApi.list(product.id).then((variants) => {
        const activeVariants = variants.filter((v) => v.active);
        setProductDrinkVariants(activeVariants);
        if (activeVariants.length > 0) {
          setSelectedDrinkVariant(activeVariants[0]);
        }
      }).catch(() => setProductDrinkVariants([]));
    }
  }, [product?.id, isPizza, isDrink]);

  const selectedSize = selectedSizeObj ? selectedSizeObj.label : selectedSizeFallback;

  if (!product) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00 flex items-center justify-center">
        <div className="text-center">
          <p className="text-cream text-xl">Produto não encontrado</p>
          <Link to="/" className="text-gold hover:text-gold-light mt-4 block">Voltar ao início</Link>
        </div>
      </div>
    );
  }

  // ── Computed values ──────────────────────────────────────────────────────────

  const activeFlavors = flavorSlots.slice(0, division);
  const allFilled = activeFlavors.every((f) => f !== null);

  const flavorPrice = useMemo(() => {
    if (isDrink) {
      // For drinks: price is the size price or product base price
      return selectedSizeObj?.price ?? product.price;
    }
    if (productSizes.length > 0 && selectedSizeObj) {
      const slotsWithSizePrice = activeFlavors.map((f) =>
        f ? { ...f, price: selectedSizeObj.price } : null
      );
      return computeFlavorPrice(slotsWithSizePrice as (Pizza | null)[], division, multiFlavorsConfig.pricingRule);
    }
    return computeFlavorPrice(activeFlavors, division, multiFlavorsConfig.pricingRule);
  }, [activeFlavors, division, multiFlavorsConfig.pricingRule, productSizes, selectedSizeObj, isDrink, product.price]);

  const variantPriceAddition = useMemo(() => {
    if (isPizza && selectedCrust) return normalizeCrustPriceAddition(selectedCrust.price_addition, product.price);
    if (isDrink && selectedDrinkVariant) return selectedDrinkVariant.price_addition;
    return 0;
  }, [isPizza, isDrink, selectedCrust, selectedDrinkVariant, product.price]);

  const pricePerUnit = flavorPrice + variantPriceAddition;
  const totalPrice = pricePerUnit * quantity;

  // ── Handlers ─────────────────────────────────────────────────────────────────

  const handleDivisionChange = (d: FlavorDivision) => {
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
    setFlavorSlots((prev) => {
      const next = [...prev];
      next[slotIndex] = p;
      return next;
    });
    setActiveSlot(null);
    setCartError(false);
  };

  const handleSlotToggle = (i: number) => {
    setActiveSlot((prev) => (prev === i ? null : i));
    setCartError(false);
  };

  const handleAddToCart = () => {
    if (isPizza && !allFilled) {
      setCartError(true);
      return;
    }

    let flavors: PizzaFlavor[];
    if (isDrink) {
      // For drinks, the "flavor" is just the product itself at the computed price
      flavors = [{ productId: product.id, name: product.name, price: flavorPrice, icon: product.icon }];
    } else {
      // Use the size-adjusted price so backend validation passes with size-based pricing
      const priceForFlavor = selectedSizeObj?.price ?? product.price;
      flavors = (activeFlavors as Pizza[]).map((p) => ({
        productId: p.id,
        name: p.name,
        price: priceForFlavor,
        icon: p.icon,
      }));
    }

    const crustVariation: CartItemVariation | null = selectedCrust
      ? { id: selectedCrust.id, name: selectedCrust.name, priceAddition: normalizeCrustPriceAddition(selectedCrust.price_addition, product.price) }
      : null;

    const drinkVariation: CartItemVariation | null = selectedDrinkVariant
      ? { id: selectedDrinkVariant.id, name: selectedDrinkVariant.name, priceAddition: selectedDrinkVariant.price_addition }
      : null;

    addToCart(
      flavorSlots[0]!,
      quantity,
      selectedSize,
      [],
      flavors,
      isDrink ? 1 : division,
      pricePerUnit,
      notes || undefined,
      crustVariation,
      drinkVariation,
      selectedSizeObj?.id,
    );
    trackEvent("add_to_cart", totalPrice, { product_id: product.id, quantity, selected_size: selectedSize });
    navigate("/cart");
  };

  // ── Render ───────────────────────────────────────────────────────────────────

  const divisionOptions = DIVISION_OPTIONS.filter(
    (opt) => opt.value <= multiFlavorsConfig.maxFlavors || opt.value === 1
  );

  const availableForSlot = (slotIndex: number) =>
    products.filter((p) => !flavorSlots.some((f, fi) => fi !== slotIndex && f?.id === p.id));

  const canAddToCart = isDrink ? true : allFilled;

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00">

      {/* Header */}
      <div className="bg-brand-dark px-4 py-3 flex justify-between items-center sticky top-0 z-30">
        <button onClick={() => navigate(-1)} className="text-parchment hover:text-cream transition-colors">
          <ChevronLeft size={24} />
        </button>
        <MoschettieriLogo className="text-cream text-base scale-[1.14] origin-center" />
        <div className="w-6"></div>
      </div>

      {/* Content */}
      <div className="px-4 pt-6 pb-36">

        {/* ── Hero Product Image ───────────────────────────────────────────── */}
        <div className="flex flex-col items-center mb-6">
          <div className="w-52 h-52 rounded-full bg-surface-02 border-4 border-surface-03 flex items-center justify-center text-8xl shadow-2xl shadow-black/40 overflow-hidden">
            {isAssetUrl(product.icon)
              ? <img src={resolveAssetUrl(product.icon)} alt={product.name} className="w-full h-full object-cover" />
              : <span>{product.icon || "🍕"}</span>}
          </div>
          <h1 className="text-cream text-2xl font-bold mt-4 text-center">{product.name}</h1>
          <div className="flex gap-1 mt-2">
            {[...Array(5)].map((_, i) => (
              <Star key={i} size={16} className={i < Math.floor(product.rating || 4) ? "fill-yellow-400 text-yellow-400" : "text-slate-600"} />
            ))}
          </div>
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

        {/* ── Pizza: Division Selector ─────────────────────────────────────── */}
        {false && isPizza && (
          <div className="hidden">
            <h3 className="text-cream font-bold mb-3">{p.divisionLabel}</h3>
            <div className="flex gap-2">
              {divisionOptions.map(({ value, label, emoji }) => (
                <button
                  key={value}
                  onClick={() => handleDivisionChange(value)}
                  className={`flex-1 py-3 rounded-xl text-xs font-bold transition-all ${
                    division === value
                      ? "bg-gold text-cream shadow-lg shadow-gold/30"
                      : "bg-surface-02 text-parchment hover:bg-surface-03 border border-surface-03"
                  }`}
                >
                  <span className="block text-base mb-0.5">{emoji}</span>
                  {label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── Pizza: Flavor Slots ──────────────────────────────────────────── */}
        {false && isPizza && (
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
                          ? <img src={resolveAssetUrl(flavor?.icon)} alt="" className="w-full h-full object-cover" />
                          : <span>{flavor?.icon ?? "?"}</span>}
                      </div>
                      <div className="flex-1 text-left">
                        <p className="text-stone text-xs">{slotLabel}</p>
                        <p className={`text-sm font-semibold ${flavor ? "text-cream" : "text-stone/70"}`}>
                          {flavor?.name ?? "Toque para escolher o sabor"}
                        </p>
                        {flavor && <p className="text-gold-light text-xs">R$ {flavor.price.toFixed(2)}</p>}
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
                        <div className="grid grid-cols-3 gap-2">
                          {availableForSlot(i).map((p) => {
                            const isSelected = flavorSlots[i]?.id === p.id;
                            return (
                              <button
                                key={p.id}
                                onClick={() => handleSelectFlavor(i, p)}
                                className={`p-2.5 rounded-xl border text-center transition-all active:scale-95 ${
                                  isSelected ? "bg-gold/20 border-gold shadow-sm" : "bg-surface-02 border-surface-03 hover:border-gold/40"
                                }`}
                              >
                                <div className="w-10 h-10 mx-auto mb-1 flex items-center justify-center text-2xl overflow-hidden rounded-lg">
                                  {isAssetUrl(p.icon)
                                    ? <img src={resolveAssetUrl(p.icon)} alt="" className="w-full h-full object-cover" />
                                    : <span>{p.icon || "🍕"}</span>}
                                </div>
                                <p className="text-cream text-xs font-medium leading-tight line-clamp-1">{p.name}</p>
                                <p className="text-gold-light text-xs mt-0.5">R${p.price.toFixed(2)}</p>
                                {isSelected && <span className="inline-block mt-1 text-[10px] bg-gold text-cream px-1.5 py-0.5 rounded-full">✓ Selecionado</span>}
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

            {division > 1 && activeFlavors.some((f) => f !== null) && (
              <div className="mt-3 p-3 rounded-xl bg-surface-02/60 border border-surface-03">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-stone">
                    {allFilled ? `${division === 2 ? "Meio a Meio" : "3 Sabores"}` : "Preço parcial"}
                  </span>
                  <span className="text-gold-light font-bold">R$ {flavorPrice.toFixed(2)}</span>
                </div>
                <div className="flex gap-1 mt-2 flex-wrap">
                  {activeFlavors.map((f, i) =>
                    f ? (
                      <span key={i} className="inline-flex items-center gap-1 text-xs bg-surface-03 text-parchment px-2 py-0.5 rounded-full">
                        {isAssetUrl(f.icon)
                          ? <img src={resolveAssetUrl(f.icon)} alt="" className="w-4 h-4 rounded-full object-cover flex-shrink-0" />
                          : <span>{f.icon}</span>}
                        {f.name} — R${f.price.toFixed(2)}
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

        {/* ── Size Selector ───────────────────────────────────────────────── */}
        <div className="mb-6">
          <h3 className="text-cream font-bold mb-3">
            {isDrink ? "Tamanho da Bebida" : p.sizeLabel}
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
            ) : !isDrink ? (
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
            ) : (
              <p className="text-stone text-sm py-2">Nenhum tamanho configurado.</p>
            )}
          </div>
        </div>

        {/* ── Pizza: Tipo de Massa ─────────────────────────────────────────── */}
        {isPizza && productCrusts.length > 0 && (
          <div className="mb-6">
            <h3 className="text-cream font-bold mb-3">Tipo de Massa</h3>
            <div className="flex gap-2 flex-wrap">
              {productCrusts.map((crust) => {
                const effectiveAddition = normalizeCrustPriceAddition(crust.price_addition, product.price);
                return (
                <button
                  key={crust.id}
                  onClick={() => setSelectedCrust(prev => prev?.id === crust.id ? null : crust)}
                  className={`flex-1 min-w-[80px] py-3 px-2 rounded-xl text-sm font-bold transition-all ${
                    selectedCrust?.id === crust.id
                      ? "bg-amber-500 text-white shadow-lg shadow-amber-500/20"
                      : "bg-surface-02 text-parchment hover:bg-surface-03 border border-surface-03"
                  }`}
                >
                  <span className="block font-black text-xs">{crust.name}</span>
                  <span className={`block text-[10px] mt-0.5 ${selectedCrust?.id === crust.id ? "text-white/80" : effectiveAddition > 0 ? "text-amber-400" : "opacity-70"}`}>
                    {formatCrustAddition(effectiveAddition)}
                  </span>
                </button>
                );
              })}
            </div>
            {selectedCrust && (
              <p className="text-amber-400 text-xs mt-2">Massa {selectedCrust.name} selecionada - {formatCrustAddition(variantPriceAddition)}</p>
            )}
          </div>
        )}

        {/* ── Drink: Tipo da Bebida ────────────────────────────────────────── */}
        {isDrink && productDrinkVariants.length > 1 && (
          <div className="mb-6">
            <h3 className="text-cream font-bold mb-3">Tipo da Bebida</h3>
            <div className="flex gap-2 flex-wrap">
              {productDrinkVariants.map((variant) => (
                <button
                  key={variant.id}
                  onClick={() => setSelectedDrinkVariant(variant)}
                  className={`flex-1 min-w-[80px] py-3 px-2 rounded-xl text-sm font-bold transition-all ${
                    selectedDrinkVariant?.id === variant.id
                      ? "bg-blue-500 text-white shadow-lg shadow-blue-500/20"
                      : "bg-surface-02 text-parchment hover:bg-surface-03 border border-surface-03"
                  }`}
                >
                  <span className="block font-black text-xs">{variant.name}</span>
                  {variant.price_addition > 0 ? (
                    <span className={`block text-[10px] mt-0.5 ${selectedDrinkVariant?.id === variant.id ? "text-white/80" : "text-blue-400"}`}>
                      +R${variant.price_addition.toFixed(2)}
                    </span>
                  ) : (
                    <span className="block text-[10px] mt-0.5 opacity-60">Mesmo preço</span>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── Observações ─────────────────────────────────────────────────── */}
        <div className="mb-6">
          <h3 className="text-cream font-bold mb-3">Observações</h3>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder={isDrink ? "Ex: gelada, sem gelo..." : "Ex: sem cebola, ponto da massa, alergias..."}
            rows={3}
            className="w-full bg-surface-02 border border-surface-03 focus:border-gold rounded-xl px-4 py-3 text-cream placeholder-stone/70 outline-none text-sm resize-none transition-colors"
            maxLength={200}
          />
          <p className="text-stone/60 text-xs mt-1 text-right">{notes.length}/200</p>
        </div>

        {/* ── Pizza Diagram ───────────────────────────────────────────────── */}
        {isPizza && division > 1 && (
          <div className="flex flex-col items-center mb-6 p-4 bg-surface-02/50 rounded-2xl border border-surface-03">
            <PizzaDiagram division={division} slots={flavorSlots} />
            <p className="text-stone/70 text-xs mt-2">
              💰 {PRICING_LABELS[multiFlavorsConfig.pricingRule]}
            </p>
          </div>
        )}
      </div>

      {/* ── Bottom Fixed Bar ────────────────────────────────────────────────── */}
      <div className="fixed bottom-0 left-0 right-0 bg-surface-00/95 border-t border-surface-02 px-4 py-4 backdrop-blur-sm">
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-stone text-xs">Total ({quantity}x)</p>
            <p className="text-gold text-2xl font-bold">R$ {totalPrice.toFixed(2)}</p>
          </div>
          <div className="text-right">
            {isPizza && division > 1 && allFilled && (
              <p className="text-stone text-xs">
                {division === 2 ? "Meio a Meio" : "3 Sabores"} · {selectedSize}
              </p>
            )}
            {selectedCrust && (
              <p className="text-stone text-xs">Massa: {selectedCrust.name}</p>
            )}
            {selectedDrinkVariant && productDrinkVariants.length > 1 && (
              <p className="text-stone text-xs">Tipo: {selectedDrinkVariant.name}</p>
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
            ? `${p.addToCartButton} · R$ ${totalPrice.toFixed(2)}`
            : `Escolha ${activeFlavors.filter((f) => !f).length} sabor(es) restante(s)`}
        </button>
      </div>
    </div>
  );
}
