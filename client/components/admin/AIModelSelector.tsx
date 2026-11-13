import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { centralAIApi, type ApiAIModel } from "@/lib/api";

type Props = { provider: "internal" | "openai" | "claude"; value: string; onChange: (value: string) => void };
const inputClass = "min-h-10 w-full rounded-lg border border-surface-03 bg-surface-01 px-3 text-sm text-cream outline-none transition focus:border-gold/70";

export default function AIModelSelector({ provider, value, onChange }: Props) {
  const [models, setModels] = useState<ApiAIModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    if (provider === "internal") { setModels([{ id: "internal-rules-v1", name: "Regras internas" }]); setError(""); return; }
    setLoading(true); setError("");
    try { setModels((await centralAIApi.listModels(provider)).models); }
    catch (err) { setModels([]); setError(err instanceof Error ? err.message : "Não foi possível carregar os modelos."); }
    finally { setLoading(false); }
  }, [provider]);
  useEffect(() => { void load(); }, [load]);
  const options = useMemo(() => value && !models.some((model) => model.id === value) ? [{ id: value, name: `${value} (salvo anteriormente)` }, ...models] : models, [models, value]);
  return <div className="space-y-1.5"><div className="flex gap-2"><select className={inputClass} value={value} onChange={(event) => onChange(event.target.value)} disabled={loading}><option value="">{loading ? "Carregando modelos..." : options.length ? "Selecione um modelo" : "Nenhum modelo disponível"}</option>{options.map((model) => <option key={model.id} value={model.id}>{model.name}</option>)}</select>{provider !== "internal" && <button type="button" className="inline-flex min-h-10 shrink-0 items-center justify-center rounded-lg border border-surface-03 bg-surface-03 px-3 text-xs font-bold text-cream disabled:opacity-50" onClick={() => void load()} disabled={loading} title="Atualizar modelos" aria-label="Atualizar modelos"><RefreshCw size={15} className={loading ? "animate-spin" : ""} /></button>}</div>{error && <p role="alert" className="text-[11px] text-red-300">{error}</p>}</div>;
}
