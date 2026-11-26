import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { Ban, Check, Clock3, Loader2, Plus, RefreshCw, RotateCcw, Save, TicketCheck, X } from "lucide-react";
import {
  strategicCampaignsApi,
  type ApiStrategicCampaign,
  type ApiStrategicCapacitySlot,
  type ApiStrategicReservation,
  type StrategicReservationPaymentMode,
  type StrategicReservationStatus,
} from "@/lib/api";
import {
  availableCapacity,
  canConfirmReservation,
  canReleaseReservation,
  makeIdempotencyKey,
  paymentModeLabels,
  reservationStatusLabels,
  validateReservationAmounts,
} from "./strategicCampaignC6";

const inputClass = "mt-1 w-full rounded-xl border border-surface-03 bg-surface-01 px-3 py-2.5 text-sm text-cream outline-none focus:border-gold";
const statuses: Array<["" | StrategicReservationStatus, string]> = [["", "Todos os estados"], ["held", "Em retenção"], ["confirmed", "Confirmadas"], ["released", "Liberadas"], ["expired", "Expiradas"], ["cancelled", "Canceladas"]];

type ReservationDraft = {
  slot_id: string;
  offer_id: string;
  customer_reference: string;
  quantity: string;
  payment_mode: StrategicReservationPaymentMode;
  amount_total: string;
  amount_paid: string;
  hold_minutes: string;
  idempotency_key: string;
};

const emptyDraft = (): ReservationDraft => ({ slot_id: "", offer_id: "", customer_reference: "", quantity: "1", payment_mode: "no_payment", amount_total: "0", amount_paid: "0", hold_minutes: "15", idempotency_key: makeIdempotencyKey() });

