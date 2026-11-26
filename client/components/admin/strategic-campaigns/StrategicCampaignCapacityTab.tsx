import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { Ban, CalendarClock, CheckCircle2, Edit3, Loader2, Plus, RefreshCw, Save, X } from "lucide-react";
import {
  strategicCampaignsApi,
  type ApiStrategicCampaign,
  type ApiStrategicCapacitySlot,
  type StrategicCapacitySlotCreate,
} from "@/lib/api";
import { availableCapacity } from "./strategicCampaignC6";

const inputClass = "mt-1 w-full rounded-xl border border-surface-03 bg-surface-01 px-3 py-2.5 text-sm text-cream outline-none focus:border-gold";

type SlotDraft = {
  offer_id: string;
  label: string;
  starts_at: string;
  ends_at: string;
  capacity_total: string;
  blocked: boolean;
};

const emptyDraft = (): SlotDraft => ({ offer_id: "", label: "", starts_at: "", ends_at: "", capacity_total: "", blocked: false });
const toLocalDateTime = (value: string) => {
  const date = new Date(value);
  const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return shifted.toISOString().slice(0, 16);
};

export default function StrategicCampaignCapacityTab({ campaign }: { campaign: ApiStrategicCampaign }) {
  const [slots, setSlots] = useState<ApiStrategicCapacitySlot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ApiStrategicCapacitySlot | null>(null);
  const [draft, setDraft] = useState<SlotDraft>(emptyDraft);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setSlots(await strategicCampaignsApi.listCapacitySlots(campaign.id));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Não foi possível carregar os horários e capacidades.");
    } finally {
      setLoading(false);
    }
  }, [campaign.id]);

  useEffect(() => { void load(); }, [load]);

  const offerNames = useMemo(() => new Map(campaign.offers.map((offer) => [offer.id, offer.title])), [campaign.offers]);
  const openCreate = () => { setEditing(null); setDraft(emptyDraft()); setMessage(""); setFormOpen(true); };
  const openEdit = (slot: ApiStrategicCapacitySlot) => {
    setEditing(slot);
    setDraft({
      offer_id: slot.offer_id ?? "",
      label: slot.label ?? "",
      starts_at: toLocalDateTime(slot.starts_at),
      ends_at: toLocalDateTime(slot.ends_at),
      capacity_total: String(slot.capacity_total),
      blocked: slot.blocked,
    });
    setMessage("");
    setFormOpen(true);
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setMessage("");
    try {
      const common = {
        label: draft.label.trim() || null,
        starts_at: new Date(draft.starts_at).toISOString(),
        ends_at: new Date(draft.ends_at).toISOString(),
        capacity_total: Number(draft.capacity_total),
        blocked: draft.blocked,
      };
      if (editing) await strategicCampaignsApi.updateCapacitySlot(editing.id, common);
      else await strategicCampaignsApi.createCapacitySlot(campaign.id, { ...common, offer_id: draft.offer_id || null } satisfies StrategicCapacitySlotCreate);
      setFormOpen(false);
      await load();
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Não foi possível salvar o horário.");
    } finally {
      setSaving(false);
    }
  };

  const toggleBlocked = async (slot: ApiStrategicCapacitySlot) => {
    setSaving(true);
    setMessage("");
    try {
      await strategicCampaignsApi.updateCapacitySlot(slot.id, { blocked: !slot.blocked });
      await load();
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Não foi possível alterar o bloqueio do horário.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div><h2 className="text-lg font-bold text-cream">Agendamento e capacidade</h2><p className="text-sm text-stone">Gerencie datas, horários e limites sem alterar a capacidade já ocupada.</p></div>
        <button type="button" onClick={openCreate} className="inline-flex items-center justify-center gap-2 rounded-xl bg-gold px-4 py-2.5 text-sm font-bold text-surface-00"><Plus size={16} /> Novo horário</button>
      </div>

      {message && <div role="status" className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">{message}</div>}
      {loading ? <State icon={<Loader2 className="animate-spin" />} text="Carregando horários e capacidades..." />
        : error ? <State icon={<Ban />} text={error} action={<button onClick={() => void load()} className="inline-flex items-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm text-parchment"><RefreshCw size={15} /> Tentar novamente</button>} />
          : slots.length === 0 ? <State icon={<CalendarClock />} text="Nenhum horário configurado. Crie o primeiro slot para controlar a capacidade da campanha." action={<button onClick={openCreate} className="rounded-lg bg-gold px-4 py-2 text-sm font-bold text-surface-00">Criar horário</button>} />
            : <div className="grid gap-4 xl:grid-cols-2">{slots.map((slot) => {
              const available = availableCapacity(slot);
              const percent = Math.min(100, Math.round((slot.capacity_used / slot.capacity_total) * 100));
              return <article key={slot.id} className="rounded-2xl border border-surface-03 bg-surface-02 p-4 md:p-5">
                <div className="flex items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-wider text-gold">{slot.offer_id ? offerNames.get(slot.offer_id) ?? "Oferta específica" : "Toda a campanha"}</p><h3 className="mt-1 font-bold text-cream">{slot.label || "Horário sem título"}</h3></div><span className={`rounded-full px-2 py-1 text-xs font-semibold ${slot.blocked ? "bg-red-500/15 text-red-300" : "bg-emerald-500/15 text-emerald-300"}`}>{slot.blocked ? "Bloqueado" : "Disponível"}</span></div>
                <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2"><Data label="Início" value={formatDate(slot.starts_at)} /><Data label="Término" value={formatDate(slot.ends_at)} /><Data label="Ocupadas" value={`${slot.capacity_used} de ${slot.capacity_total}`} /><Data label="Disponíveis" value={available} /></dl>
                <div className="mt-4 h-2 overflow-hidden rounded-full bg-surface-03" aria-label={`${percent}% da capacidade ocupada`}><div className="h-full rounded-full bg-gold" style={{ width: `${percent}%` }} /></div>
                <div className="mt-4 flex flex-wrap gap-2"><button type="button" onClick={() => openEdit(slot)} className="inline-flex items-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm font-semibold text-parchment"><Edit3 size={14} /> Editar</button><button type="button" disabled={saving} onClick={() => void toggleBlocked(slot)} className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold ${slot.blocked ? "border-emerald-500/30 text-emerald-300" : "border-red-500/30 text-red-300"}`}>{slot.blocked ? <CheckCircle2 size={14} /> : <Ban size={14} />}{slot.blocked ? "Liberar horário" : "Bloquear horário"}</button></div>
              </article>;
            })}</div>}

      {formOpen && <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 sm:items-center sm:p-5" onMouseDown={(event) => { if (event.target === event.currentTarget) setFormOpen(false); }}><form onSubmit={save} className="max-h-[95vh] w-full max-w-2xl overflow-y-auto rounded-t-2xl border border-surface-03 bg-surface-00 p-5 sm:rounded-2xl">
        <div className="flex items-start justify-between"><div><h2 className="text-xl font-bold text-cream">{editing ? "Editar horário" : "Novo horário"}</h2><p className="text-sm text-stone">A API impede reduzir a capacidade abaixo da ocupação atual.</p></div><button type="button" onClick={() => setFormOpen(false)} aria-label="Fechar" className="rounded-lg p-2 text-stone hover:bg-surface-02"><X /></button></div>
        {message && <div role="alert" className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">{message}</div>}
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          {!editing && <label className="text-sm text-parchment sm:col-span-2">Aplicar à oferta<select value={draft.offer_id} onChange={(event) => setDraft({ ...draft, offer_id: event.target.value })} className={inputClass}><option value="">Toda a campanha</option>{campaign.offers.filter((offer) => !offer.archived_at).map((offer) => <option key={offer.id} value={offer.id}>{offer.title}</option>)}</select></label>}
          <label className="text-sm text-parchment sm:col-span-2">Título do horário<input value={draft.label} onChange={(event) => setDraft({ ...draft, label: event.target.value })} className={inputClass} placeholder="Ex.: Retirada no sábado à noite" /></label>
          <label className="text-sm text-parchment">Início<input required type="datetime-local" value={draft.starts_at} onChange={(event) => setDraft({ ...draft, starts_at: event.target.value })} className={inputClass} /></label>
          <label className="text-sm text-parchment">Término<input required type="datetime-local" min={draft.starts_at || undefined} value={draft.ends_at} onChange={(event) => setDraft({ ...draft, ends_at: event.target.value })} className={inputClass} /></label>
          <label className="text-sm text-parchment">Capacidade total<input required min={editing ? editing.capacity_used || 1 : 1} max="1000000" type="number" value={draft.capacity_total} onChange={(event) => setDraft({ ...draft, capacity_total: event.target.value })} className={inputClass} /></label>
          <label className="flex items-center gap-3 self-end rounded-xl border border-surface-03 bg-surface-01 p-3 text-sm text-parchment"><input type="checkbox" checked={draft.blocked} onChange={(event) => setDraft({ ...draft, blocked: event.target.checked })} className="accent-gold" /> Criar/salvar bloqueado</label>
        </div>
        <div className="mt-6 flex justify-end gap-2 border-t border-surface-03 pt-4"><button type="button" onClick={() => setFormOpen(false)} className="rounded-xl border border-surface-03 px-4 py-2.5 text-sm font-semibold text-parchment">Cancelar</button><button disabled={saving} className="inline-flex items-center gap-2 rounded-xl bg-gold px-5 py-2.5 text-sm font-bold text-surface-00 disabled:opacity-60">{saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} Salvar horário</button></div>
      </form></div>}
    </div>
  );
}

function State({ icon, text, action }: { icon: React.ReactNode; text: string; action?: React.ReactNode }) { return <div className="flex min-h-52 flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-surface-03 bg-surface-01 p-6 text-center text-gold"><span className="rounded-full bg-gold/10 p-3">{icon}</span><p className="max-w-xl text-sm text-stone">{text}</p>{action}</div>; }
function Data({ label, value }: { label: string; value: React.ReactNode }) { return <div><dt className="text-xs text-stone">{label}</dt><dd className="mt-1 font-semibold text-parchment">{value}</dd></div>; }
function formatDate(value: string) { return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(value)); }
