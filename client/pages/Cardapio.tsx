import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft, Search, Plus, Check } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { categoriesApi, isAssetUrl, resolveAssetUrl, resolveOptimizedAssetUrl, type ApiProductCategory } from "@/lib/api";
import { sortCategoryNamesByCatalogOrder } from "@/lib/catalogOrdering";
import { trackEvent } from "@/lib/tracking";
import BottomNav from "@/components/BottomNav";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import CategorySeal from "@/components/CategorySeal";
import BestSellerSeal from "@/components/BestSellerSeal";

export default function Cardapio() {
  const navigate = useNavigate();
  const { products, productsLoaded, addToCart } = useApp();
  const PROMO_LABEL = "Promoções";
  const [activeCategory, setActiveCategory] = useState("");
  const [search, setSearch] = useState("");
  const [justAdded, setJustAdded] = useState<string | null>(null);
  const [catalogCategories, setCatalogCategories] = useState<ApiProductCategory[]>([]);

  useEffect(() => {
    categoriesApi.list(true)
      .then(setCatalogCategories)
      .catch(() => setCatalogCategories([]));
  }, []);

  // Categories derived from backend products (source of truth)
  const productCats = useMemo(() => {
    const categoryNames = [...new Set(
      products.filter(p => p.active && (p.subcategory || p.category)).map(p => (p.subcategory || p.category) as string)
    )];
    return sortCategoryNamesByCatalogOrder(categoryNames, catalogCategories);
  }, [products, catalogCategories]);
  const hasPromos = useMemo(
    () => products.some(p => p.active && p.promotion_applied),
    [products]
  );
  const effectiveCategories = useMemo(
    () => [...(hasPromos ? [PROMO_LABEL] : []), ...productCats],
    [hasPromos, productCats]
  );

  useEffect(() => {
    if (effectiveCategories.length === 0) {
      if (activeCategory !== "") {
        setActiveCategory("");
      }
      return;
    }

    if (!effectiveCategories.includes(activeCategory)) {
      setActiveCategory(effectiveCategories[0]);
    }
  }, [activeCategory, effectiveCategories]);

  const filtered = products.filter((p) => {
    const matchSearch = p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.description.toLowerCase().includes(search.toLowerCase());
    const matchCat =
      activeCategory !== "" &&
      (activeCategory === PROMO_LABEL ? p.promotion_applied : ((p.subcategory || p.category) ?? "").toLowerCase() === activeCategory.toLowerCase());
    return matchSearch && matchCat && p.active;
  });
  const isCatalogLoading = !productsLoaded && products.length === 0;

  const productTarget = (product: typeof products[0]) =>
    product.promotion_landing_url || `/product/${product.id}`;

  const handleQuickAdd = (e: React.MouseEvent, product: typeof products[0]) => {
    e.stopPropagation();
    if (product.inventory_available === false) return;
    const productType = (product as any).product_type as string | null | undefined;
    const isPizza = !productType || productType === "pizza";
    if (isPizza) {
      navigate(productTarget(product));
      return;
    }
    const unitPrice = product.current_price ?? product.price;
    addToCart(
      product,
      1,
      "M",
      [],
      [{ productId: product.id, name: product.name, price: unitPrice, icon: product.icon || "🍕" }],
      1,
      unitPrice,
      undefined,
      undefined,
      undefined,
      undefined,
      product.promotion_applied ? {
        applied: true,
        id: product.promotion_id,
        name: product.promotion_name,
        discount: product.promotion_discount,
        freeShipping: product.promotion_free_shipping,
        giftEnabled: product.promotion_gift_enabled,
        giftProductId: product.promotion_gift_product_id,
        giftQuantity: product.promotion_gift_quantity,
        giftName: product.promotion_gift_name,
        giftIcon: product.promotion_gift_icon,
        blocksOtherCoupons: product.promotion_blocks_other_coupons,
      } : undefined
    );
    trackEvent("add_to_cart", unitPrice, { product_id: product.id, source: "cardapio" });
    setJustAdded(product.id);
    setTimeout(() => setJustAdded(null), 1500);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00">
      {/* Header */}
      <div className="bg-brand-dark px-4 py-3 sticky top-0 z-30 border-b border-surface-02">
        <div className="flex items-center justify-between mb-3">
          <button onClick={() => navigate(-1)} className="text-parchment hover:text-cream transition-colors">
            <ChevronLeft size={24} />
          </button>
          <button onClick={() => navigate("/")} aria-label="Ir para a home da loja">
            <MoschettieriLogo className="text-cream text-base scale-[1.14] origin-center" />
          </button>
          <div className="w-6" />
        </div>
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone/70" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar produtos..."
            className="w-full bg-surface-02 text-cream placeholder-stone/70 rounded-full py-2.5 pl-9 pr-4 text-sm border border-surface-03 focus:outline-none focus:border-gold transition-colors"
          />
        </div>
      </div>

      {/* Category Pills */}
      <div className="flex gap-2 px-4 py-3 overflow-x-auto scrollbar-hide max-w-2xl mx-auto">
        {effectiveCategories.map((cat) => (
          <button
            key={cat}
            onClick={() => setActiveCategory(cat)}
            className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-all flex-shrink-0 ${
              activeCategory === cat
                ? "bg-gold text-cream shadow-lg shadow-gold/30"
                : "bg-surface-02 text-parchment hover:bg-surface-03 border border-surface-03"
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Products Grid */}
      <div className="px-4 pb-32 max-w-2xl mx-auto w-full">
        {isCatalogLoading ? (
          <CatalogGridSkeleton />
        ) : filtered.length === 0 ? (
          <div className="text-center py-16">
            <div className="text-5xl mb-4">🍕</div>
            <p className="text-stone">Nenhum produto encontrado</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {filtered.map((product, index) => (
              <div
                key={product.id}
                className="bg-surface-02 rounded-2xl p-4 border border-surface-03 hover:border-gold/40 transition-all"
              >
                <button
                  onClick={() => navigate(productTarget(product))}
                  className="w-full text-left"
                >
                  {/* Image wrapper — outer is relative for BestSellerSeal positioning */}
                  <div className="relative w-full aspect-square mb-3">
                    {/* Inner container clips scaled image */}
                    <div className="absolute inset-0 rounded-xl bg-surface-03 flex items-center justify-center overflow-hidden">
                      {/* Warm oven glow — organic, asymmetric, premium */}
                      <div
                        className="absolute inset-0 z-0 pointer-events-none"
                        style={{
                          background:
                            "radial-gradient(ellipse 80% 70% at 50% 60%, rgba(251,146,60,0.20) 0%, rgba(234,88,12,0.09) 42%, transparent 70%)",
                        }}
                      />
                      <CategorySeal product={product} />
                      {isAssetUrl(product.icon) ? (
                        <img
                          src={resolveOptimizedAssetUrl(product.icon, 360)}
                          alt={product.name}
                          className="relative z-[1] w-full h-full object-cover scale-[1.10] transition-transform duration-300"
                          width={320}
                          height={320}
                          loading={index === 0 ? "eager" : "lazy"}
                          decoding="async"
                          fetchPriority={index === 0 ? "high" : "auto"}
                        />
                      ) : (
                        <span className="relative z-[1] text-5xl scale-[1.10] inline-block">
                          {product.icon || "🍕"}
                        </span>
                      )}
                    </div>
                    {/* Best seller seal floats over bottom-right corner */}
                    <BestSellerSeal show={(product as any).show_best_seller_badge} />
                  </div>
                  <h3 className="text-cream font-semibold text-sm leading-tight line-clamp-1">
                    {product.name}
                  </h3>
                  <p className="text-stone/70 text-xs mt-1 line-clamp-2 leading-tight">
                    {product.description}
                  </p>
                  {product.inventory_available === false && (
                    <span className="mt-2 inline-flex rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[10px] font-bold text-amber-300">
                      Indisponivel no momento
                    </span>
                  )}
                </button>
                <div className="flex items-center justify-between mt-3">
                  <div>
                    <span className="text-gold font-bold text-sm">
                      R$ {(product.current_price ?? product.price).toFixed(2)}
                    </span>
                    {product.promotion_applied && product.standard_price && (
                      <span className="block text-[10px] text-stone line-through">
                        R$ {product.standard_price.toFixed(2)}
                      </span>
                    )}
                  </div>
                  <button
                    onClick={(e) => handleQuickAdd(e, product)}
                    disabled={product.inventory_available === false}
                    className={`w-8 h-8 rounded-full flex items-center justify-center transition-all active:scale-90 ${
                      product.inventory_available === false
                        ? "bg-surface-03 text-stone cursor-not-allowed"
                        : justAdded === product.id
                        ? "bg-green-500 scale-110"
                        : "bg-gold hover:bg-gold/80"
                    }`}
                    title={product.inventory_available === false ? "Indisponivel no momento" : "Adicionar ao carrinho"}
                  >
                    {justAdded === product.id
                      ? <Check size={15} className="text-cream" />
                      : <Plus size={16} className="text-cream" />
                    }
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <BottomNav />

      <style>{`
        .scrollbar-hide::-webkit-scrollbar { display: none; }
        .scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
      `}</style>
    </div>
  );
}

function CatalogGridSkeleton() {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3" aria-label="Carregando produtos">
      {[0, 1, 2, 3, 4, 5].map((item) => (
        <div key={item} className="rounded-2xl border border-surface-03 bg-surface-02 p-4">
          <div className="mb-3 aspect-square rounded-xl bg-surface-03 animate-pulse" />
          <div className="h-4 w-24 rounded bg-surface-03 animate-pulse" />
          <div className="mt-2 h-3 w-16 rounded bg-surface-03 animate-pulse" />
          <div className="mt-3 h-4 w-20 rounded bg-surface-03 animate-pulse" />
        </div>
      ))}
    </div>
  );
}