export default function StrategicCampaignReservationsTab({ campaign }: { campaign: ApiStrategicCampaign }) {
  const [reservations, setReservations] = useState<ApiStrategicReservation[]>([]);
  const [slots, setSlots] = useState<ApiStrategicCapacitySlot[]>([]);
  const [status, setStatus] = useState<"" | StrategicReservationStatus>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [draft, setDraft] = useState<ReservationDraft>(emptyDraft);
  const [releaseTarget, setReleaseTarget] = useState<ApiStrategicReservation | null>(null);
  const [releaseReason, setReleaseReason] = useState("");
  const [cancelled, setCancelled] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [reservationRows, slotRows] = await Promise.all([
        strategicCampaignsApi.listReservations(campaign.id, status || undefined),
        strategicCampaignsApi.listCapacitySlots(campaign.id),
      ]);
      setReservations(reservationRows);
      setSlots(slotRows);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Não foi possível carregar as reservas.");
    } finally {
      setLoading(false);
    }
  }, [campaign.id, status]);

  useEffect(() => { void load(); }, [load]);

  const slotMap = useMemo(() => new Map(slots.map((slot) => [slot.id, slot])), [slots]);
  const offerMap = useMemo(() => new Map(campaign.offers.map((offer) => [offer.id, offer.title])), [campaign.offers]);
  const usableSlots = slots.filter((slot) => !slot.blocked && availableCapacity(slot) > 0);

  const openCreate = () => { setDraft(emptyDraft()); setMessage(""); setFormOpen(true); };
  const changePaymentMode = (mode: StrategicReservationPaymentMode) => setDraft((current) => ({ ...current, payment_mode: mode, amount_paid: mode === "no_payment" ? "0" : mode === "full" ? current.amount_total : current.amount_paid }));

  const createReservation = async (event: FormEvent) => {
    event.preventDefault();
    const total = Number(draft.amount_total);
    const paid = Number(draft.amount_paid);
    const amountError = validateReservationAmounts(draft.payment_mode, total, paid);
    if (amountError) { setMessage(amountError); return; }
    setSaving(true);
    setMessage("");
    try {
      await strategicCampaignsApi.createReservation(campaign.id, {
        slot_id: draft.slot_id,
        offer_id: draft.offer_id || null,
        customer_reference: draft.customer_reference.trim(),
        quantity: Number(draft.quantity),
        payment_mode: draft.payment_mode,
        amount_total: total,
        amount_paid: paid,
        hold_minutes: Number(draft.hold_minutes),
        idempotency_key: draft.idempotency_key,
      });
      setFormOpen(false);
      await load();
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Não foi possível criar a reserva.");
    } finally {
      setSaving(false);
    }
  };

  const confirm = async (reservation: ApiStrategicReservation) => {
    setSaving(true); setMessage("");
    try { await strategicCampaignsApi.confirmReservation(reservation.id); await load(); }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : "Não foi possível confirmar a reserva."); }
    finally { setSaving(false); }
  };

  const release = async (event: FormEvent) => {
    event.preventDefault();
    if (!releaseTarget) return;
    setSaving(true); setMessage("");
    try {
      await strategicCampaignsApi.releaseReservation(releaseTarget.id, { reason: releaseReason.trim(), cancelled });
      setReleaseTarget(null); setReleaseReason(""); setCancelled(false); await load();
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : "Não foi possível liberar a reserva."); }
    finally { setSaving(false); }
  };

  const expire = async () => {
    setSaving(true); setMessage("");
    try {
      const result = await strategicCampaignsApi.expireReservations(campaign.id);
      setMessage(result.expired_count ? `${result.expired_count} reserva(s) expirada(s) e capacidade devolvida.` : "Nenhuma reserva vencida encontrada.");
      await load();
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : "Não foi possível processar as expirações."); }
    finally { setSaving(false); }
  };

  return <div className="space-y-5">
    <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between"><div><h2 className="text-lg font-bold text-cream">Pedidos e reservas</h2><p className="text-sm text-stone">Acompanhe retenções de capacidade. Pedidos confirmados continuam no fluxo canônico de pedidos.</p></div><div className="flex flex-col gap-2 sm:flex-row"><button type="button" disabled={saving} onClick={() => void expire()} className="inline-flex items-center justify-center gap-2 rounded-xl border border-surface-03 px-4 py-2.5 text-sm font-semibold text-parchment"><Clock3 size={16} /> Processar vencidas</button><button type="button" onClick={openCreate} disabled={usableSlots.length === 0} className="inline-flex items-center justify-center gap-2 rounded-xl bg-gold px-4 py-2.5 text-sm font-bold text-surface-00 disabled:cursor-not-allowed disabled:opacity-50"><Plus size={16} /> Nova reserva</button></div></div>

    {message && <div role="status" className={`rounded-xl border p-3 text-sm ${message.startsWith("Não foi") ? "border-red-500/30 bg-red-500/10 text-red-300" : "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"}`}>{message}</div>}
    <div className="flex flex-col gap-2 rounded-2xl border border-surface-03 bg-surface-02 p-4 sm:flex-row sm:items-end sm:justify-between"><label className="text-sm text-parchment">Filtrar por estado<select value={status} onChange={(event) => setStatus(event.target.value as "" | StrategicReservationStatus)} className={`${inputClass} min-w-52`}>{statuses.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><p className="text-xs text-stone">{reservations.length} registro(s) no filtro atual</p></div>

    {loading ? <State icon={<Loader2 className="animate-spin" />} text="Carregando reservas..." />
      : error ? <State icon={<Ban />} text={error} action={<button onClick={() => void load()} className="inline-flex items-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm text-parchment"><RefreshCw size={15} /> Tentar novamente</button>} />
        : reservations.length === 0 ? <State icon={<TicketCheck />} text={status ? "Nenhuma reserva encontrada neste estado." : usableSlots.length ? "Nenhuma reserva criada para esta campanha." : "Crie e libere um horário com capacidade antes de registrar reservas."} action={usableSlots.length ? <button onClick={openCreate} className="rounded-lg bg-gold px-4 py-2 text-sm font-bold text-surface-00">Criar reserva</button> : undefined} />
          : <div className="space-y-3">{reservations.map((reservation) => {
            const slot = slotMap.get(reservation.slot_id);
            return <article key={reservation.id} className="rounded-2xl border border-surface-03 bg-surface-02 p-4 md:p-5"><div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between"><div><div className="flex flex-wrap items-center gap-2"><h3 className="font-bold text-cream">{reservation.customer_reference}</h3><Status status={reservation.status} /></div><p className="mt-1 text-sm text-stone">{slot?.label || (slot ? formatDate(slot.starts_at) : "Horário não encontrado")} · {reservation.offer_id ? offerMap.get(reservation.offer_id) ?? "Oferta vinculada" : "Campanha"}</p></div><div className="flex flex-wrap gap-2">{canConfirmReservation(reservation) && <button type="button" disabled={saving} onClick={() => void confirm(reservation)} className="inline-flex items-center gap-2 rounded-lg border border-emerald-500/30 px-3 py-2 text-sm font-semibold text-emerald-300"><Check size={14} /> Confirmar</button>}{canReleaseReservation(reservation) && <button type="button" disabled={saving} onClick={() => { setReleaseTarget(reservation); setReleaseReason(""); setCancelled(false); }} className="inline-flex items-center gap-2 rounded-lg border border-red-500/30 px-3 py-2 text-sm font-semibold text-red-300"><RotateCcw size={14} /> Liberar/cancelar</button>}</div></div><dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-5"><Data label="Quantidade" value={reservation.quantity} /><Data label="Pagamento" value={paymentModeLabels[reservation.payment_mode]} /><Data label="Valor total" value={money(reservation.amount_total)} /><Data label="Valor pago" value={money(reservation.amount_paid)} /><Data label="Expira em" value={reservation.expires_at ? formatDate(reservation.expires_at) : "—"} /></dl>{reservation.release_reason && <p className="mt-3 rounded-lg bg-surface-01 p-3 text-sm text-stone"><strong className="text-parchment">Motivo:</strong> {reservation.release_reason}</p>}</article>;
          })}</div>}

    {formOpen && <Modal onClose={() => setFormOpen(false)}><form onSubmit={createReservation} className="p-5"><ModalHeader title="Nova reserva" description="A capacidade será retida de forma transacional pelo backend." onClose={() => setFormOpen(false)} />{message && <Alert text={message} />}<div className="mt-5 grid gap-4 sm:grid-cols-2"><label className="text-sm text-parchment sm:col-span-2">Horário<select required value={draft.slot_id} onChange={(event) => { const slot = slotMap.get(event.target.value); setDraft({ ...draft, slot_id: event.target.value, offer_id: slot?.offer_id ?? "" }); }} className={inputClass}><option value="">Selecione</option>{usableSlots.map((slot) => <option key={slot.id} value={slot.id}>{slot.label || formatDate(slot.starts_at)} — {availableCapacity(slot)} disponível(is)</option>)}</select></label><label className="text-sm text-parchment sm:col-span-2">Referência do cliente<input required maxLength={200} value={draft.customer_reference} onChange={(event) => setDraft({ ...draft, customer_reference: event.target.value })} className={inputClass} placeholder="Nome, telefone ou código do cliente" /></label><label className="text-sm text-parchment">Quantidade<input required min="1" max="100000" type="number" value={draft.quantity} onChange={(event) => setDraft({ ...draft, quantity: event.target.value })} className={inputClass} /></label><label className="text-sm text-parchment">Retenção (minutos)<input required min="1" max="1440" type="number" value={draft.hold_minutes} onChange={(event) => setDraft({ ...draft, hold_minutes: event.target.value })} className={inputClass} /></label><label className="text-sm text-parchment sm:col-span-2">Modalidade de pagamento<select value={draft.payment_mode} onChange={(event) => changePaymentMode(event.target.value as StrategicReservationPaymentMode)} className={inputClass}>{Object.entries(paymentModeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label className="text-sm text-parchment">Valor total<input required min="0" step="0.01" type="number" value={draft.amount_total} onChange={(event) => setDraft({ ...draft, amount_total: event.target.value, amount_paid: draft.payment_mode === "full" ? event.target.value : draft.amount_paid })} className={inputClass} /></label><label className="text-sm text-parchment">Valor pago<input required disabled={draft.payment_mode === "no_payment" || draft.payment_mode === "full"} min="0" step="0.01" type="number" value={draft.amount_paid} onChange={(event) => setDraft({ ...draft, amount_paid: event.target.value })} className={inputClass} /></label></div><ModalActions saving={saving} onCancel={() => setFormOpen(false)} label="Criar reserva" /></form></Modal>}

    {releaseTarget && <Modal onClose={() => setReleaseTarget(null)}><form onSubmit={release} className="p-5"><ModalHeader title="Liberar capacidade" description={`Reserva de ${releaseTarget.customer_reference}. Esta ação devolve a capacidade apenas uma vez.`} onClose={() => setReleaseTarget(null)} />{message && <Alert text={message} />}<label className="mt-5 block text-sm text-parchment">Motivo<textarea required minLength={1} maxLength={300} value={releaseReason} onChange={(event) => setReleaseReason(event.target.value)} className={`${inputClass} min-h-24`} placeholder="Informe o motivo operacional" /></label><label className="mt-4 flex items-start gap-3 rounded-xl border border-surface-03 bg-surface-01 p-4 text-sm text-parchment"><input type="checkbox" checked={cancelled} onChange={(event) => setCancelled(event.target.checked)} className="mt-1 accent-gold" /><span><strong className="block text-cream">Marcar como cancelada</strong>Desmarcado, o registro ficará como liberado.</span></label><ModalActions saving={saving} onCancel={() => setReleaseTarget(null)} label={cancelled ? "Cancelar reserva" : "Liberar reserva"} /></form></Modal>}
  </div>;
}

function Modal({ children, onClose }: { children: React.ReactNode; onClose: () => void }) { return <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 sm:items-center sm:p-5" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><div className="max-h-[95vh] w-full max-w-2xl overflow-y-auto rounded-t-2xl border border-surface-03 bg-surface-00 sm:rounded-2xl">{children}</div></div>; }
function ModalHeader({ title, description, onClose }: { title: string; description: string; onClose: () => void }) { return <div className="flex items-start justify-between gap-3"><div><h2 className="text-xl font-bold text-cream">{title}</h2><p className="text-sm text-stone">{description}</p></div><button type="button" onClick={onClose} aria-label="Fechar" className="rounded-lg p-2 text-stone hover:bg-surface-02"><X /></button></div>; }
function ModalActions({ saving, onCancel, label }: { saving: boolean; onCancel: () => void; label: string }) { return <div className="mt-6 flex justify-end gap-2 border-t border-surface-03 pt-4"><button type="button" onClick={onCancel} className="rounded-xl border border-surface-03 px-4 py-2.5 text-sm font-semibold text-parchment">Voltar</button><button disabled={saving} className="inline-flex items-center gap-2 rounded-xl bg-gold px-5 py-2.5 text-sm font-bold text-surface-00 disabled:opacity-60">{saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}{label}</button></div>; }
function Alert({ text }: { text: string }) { return <div role="alert" className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">{text}</div>; }
function State({ icon, text, action }: { icon: React.ReactNode; text: string; action?: React.ReactNode }) { return <div className="flex min-h-52 flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-surface-03 bg-surface-01 p-6 text-center text-gold"><span className="rounded-full bg-gold/10 p-3">{icon}</span><p className="max-w-xl text-sm text-stone">{text}</p>{action}</div>; }
function Status({ status }: { status: StrategicReservationStatus }) { const styles: Record<StrategicReservationStatus, string> = { held: "bg-amber-500/15 text-amber-300", confirmed: "bg-emerald-500/15 text-emerald-300", released: "bg-sky-500/15 text-sky-300", expired: "bg-surface-03 text-stone", cancelled: "bg-red-500/15 text-red-300" }; return <span className={`rounded-full px-2 py-1 text-xs font-semibold ${styles[status]}`}>{reservationStatusLabels[status]}</span>; }
function Data({ label, value }: { label: string; value: React.ReactNode }) { return <div><dt className="text-xs text-stone">{label}</dt><dd className="mt-1 font-semibold text-parchment">{value}</dd></div>; }
function formatDate(value: string) { return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(value)); }
function money(value: number) { return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value); }
