import { useState, type FormEvent } from "react";
import { Loader2, Save } from "lucide-react";
import { strategicCampaignsApi, type ApiStrategicCampaign, type StrategicCommercialConfig } from "@/lib/api";

const paymentOptions: Array<[StrategicCommercialConfig["allowed_payment_methods"][number], string]> = [
  ["pix", "PIX"],
  ["credit_card", "Cartão de crédito"],
  ["debit_card", "Cartão de débito"],
  ["pay_on_delivery", "Pagamento na entrega"],
];

const inputClass = "mt-1 w-full rounded-xl border border-surface-03 bg-surface-01 px-3 py-2.5 text-sm text-cream outline-none focus:border-gold";

export default function StrategicCampaignCommercialTab({ campaign, onChanged }: { campaign: ApiStrategicCampaign; onChanged: (campaign: ApiStrategicCampaign) => void }) {
  const [form, setForm] = useState<StrategicCommercialConfig>(campaign.commercial_config);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);

  const togglePayment = (method: StrategicCommercialConfig["allowed_payment_methods"][number]) => {
    setForm((current) => ({
      ...current,
      allowed_payment_methods: current.allowed_payment_methods.includes(method)
        ? current.allowed_payment_methods.filter((item) => item !== method)
        : [...current.allowed_payment_methods, method],
    }));
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setMessage("");
    try {
      const updated = await strategicCampaignsApi.update(campaign.id, { commercial_config: form });
      onChanged(updated);
      setFailed(false);
      setMessage("Configurações comerciais salvas no rascunho.");
    } catch (error) {
      setFailed(true);
      setMessage(error instanceof Error ? error.message : "Não foi possível salvar a comercialização.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={save} className="space-y-5">
      <div>
        <h2 className="text-lg font-bold text-cream">Comercialização</h2>
        <p className="text-sm text-stone">Configure a modalidade sem alterar o funcionamento convencional da loja.</p>
      </div>
      {message && <div role="status" className={`rounded-xl border p-3 text-sm ${failed ? "border-red-500/30 bg-red-500/10 text-red-300" : "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"}`}>{message}</div>}
      <section className="grid gap-5 rounded-2xl border border-surface-03 bg-surface-02 p-4 md:grid-cols-2 md:p-6">
        <label className="text-sm text-parchment">Modalidade<select value={form.sales_mode} onChange={(event) => setForm((current) => ({ ...current, sales_mode: event.target.value as StrategicCommercialConfig["sales_mode"] }))} className={inputClass}><option value="immediate">Venda imediata</option><option value="preorder">Venda antecipada</option><option value="hybrid">Venda imediata + antecipada</option></select></label>
        <label className="text-sm text-parchment">Antecedência mínima (minutos)<input type="number" min="0" max="43200" value={form.min_lead_minutes} onChange={(event) => setForm((current) => ({ ...current, min_lead_minutes: Number(event.target.value) }))} className={inputClass} /></label>
        <label className="text-sm text-parchment">Antecedência máxima (dias)<input type="number" min="1" max="365" value={form.max_lead_days ?? ""} onChange={(event) => setForm((current) => ({ ...current, max_lead_days: event.target.value ? Number(event.target.value) : null }))} className={inputClass} placeholder="Sem limite adicional" /></label>
        <div className="space-y-3 md:col-span-2">
          <label className="flex items-start gap-3 rounded-xl border border-surface-03 bg-surface-01 p-4 text-sm text-parchment"><input type="checkbox" checked={form.require_scheduled_order} onChange={(event) => setForm((current) => ({ ...current, require_scheduled_order: event.target.checked }))} className="mt-1 accent-gold" /><span><strong className="block text-cream">Exigir data e horário</strong>O checkout deverá coletar agendamento antes da confirmação.</span></label>
          <label className="flex items-start gap-3 rounded-xl border border-surface-03 bg-surface-01 p-4 text-sm text-parchment"><input type="checkbox" checked={form.allow_when_store_closed} onChange={(event) => setForm((current) => ({ ...current, allow_when_store_closed: event.target.checked, require_scheduled_order: event.target.checked ? true : current.require_scheduled_order }))} className="mt-1 accent-gold" /><span><strong className="block text-cream">Permitir venda com a loja fechada</strong>Afeta somente esta campanha e exige pedido programado.</span></label>
        </div>
      </section>
      <section className="rounded-2xl border border-surface-03 bg-surface-02 p-4 md:p-6">
        <h3 className="font-bold text-cream">Meios de pagamento autorizados</h3>
        <p className="mt-1 text-sm text-stone">Sem seleção, o checkout mantém os meios habilitados para o estabelecimento.</p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{paymentOptions.map(([value, label]) => <label key={value} className={`flex items-center gap-3 rounded-xl border p-3 text-sm ${form.allowed_payment_methods.includes(value) ? "border-gold bg-gold/10 text-gold" : "border-surface-03 bg-surface-01 text-parchment"}`}><input type="checkbox" checked={form.allowed_payment_methods.includes(value)} onChange={() => togglePayment(value)} className="accent-gold" />{label}</label>)}</div>
      </section>
      <div className="flex justify-end"><button disabled={saving} className="inline-flex items-center gap-2 rounded-xl bg-gold px-5 py-2.5 text-sm font-bold text-cream disabled:opacity-60">{saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} Salvar comercialização</button></div>
    </form>
  );
}
