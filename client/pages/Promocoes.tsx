import { useEffect, useState } from "react";
import { ChevronLeft, Tag, ArrowRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { campaignsApi, isAssetUrl, resolveOptimizedAssetUrl, type ApiCampaign, type ApiPromotionalKit } from "@/lib/api";
import BottomNav from "@/components/BottomNav";
import MoschettieriLogo from "@/components/MoschettieriLogo";

export default function Promocoes() {
  const navigate = useNavigate();
  const [campaigns, setCampaigns] = useState<ApiCampaign[]>([]);
  const [combos, setCombos] = useState<ApiPromotionalKit[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([campaignsApi.list(true), campaignsApi.listKits(true)])
      .then(([campaignList, comboList]) => { setCampaigns(campaignList); setCombos(comboList); })
      .catch(() => setError("Não foi possível carregar as promoções."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00 pb-24">
      <header className="bg-brand-dark px-4 py-3 flex items-center justify-between sticky top-0 z-30 border-b border-surface-02">
        <button onClick={() => navigate(-1)} className="text-parchment hover:text-cream" aria-label="Voltar"><ChevronLeft size={24} /></button>
        <button onClick={() => navigate("/")} aria-label="Ir para a home da loja"><MoschettieriLogo className="text-cream text-base scale-[1.31] origin-center" /></button>
        <div className="w-6" />
      </header>

      <main className="px-4 pt-6 max-w-lg lg:max-w-5xl mx-auto">
        <div className="flex items-center gap-2 mb-5">
          <Tag className="text-gold" size={20} />
          <div>
            <h1 className="text-2xl font-bold text-cream">Promoções</h1>
            <p className="text-stone text-sm">Ofertas disponíveis na loja</p>
          </div>
        </div>

        {loading && <p className="text-stone text-center py-12">Carregando promoções...</p>}
        {!loading && error && <p className="text-red-300 text-center py-12">{error}</p>}
        {!loading && !error && campaigns.length === 0 && <p className="text-stone text-center py-12">Nenhuma promoção disponível no momento.</p>}
        {!loading && !error && campaigns.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2">
            {campaigns.map((campaign) => (
              <button key={campaign.id} onClick={() => navigate(`/campanha/${campaign.slug}`)} className="text-left bg-surface-02 rounded-2xl overflow-hidden border border-surface-03 hover:border-gold/60 transition-colors">
                <div className="h-40 bg-surface-03 relative overflow-hidden">
                  {campaign.banner && isAssetUrl(campaign.banner) ? (
                    <img src={resolveOptimizedAssetUrl(campaign.banner, 640)} alt="" className="w-full h-full object-cover" loading="lazy" />
                  ) : campaign.banner ? (
                    <div className="w-full h-full flex items-center justify-center text-6xl">{campaign.banner}</div>
                  ) : <div className="w-full h-full flex items-center justify-center"><Tag className="text-gold" size={40} /></div>}
                </div>
                <div className="p-4">
                  <h2 className="text-cream font-bold text-lg">{campaign.display_title || campaign.name}</h2>
                  {(campaign.display_subtitle || campaign.description) && <p className="text-stone text-sm mt-1 line-clamp-2">{campaign.display_subtitle || campaign.description}</p>}
                  <span className="text-gold text-sm font-semibold mt-3 inline-flex items-center gap-1">Ver promoção <ArrowRight size={15} /></span>
                </div>
              </button>
            ))}
          </div>
        )}
        {!loading && !error && combos.length > 0 && <>
          <h2 className="text-cream text-xl font-bold mt-8 mb-4">Combos</h2>
          <div className="grid gap-4 sm:grid-cols-2">{combos.map((combo) => <button key={combo.id} onClick={() => navigate(`/combo/${combo.slug}`)} className="text-left bg-surface-02 rounded-2xl overflow-hidden border border-surface-03 hover:border-gold/60 transition-colors">
            <div className="h-40 bg-surface-03 relative overflow-hidden">{combo.image_url && isAssetUrl(combo.image_url) ? <img src={resolveOptimizedAssetUrl(combo.image_url, 640)} alt="" className="w-full h-full object-cover" /> : <div className="w-full h-full flex items-center justify-center text-6xl">{combo.icon || "🎁"}</div>}</div>
            <div className="p-4"><h3 className="text-cream font-bold text-lg">{combo.name}</h3>{combo.description && <p className="text-stone text-sm mt-1 line-clamp-2">{combo.description}</p>}<span className="text-gold text-sm font-semibold mt-3 inline-flex items-center gap-1">Ver combo <ArrowRight size={15} /></span></div>
          </button>)}</div>
        </>}
      </main>
      <BottomNav />
    </div>
  );
}
