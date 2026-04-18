import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Menu, Search, Star, ChevronRight, ChevronLeft, X, ShoppingCart, Bell, User, Tag, Heart, UtensilsCrossed } from "lucide-react";

import { useApp } from "@/context/AppContext";
import BottomNav from "@/components/BottomNav";
import MoschettieriLogo from "@/components/MoschettieriLogo";

const PIZZA_IMAGES = ["🍕", "🫓", "🧀", "🍅", "🌶️", "🫑", "🍖", "🥩", "🍄", "🫒", "🌿", "🔥"];

export default function Home() {
  const navigate = useNavigate();
  const { products, promotions, siteContent } = useApp();
  const { categories, sectionSubtitle, sectionTitle, bannerRotationInterval } = siteContent.home;
  const rotationInterval = (bannerRotationInterval ?? 5) * 1000;

  const [activeCategory, setActiveCategory] = useState(categories[1] ?? categories[0]);
  const [clickedPizza, setClickedPizza] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeBannerIndex, setActiveBannerIndex] = useState(0);

  const activePromotions = promotions.filter((p) => p.active);
  const displayBanner = activePromotions.length > 0 ? activePromotions[activeBannerIndex] : promotions[0];

  useEffect(() => {
    if (activePromotions.length <= 1 || rotationInterval <= 0) return;
    const timer = setInterval(() => {
      setActiveBannerIndex((prev) => (prev + 1) % activePromotions.length);
    }, rotationInterval);
    return () => clearInterval(timer);
  }, [activePromotions.length, rotationInterval]);

  const filteredProducts = activeCategory === categories[0]
    ? products
    : products.filter((p) =>
        p.name.toLowerCase().includes(activeCategory.toLowerCase()) ||
        p.description?.toLowerCase().includes(activeCategory.toLowerCase())
      );

  const searchResults = searchQuery.trim()
    ? products.filter((p) =>
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.description?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : [];

  const { home, media } = siteContent;

  const handlePizzaClick = (productId: string) => {
    setClickedPizza(productId);
    setTimeout(() => {
      navigate(`/product/${productId}`);
    }, 350);
  };

  const getPizzaEmoji = (icon: string | undefined, index: number) => {
    return icon || PIZZA_IMAGES[index % PIZZA_IMAGES.length];
  };

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
            ) : searchResults.length === 0 ? (
              <p className="text-stone text-center mt-8">Nenhum produto encontrado</p>
            ) : (
              <div className="space-y-3">
                {searchResults.map((product) => (
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
      <div className="px-4 pt-4 pb-2">
        <div
          className="relative bg-gradient-to-r from-slate-800 to-slate-700 rounded-2xl p-4 flex items-center justify-between overflow-hidden"
          style={media.heroBannerImage ? { backgroundImage: `url(${media.heroBannerImage})`, backgroundSize: "cover", backgroundPosition: "center" } : undefined}
        >
          <div className="flex-1 pr-2">
            <p className="text-sm text-parchment">{displayBanner?.title || "20% off"}</p>
            <p className="text-xl font-bold text-cream leading-tight">
              {displayBanner?.subtitle || "Em qualquer pizza"}
            </p>
            <p className="text-xs text-stone mt-1">{home.bannerValidityText}</p>
          </div>
          <div className="w-16 h-16 flex-shrink-0 flex items-center justify-center text-5xl">
            {displayBanner?.icon || "🍕"}
          </div>
          <button className="absolute right-3 top-3 bg-surface-03/80 rounded-full p-1.5 text-parchment hover:text-cream transition-colors">
            <ChevronRight size={14} />
          </button>

          {/* Banner dots */}
          {activePromotions.length > 1 && (
            <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-1.5">
              {activePromotions.map((_, i) => (
                <button
                  key={i}
                  onClick={() => setActiveBannerIndex(i)}
                  className={`w-1.5 h-1.5 rounded-full transition-all ${i === activeBannerIndex ? "bg-gold w-4" : "bg-stone/50"}`}
                />
              ))}
            </div>
          )}
        </div>

        {/* Banner navigation arrows */}
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
      <div className="px-4 pb-28">
        {/* Section Title */}
        <div className="mt-5 mb-3">
          <p className="text-stone text-sm">{sectionSubtitle}</p>
          <h2 className="text-xl font-bold text-cream mt-0.5">{sectionTitle}</h2>
        </div>

        {/* Category Pills */}
        <div className="flex gap-2 mb-4 overflow-x-auto pb-1 scrollbar-hide">
          {categories.map((category) => (
            <button
              key={category}
              onClick={() => setActiveCategory(category)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-all flex-shrink-0 ${
                activeCategory === category
                  ? "bg-gold text-cream"
                  : "bg-surface-02 text-parchment hover:bg-surface-03"
              }`}
            >
              {category}
            </button>
          ))}
        </div>

        {/* Product Grid */}
        {filteredProducts.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-5xl mb-3">🍕</p>
            <p className="text-stone">Nenhum produto nesta categoria</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {filteredProducts.map((product, index) => (
              <button
                key={product.id}
                onClick={() => handlePizzaClick(product.id)}
                className={`bg-surface-02 rounded-2xl p-3 border border-surface-03 text-left transition-all duration-300 ${
                  clickedPizza === product.id
                    ? "scale-105 border-gold/60 shadow-lg shadow-gold/20"
                    : "hover:border-gold/40 hover:scale-[1.02] active:scale-95"
                }`}
              >
                {/* Pizza image with slow spin */}
                <div className="w-full aspect-square rounded-xl bg-surface-03 flex items-center justify-center mb-2 overflow-hidden">
                  <span className="text-5xl pizza-spin">
                    {getPizzaEmoji(product.icon, index)}
                  </span>
                </div>

                <p className="text-cream font-semibold text-sm leading-snug line-clamp-1">
                  {product.name}
                </p>

                <div className="flex gap-0.5 mt-1 mb-1">
                  {[...Array(5)].map((_, i) => (
                    <Star
                      key={i}
                      size={10}
                      className={
                        i < Math.floor(product.rating || 0)
                          ? "fill-yellow-400 text-yellow-400"
                          : "text-slate-600"
                      }
                    />
                  ))}
                </div>

                <p className="text-gold font-bold text-sm">
                  R$ {product.price.toFixed(2)}
                </p>

                <p className="text-xs text-stone mt-1 leading-tight line-clamp-2">
                  {product.description}
                </p>
              </button>
            ))}
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
          transform-origin: center;
        }
        .scrollbar-hide::-webkit-scrollbar { display: none; }
        .scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
      `}</style>
    </div>
  );
}
