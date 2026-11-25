import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ShoppingCart, Package } from "lucide-react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { campaignsApi, isAssetUrl, productsApi, resolveOptimizedAssetUrl, type ApiProduct, type ApiPromotionalKit } from "@/lib/api";
import { useApp, type CartKitMeta } from "@/context/AppContext";
import BottomNav from "@/components/BottomNav";
import MoschettieriLogo from "@/components/MoschettieriLogo";

interface ComboProps {
  kitId?: string;
}

export default function Combo({ kitId }: ComboProps) {
  const { slug } = useParams<{ slug: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { addToCart } = useApp();
  const [combo, setCombo] = useState<ApiPromotionalKit | null>(null);
  const [products, setProducts] = useState<ApiProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    const lookup = kitId || slug;
    if (!lookup) return;
    const loadKit = kitId ? campaignsApi.getKitById(kitId) : campaignsApi.getKitBySlug(slug!);
    loadKit.then(async (kit) => {
      const loaded = await Promise.all(kit.items.map((item) => productsApi.get(item.product_id).catch(() => null)));
      if (loaded.some((product) => !product)) {
        setLoadError(true);
        setCombo(null);
        setProducts([]);
        return;
      }
      setCombo(kit);
      setProducts(loaded as ApiProduct[]);
    }).catch(() => {
      setLoadError(true);
      setCombo(null);
      setProducts([]);
    }).finally(() => setLoading(false));
  }, [kitId, slug]);

  const productMap = useMemo(() => new Map(products.map((product) => [product.id, product])), [products]);
  const originalTotal = combo?.price_original || 0;
  const promotionalTotal = combo?.price_promotional || originalTotal;

  const buyCombo = () => {
    if (!combo || products.length !== combo.items.length || combo.items.some((item) => !productMap.has(item.product_id))) return;
    const kit: CartKitMeta = {
      instanceId: `kit-${combo.id}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      id: combo.id,
      name: combo.name,
      components: combo.items.map((item) => {
        const product = productMap.get(item.product_id)!;
        return { productId: product.id, name: product.name, icon: product.icon, quantity: item.quantity };
      }),
    };
    const primary = products[0];
    const strategicOfferId = searchParams.get("strategic_offer_id");
    addToCart(primary, 1, "Combo", [], [{ productId: primary.id, name: primary.name, price: primary.price, icon: primary.icon }], 1, promotionalTotal, undefined, undefined, undefined, undefined, undefined, undefined, undefined, kit, strategicOfferId ? { offerId: strategicOfferId } : undefined);
    navigate("/cart");
  };

  if (loading) return <div className="min-h-screen bg-surface-00 flex items-center justify-center text-gold">Carregando combo...</div>;
  if (!combo) return <div className="min-h-screen bg-surface-00 flex flex-col items-center justify-center gap-4 text-cream"><p>{loadError ? "Não foi possível carregar todos os itens do combo." : "Combo indisponível."}</p><button className="text-gold" onClick={() => navigate("/promocoes")}>Voltar</button></div>;

  return <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00 pb-24">
    <header className="bg-brand-dark px-4 py-3 flex items-center justify-between sticky top-0 z-30 border-b border-surface-02">
      <button onClick={() => navigate(-1)} aria-label="Voltar" className="text-parchment"><ChevronLeft size={24} /></button>
      <button onClick={() => navigate("/")} aria-label="Ir para a home"><MoschettieriLogo className="text-cream text-base scale-[1.31] origin-center" /></button><div className="w-6" />
    </header>
    {combo.image_url && <img src={isAssetUrl(combo.image_url) ? resolveOptimizedAssetUrl(combo.image_url, 960) : combo.image_url} alt={combo.name} className="w-full max-h-72 object-cover" />}
    {combo.video_url && <video src={combo.video_url} controls className="w-full max-h-72 object-cover" />}
    <main className="px-4 pt-6 max-w-lg mx-auto">
      <div className="flex items-center gap-2"><Package className="text-gold" size={20} /><h1 className="text-2xl font-bold text-cream">{combo.name}</h1></div>
      {combo.description && <p className="text-stone mt-2">{combo.description}</p>}
      <div className="mt-5 space-y-3">{combo.items.map((item) => { const product = productMap.get(item.product_id); return product ? <div key={item.id} className="flex items-center gap-3 rounded-xl bg-surface-02 p-3 border border-surface-03"><div className="w-14 h-14 rounded-lg overflow-hidden bg-surface-03 flex items-center justify-center">{isAssetUrl(product.icon) ? <img src={resolveOptimizedAssetUrl(product.icon, 160)} alt="" className="w-full h-full object-contain" /> : <span className="text-2xl">{product.icon}</span>}</div><span className="text-cream flex-1">{item.quantity}x {product.name}</span></div> : null; })}</div>
      <div className="mt-6 rounded-2xl bg-surface-02 p-4"><p className="text-stone text-sm">De R$ {originalTotal.toFixed(2)}</p><p className="text-gold text-2xl font-bold">R$ {promotionalTotal.toFixed(2)}</p><button onClick={buyCombo} className="mt-4 w-full rounded-xl bg-gold py-3 font-bold text-cream inline-flex justify-center items-center gap-2"><ShoppingCart size={18} /> Comprar combo</button></div>
    </main><BottomNav />
  </div>;
}
