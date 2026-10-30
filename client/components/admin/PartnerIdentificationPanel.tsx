import { useEffect, useState } from "react";
import { Check, Loader2, Upload } from "lucide-react";
import { partnerIdentificationApi, uploadApi, type PartnerIdentification } from "@/lib/api";
import { DEFAULT_PARTNER_IDENTIFICATION, normalizePartnerIdentification, rememberPartnerIdentification } from "@/lib/partnerIdentification";
import PartnerOrderIdentity from "./PartnerOrderIdentity";

const input = "w-full rounded-xl border border-surface-03 bg-surface-01 px-3 py-2.5 text-sm text-cream outline-none focus:border-gold";

export default function PartnerIdentificationPanel() {
  const [partners, setPartners] = useState<PartnerIdentification[]>(DEFAULT_PARTNER_IDENTIFICATION);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let active = true;
    partnerIdentificationApi.get().then((value) => {
      if (active) setPartners(rememberPartnerIdentification(value));
    }).catch(() => {
      if (active) setPartners(normalizePartnerIdentification(null));
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const patch = (origin: PartnerIdentification["order_origin"], values: Partial<PartnerIdentification>) => {
    setPartners((current) => current.map((item) => item.order_origin === origin ? { ...item, ...values } : item));
  };

  async function uploadLogo(origin: PartnerIdentification["order_origin"], file?: File) {
    if (!file) return;
    setError("");
    try {
      const url = await uploadApi.upload(file);
      patch(origin, { logo_url: url });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível enviar o logo.");
    }
  }

  async function save() {
    setSaving(true); setError(""); setSaved(false);
    try {
      const value = await partnerIdentificationApi.update(partners);
      setPartners(rememberPartnerIdentification(value));
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2500);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível salvar a identificação dos parceiros.");
    } finally { setSaving(false); }
  }

  return <section className="space-y-5" aria-labelledby="partner-identification-heading">
    <div>
      <h3 id="partner-identification-heading" className="text-lg font-black text-cream">Identificação de Parceiros</h3>
      <p className="mt-1 text-sm text-stone">Configure o nome e o logo que aparecem no pedido, na nota e nas etiquetas. Os logos são exclusivos desta empresa.</p>
    </div>
    {error && <p role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
    {loading ? <p role="status" className="flex items-center gap-2 text-stone"><Loader2 className="animate-spin" size={18} /> Carregando identificação...</p> : <div className="grid gap-4 md:grid-cols-2">
      {partners.map((partner) => <article key={partner.order_origin} className="space-y-4 rounded-2xl border border-surface-03 bg-surface-02 p-4">
        <div className="flex items-center justify-between gap-3"><PartnerOrderIdentity order={{ order_origin: partner.order_origin, partner_order_number: null, partner_logo_url: partner.logo_url }} /><label className="flex items-center gap-2 text-xs font-bold text-stone"><input type="checkbox" checked={partner.enabled} onChange={(event) => patch(partner.order_origin, { enabled: event.target.checked })} /> Ativo</label></div>
        <label className="block text-sm font-bold text-parchment">Nome exibido<input className={`${input} mt-2`} value={partner.display_name} maxLength={80} onChange={(event) => patch(partner.order_origin, { display_name: event.target.value })} /></label>
        <label className="block text-sm font-bold text-parchment">Referência do logo (opcional)<input className={`${input} mt-2`} value={partner.logo_url || ""} placeholder="/uploads/logo.png ou https://..." onChange={(event) => patch(partner.order_origin, { logo_url: event.target.value || null })} /></label>
        <label className="flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-gold/40 px-3 text-sm font-bold text-gold hover:bg-gold/10"><Upload size={16} /> Enviar arquivo<input className="sr-only" type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" onChange={(event) => void uploadLogo(partner.order_origin, event.target.files?.[0])} /></label>
        <div className="flex min-h-20 items-center justify-center rounded-xl bg-white p-3"><PartnerOrderIdentity order={{ order_origin: partner.order_origin, partner_order_number: "#12345", partner_logo_url: partner.logo_url }} className="text-black" /></div>
        <p className="text-xs text-stone">Prévia: etiqueta e nota usam o logo quando disponível e mantêm o nome como fallback.</p>
      </article>)}
    </div>}
    <button type="button" disabled={loading || saving} onClick={() => void save()} className="flex min-h-11 items-center gap-2 rounded-xl bg-gold px-5 font-black text-black disabled:opacity-50">{saving ? <Loader2 className="animate-spin" size={17} /> : saved ? <Check size={17} /> : <Upload size={17} />}{saved ? "Salvo" : "Salvar identificação"}</button>
  </section>;
}
