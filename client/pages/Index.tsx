import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Menu, Search, Star, ChevronRight, ChevronLeft, X, ShoppingCart, Bell, User, Tag, Heart, UtensilsCrossed } from "lucide-react";

import { useApp } from "@/context/AppContext";
import BottomNav from "@/components/BottomNav";
import MoschettieriLogo from "@/components/MoschettieriLogo";

const PIZZA_FALLBACKS = ["🍕", "🫓", "🧀", "🍅", "🌶️", "🍖", "🍄", "🫒", "🔥", "🥩", "🌿", "🫑"];

export default function Home() {
  const navigate = useNavigate();
  const { products, promotions, siteContent } = useApp();
  const { categories, sectionSubtitle, sectionTitle, bannerRotationInterval } = siteContent.home;
  const rotationInterval = (bannerRotationInterval ?? 5) * 1000;

  const [activeCategory, setActiveCategory] = useState(categories[1] ?? categories[0]);
  const [carouselPosition, setCarouselPosition] = useState(0);
  const [clickedPizza, setClickedPizza] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [touchStartX, setTouchStartX] = useState<number | null>(null);
  const [activeBannerIndex, setActiveBannerIndex] = useState(0);

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

  const ALL_LABEL = categories[0] ?? "Todas";
  const categoryProducts =
    activeCategory === ALL_LABEL || !activeCategory
      ? products
      : products.filter((p) => (p.category ?? "").toLowerCase() === activeCategory.toLowerCase());

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
    if (Math.abs(diff) > 40) diff > 0 ? handleNext() : handlePrev();
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
          <div className="bg-brand-dark px-4 py-4 flex items-center gap-3">
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
                    <span className="text-4xl">{product.icon || "🍕"}</span>
                    <div className="flex-1">
                      <p className="text-cream font-semibold">{product.name}</p>
                      <p className="text-stone text-sm line-clamp-1">{product.description}</p>
                    </div>
                    <p className="text-gold font-bold">R$ {product.price.toFixed(2)}</p>
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
              <MoschettieriLogo className="text-cream text-base" />
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
      <div className="bg-brand-dark px-4 py-4 flex justify-between items-center sticky top-0 z-30">
        <button onClick={() => setMenuOpen(true)} className="text-parchment hover:text-cream transition-colors">
          <Menu size={24} />
        </button>
        <MoschettieriLogo className="text-cream text-base" />
        <button onClick={() => setSearchOpen(true)} className="text-parchment hover:text-cream transition-colors">
          <Search size={24} />
        </button>
      </div>

      {/* Promo Banner with auto-rotation */}
      <div className="px-4 py-4">
        <div
          className="bg-gradient-to-r from-slate-800 to-slate-700 rounded-2xl p-4 flex items-center justify-between overflow-hidden relative"
          style={media.heroBannerImage ? { backgroundImage: `url(${media.heroBannerImage})`, backgroundSize: "cover", backgroundPosition: "center" } : undefined}
        >
          <div className="flex-1">
            <p className="text-sm text-parchment">{displayBanner?.title || "20% off"}</p>
            <p className="text-xl font-bold text-cream">
              {displayBanner?.subtitle || "Em qualquer pizza"}
            </p>
            {(displayBanner as any)?.validity_text || home.bannerValidityText ? (
              <p className="text-xs text-stone mt-1">{(displayBanner as any)?.validity_text || home.bannerValidityText}</p>
            ) : null}
          </div>
          <div className="w-32 h-32 flex-shrink-0 relative -mr-8 text-5xl flex items-center justify-center">
            {displayBanner?.icon || "🍕"}
          </div>
          <button className="absolute right-4 top-4 bg-surface-03 rounded-full p-2 text-parchment hover:text-cream transition-colors">
            <ChevronRight size={16} />
          </button>

          {/* Banner dots */}
          {activePromotions.length > 1 && (
            <div className="absolute bottom-2 left-4 flex gap-1.5">
              {activePromotions.map((_, i) => (
                <button
                  key={i}
                  onClick={() => setActiveBannerIndex(i)}
                  className={`h-1.5 rounded-full transition-all ${i === activeBannerIndex ? "bg-gold w-4" : "bg-stone/50 w-1.5"}`}
                />
              ))}
            </div>
          )}
        </div>

        {/* Banner nav arrows — only when multiple banners */}
        {activePromotions.length > 1 && (
          <div className="flex justify-center gap-2 mt-2">
            <button
              onClick={() => setActiveBannerIndex((prev) => (prev - 1 + activePromotions.length) % activePromotions.length)}
              className="w-7 h-7 rounded-full bg-surface-02 hover:bg-surface-03 text-stone hover:text-cream flex items-center justify-center transition-colors"
            >
              <ChevronLeft size={14} />
            </button>
            <button
              onClick={() => setActiveBannerIndex((prev) => (prev + 1) % activePromotions.length)}
              className="w-7 h-7 rounded-full bg-surface-02 hover:bg-surface-03 text-stone hover:text-cream flex items-center justify-center transition-colors"
            >
              <ChevronRight size={14} />
            </button>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="px-4 pb-32">
        {/* Section Title */}
        <div className="mt-4 mb-4">
          <p className="text-stone text-sm">{sectionSubtitle}</p>
          <h2 className="text-2xl font-bold text-cream mt-1">
            {sectionTitle}
          </h2>
        </div>

        {/* Category Pills */}
        <div className="flex gap-2 mb-6 overflow-x-auto pb-2 scrollbar-hide">
          {categories.map((category) => (
            <button
              key={category}
              onClick={() => setActiveCategory(category)}
              className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-all flex-shrink-0 ${
                activeCategory === category
                  ? "bg-gold text-cream"
                  : "bg-surface-02 text-parchment hover:bg-surface-03"
              }`}
            >
              {category}
            </button>
          ))}
        </div>

        {/* Empty state for filtered category */}
        {categoryProducts.length === 0 && (
          <div className="text-center py-10">
            <p className="text-stone text-sm">Nenhum produto nesta categoria.</p>
          </div>
        )}

        {/* Product Carousel — layout original */}
        {categoryProducts.length > 0 && (
        <div
          className="relative overflow-hidden"
          onTouchStart={handleTouchStart}
          onTouchEnd={handleTouchEnd}
        >
          <div className="flex items-stretch justify-center gap-3 px-2">
            {/* Previous item (partially visible) */}
            <div className="w-[22vw] max-w-[90px] flex-shrink-0 opacity-40 self-center">
              <div className="w-full aspect-square rounded-xl bg-surface-02 flex items-center justify-center overflow-hidden">
                <span className="text-4xl pizza-spin">
                  {getIcon(prevPizza?.icon, getPizzaIndex(-1))}
                </span>
              </div>
            </div>

            {/* Featured item (center, larger) */}
            <div className="flex-1 min-w-0 max-w-[220px]">
              <button
                onClick={() => handlePizzaClick(currentPizza.id)}
                className={`w-full bg-surface-02 rounded-2xl p-4 shadow-2xl transition-all duration-300 ${
                  clickedPizza === currentPizza.id
                    ? "scale-110 shadow-gold/30"
                    : "hover:shadow-gold/20 active:scale-95"
                }`}
              >
                <div className="w-[min(128px,30vw)] h-[min(128px,30vw)] mx-auto mb-3 rounded-full bg-surface-03 flex items-center justify-center overflow-hidden">
                  <span className="text-5xl pizza-spin">
                    {getIcon(currentPizza?.icon, carouselPosition)}
                  </span>
                </div>
                <p className="text-cream font-bold text-center text-sm leading-snug">
                  {currentPizza?.name}
                </p>
                <div className="flex justify-center gap-1 mt-1 mb-2">
                  {[...Array(5)].map((_, i) => (
                    <Star
                      key={i}
                      size={12}
                      className={
                        i < Math.floor(currentPizza?.rating || 0)
                          ? "fill-yellow-400 text-yellow-400"
                          : "text-slate-600"
                      }
                    />
                  ))}
                </div>
                <p className="text-gold font-bold text-center">
                  R$ {currentPizza?.price.toFixed(2)}
                </p>
                <p className="text-xs text-stone text-center mt-2 leading-tight line-clamp-2">
                  {currentPizza?.description}
                </p>
              </button>
            </div>

            {/* Next item (partially visible) */}
            <div className="w-[22vw] max-w-[90px] flex-shrink-0 opacity-40 self-center">
              <div className="w-full aspect-square rounded-xl bg-surface-02 flex items-center justify-center overflow-hidden">
                <span className="text-4xl pizza-spin">
                  {getIcon(nextPizza?.icon, getPizzaIndex(1))}
                </span>
              </div>
            </div>
          </div>

          {/* Carousel Navigation */}
          <div className="flex justify-center gap-2 mt-5">
            <button
              onClick={handlePrev}
              className="w-8 h-8 rounded-full bg-surface-02 hover:bg-surface-03 text-stone hover:text-cream flex items-center justify-center transition-colors"
            >
              ←
            </button>
            <button
              onClick={handleNext}
              className="w-8 h-8 rounded-full bg-surface-02 hover:bg-surface-03 text-stone hover:text-cream flex items-center justify-center transition-colors"
            >
              →
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
