import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw, Search } from "lucide-react";
import { AuditLogTimeline } from "@/components/platform/PlatformComponents";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  platformAuditApi,
  type ApiPlatformAuditLog,
  type ApiPlatformPage,
} from "@/lib/api";

const EMPTY: ApiPlatformPage<ApiPlatformAuditLog> = { items: [], total: 0, page: 1, page_size: 30, pages: 0 };

export default function PlatformAudit() {
  const [data, setData] = useState(EMPTY);
  const [page, setPage] = useState(1);
  const [tenantId, setTenantId] = useState("");
  const [action, setAction] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await platformAuditApi.list({
        page,
        page_size: 30,
        tenant_id: tenantId.trim() || undefined,
        action: action.trim() || undefined,
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel carregar a auditoria.");
    } finally { setLoading(false); }
  }, [action, page, tenantId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), tenantId || action ? 300 : 0);
    return () => window.clearTimeout(timer);
  }, [action, load, tenantId]);

  return (
    <div className="space-y-5">
      <div className="grid gap-3 rounded-2xl border border-surface-03 bg-surface-02 p-4 md:grid-cols-2">
        <div className="relative"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone" /><Input value={tenantId} onChange={(event) => { setTenantId(event.target.value); setPage(1); }} placeholder="Filtrar por tenant_id" className="border-surface-03 bg-surface-01 pl-9 text-cream" /></div>
        <Input value={action} onChange={(event) => { setAction(event.target.value); setPage(1); }} placeholder="Filtrar por acao exata" className="border-surface-03 bg-surface-01 text-cream" />
      </div>
      {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">{error}<Button variant="ghost" size="sm" className="ml-3 gap-1" onClick={() => void load()}><RefreshCw size={13} /> Repetir</Button></div>}
      <section className="rounded-2xl border border-surface-03 bg-surface-02 p-5">
        <div className="mb-5 flex items-center justify-between"><div><h2 className="font-black text-cream">Eventos de auditoria</h2><p className="mt-1 text-xs text-stone">{data.total} evento(s)</p></div>{loading && <Loader2 size={17} className="animate-spin text-gold" />}</div>
        {!loading && <AuditLogTimeline items={data.items} />}
        <div className="mt-5 flex items-center justify-between border-t border-surface-03 pt-4 text-sm"><span className="text-stone">Pagina {data.page} de {Math.max(1, data.pages)}</span><div className="flex gap-2"><Button variant="outline" size="sm" disabled={loading || page <= 1} onClick={() => setPage((current) => current - 1)}>Anterior</Button><Button variant="outline" size="sm" disabled={loading || page >= data.pages} onClick={() => setPage((current) => current + 1)}>Proxima</Button></div></div>
      </section>
    </div>
  );
}
