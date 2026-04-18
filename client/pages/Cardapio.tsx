import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Star, Plus } from "lucide-react";
import { useApp } from "@/context/AppContext";
import BottomNav from "@/components/BottomNav";

export default function Cardapio() {
  const navigate = useNavigate();
  const { products, siteContent } = useApp();
  const { categories } = siteContent.home;
  const [activeCategory, setActiveCategory] = useState("Todos");
  const [search, setSearch] = useState("");

  const allCategories = ["Todos", ...categories];

  const filtered = products.filter((p) => {
    const matchSearch = p.name.toLowerCase().includes(search.toLowerCase());
    const matchCat = activeCategory === "Todos" || true;
    return matchSearch && matchCat && p.active;
  });

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-950">
      {/* Header */}
      <div className="bg-slate-900 px-4 py-4 sticky top-0 z-30 border-b border-slate-800">
        <h1 className="text-white font-bold text-xl text-center mb-3">Cardápio</h1>
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar produtos..."
            className="w-full bg-slate-800 text-white placeholder-slate-500 rounded-full py-2.5 pl-9 pr-4 text-sm border border-slate-700 focus:outline-none focus:border-orange-500 transition-colors"
          />
        </div>
      </div>

      {/* Category Pills */}
      <div className="flex gap-2 px-4 py-4 overflow-x-auto scrollbar-hide">
        {allCategories.map((cat) => (
          <button
            key={cat}
            onClick={() => setActiveCategory(cat)}
            className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-all flex-shrink-0 ${
              activeCategory === cat
                ? "bg-orange-500 text-white shadow-lg shadow-orange-500/30"
                : "bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700"
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Products Grid */}
      <div className="px-4 pb-32">
        {filtered.length === 0 ? (
          <div className="text-center py-16">
            <div className="text-5xl mb-4">🍕</div>
            <p className="text-slate-400">Nenhum produto encontrado</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {filtered.map((product) => (
              <button
                key={product.id}
                onClick={() => navigate(`/product/${product.id}`)}
                className="bg-slate-800 rounded-2xl p-4 border border-slate-700 hover:border-orange-500/40 transition-all active:scale-95 text-left"
              >
                <div className="w-full aspect-square rounded-xl bg-slate-700 flex items-center justify-center text-5xl mb-3">
                  {product.icon}
                </div>
                <h3 className="text-white font-semibold text-sm leading-tight line-clamp-1">
                  {product.name}
                </h3>
                <div className="flex items-center gap-1 mt-1">
                  <Star size={10} className="fill-yellow-400 text-yellow-400" />
                  <span className="text-slate-400 text-xs">{product.rating?.toFixed(1) ?? "4.5"}</span>
                </div>
                <p className="text-slate-500 text-xs mt-1 line-clamp-2 leading-tight">
                  {product.description}
                </p>
                <div className="flex items-center justify-between mt-3">
                  <span className="text-orange-500 font-bold text-sm">
                    R$ {product.price.toFixed(2)}
                  </span>
                  <div className="w-7 h-7 rounded-full bg-orange-500 flex items-center justify-center">
                    <Plus size={14} className="text-white" />
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      <BottomNav />
    </div>
  );
}
