import { Camera, Loader2, Save } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { productionVisionApi, type ProductionVisionCaptureConfig, type ProductionVisionStation } from "@/lib/productionVision";

export default function ProductionCaptureRulesPanel({ stations }: { stations: ProductionVisionStation[] }) {
  const options = useMemo(() => stations.map((station) => ({ id: station.id, label: station.name || station.id })), [stations]);
  const [rules, setRules] = useState<Record<string, ProductionVisionCaptureConfig>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => { let active = true; setLoading(true); void Promise.all(options.map((option) => productionVisionApi.getCaptureConfig(option.id))).then((configs) => { if (active) setRules(Object.fromEntries(configs.map((config) => [config.station_id, config]))); }).catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "Não foi possível carregar as regras."); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, [options]);
  const update = (stationId: string, patch: Partial<ProductionVisionCaptureConfig>) => setRules((current) => ({ ...current, [stationId]: { ...current[stationId], ...patch, station_id: stationId } as ProductionVisionCaptureConfig }));
  const save = async () => { setSaving(true); setError(""); try { await Promise.all(Object.values(rules).map((rule) => productionVisionApi.updateCaptureConfig(rule))); setSaved(true); window.setTimeout(() => setSaved(false), 1800); } catch (cause) { setError(cause instanceof Error ? cause.message : "Não foi possível salvar as regras."); } finally { setSaving(false); } };
  return <section className="rounded-xl border border-surface-03 bg-surface-01 p-4" aria-label="Regras de captura por estação">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><Camera className="text-gold" size={22} /><h2 className="mt-3 text-lg font-black text-cream">Captura por estação</h2><p className="mt-1 max-w-3xl text-sm text-stone">Configure o tempo de cada foto. Zero segundos deixa o marco para acionamento manual.</p></div><button type="button" onClick={() => void save()} disabled={loading || saving} className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-gold px-3 text-sm font-black text-zinc-950 disabled:opacity-50">{saving ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}{saved ? "Salvo" : "Salvar regras"}</button></div>
    {error && <p role="alert" className="mt-3 text-sm text-red-200">{error}</p>}
    {loading ? <p className="mt-4 text-sm text-stone">Carregando regras...</p> : <div className="mt-4 grid gap-3 lg:grid-cols-2">{options.map((option) => { const rule = rules[option.id]; if (!rule) return null; return <div key={option.id} className="rounded-lg border border-surface-03 p-3"><div className="flex items-center justify-between gap-3"><strong className="text-cream">{option.label}</strong><label className="flex items-center gap-2 text-xs text-stone"><input type="checkbox" checked={rule.enabled} onChange={(event) => update(option.id, { enabled: event.target.checked })} /> Ativo</label></div><div className="mt-3 grid grid-cols-3 gap-2 text-xs text-stone">{([1, 2, 3] as const).map((index) => <label key={index} className="block">Foto {index} (s)<input className="mt-1 w-full rounded-lg border border-surface-03 bg-surface-02 px-2 py-2 text-cream" type="number" min="0" max="86400" value={rule[`milestone_${index}_seconds`]} onChange={(event) => update(option.id, { [`milestone_${index}_seconds`]: Number(event.target.value) })} /></label>)}</div></div>; })}</div>}
  </section>;
}
