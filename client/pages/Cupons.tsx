import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft, Copy, Check, Tag } from "lucide-react";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import { useApp, Coupon } from "@/context/AppContext";

const typeColor = (type: Coupon["type"]) => {
  if (type === "percentage") return "bg-gold/20 text-gold-light border-gold/40";
  return "bg-green-500/20 text-green-400 border-green-500/40";
};

export default function Cupons() {
  const navigate = useNavigate();
  const { coupons } = useApp();
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "available" | "used">("all");

  const handleCopy = (coupon: Coupon) => {
    navigator.clipboard.writeText(coupon.code).catch(() => {});
    setCopiedId(coupon.id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const filtered = coupons.filter((c) => {
    if (filter === "available") return !c.used;
    if (filter === "used") return c.used;
    return true;
  });

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00">

      {/* Header */}
      <div className="bg-brand-dark px-4 py-3 flex justify-between items-center sticky top-0 z-30">
        <button onClick={() => navigate(-1)} className="text-parchment hover:text-cream transition-colors">
          <ChevronLeft size={24} />
        </button>
        <MoschettieriLogo className="text-cream text-base" />
        <div className="w-6"></div>
      </div>

      <div className="px-4 pt-6 pb-32 space-y-6">
        {/* Summary Banner */}
        <div className="bg-gradient-to-r from-orange-500 to-orange-600 rounded-2xl p-5 flex items-center gap-4 shadow-lg">
          <Tag size={40} className="text-cream/80 flex-shrink-0" />
          <div>
            <p className="text-orange-100 text-sm">Cupons disponíveis</p>
            <p className="text-cream text-3xl font-bold">{coupons.filter((c) => !c.used).length}</p>
            <p className="text-orange-100 text-xs mt-1">Use no checkout para economizar</p>
          </div>
        </div>

        {/* Filter Tabs */}
        <div className="flex gap-2">
          {(["all", "available", "used"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`flex-1 py-2 rounded-full text-sm font-medium transition-all ${filter === f ? "bg-gold text-cream" : "bg-surface-02 text-parchment hover:bg-surface-03"}`}
            >
              {f === "all" ? "Todos" : f === "available" ? "Disponíveis" : "Usados"}
            </button>
          ))}
        </div>

        {/* Coupon List */}
        <div className="space-y-4">
          {filtered.map((coupon) => (
            <div key={coupon.id} className={`rounded-2xl border overflow-hidden ${coupon.used ? "opacity-50 border-surface-03" : "border-surface-03"}`}>
              {/* Coupon Top */}
              <div className={`flex items-center gap-4 p-4 ${coupon.used ? "bg-surface-02/60" : "bg-surface-02"}`}>
                <div className="w-14 h-14 rounded-full bg-surface-03 flex items-center justify-center text-3xl flex-shrink-0">
                  {coupon.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-cream font-bold text-sm">{coupon.description}</p>
                  <div className={`inline-block mt-1 px-2 py-0.5 rounded-full text-xs border ${typeColor(coupon.type)}`}>
                    {coupon.discount}
                  </div>
                </div>
              </div>

              {/* Coupon Divider */}
              <div className="flex items-center px-4">
                <div className="w-4 h-4 rounded-full bg-brand-dark -ml-6 flex-shrink-0" />
                <div className="flex-1 border-t border-dashed border-surface-03 mx-2" />
                <div className="w-4 h-4 rounded-full bg-brand-dark -mr-6 flex-shrink-0" />
              </div>

              {/* Coupon Bottom */}
              <div className={`flex items-center justify-between px-4 py-3 ${coupon.used ? "bg-surface-02/60" : "bg-surface-02"}`}>
                <div>
                  <p className="text-stone text-xs">Código</p>
                  <p className="text-gold-light font-bold tracking-widest text-sm">{coupon.code}</p>
                </div>
                <div className="text-right mr-4">
                  <p className="text-stone text-xs">Válido até</p>
                  <p className="text-cream text-sm font-medium">{coupon.expiry}</p>
                </div>
                {coupon.used ? (
                  <span className="text-xs text-stone/70 bg-surface-03 px-3 py-2 rounded-full">Usado</span>
                ) : (
                  <button
                    onClick={() => handleCopy(coupon)}
                    className="flex items-center gap-1 bg-gold hover:bg-gold/90 text-cream text-xs font-bold px-3 py-2 rounded-full transition-colors active:scale-95"
                  >
                    {copiedId === coupon.id ? (
                      <><Check size={14} />Copiado</>
                    ) : (
                      <><Copy size={14} />Copiar</>
                    )}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        {filtered.length === 0 && (
          <div className="text-center py-16">
            <span className="text-6xl">🎟️</span>
            <p className="text-cream font-bold mt-4 text-lg">Nenhum cupom aqui</p>
            <p className="text-stone text-sm mt-2">Acumule pontos no programa de fidelidade para ganhar cupons.</p>
          </div>
        )}
      </div>
    </div>
  );
}
