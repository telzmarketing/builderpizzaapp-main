import { useEffect, useRef, useState, type FormEvent } from "react";
import { inventoryFoundationApi as api, type FoundationUnit } from "@/lib/api";

const input = "w-full rounded border border-surface-03 bg-surface-01 p-2 text-cream";
const button = "rounded bg-gold px-3 py-2 font-bold text-black disabled:opacity-50";

const emptyDefinition = {
  id: "",
  name: "",
  symbol: "",
  code: "",
  dimension: "mass",
  conversion_factor: "1",
};

const decimal = (value: string) => value.trim().replace(",", ".");

export default function InventoryUnitClassificationPanel() {
  const [units, setUnits] = useState<FoundationUnit[]>([]);
  const [definition, setDefinition] = useState(emptyDefinition);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const mounted = useRef(true);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const result = await api.units();
      if (mounted.current) setUnits(result.items);
    } catch (caught) {
      if (mounted.current) setError(caught instanceof Error ? caught.message : "Falha ao carregar unidades.");
    } finally {
      if (mounted.current) setLoading(false);
    }
  };

  useEffect(() => {
    mounted.current = true;
    void load();
    return () => {
      mounted.current = false;
    };
  }, []);

  const selectedUnit = units.find((row) => row.id === definition.id);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    setError("");
    setMessage("");
    const method = definition.id ? "PUT" : "POST";
    const resource = definition.id ? `units/${definition.id}` : "units";
    try {
      await api.command(
        resource,
        {
          ...definition,
          id: undefined,
          conversion_factor: decimal(definition.conversion_factor),
          expected_version: selectedUnit?.version ?? 0,
        },
        crypto.randomUUID(),
        method,
      );
      setMessage("Unidade confirmada.");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Falha ao salvar unidade.");
    } finally {
      if (mounted.current) setSaving(false);
    }
  };

  const selectUnit = (id: string) => {
    const row = units.find((unit) => unit.id === id);
    setDefinition(row ? {
      id: row.id,
      name: row.name,
      symbol: row.symbol,
      code: row.code || "",
      dimension: row.dimension || "mass",
      conversion_factor: row.conversion_factor || "1",
    } : emptyDefinition);
  };

  return (
    <form className="space-y-3 rounded-lg border border-surface-03 bg-surface-01 p-4" onSubmit={submit}>
      <h3 className="font-bold text-cream">Classificação técnica das unidades</h3>
      <p className="text-sm text-stone">Classifique a unidade de compra para permitir conversões como KG → GR. O peso por embalagem só é necessário para pacotes, caixas ou unidades.</p>
      {loading ? <p className="text-sm text-stone">Carregando unidades...</p> : <>
        <select aria-label="Unidade a classificar" className={input} value={definition.id} onChange={(event) => selectUnit(event.target.value)}>
          <option value="">Nova unidade</option>
          {units.map((row) => <option key={row.id} value={row.id}>{row.name} ({row.symbol}){row.dimension ? "" : " - classificação pendente"}</option>)}
        </select>
        {(["name", "symbol", "code", "conversion_factor"] as const).map((field) => (
          <label key={field} className="block text-sm text-stone">
            {{ name: "Nome", symbol: "Sigla", code: "Código único", conversion_factor: "Fator de conversão" }[field]}
            <input required className={input} value={definition[field]} onChange={(event) => setDefinition({ ...definition, [field]: event.target.value })} />
          </label>
        ))}
        <label className="block text-sm text-stone">Dimensão
        <select aria-label="Dimensão" className={input} value={definition.dimension} onChange={(event) => setDefinition({ ...definition, dimension: event.target.value })}>
          <option value="mass">Massa (kg)</option>
          <option value="volume">Volume (L)</option>
          <option value="count">Contagem (unidade)</option>
        </select></label>
        <p className="text-xs text-stone">Use fator 1 para a unidade de referência (KG) e 0,001 para gramas (GR).</p>
        <button className={button} disabled={saving}>{saving ? "Salvando..." : "Confirmar unidade"}</button>
      </>}
      {message && <p role="status" className="text-sm text-emerald-300">{message}</p>}
      {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
    </form>
  );
}
