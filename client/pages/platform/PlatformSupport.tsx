import { useCallback, useEffect, useState } from "react";
import { Headphones, Loader2, RefreshCw, Search } from "lucide-react";
import PlatformSupportAccessDialog from "@/components/platform/PlatformSupportAccessDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { platformTenantsApi, type ApiPlatformTenant } from "@/lib/api";

export default function PlatformSupport() {
  const [items, setItems] = useState<ApiPlatformTenant[]>([]);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<ApiPlatformTenant | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await platformTenantsApi.list({
        page: 1,
        page_size: 50,
        q: query.trim() || undefined,
        status: "active",
        sort_by: "name",
        sort_dir: "asc",
      });
      setItems(result.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel carregar as empresas.");
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), query ? 300 : 0);
    return () => window.clearTimeout(timer);
  }, [load, query]);

  return (
    <div className="space-y-5">
      <div className="relative max-w-xl">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-stone" size={15} />
        <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar empresa ativa" className="border-surface-03 bg-surface-02 pl-9 text-cream" />
      </div>
      {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-200">{error}<Button variant="ghost" size="sm" onClick={() => void load()} className="ml-3 gap-2"><RefreshCw size={14} /> Repetir</Button></div>}
      {loading ? <div className="flex min-h-56 items-center justify-center"><Loader2 className="animate-spin text-gold" /></div>
        : !items.length ? <div className="rounded-2xl border border-dashed border-surface-03 p-10 text-center text-stone">Nenhuma empresa ativa encontrada.</div>
          : <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{items.map((tenant) => (
            <article key={tenant.id} className="rounded-2xl border border-surface-03 bg-surface-02 p-5">
              <h2 className="font-black text-cream">{tenant.name}</h2>
              <p className="mt-1 truncate text-xs text-stone">{tenant.id}</p>
              <p className="mt-3 text-sm text-stone">{tenant.primary_domain?.hostname || "Sem dominio principal"}</p>
              <Button onClick={() => setSelected(tenant)} className="mt-4 w-full gap-2 bg-gold text-surface-00 hover:bg-gold/90"><Headphones size={15} /> Iniciar suporte</Button>
            </article>
          ))}</div>}
      {selected && <PlatformSupportAccessDialog open onOpenChange={(open) => { if (!open) setSelected(null); }} tenant={selected} />}
    </div>
  );
}
