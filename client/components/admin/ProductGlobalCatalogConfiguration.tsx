import { useEffect, useMemo, useState } from "react";
import { Check, Loader2, Settings2, X } from "lucide-react";
import {
  ApiGlobalCatalogItem,
  globalCatalogApi,
  productCatalogConfigurationApi,
  ApiProductCatalogConfiguration,
} from "@/lib/api";

type CatalogKey = "sizes" | "dough_types" | "crusts";
type Draft = Record<CatalogKey, string[]>;

const EMPTY_DRAFT: Draft = { sizes: [], dough_types: [], crusts: [] };
const labels: Record<CatalogKey, string> = {
  sizes: "Tamanhos globais",
  dough_types: "Massas globais",
  crusts: "Bordas globais",
};

const toDraft = (configuration: Partial<ApiProductCatalogConfiguration>): Draft => ({
  sizes: configuration.sizes ?? [],
  dough_types: configuration.dough_types ?? [],
  crusts: configuration.crusts ?? [],
});

export default function ProductGlobalCatalogConfiguration({
  productId,
  productName,
  onClose,
}: {
  productId: string;
  productName: string;
  onClose: () => void;
}) {
  const [catalog, setCatalog] = useState<Record<CatalogKey, ApiGlobalCatalogItem[]>>({ sizes: [], dough_types: [], crusts: [] });
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [sizePrices, setSizePrices] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [contractUnavailable, setContractUnavailable] = useState(false);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      setError("");
      setSuccess("");
      try {
        const [sizes, doughTypes, crusts] = await Promise.all([
          globalCatalogApi.sizes.list(),
          globalCatalogApi.doughTypes.list(),
          globalCatalogApi.crusts.list(),
        ]);
        if (!mounted) return;
        setCatalog({ sizes, dough_types: doughTypes, crusts });
        try {
          const configuration = await productCatalogConfigurationApi.get(productId);
          if (mounted) { setDraft(toDraft(configuration)); setSizePrices(configuration.size_prices ?? {}); }
        } catch (cause) {
          if (!mounted) return;
          setContractUnavailable(true);
          setError(cause instanceof Error ? cause.message : "O contrato de associação ainda não está disponível no backend.");
        }
      } catch (cause) {
        if (mounted) setError(cause instanceof Error ? cause.message : "Não foi possível carregar os cadastros globais.");
      } finally {
        if (mounted) setLoading(false);
      }
    };
    void load();
    return () => { mounted = false; };
  }, [productId]);

  const activeCatalog = useMemo(() => ({
    sizes: catalog.sizes.filter((item) => item.active),
    dough_types: catalog.dough_types.filter((item) => item.active),
    crusts: catalog.crusts.filter((item) => item.active),
  }), [catalog]);
  const invalidSizePrice = draft.sizes.some((id) => !(sizePrices[id] > 0));

  const toggle = (key: CatalogKey, id: string) => {
    setDraft((current) => ({
      ...current,
      [key]: current[key].includes(id) ? current[key].filter((item) => item !== id) : [...current[key], id],
    }));
    setSuccess("");
  };

  const save = async () => {
    if (invalidSizePrice) { setError("Informe um preço válido para cada tamanho selecionado."); return; }
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await productCatalogConfigurationApi.update(productId, { ...draft, size_prices: sizePrices });
      setSuccess("Configuração do produto salva.");
      setContractUnavailable(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Não foi possível salvar a configuração.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm" onClick={onClose}>
      <section className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-surface-03 bg-surface-02 shadow-2xl" onClick={(event) => event.stopPropagation()}>
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-surface-03 bg-surface-02 px-6 py-4">
          <div className="flex items-center gap-3"><Settings2 className="text-gold" size={18} /><div><h2 className="font-bold text-cream">Catálogo global do produto</h2><p className="text-xs text-stone">{productName}</p></div></div>
          <button type="button" onClick={onClose} aria-label="Fechar" className="text-stone hover:text-cream"><X size={20} /></button>
        </header>
        <div className="space-y-5 p-6">
          <p className="rounded-xl border border-gold/20 bg-gold/10 p-3 text-xs text-parchment">Selecione quais cadastros globais ficam disponíveis nesta pizza. Isso não altera os tamanhos, massas ou bordas legados já cadastrados.</p>
          {loading ? <div className="flex items-center justify-center gap-2 py-10 text-stone"><Loader2 className="animate-spin" size={18} /> Carregando configurações...</div> : (Object.keys(labels) as CatalogKey[]).map((key) => (
            <div key={key} className="rounded-xl border border-surface-03 bg-surface-01 p-4">
              <h3 className="mb-3 text-sm font-bold text-cream">{labels[key]}</h3>
              {activeCatalog[key].length === 0 ? <p className="text-xs text-stone">Nenhum cadastro global ativo.</p> : <div className="grid gap-2 sm:grid-cols-2">{activeCatalog[key].map((item) => <label key={item.id} className="flex cursor-pointer items-center gap-2 rounded-lg bg-surface-03 px-3 py-2 text-sm text-parchment"><input type="checkbox" checked={draft[key].includes(item.id)} onChange={() => toggle(key, item.id)} disabled={contractUnavailable} className="accent-gold" /><span className="min-w-0 flex-1">{item.name}</span>{key === "sizes" ? <input aria-label={`Preço de ${item.name}`} type="number" min="0.01" step="0.01" value={sizePrices[item.id] ?? ""} onChange={(event) => setSizePrices((current) => ({ ...current, [item.id]: Number(event.target.value) }))} disabled={!draft[key].includes(item.id) || contractUnavailable} className="w-24 rounded bg-surface-01 px-2 py-1 text-right text-xs text-cream" /> : <span className="text-xs text-stone">+ R$ {(item.price_addition ?? 0).toFixed(2)}</span>}</label>)}</div>}
            </div>
          ))}
          {error && <div role="alert" className="rounded-xl border border-red-400/30 bg-red-500/10 p-3 text-sm text-red-200">{contractUnavailable ? "A associação por produto ainda não está disponível no backend. Os cadastros globais continuam preservados; nenhuma alteração foi aplicada." : error}</div>}
          {success && <div role="status" className="flex items-center gap-2 text-sm text-emerald-300"><Check size={16} /> {success}</div>}
          <div className="flex justify-end gap-2 border-t border-surface-03 pt-4"><button type="button" onClick={onClose} className="rounded-lg px-4 py-2 text-sm text-stone hover:text-cream">Fechar</button><button type="button" onClick={() => void save()} disabled={loading || saving || contractUnavailable || invalidSizePrice} className="flex items-center gap-2 rounded-lg bg-gold px-5 py-2 text-sm font-bold text-cream disabled:cursor-not-allowed disabled:opacity-50">{saving ? <Loader2 className="animate-spin" size={16} /> : <Check size={16} />}Salvar configuração</button></div>
        </div>
      </section>
    </div>
  );
}
