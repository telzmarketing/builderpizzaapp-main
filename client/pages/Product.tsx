import { useState, useMemo } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { ChevronLeft, Star, Minus, Plus, AlertCircle, Check } from "lucide-react";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import { useApp, Pizza, PizzaFlavor, FlavorDivision, PricingRule } from "@/context/AppContext";

// ─── Add-ons ──────────────────────────────────────────────────────────────────

interface AddOn { id: string; name: string; price: number; icon: string; }
const addOns: AddOn[] = [
  { id: "1", name: "Pimenta", price: 0.5, icon: "🌶️" },
  { id: "2", name: "Cogumelo", price: 1.0, icon: "🍄" },
  { id: "3", name: "Abacaxi", price: 1.5, icon: "🍍" },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

const SIZES = ["P", "M", "G", "GG"];
const SIZE_LABELS: Record<string, string> = { P: "Pequena", M: "Média", G: "Grande", GG: "Gigante" };

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
  // proportional
  return filled.reduce((s, f) => s + f.price / division, 0);
}

// ─── SVG Pizza Diagram ────────────────────────────────────────────────────────

function SvgIcon({ icon, x, y, size }: { icon: string | undefined; x: number; y: number; size: number }) {
  if (!icon) return <text x={x} y={y} textAnchor="middle" dominantBaseline="middle" fontSize={size}>?</text>;
  if (icon.startsWith("data:") || icon.startsWith("http")) {
    return <image href={icon} x={x - size / 2} y={y - size / 2} width={size} height={size} />;
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

  // 3 sectors — 120° each, starting at top (-90°)
  const toRad = (d: number) => (d * Math.PI) / 180;
  const sectorPath = (start: number, end: number) => {
    const x1 = cx + r * Math.cos(toRad(start));
    const y1 = cy + r * Math.sin(toRad(start));
    const x2 = cx + r * Math.cos(toRad(end));
    const y2 = cy + r * Math.sin(toRad(end));
    return `M ${cx} ${cy} L ${x1.toFixed(2)} ${y1.toFixed(2)} A ${r} ${r} 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)} Z`;
  };
  const sectors = [
    { start: -90, end: 30 },
    { start: 30, end: 150 },
    { start: 150, end: 270 },
  ];
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
        <line
          key={i}
          x1={cx} y1={cy}
          x2={cx + r * Math.cos(toRad(deg))}
          y2={cy + r * Math.sin(toRad(deg))}
          stroke={borderColor} strokeWidth="4"
        />
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

  const [quantity, setQuantity] = useState(1);
  const [selectedSize, setSelectedSize] = useState("M");
  const [selectedAddOns] = useState<string[]>([]);
  const [notes, setNotes] = useState("");
  const [division, setDivision] = useState<FlavorDivision>(1);
  // 3 slots always; only division first slots are active
  const [flavorSlots, setFlavorSlots] = useState<(Pizza | null)[]>([product ?? null, null, null]);
  const [activeSlot, setActiveSlot] = useState<number | null>(null);
  const [cartError, setCartError] = useState(false);

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

  const addOnPrice = useMemo(
    () => addOns.filter((a) => selectedAddOns.includes(a.id)).reduce((s, a) => s + a.price, 0),
    [selectedAddOns]
  );

  const flavorPrice = useMemo(
    () => computeFlavorPrice(activeFlavors, division, multiFlavorsConfig.pricingRule),
    [activeFlavors, division, multiFlavorsConfig.pricingRule]
  );

  const pricePerUnit = flavorPrice + addOnPrice;
  const totalPrice = pricePerUnit * quantity;

  // ── Handlers ─────────────────────────────────────────────────────────────────

  const handleDivisionChange = (d: FlavorDivision) => {
    setDivision(d);
    setActiveSlot(null);
    setCartError(false);
    // Preserve slot 0 (base product), reset rest if going down
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

  const toggleAddOn = (addOnId: string) =>
    setSelectedAddOns((prev) =>
      prev.includes(addOnId) ? prev.filter((x) => x !== addOnId) : [...prev, addOnId]
    );

  const handleAddToCart = () => {
    if (!allFilled) {
      setCartError(true);
      return;
    }
    const flavors: PizzaFlavor[] = (activeFlavors as Pizza[]).map((p) => ({
      productId: p.id,
      name: p.name,
      price: p.price,
      icon: p.icon,
    }));
    addToCart(flavorSlots[0]!, quantity, selectedSize, selectedAddOns, flavors, division, pricePerUnit, notes || undefined);
    navigate("/cart");
  };

  // ── Render ───────────────────────────────────────────────────────────────────

  const divisionOptions = DIVISION_OPTIONS.filter(
    (opt) => opt.value <= multiFlavorsConfig.maxFlavors || opt.value === 1
  );

  // Products available for a given slot (no duplicates across other slots)
  const availableForSlot = (slotIndex: number) =>
    products.filter((p) => !flavorSlots.some((f, fi) => fi !== slotIndex && f?.id === p.id));

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00">

      {/* Header */}
      <div className="bg-brand-dark px-4 py-4 flex justify-between items-center sticky top-0 z-30">
        <button onClick={() => navigate(-1)} className="text-parchment hover:text-cream transition-colors">
          <ChevronLeft size={24} />
        </button>
        <MoschettieriLogo className="text-cream text-base" />
        <div className="w-6"></div>
      </div>

      {/* Content */}
      <div className="px-4 pt-6 pb-36">

        {/* ── Hero Product Image ───────────────────────────────────────────── */}
        <div className="flex flex-col items-center mb-6">
          <div className="w-52 h-52 rounded-full bg-surface-02 border-4 border-surface-03 flex items-center justify-center text-8xl shadow-2xl shadow-black/40 overflow-hidden">
            {product.icon && (product.icon.startsWith("data:") || product.icon.startsWith("http"))
              ? <img src={product.icon} alt={product.name} className="w-full h-full object-cover" />
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

        {/* ── Division Selector ───────────────────────────────────────────── */}
        <div className="mb-6">
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

        {/* ── Flavor Slots ────────────────────────────────────────────────── */}
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
                  {/* Slot card */}
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
                    {/* Icon */}
                    <div className="w-12 h-12 rounded-full bg-surface-03 flex items-center justify-center text-2xl flex-shrink-0 overflow-hidden">
                      {flavor?.icon && (flavor.icon.startsWith("data:") || flavor.icon.startsWith("http"))
                        ? <img src={flavor.icon} alt="" className="w-full h-full object-cover" />
                        : <span>{flavor?.icon ?? "?"}</span>}
                    </div>

                    {/* Info */}
                    <div className="flex-1 text-left">
                      <p className="text-stone text-xs">{slotLabel}</p>
                      <p className={`text-sm font-semibold ${flavor ? "text-cream" : "text-stone/70"}`}>
                        {flavor?.name ?? "Toque para escolher o sabor"}
                      </p>
                      {flavor && (
                        <p className="text-gold-light text-xs">R$ {flavor.price.toFixed(2)}</p>
                      )}
                    </div>

                    {/* Status indicator */}
                    <div className="flex-shrink-0">
                      {flavor ? (
                        <span className="flex items-center gap-1 text-xs text-green-400 bg-green-500/10 border border-green-500/30 px-2 py-1 rounded-full">
                          <Check size={11} />
                          {isOpen ? "Trocar" : "Ok"}
                        </span>
                      ) : (
                        <span className="text-xs text-gold-light bg-gold/10 border border-gold/30 px-2 py-1 rounded-full">
                          Escolher
                        </span>
                      )}
                    </div>
                  </button>

                  {/* Inline flavor picker */}
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
                                isSelected
                                  ? "bg-gold/20 border-gold shadow-sm"
                                  : "bg-surface-02 border-surface-03 hover:border-gold/40"
                              }`}
                            >
                              <div className="w-10 h-10 mx-auto mb-1 flex items-center justify-center text-2xl overflow-hidden rounded-lg">
                                {p.icon && (p.icon.startsWith("data:") || p.icon.startsWith("http"))
                                  ? <img src={p.icon} alt="" className="w-full h-full object-cover" />
                                  : <span>{p.icon || "🍕"}</span>}
                              </div>
                              <p className="text-cream text-xs font-medium leading-tight line-clamp-1">{p.name}</p>
                              <p className="text-gold-light text-xs mt-0.5">R${p.price.toFixed(2)}</p>
                              {isSelected && (
                                <span className="inline-block mt-1 text-[10px] bg-gold text-cream px-1.5 py-0.5 rounded-full">
                                  ✓ Selecionado
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

          {/* Price preview when multiple flavors */}
          {division > 1 && activeFlavors.some((f) => f !== null) && (
            <div className="mt-3 p-3 rounded-xl bg-surface-02/60 border border-surface-03">
              <div className="flex items-center justify-between text-sm">
                <span className="text-stone">
                  {allFilled
                    ? `${division === 2 ? "Meio a Meio" : "3 Sabores"} — sabor mais caro`
                    : "Preço parcial (preencha todos os sabores)"}
                </span>
                <span className="text-gold-light font-bold">
                  R$ {flavorPrice.toFixed(2)}
                </span>
              </div>
              {activeFlavors.filter(Boolean).length > 0 && (
                <div className="flex gap-1 mt-2 flex-wrap">
                  {activeFlavors.map((f, i) =>
                    f ? (
                      <span key={i} className="text-xs bg-surface-03 text-parchment px-2 py-0.5 rounded-full">
                        {f.icon} {f.name} — R${f.price.toFixed(2)}
                      </span>
                    ) : (
                      <span key={i} className="text-xs bg-surface-03/50 text-stone/70 px-2 py-0.5 rounded-full border border-dashed border-brand-mid">
                        Sabor {i + 1} — ?
                      </span>
                    )
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Size Selector ───────────────────────────────────────────────── */}
        <div className="mb-6">
          <h3 className="text-cream font-bold mb-3">{p.sizeLabel}</h3>
          <div className="flex gap-2">
            {SIZES.map((size) => (
              <button
                key={size}
                onClick={() => setSelectedSize(size)}
                className={`flex-1 py-3 rounded-xl text-sm font-bold transition-all ${
                  selectedSize === size
                    ? "bg-gold text-cream shadow-lg shadow-gold/30"
                    : "bg-surface-02 text-parchment hover:bg-surface-03 border border-surface-03"
                }`}
              >
                <span className="block font-black">{size}</span>
                <span className="block text-[10px] opacity-70 font-normal">{SIZE_LABELS[size]}</span>
              </button>
            ))}
          </div>
        </div>

        {/* ── Observações ─────────────────────────────────────────────────── */}
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

        {/* ── Pizza Diagram ───────────────────────────────────────────────── */}
        {division > 1 && (
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
          {division > 1 && allFilled && (
            <div className="text-right">
              <p className="text-stone text-xs">
                {division === 2 ? "Meio a Meio" : "3 Sabores"} · {selectedSize}
              </p>
              <p className="text-stone text-xs">
                {(activeFlavors as Pizza[]).map((f) => f.name).join(" + ")}
              </p>
            </div>
          )}
        </div>
        <button
          onClick={handleAddToCart}
          disabled={!allFilled}
          className={`w-full font-bold py-3.5 px-4 rounded-full text-center transition-all text-base active:scale-95 ${
            allFilled
              ? "bg-gold hover:bg-gold/90 text-cream shadow-lg shadow-gold/30"
              : "bg-surface-03 text-stone/70 cursor-not-allowed"
          }`}
        >
          {allFilled
            ? `${p.addToCartButton} · R$ ${totalPrice.toFixed(2)}`
            : `Escolha ${activeFlavors.filter((f) => !f).length} sabor(es) restante(s)`}
        </button>
      </div>
    </div>
  );
}
