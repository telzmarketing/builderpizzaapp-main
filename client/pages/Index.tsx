import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Menu, Search, Star, ChevronRight, ChevronLeft, X, ShoppingCart, Bell, User, Tag, Heart, UtensilsCrossed } from "lucide-react";

import { useApp } from "@/context/AppContext";
import { homeCatalogApi, isAssetUrl, resolveAssetUrl } from "@/lib/api";
import BottomNav from "@/components/BottomNav";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import StoreStatusBanner from "@/components/StoreStatusBanner";

const PIZZA_FALLBACKS = ["🍕", "🫓", "🧀", "🍅", "🌶️", "🍖", "🍄", "🫒", "🔥", "🥩", "🌿", "🫑"];

export default function Home() {
  const navigate = useNavigate();
  const { products, promotions, siteContent } = useApp();
  const { sectionSubtitle, sectionTitle, bannerRotationInterval } = siteContent.home;
  const rotationInterval = (bannerRotationInterval ?? 5) * 1000;
  const ALL_LABEL = "Todos";

  const [activeCategory, setActiveCategory] = useState(ALL_LABEL);
  const [carouselPosition, setCarouselPosition] = useState(0);
  const [clickedPizza, setClickedPizza] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [touchStartX, setTouchStartX] = useState<number | null>(null);
  const [activeBannerIndex, setActiveBannerIndex] = useState(0);

  // Home catalog config
  const [homeConfig, setHomeConfig] = useState<{
    mode: string;
    selectedCategories: string[];
    selectedProductIds: string[];
    showPromotions: boolean;
  }>({ mode: "all", selectedCategories: [], selectedProductIds: [], showPromotions: true });

  useEffect(() => {
    homeCatalogApi.get().then((config) => {
      try {
        setHomeConfig({
          mode: config.mode,
          selectedCategories: JSON.parse(config.selected_categories || "[]"),
          selectedProductIds: JSON.parse(config.selected_product_ids || "[]"),
          showPromotions: config.show_promotions,
        });
      } catch { /* use defaults on parse error */ }
    }).catch(() => { /* use defaults if backend unavailable */ });
  }, []);

  const activePromotions = promotions.filter((p) => p.active);
  const displayBanner = activePromotions.length > 0 ? activePromotions[activeBannerIndex] : promotions[0];

  // Banner auto-rotation
  useEffect(() => {
    if (activePromotions.length <= 1 || rotationInterval <= 0) return;
    const timer = setInterval(() => {
      setActiveBannerIndex((prev) => (prev + 1) % activePromotions.length);
    }, rotationInterval);
    return () => clearInterval(timer);
  }, [activePromotions.length, rotationInterval]);

  const filteredProducts = searchQuery.trim()
    ? products.filter((p) =>
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.description?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : [];
  // (search always spans full product list, not filtered by homeConfig — intentional)

  // Apply home catalog config filter on top of all active products
  const catalogProducts = useMemo(() => {
    if (homeConfig.mode === "categories" && homeConfig.selectedCategories.length > 0) {
      return products.filter(p => homeConfig.selectedCategories.includes(p.category ?? ""));
    }
    if (homeConfig.mode === "products" && homeConfig.selectedProductIds.length > 0) {
      return products.filter(p => homeConfig.selectedProductIds.includes(p.id));
    }
    return products;
  }, [products, homeConfig]);

  // Categories derived from catalogProducts (respect home config)
  const productCats = [...new Set(
    catalogProducts.filter(p => p.active && p.category).map(p => p.category as string)
  )].sort();
  const effectiveCategories = [ALL_LABEL, ...productCats];

  const categoryProducts =
    activeCategory === ALL_LABEL || !activeCategory
      ? catalogProducts
      : catalogProducts.filter((p) => (p.category ?? "").toLowerCase() === activeCategory.toLowerCase());

  const { home, media } = siteContent;

  const handleNext = () => {
    setCarouselPosition((prev) => (prev + 1) % Math.max(1, categoryProducts.length));
  };

  const handlePrev = () => {
    setCarouselPosition((prev) => (prev - 1 + Math.max(1, categoryProducts.length)) % Math.max(1, categoryProducts.length));
  };

  const handleTouchStart = (e: React.TouchEvent) => {
    setTouchStartX(e.touches[0].clientX);
  };

  const handleTouchEnd = (e: React.TouchEvent) => {
    if (touchStartX === null) return;
    const diff = touchStartX - e.changedTouches[0].clientX;
    if (Math.abs(diff) > 40) {
      e.preventDefault();
      diff > 0 ? handleNext() : handlePrev();
    }
    setTouchStartX(null);
  };

  const handlePizzaClick = (productId: string) => {
    setClickedPizza(productId);
    setTimeout(() => {
      navigate(`/product/${productId}`);
    }, 300);
  };

  const getPizzaIndex = (offset: number) => {
    const len = Math.max(1, categoryProducts.length);
    return (carouselPosition + offset + len) % len;
  };

  const getIcon = (icon: string | undefined, index: number) =>
    icon || PIZZA_FALLBACKS[index % PIZZA_FALLBACKS.length];

  const renderIcon = (icon: string | undefined, index: number, size: "sm" | "md" | "lg" = "md") => {
    const resolved = getIcon(icon, index);
    const isImage = isAssetUrl(resolved);
    const textCls = size === "lg" ? "text-5xl pizza-spin" : "text-4xl pizza-spin";
    return isImage
      ? <img src={resolveAssetUrl(resolved)} alt="" className="w-full h-full object-contain pizza-spin" />
      : <span className={textCls}>{resolved}</span>;
  };

  const prevPizza = categoryProducts.length > 0 ? categoryProducts[getPizzaIndex(-1)] : undefined;
  const currentPizza = categoryProducts.length > 0 ? categoryProducts[getPizzaIndex(0)] : undefined;
  const nextPizza = categoryProducts.length > 0 ? categoryProducts[getPizzaIndex(1)] : undefined;

  useEffect(() => { setCarouselPosition(0); }, [activeCategory]);

  if (products.length === 0) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00 flex items-center justify-center">
        <div className="text-center text-stone">
          <div className="text-4xl mb-4">🍕</div>
          <p className="text-lg">Carregando cardápio...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00">
      {/* Search Overlay */}
      {searchOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 flex flex-col">
          <div className="bg-brand-dark px-4 py-3 flex items-center gap-3">
            <button onClick={() => { setSearchOpen(false); setSearchQuery(""); }} className="text-stone hover:text-cream transition-colors">
              <X size={24} />
            </button>
            <input
              autoFocus
              type="text"
              placeholder="Buscar pizza, massa, burger..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="flex-1 bg-surface-02 text-cream placeholder-stone rounded-xl px-4 py-2 outline-none focus:ring-2 focus:ring-gold"
            />
          </div>
          <div className="flex-1 overflow-y-auto px-4 py-4">
            {searchQuery.trim() === "" ? (
              <p className="text-stone text-center mt-8">Digite para buscar produtos</p>
            ) : filteredProducts.length === 0 ? (
              <p className="text-stone text-center mt-8">Nenhum produto encontrado</p>
            ) : (
              <div className="space-y-3">
                {filteredProducts.map((product) => (
                  <button
                    key={product.id}
                    onClick={() => { setSearchOpen(false); setSearchQuery(""); navigate(`/product/${product.id}`); }}
                    className="w-full bg-surface-02 rounded-xl p-4 flex items-center gap-4 hover:bg-surface-03 transition-colors text-left"
                  >
                    <div className="w-12 h-12 rounded-xl bg-surface-03 flex items-center justify-center overflow-hidden flex-shrink-0">
                      {renderIcon(product.icon, 0, "sm")}
                    </div>
                    <div className="flex-1">
                      <p className="text-cream font-semibold">{product.name}</p>
                      <p className="text-stone text-sm line-clamp-1">{product.description}</p>
                    </div>
                    <p className="text-gold font-bold">R$ {(product.current_price ?? product.price).toFixed(2)}</p>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Drawer overlay */}
      {menuOpen && (
        <div className="fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMenuOpen(false)} />
          <div className="relative w-72 bg-brand-dark h-full flex flex-col shadow-2xl">
            <div className="flex items-center justify-between px-6 py-5 border-b border-surface-02">
              <MoschettieriLogo className="text-cream text-base scale-[1.14] origin-center" />
              <button onClick={() => setMenuOpen(false)} className="text-stone hover:text-cream transition-colors">
                <X size={24} />
              </button>
            </div>
            <nav className="flex-1 px-4 py-6 space-y-1">
              {[
                { icon: <UtensilsCrossed size={20} />, label: "Cardápio", path: "/cardapio" },
                { icon: <ShoppingCart size={20} />, label: "Carrinho", path: "/cart" },
                { icon: <Bell size={20} />, label: "Meus Pedidos", path: "/pedidos" },
                { icon: <Tag size={20} />, label: "Cupons", path: "/cupons" },
                { icon: <Heart size={20} />, label: "Fidelidade", path: "/fidelidade" },
                { icon: <User size={20} />, label: "Minha Conta", path: "/conta" },
              ].map(({ icon, label, path }) => (
                <button
                  key={path}
                  onClick={() => { setMenuOpen(false); navigate(path); }}
                  className="w-full flex items-center gap-4 px-4 py-3 rounded-xl text-parchment hover:text-cream hover:bg-surface-02 transition-colors text-left"
                >
                  <span className="text-gold">{icon}</span>
                  <span className="font-medium">{label}</span>
                </button>
              ))}
            </nav>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="bg-brand-dark px-4 py-3 flex justify-between items-center sticky top-0 z-30">
        <button onClick={() => setMenuOpen(true)} className="text-parchment hover:text-cream transition-colors">
          <Menu size={24} />
        </button>
        <MoschettieriLogo className="text-cream text-base scale-[1.14] origin-center" />
        <button onClick={() => setSearchOpen(true)} className="text-parchment hover:text-cream transition-colors">
          <Search size={24} />
        </button>
      </div>

      {/* ── Promo Banner (only if homeConfig.showPromotions) ── */}
      <div className="px-4 lg:px-8 pt-4">
        <div className="max-w-sm lg:max-w-4xl mx-auto">
          <StoreStatusBanner />
        </div>
      </div>

      {homeConfig.showPromotions && <div className="px-4 lg:px-8 pt-4 pb-3">
        <div className="max-w-sm lg:max-w-4xl mx-auto">
          <div
            className="rounded-2xl px-4 py-3 lg:px-10 lg:py-6 flex items-center gap-3 lg:gap-8 overflow-hidden relative"
            style={media.heroBannerImage
              ? { backgroundImage: `url(${resolveAssetUrl(media.heroBannerImage)})`, backgroundSize: "cover", backgroundPosition: "center" }
              : { background: "var(--home-banner-bg)" }}
          >
            {/* Icon */}
            <div className="w-16 h-16 lg:w-28 lg:h-28 flex-shrink-0 flex items-center justify-center overflow-hidden rounded-xl bg-white/5">
              {renderIcon(displayBanner?.icon, 0, "md")}
            </div>

            {/* Text */}
            <div className="flex-1 min-w-0">
              <p className="text-xs lg:text-sm text-parchment/80 truncate">{displayBanner?.title || "Promoção"}</p>
              <p className="text-base lg:text-3xl font-bold text-cream leading-tight line-clamp-2">
                {displayBanner?.subtitle || "Em qualquer pizza"}
              </p>
              {((displayBanner as any)?.validity_text || home.bannerValidityText) && (
                <p className="text-[10px] lg:text-sm text-stone mt-0.5 lg:mt-1.5 truncate">
                  {(displayBanner as any)?.validity_text || home.bannerValidityText}
                </p>
              )}
            </div>

            {/* Dots + arrows when multiple */}
            {activePromotions.length > 1 && (
              <div className="flex flex-col items-center gap-1.5 flex-shrink-0">
                <button
                  onClick={() => setActiveBannerIndex((prev) => (prev - 1 + activePromotions.length) % activePromotions.length)}
                  className="w-6 h-6 lg:w-8 lg:h-8 rounded-full bg-surface-03/80 text-stone hover:text-cream flex items-center justify-center"
                >
                  <ChevronLeft size={13} />
                </button>
                <div className="flex gap-1">
                  {activePromotions.map((_, i) => (
                    <button
                      key={i}
                      onClick={() => setActiveBannerIndex(i)}
                      className={`h-1 rounded-full transition-all ${i === activeBannerIndex ? "bg-gold w-3" : "bg-stone/50 w-1"}`}
                    />
                  ))}
                </div>
                <button
                  onClick={() => setActiveBannerIndex((prev) => (prev + 1) % activePromotions.length)}
                  className="w-6 h-6 lg:w-8 lg:h-8 rounded-full bg-surface-03/80 text-stone hover:text-cream flex items-center justify-center"
                >
                  <ChevronRight size={13} />
                </button>
              </div>
            )}
          </div>
        </div>
      </div>}

      {/* ── Content ── */}
      <div className="px-4 lg:px-8 pb-32 max-w-lg lg:max-w-5xl mx-auto w-full">
        {/* Section Title */}
        <div className="mt-4 mb-3">
          <p className="text-stone text-xs lg:text-sm">{sectionSubtitle}</p>
          <h2 className="text-xl lg:text-3xl font-bold text-cream mt-0.5">{sectionTitle}</h2>
        </div>

        {/* Category Pills */}
        <div className="flex gap-2 mb-5 overflow-x-auto pb-1 scrollbar-hide -mx-4 px-4 lg:mx-0 lg:px-0 lg:flex-wrap">
          {effectiveCategories.map((category) => (
            <button
              key={category}
              onClick={() => setActiveCategory(category)}
              className={`px-3.5 py-1.5 lg:px-5 lg:py-2 rounded-full text-sm lg:text-base font-medium whitespace-nowrap transition-all flex-shrink-0 ${
                activeCategory === category
                  ? "bg-gold text-cream shadow-lg shadow-gold/20"
                  : "bg-surface-02 text-parchment hover:bg-surface-03 border border-surface-03"
              }`}
            >
              {category}
            </button>
          ))}
        </div>

        {/* Empty state */}
        {categoryProducts.length === 0 && (
          <div className="text-center py-10">
            <p className="text-4xl mb-3">🍕</p>
            <p className="text-stone text-sm">Nenhum produto nesta categoria.</p>
          </div>
        )}

        {/* ── Desktop Grid (lg+) ── */}
        {categoryProducts.length > 0 && (
          <div className="hidden lg:grid lg:grid-cols-3 xl:grid-cols-4 gap-5">
            {categoryProducts.map((product, index) => (
              <button
                key={product.id}
                onClick={() => handlePizzaClick(product.id)}
                className={`w-full bg-surface-02 rounded-2xl p-5 shadow-lg hover:shadow-xl border border-surface-03 hover:border-gold/30 transition-all duration-300 text-left ${
                  clickedPizza === product.id ? "scale-105 shadow-gold/30" : "hover:scale-[1.02]"
                }`}
              >
                <div className="w-28 h-28 mx-auto mb-4 rounded-full bg-surface-03 flex items-center justify-center overflow-hidden">
                  {renderIcon(product.icon, index, "lg")}
                </div>
                <p className="text-cream font-bold text-center text-base leading-snug line-clamp-1">
                  {product.name}
                </p>
                <div className="flex justify-center gap-0.5 mt-1.5 mb-2">
                  {[...Array(5)].map((_, i) => (
                    <Star
                      key={i}
                      size={13}
                      className={i < Math.floor(product.rating || 0) ? "fill-yellow-400 text-yellow-400" : "text-slate-600"}
                    />
                  ))}
                </div>
                <p className="text-gold font-bold text-center text-base">
                  R$ {(product.current_price ?? product.price).toFixed(2)}
                </p>
                <p className="text-xs text-stone text-center mt-1 leading-tight line-clamp-2">
                  {product.description}
                </p>
              </button>
            ))}
          </div>
        )}

        {/* ── Mobile Carousel (hidden on lg+) ── */}
        {categoryProducts.length > 0 && (
          <div
            className="relative overflow-hidden select-none lg:hidden"
            onTouchStart={handleTouchStart}
            onTouchEnd={handleTouchEnd}
          >
            <div className="flex items-center justify-center gap-2">
              {/* Previous (partially visible) */}
              <div className="w-[18vw] max-w-[72px] flex-shrink-0 opacity-35 pointer-events-none">
                <div className="w-full aspect-square rounded-xl bg-surface-02 flex items-center justify-center overflow-hidden">
                  {renderIcon(prevPizza?.icon, getPizzaIndex(-1), "sm")}
                </div>
              </div>

              {/* Featured center card */}
              <div className="flex-1 min-w-0" style={{ maxWidth: "min(240px, 56vw)" }}>
                <button
                  onTouchStart={handleTouchStart}
                  onTouchEnd={handleTouchEnd}
                  onClick={() => handlePizzaClick(currentPizza.id)}
                  className={`w-full bg-surface-02 rounded-2xl p-4 shadow-2xl transition-all duration-300 ${
                    clickedPizza === currentPizza.id ? "scale-105 shadow-gold/30" : "active:scale-95"
                  }`}
                >
                  <div className="w-[min(120px,28vw)] h-[min(120px,28vw)] mx-auto mb-3 rounded-full bg-surface-03 flex items-center justify-center overflow-hidden">
                    {renderIcon(currentPizza?.icon, carouselPosition, "lg")}
                  </div>
                  <p className="text-cream font-bold text-center text-sm leading-snug line-clamp-1">
                    {currentPizza?.name}
                  </p>
                  <div className="flex justify-center gap-0.5 mt-1 mb-1.5">
                    {[...Array(5)].map((_, i) => (
                      <Star
                        key={i}
                        size={11}
                        className={i < Math.floor(currentPizza?.rating || 0) ? "fill-yellow-400 text-yellow-400" : "text-slate-600"}
                      />
                    ))}
                  </div>
                  <p className="text-gold font-bold text-center text-sm">
                    R$ {((currentPizza as any)?.current_price ?? currentPizza?.price ?? 0).toFixed(2)}
                  </p>
                  <p className="text-[11px] text-stone text-center mt-1 leading-tight line-clamp-2">
                    {currentPizza?.description}
                  </p>
                </button>
              </div>

              {/* Next (partially visible) */}
              <div className="w-[18vw] max-w-[72px] flex-shrink-0 opacity-35 pointer-events-none">
                <div className="w-full aspect-square rounded-xl bg-surface-02 flex items-center justify-center overflow-hidden">
                  {renderIcon(nextPizza?.icon, getPizzaIndex(1), "sm")}
                </div>
              </div>
            </div>

            {/* Navigation */}
            <div className="flex items-center justify-center gap-3 mt-4">
              <button
                onClick={handlePrev}
                className="w-9 h-9 rounded-full bg-surface-02 hover:bg-surface-03 text-stone hover:text-cream flex items-center justify-center transition-colors active:scale-90"
              >
                <ChevronLeft size={18} />
              </button>
              <span className="text-stone text-xs">
                {(carouselPosition % categoryProducts.length) + 1} / {categoryProducts.length}
              </span>
              <button
                onClick={handleNext}
                className="w-9 h-9 rounded-full bg-surface-02 hover:bg-surface-03 text-stone hover:text-cream flex items-center justify-center transition-colors active:scale-90"
              >
                <ChevronRight size={18} />
              </button>
            </div>
          </div>
        )}
      </div>

      <BottomNav />

      <style>{`
        @keyframes pizzaSpin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .pizza-spin {
          display: inline-block;
          animation: pizzaSpin 20s linear infinite;
        }
        .scrollbar-hide::-webkit-scrollbar { display: none; }
        .scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
      `}</style>
    </div>
  );
}
