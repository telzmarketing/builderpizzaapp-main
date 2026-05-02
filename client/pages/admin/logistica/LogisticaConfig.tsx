import { useEffect, useState } from "react";
import { Loader2, Save } from "lucide-react";
import { deliveryApi, type LogisticsSettings } from "@/lib/api";

function Toggle({ label, checked, onChange, description }: {
  label: string; checked: boolean; onChange: (v: boolean) => void; description?: string;
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <p className="text-cream text-sm font-medium">{label}</p>
        {description && <p className="text-stone text-xs mt-0.5">{description}</p>}
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors ${
          checked ? "bg-gold" : "bg-surface-03"
        }`}
      >
        <span className={`inline-block h-4 w-4 rounded-full bg-cream shadow transform transition-transform ${
          checked ? "translate-x-6" : "translate-x-1"
        }`} />
      </button>
    </div>
  );
}

export default function LogisticaConfig() {
  const [settings, setSettings] = useState<Partial<LogisticsSettings>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    deliveryApi.getSettings()
      .then((data) => setSettings(data))
      .catch(() => setError("Erro ao carregar configurações."))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    setError("");
    try {
      await deliveryApi.updateSettings(settings);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch {
      setError("Erro ao salvar configurações.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 size={36} className="animate-spin text-gold" />
      </div>
    );
  }

  return (
    <div className="max-w-xl">
      <h3 className="text-cream font-bold text-lg mb-6">Configurações de Logística</h3>

      <div className="rounded-2xl border border-surface-03 bg-surface-02 p-6 space-y-6">
        <Toggle
          label="Atribuição automática"
          description="Atribui automaticamente o motoboy disponível mais próximo ao marcar pedido como pronto"
          checked={settings.auto_assign ?? false}
          onChange={(v) => setSettings((s) => ({ ...s, auto_assign: v }))}
        />

        <div className="border-t border-surface-03" />

        <Toggle
          label="Código de confirmação"
          description="Gera um código de 4 dígitos que o cliente precisa fornecer ao motoboy para confirmar a entrega"
          checked={settings.confirmation_code_enabled ?? true}
          onChange={(v) => setSettings((s) => ({ ...s, confirmation_code_enabled: v }))}
        />

        <div className="border-t border-surface-03" />

        <label className="flex flex-col gap-2">
          <div>
            <p className="text-cream text-sm font-medium">Tempo estimado padrão</p>
            <p className="text-stone text-xs mt-0.5">Sugerido ao atribuir motoboy (em minutos)</p>
          </div>
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={10} max={120} step={5}
              value={settings.default_estimated_minutes ?? 40}
              onChange={(e) => setSettings((s) => ({ ...s, default_estimated_minutes: Number(e.target.value) }))}
              className="flex-1 accent-gold"
            />
            <span className="text-gold font-bold text-sm w-14 text-right">
              {settings.default_estimated_minutes ?? 40} min
            </span>
          </div>
        </label>

        <div className="border-t border-surface-03" />

        <label className="flex flex-col gap-2">
          <div>
            <p className="text-cream text-sm font-medium">Entregas simultâneas por motoboy</p>
            <p className="text-stone text-xs mt-0.5">Máximo de pedidos que um motoboy pode ter em rota ao mesmo tempo</p>
          </div>
          <input
            type="number"
            min={1} max={10}
            value={settings.max_concurrent_deliveries ?? 3}
            onChange={(e) => setSettings((s) => ({ ...s, max_concurrent_deliveries: Number(e.target.value) }))}
            className="w-24 rounded-lg bg-surface-03 border border-surface-03 text-cream px-3 py-2 text-sm"
          />
        </label>

        <div className="border-t border-surface-03" />

        <label className="flex flex-col gap-2">
          <div>
            <p className="text-cream text-sm font-medium">Valor por entrega (R$)</p>
            <p className="text-stone text-xs mt-0.5">Repasse automático creditado ao motoboy ao finalizar cada entrega · visível na aba Financeiro</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-stone text-sm font-medium">R$</span>
            <input
              type="number"
              min={0} step={0.50}
              value={settings.rate_per_delivery ?? 0}
              onChange={(e) => setSettings((s) => ({ ...s, rate_per_delivery: Number(e.target.value) }))}
              className="w-28 rounded-lg bg-surface-03 border border-surface-03 text-cream px-3 py-2 text-sm"
            />
          </div>
          {(settings.rate_per_delivery ?? 0) === 0 && (
            <p className="text-stone/60 text-xs">Deixe em R$ 0,00 para não gerar registros financeiros automaticamente.</p>
          )}
        </label>
      </div>

      {error && <p className="mt-3 text-sm text-red-300">{error}</p>}
      {saved && <p className="mt-3 text-sm text-green-300">Configurações salvas!</p>}

      <button
        onClick={handleSave}
        disabled={saving}
        className="mt-5 flex items-center gap-2 rounded-xl bg-gold px-6 py-2.5 text-sm font-bold text-cream hover:bg-gold/90 disabled:opacity-50 transition-colors"
      >
        {saving ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
        {saving ? "Salvando..." : "Salvar configurações"}
      </button>
    </div>
  );
}
