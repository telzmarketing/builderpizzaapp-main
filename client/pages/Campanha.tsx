import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ChevronLeft, ShoppingCart, Clock, Tag } from "lucide-react";
import { campaignsApi, type ApiCampaign, type ApiCampaignProduct, productsApi, type ApiProduct } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import BottomNav from "@/components/BottomNav";
import MoschettieriLogo from "@/components/MoschettieriLogo";

export default function Campanha() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const { addToCart } = useApp();

  const [campaign, setCampaign] = useState<ApiCampaign | null>(null);
  const [campaignProducts, setCampaignProducts] = useState<ApiCampaignProduct[]>([]);
  const [products, setProducts] = useState<ApiProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!slug) return;
    setLoading(true);
    campaignsApi.getBySlug(slug)
      .then(async (c) => {
        setCampaign(c);
        const [cps, prods] = await Promise.all([
          campaignsApi.listProducts(c.id),
          productsApi.list(true),
        ]);
        setCampaignProducts(cps.filter((cp) => cp.active));
        setProducts(prods);
      })
      .catch(() => setError("Campanha não encontrada ou não disponível."))
      .finally(() => setLoading(false));
  }, [slug]);

  const getProduct = (id: string) => products.find((p) => p.id === id);

  const getPrice = (cp: ApiCampaignProduct, product: ApiProduct): number => {
    if (cp.promotional_price !== null && cp.promotional_price !== undefined) return cp.promotional_price;
    if (cp.discount_type === "percentage" && cp.discount_value) {
      return +(product.price * (1 - cp.discount_value / 100)).toFixed(2);
    }
    if (cp.discount_type === "fixed" && cp.discount_value) {
      return Math.max(0, +(product.price - cp.discount_value).toFixed(2));
    }
    return product.price;
  };

  const handleAddToCart = (cp: ApiCampaignProduct) => {
    if (!cp.product_id) return;
    const product = getProduct(cp.product_id);
    if (!product) return;
    const price = getPrice(cp, product);
    addToCart(
      product,
      1,
      "M",
      [],
      [{ productId: product.id, name: product.name, price: product.price, icon: product.icon }],
      1,
      price,
    );
    navigate("/cart");
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-surface-00 flex items-center justify-center">
        <div className="text-gold text-lg animate-pulse">Carregando campanha...</div>
      </div>
    );
  }

  if (error || !campaign) {
    return (
      <div className="min-h-screen bg-surface-00 flex flex-col items-center justify-center gap-4 px-4">
        <div className="text-5xl">😕</div>
        <p className="text-cream text-lg font-bold">Campanha não encontrada</p>
        <p className="text-stone text-sm text-center">{error}</p>
        <button onClick={() => navigate("/")} className="bg-gold hover:bg-gold/90 text-cream font-bold py-3 px-6 rounded-full transition-colors">
          Voltar ao início
        </button>
      </div>
    );
  }

  const productItems = campaignProducts.filter((cp) => cp.product_id);

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00 pb-24">
      {/* Header */}
      <div className="bg-brand-dark px-4 py-3 flex justify-between items-center sticky top-0 z-30">
        <button onClick={() => navigate(-1)} className="text-parchment hover:text-cream transition-colors">
          <ChevronLeft size={24} />
        </button>
        <MoschettieriLogo className="text-cream text-base" />
        <div className="w-6" />
      </div>

      {/* Banner */}
      {campaign.banner && (
        <div className="w-full h-48 overflow-hidden">
          {campaign.banner.startsWith("http") || campaign.banner.startsWith("data:") ? (
            <img src={campaign.banner} alt={campaign.name} className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full bg-gradient-to-br from-gold/20 to-gold/5 flex items-center justify-center text-7xl">
              {campaign.banner}
            </div>
          )}
        </div>
      )}

      <div className="px-4 pt-6">
        {/* Campaign Info */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-cream mb-1">
            {campaign.display_title || campaign.name}
          </h1>
          {campaign.display_subtitle && (
            <p className="text-gold font-medium mb-2">{campaign.display_subtitle}</p>
          )}
          {campaign.description && (
            <p className="text-stone text-sm leading-relaxed">{campaign.description}</p>
          )}

          {(campaign.start_at || campaign.end_at) && (
            <div className="flex items-center gap-2 mt-3 text-xs text-stone">
              <Clock size={12} />
              {campaign.end_at && (
                <span>Válido até {new Date(campaign.end_at).toLocaleDateString("pt-BR")}</span>
              )}
            </div>
          )}
        </div>

        {/* Products in Campaign */}
        {productItems.length > 0 && (
          <>
            <div className="flex items-center gap-2 mb-4">
              <Tag size={16} className="text-gold" />
              <h2 className="text-cream font-bold text-lg">Produtos da Campanha</h2>
            </div>

            <div className="space-y-3">
              {productItems.map((cp) => {
                const product = cp.product_id ? getProduct(cp.product_id) : null;
                if (!product) return null;
                const promoPrice = getPrice(cp, product);
                const hasDiscount = promoPrice < product.price;

                return (
                  <div key={cp.id} className="bg-surface-02 rounded-2xl p-4 border border-surface-03 flex items-center gap-4">
                    <div className="w-14 h-14 rounded-xl bg-surface-03 flex-shrink-0 flex items-center justify-center text-2xl">
                      {product.icon}
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-cream font-semibold text-sm">{product.name}</h3>
                      <p className="text-stone text-xs mt-0.5 line-clamp-1">{product.description}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-gold font-bold text-sm">R$ {promoPrice.toFixed(2)}</span>
                        {hasDiscount && (
                          <span className="text-stone text-xs line-through">R$ {product.price.toFixed(2)}</span>
                        )}
                        {hasDiscount && cp.discount_type === "percentage" && cp.discount_value && (
                          <span className="text-xs bg-green-500/20 text-green-400 px-1.5 py-0.5 rounded-full">
                            -{cp.discount_value}%
                          </span>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={() => handleAddToCart(cp)}
                      className="flex-shrink-0 bg-gold hover:bg-gold/90 text-cream p-2.5 rounded-full transition-colors active:scale-95"
                    >
                      <ShoppingCart size={16} />
                    </button>
                  </div>
                );
              })}
            </div>
          </>
        )}

        {productItems.length === 0 && (
          <div className="text-center py-12">
            <div className="text-5xl mb-4">🎉</div>
            <p className="text-parchment font-medium">Campanha em preparação</p>
            <p className="text-stone text-sm mt-1">Os produtos serão exibidos em breve</p>
          </div>
        )}
      </div>

      <BottomNav />
    </div>
  );
}
