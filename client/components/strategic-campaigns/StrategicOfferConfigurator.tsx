import { useMemo, useState } from "react";
import { ArrowLeft, Check, Loader2 } from "lucide-react";
import Product from "@/pages/Product";
import type { MultiFlavorsConfig } from "@/context/AppContext";
import {
  buildStrategicOfferSelection,
  configuredStrategicStep,
  type ConfiguredStrategicStep,
  type StrategicOfferConfiguration,
  type StrategicOfferSelection,
} from "@/lib/strategicOfferSelection";
import type { ManualCartLine } from "@/lib/manualOrder";
import { isAssetUrl, resolveOptimizedAssetUrl } from "@/lib/api";

export default function StrategicOfferConfigurator({
  configuration,
  flavorConfig,
  onCancel,
  onComplete,
}: {
  configuration: StrategicOfferConfiguration;
  flavorConfig?: MultiFlavorsConfig | null;
  onCancel: () => void;
  onComplete: (result: {
    selection: StrategicOfferSelection;
    lines: ManualCartLine[];
    configured: ConfiguredStrategicStep[];
    instanceId: string;
  }) => void;
}) {
  const [configured, setConfigured] = useState<ConfiguredStrategicStep[]>([]);
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);
  const [finishing, setFinishing] = useState(false);
  const step = configuration.steps[configured.length];
  const products = useMemo(
    () => (step?.eligible_products ?? []).filter((product) => product.inventory_available !== false),
    [step],
  );

  if (!configuration.steps.length) {
    return (
      <section className="space-y-4 rounded-2xl border border-amber-400/30 bg-surface-01 p-5 text-cream">
        <p role="alert" className="text-amber-200">Esta oferta não possui itens configuráveis disponíveis.</p>
        <button type="button" onClick={onCancel} className="min-h-11 rounded-xl border border-surface-03 px-4 font-bold">Voltar</button>
      </section>
    );
  }

  if (step && selectedProductId) {
    return (
      <Product
        productId={selectedProductId}
        catalog={products}
        flavorConfig={flavorConfig ?? undefined}
        restrictions={step.restrictions as {
          size_ids?: string[];
          crust_ids?: string[];
          border_ids?: string[];
          drink_ids?: string[];
          option_ids?: string[];
          flavor_count?: number;
        } | undefined}
        embedded
        onBack={() => setSelectedProductId(null)}
        onAdd={(...args) => {
          setConfigured((current) => [...current, configuredStrategicStep(step, args)]);
          setSelectedProductId(null);
        }}
      />
    );
  }

  const complete = configured.length === configuration.steps.length;
  return (
    <section className="min-h-0 overflow-y-auto bg-surface-00 p-4 text-cream sm:p-6" aria-label={`Configurar ${configuration.title}`}>
      <div className="mx-auto max-w-5xl space-y-5">
        <div className="flex items-center gap-3">
          <button type="button" onClick={onCancel} aria-label="Voltar às ofertas" className="grid min-h-11 min-w-11 place-items-center rounded-xl border border-surface-03"><ArrowLeft size={18} /></button>
          <div className="min-w-0">
            <p className="text-xs font-black uppercase tracking-widest text-gold">Oferta estratégica</p>
            <h2 className="truncate text-xl font-black">{configuration.title}</h2>
          </div>
        </div>
        <ol className="flex gap-2 overflow-x-auto pb-1" aria-label="Etapas da oferta">
          {configuration.steps.map((item, index) => (
            <li key={item.key} className={`flex min-h-10 shrink-0 items-center gap-2 rounded-full border px-3 text-sm font-bold ${index < configured.length ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-200" : index === configured.length ? "border-gold bg-gold/10 text-gold" : "border-surface-03 text-stone"}`}>
              {index < configured.length ? <Check size={14} /> : index + 1} {item.title}
            </li>
          ))}
        </ol>
        {!complete && step && (
          <div>
            <p className="mb-3 text-sm text-stone">Etapa {configured.length + 1} de {configuration.steps.length}: escolha um produto de <strong className="text-cream">{step.title}</strong>.</p>
            {products.length ? (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                {products.map((product) => (
                  <button key={product.id} type="button" onClick={() => setSelectedProductId(product.id)} className="min-h-32 rounded-2xl border border-surface-03 bg-surface-01 p-4 text-left transition-colors hover:border-gold">
                    <span className="flex h-24 w-full items-center justify-center overflow-hidden rounded-xl bg-surface-02">
                      {isAssetUrl(product.icon) ? (
                        <img
                          src={resolveOptimizedAssetUrl(product.icon, 240)}
                          alt={product.name}
                          className="h-full w-full object-contain"
                          loading="lazy"
                        />
                      ) : <span className="text-3xl">{product.icon || "🍕"}</span>}
                    </span>
                    <strong className="mt-3 block">{product.name}</strong>
                    <span className="mt-1 block text-xs text-stone">Escolher</span>
                  </button>
                ))}
              </div>
            ) : <p role="alert" className="rounded-xl bg-amber-500/10 p-4 text-amber-200">Nenhum produto elegível nesta etapa.</p>}
          </div>
        )}
        {complete && (
          <div className="rounded-2xl border border-emerald-400/30 bg-emerald-500/10 p-5">
            <h3 className="font-black text-emerald-200">Composição pronta</h3>
            <ul className="mt-3 space-y-2 text-sm">{configured.map(({ line, step: item }) => <li key={item.key}><strong>{item.title}:</strong> {line.name}</li>)}</ul>
            <button type="button" disabled={finishing} onClick={() => {
              setFinishing(true);
              try {
                const result = buildStrategicOfferSelection(configuration, configured);
                onComplete({ ...result, configured });
              } finally {
                setFinishing(false);
              }
            }} className="mt-5 inline-flex min-h-12 items-center gap-2 rounded-xl bg-gold px-5 font-black text-black disabled:opacity-50">
              {finishing && <Loader2 className="animate-spin" size={18} />} Adicionar oferta completa
            </button>
          </div>
        )}
      </div>
    </section>
  );
}

