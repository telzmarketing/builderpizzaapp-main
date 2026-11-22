import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Download, Printer, RefreshCw, Server } from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";
import { printServerApi, type ApiPrintServerAgentRelease, type ApiPrintServerOverview } from "@/lib/api";

const empty: ApiPrintServerOverview = { summary: { stations_online: 0, stations_total: 0, printers_ready: 0, printers_total: 0, pending_jobs: 0, failed_jobs: 0 }, stations: [], printers: [], rules: [], queue: [] };

function Metric({ label, value, detail }: { label: string; value: number; detail: string }) {
  return <div className="rounded-2xl border border-surface-03 bg-surface-02 p-5"><p className="text-xs uppercase tracking-wide text-stone">{label}</p><p className="mt-2 text-3xl font-bold text-cream">{value}</p><p className="mt-1 text-xs text-stone">{detail}</p></div>;
}

export default function PrintServer() {
  const [overview, setOverview] = useState(empty);
  const [release, setRelease] = useState<ApiPrintServerAgentRelease | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [pairing, setPairing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [nextOverview, nextRelease] = await Promise.all([printServerApi.overview(), printServerApi.agentRelease()]);
      setOverview(nextOverview); setRelease(nextRelease);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Não foi possível carregar a Central de Impressão."); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const download = async () => {
    setDownloading(true); setError(null);
    try {
      const result = await printServerApi.downloadAgentInstaller();
      const url = URL.createObjectURL(result.blob);
      const anchor = document.createElement("a"); anchor.href = url; anchor.download = result.fileName; anchor.click(); URL.revokeObjectURL(url);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "O instalador ainda não está disponível."); }
    finally { setDownloading(false); }
  };

  const createPairingCode = async (stationId: string) => {
    setPairing(null); setError(null);
    try { const result = await printServerApi.createPairingCode(stationId); setPairing(`Código de pareamento: ${result.code} (válido por ${result.expires_in_minutes} min)`); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Não foi possível gerar o código de pareamento."); }
  };

  return <div className="min-h-screen bg-surface-00"><div className="flex min-h-screen flex-col md:flex-row"><AdminSidebar /><main className="min-w-0 flex-1 overflow-auto"><header className="flex items-center justify-between border-b border-surface-03 bg-surface-02 px-5 py-4 sm:px-8"><div className="flex items-center gap-3"><Printer className="text-gold" size={22} /><div><h1 className="text-xl font-bold text-cream sm:text-2xl">Central de Impressão</h1><p className="text-sm text-stone">Agente Windows, estações e fila de trabalhos</p></div></div><AdminTopActions /></header><div className="mx-auto max-w-7xl space-y-6 p-5 sm:p-8">
    {error && <div role="alert" className="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200"><AlertTriangle size={16} />{error}</div>}
    {pairing && <div role="status" className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm font-semibold text-emerald-200">{pairing}</div>}
    <section className="rounded-2xl border border-gold/30 bg-surface-02 p-6"><div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between"><div className="flex gap-4"><div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-gold/40 bg-gold/10 text-gold"><Server size={22} /></div><div><div className="flex flex-wrap items-center gap-2"><h2 className="font-bold text-cream">Agente Windows</h2><span className={`rounded-full border px-2 py-1 text-[11px] font-semibold ${release?.available ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200" : "border-surface-03 text-stone"}`}>{release?.available ? `Disponível${release.version ? ` · v${release.version}` : ""}` : "Instalador indisponível"}</span></div><p className="mt-1 max-w-2xl text-sm text-stone">Instale o Gran Torino Print Service no computador conectado às impressoras. Ele funciona em segundo plano, pareia com o ERP e imprime sem abrir diálogo do navegador.</p>{release?.available && <p className="mt-3 text-xs text-stone">{release.min_windows_version || "Windows 10 ou superior"}{release.size_bytes ? ` · ${(release.size_bytes / 1024 / 1024).toFixed(1)} MB` : ""}{release.sha256 ? ` · SHA-256 ${release.sha256}` : ""}</p>}</div></div><button type="button" onClick={() => void download()} disabled={!release?.available || downloading} className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-gold px-4 py-2.5 text-sm font-bold text-surface-00 disabled:cursor-not-allowed disabled:opacity-50"><Download size={16} />{downloading ? "Baixando…" : "Baixar instalador"}</button></div><div className="mt-5 grid gap-2 text-xs text-stone sm:grid-cols-3"><span>1. Baixe e instale o serviço</span><span>2. Gere um código na estação</span><span>3. Informe o código no aplicativo</span></div></section>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Metric label="Estações online" value={overview.summary.stations_online} detail={`de ${overview.summary.stations_total} vinculadas`} /><Metric label="Impressoras prontas" value={overview.summary.printers_ready} detail={`de ${overview.summary.printers_total} cadastradas`} /><Metric label="Trabalhos pendentes" value={overview.summary.pending_jobs} detail="aguardando processamento" /><Metric label="Falhas na fila" value={overview.summary.failed_jobs} detail="requerem acompanhamento" /></div>
    <section className="rounded-2xl border border-surface-03 bg-surface-02 p-6"><div className="flex items-center justify-between"><div><h2 className="font-bold text-cream">Status do Print Server</h2><p className="text-sm text-stone">Estações e impressoras reportadas pelo agente Windows</p></div><button type="button" onClick={() => void load()} disabled={loading} className="inline-flex items-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm text-parchment disabled:opacity-50"><RefreshCw size={15} className={loading ? "animate-spin" : ""} />Atualizar</button></div><div className="mt-5 overflow-x-auto"><table className="w-full min-w-[780px] text-left text-sm"><thead className="border-b border-surface-03 text-xs uppercase tracking-wide text-stone"><tr><th className="px-3 py-3">Estação</th><th className="px-3 py-3">Host</th><th className="px-3 py-3">Status</th><th className="px-3 py-3">Impressoras</th><th className="px-3 py-3 text-right">Pareamento</th></tr></thead><tbody>{overview.stations.map((station) => <tr key={station.id} className="border-b border-surface-03/70"><td className="px-3 py-3 font-semibold text-cream">{station.name}</td><td className="px-3 py-3 text-stone">{station.hostname || "—"}</td><td className="px-3 py-3"><span className={station.status === "online" ? "text-emerald-300" : "text-amber-200"}>{station.status}</span></td><td className="px-3 py-3 text-parchment">{station.printer_count ?? 0}</td><td className="px-3 py-3 text-right"><button type="button" onClick={() => void createPairingCode(station.id)} className="rounded-lg border border-gold/50 px-3 py-2 text-xs font-semibold text-gold">Gerar código</button></td></tr>)}{!overview.stations.length && <tr><td colSpan={5} className="px-3 py-8 text-center text-stone">Nenhuma estação pareada ainda.</td></tr>}</tbody></table></div></section>
  </div></main></div></div>;
}
