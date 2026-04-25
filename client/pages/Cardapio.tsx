import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft, Search, Star, Plus, Check } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { isAssetUrl, resolveAssetUrl } from "@/lib/api";
import { trackEvent } from "@/lib/tracking";
import BottomNav from "@/components/BottomNav";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import StoreStatusBanner from "@/components/StoreStatusBanner";

export default function Cardapio() {
  const navigate = useNavigate();
  const { products, addToCart } = useApp();
  const ALL_LABEL = "Todos";
  const [activeCategory, setActiveCategory] = useState(ALL_LABEL);
  const [search, setSearch] = useState("");
  const [justAdded, setJustAdded] = useState<string | null>(null);

  // Categories derived from backend products (source of truth)
  const productCats = [...new Set(
    products.filter(p => p.active && p.category).map(p => p.category as string)
  )].sort();
  const effectiveCategories = [ALL_LABEL, ...productCats];

  const filtered = products.filter((p) => {
    const matchSearch = p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.description.toLowerCase().includes(search.toLowerCase());
    const matchCat = activeCategory === ALL_LABEL ||
      (p.category ?? "").toLowerCase() === activeCategory.toLowerCase();
    return matchSearch && matchCat && p.active;
  });

  const handleQuickAdd = (e: React.MouseEvent, product: typeof products[0]) => {
    e.stopPropagation();
    const productType = (product as any).product_type as string | null | undefined;
    const isPizza = !productType || productType === "pizza";
    if (isPizza) {
      navigate(`/product/${product.id}`);
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
      unitPrice
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
          <MoschettieriLogo className="text-cream text-base scale-[1.14] origin-center" />
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

      <div className="px-4 pb-3 max-w-2xl mx-auto">
        <StoreStatusBanner compact />
      </div>

      {/* Products Grid */}
      <div className="px-4 pb-32 max-w-2xl mx-auto w-full">
        {filtered.length === 0 ? (
          <div className="text-center py-16">
            <div className="text-5xl mb-4">🍕</div>
            <p className="text-stone">Nenhum produto encontrado</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {filtered.map((product) => (
              <div
                key={product.id}
                className="bg-surface-02 rounded-2xl p-4 border border-surface-03 hover:border-gold/40 transition-all"
              >
                <button
                  onClick={() => navigate(`/product/${product.id}`)}
                  className="w-full text-left"
                >
                  <div className="w-full aspect-square rounded-xl bg-surface-03 flex items-center justify-center overflow-hidden mb-3">
                    {isAssetUrl(product.icon) ? (
                      <img src={resolveAssetUrl(product.icon)} alt={product.name} className="w-full h-full object-cover" />
                    ) : (
                      <span className="text-5xl">{product.icon || "🍕"}</span>
                    )}
                  </div>
                  <h3 className="text-cream font-semibold text-sm leading-tight line-clamp-1">
                    {product.name}
                  </h3>
                  <div className="flex items-center gap-1 mt-1">
                    <Star size={10} className="fill-yellow-400 text-yellow-400" />
                    <span className="text-stone text-xs">{product.rating?.toFixed(1) ?? "4.5"}</span>
                  </div>
                  <p className="text-stone/70 text-xs mt-1 line-clamp-2 leading-tight">
                    {product.description}
                  </p>
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
                    className={`w-8 h-8 rounded-full flex items-center justify-center transition-all active:scale-90 ${
                      justAdded === product.id
                        ? "bg-green-500 scale-110"
                        : "bg-gold hover:bg-gold/80"
                    }`}
                    title="Adicionar ao carrinho"
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
