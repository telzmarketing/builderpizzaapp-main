import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Menu, Search, Star, ChevronRight, X, ShoppingCart, Bell, User, Tag, Heart, UtensilsCrossed } from "lucide-react";

import { useApp } from "@/context/AppContext";
import BottomNav from "@/components/BottomNav";
import MoschettieriLogo from "@/components/MoschettieriLogo";

export default function Home() {
  const navigate = useNavigate();
  const { products, promotions, siteContent } = useApp();
  const { categories, sectionSubtitle, sectionTitle } = siteContent.home;
  const [activeCategory, setActiveCategory] = useState(categories[1] ?? categories[0]);
  const [carouselPosition, setCarouselPosition] = useState(0);
  const [clickedPizza, setClickedPizza] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [touchStartX, setTouchStartX] = useState<number | null>(null);

  const { home, media } = siteContent;
  const activePromotion = promotions.find((p) => p.active) || promotions[0];

  const handleNext = () => {
    setCarouselPosition((prev) => (prev + 1) % products.length);
  };

  const handlePrev = () => {
    setCarouselPosition((prev) => (prev - 1 + products.length) % products.length);
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
    // Animation timing
    setTimeout(() => {
      navigate(`/product/${productId}`);
    }, 300);
  };

  const getPizzaIndex = (offset: number) => {
    return (carouselPosition + offset + products.length) % products.length;
  };

  const prevPizza = products.length > 0 ? products[getPizzaIndex(-1)] : undefined;
  const currentPizza = products.length > 0 ? products[getPizzaIndex(0)] : undefined;
  const nextPizza = products.length > 0 ? products[getPizzaIndex(1)] : undefined;

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
        <button className="text-parchment hover:text-cream transition-colors">
          <Search size={24} />
        </button>
      </div>

      {/* Promo Banner */}
      <div className="px-4 py-4">
        <div
          className="bg-gradient-to-r from-slate-800 to-slate-700 rounded-2xl p-4 flex items-center justify-between overflow-hidden relative"
          style={media.heroBannerImage ? { backgroundImage: `url(${media.heroBannerImage})`, backgroundSize: "cover", backgroundPosition: "center" } : undefined}
        >
          <div className="flex-1">
            <p className="text-sm text-parchment">{activePromotion?.title || "20% off to"}</p>
            <p className="text-xl font-bold text-cream">
              {activePromotion?.subtitle || "any fast food"}
            </p>
            <p className="text-xs text-stone mt-1">{home.bannerValidityText}</p>
          </div>
          <div className="w-32 h-32 flex-shrink-0 relative -mr-8 text-5xl">
            {activePromotion?.icon || "🍕"}
          </div>
          <button className="absolute right-4 top-4 bg-surface-03 rounded-full p-2 text-parchment hover:text-cream transition-colors">
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="px-4 pb-32">
        {/* Section Title */}
        <div className="mt-8 mb-4">
          <p className="text-stone text-sm">{sectionSubtitle}</p>
          <h2 className="text-2xl font-bold text-cream mt-1">
            {sectionTitle}
          </h2>
        </div>

        {/* Category Pills */}
        <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
          {categories.map((category) => (
            <button
              key={category}
              onClick={() => setActiveCategory(category)}
              className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-all ${
                activeCategory === category
                  ? "bg-gold text-cream"
                  : "bg-surface-02 text-parchment hover:bg-surface-03"
              }`}
            >
              {category}
            </button>
          ))}
        </div>

        {/* Product Carousel */}
        <div
          className="relative"
          onTouchStart={handleTouchStart}
          onTouchEnd={handleTouchEnd}
        >
          <div className="flex items-center justify-center gap-4">
            {/* Previous item (partially visible) */}
            <div className="w-24 h-32 flex-shrink-0 opacity-40">
              <div className="w-full h-full rounded-xl bg-surface-02 flex items-center justify-center p-2 text-4xl">
                {prevPizza?.icon || "🍕"}
              </div>
            </div>

            {/* Featured item (center, larger) */}
            <div className="w-40 flex-shrink-0">
              <button
                onClick={() => handlePizzaClick(currentPizza.id)}
                className={`w-full bg-surface-02 rounded-2xl p-4 shadow-2xl hover:shadow-gold/20 transition-all ${
                  clickedPizza === currentPizza.id
                    ? "scale-95 animate-spin"
                    : "hover:scale-105"
                }`}
                style={{
                  animation:
                    clickedPizza === currentPizza.id
                      ? "spin 0.3s ease-in-out forwards"
                      : "none",
                }}
              >
                <div className="w-32 h-32 mx-auto mb-4 rounded-full overflow-hidden bg-surface-03 flex items-center justify-center text-6xl">
                  {currentPizza?.icon || "🍕"}
                </div>
                <p className="text-cream font-bold text-center text-sm">
                  {currentPizza?.name}
                </p>
                <div className="flex justify-center gap-1 mt-1 mb-2">
                  {[...Array(5)].map((_, i) => (
                    <Star
                      key={i}
                      size={12}
                      className={`${
                        i < Math.floor(currentPizza?.rating || 0)
                          ? "fill-yellow-400 text-yellow-400"
                          : "text-slate-600"
                      }`}
                    />
                  ))}
                </div>
                <p className="text-gold font-bold text-center">
                  ${currentPizza?.price.toFixed(2)}
                </p>
                <p className="text-xs text-stone text-center mt-2 leading-tight">
                  {currentPizza?.description}
                </p>
              </button>
            </div>

            {/* Next item (partially visible) */}
            <div className="w-24 h-32 flex-shrink-0 opacity-40">
              <div className="w-full h-full rounded-xl bg-surface-02 flex items-center justify-center p-2 text-4xl">
                {nextPizza?.icon || "🍕"}
              </div>
            </div>
          </div>

          {/* Carousel Navigation */}
          <div className="flex justify-center gap-2 mt-6">
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
      </div>

      <BottomNav />

      <style>{`
        @keyframes spin {
          from {
            transform: scale(1) rotateY(0deg);
          }
          to {
            transform: scale(0.95) rotateY(180deg);
          }
        }
      `}</style>
    </div>
  );
}
