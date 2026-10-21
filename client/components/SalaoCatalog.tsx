import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { productsApi, isAssetUrl, resolveOptimizedAssetUrl, type ApiProduct } from "@/lib/api";

export default function SalaoCatalog() {
  const [products, setProducts] = useState<ApiProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try { setProducts(await productsApi.list(true, undefined, "dine_in")); }
    catch { setError("Nao foi possivel carregar o cardapio do salao."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  return <main className="min-h-screen bg-surface-01 px-4 py-8 text-cream">
    <div className="mx-auto max-w-5xl">
      <Link to="/" className="text-gold underline">Voltar ao salao</Link>
      <h1 className="my-6 text-3xl font-bold">Cardapio do salao</h1>
      {loading && <p role="status">Carregando cardapio...</p>}
      {error && <p role="alert">{error} <button className="text-gold underline" onClick={() => { void load(); }}>Tentar novamente</button></p>}
      {!loading && !error && products.length === 0 && <p>Nenhum produto disponivel no momento.</p>}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{products.map((product) => <article key={product.id} className="rounded-xl border border-surface-03 bg-surface-02 p-4">
        {isAssetUrl(product.icon) && <img src={resolveOptimizedAssetUrl(product.icon, 480)} alt="" className="mb-3 aspect-video w-full rounded-lg object-cover" loading="lazy" />}
        <p className="text-xs text-stone">{product.subcategory || product.category || "Produtos"}</p>
        <h2 className="text-xl font-bold">{product.name}</h2>
        <p className="my-2 text-sm text-stone">{product.description}</p>
        <p className="font-bold text-gold">R$ {(product.current_price ?? product.dine_in_price ?? product.price).toFixed(2)}</p>
        {(product.sizes ?? []).filter((size) => size.active).map((size) => <p key={size.id} className="mt-1 text-sm">{size.label}: R$ {size.price.toFixed(2)}</p>)}
        {(product.drink_variants ?? []).filter((variant) => variant.active).map((variant) => <p key={variant.id} className="mt-1 text-sm">{variant.name}{variant.price_addition ? ` (+ R$ ${variant.price_addition.toFixed(2)})` : ""}</p>)}
        {product.inventory_available === false && <p className="mt-2 text-amber-300">Indisponivel no momento</p>}
      </article>)}</div>
    </div>
  </main>;
}
