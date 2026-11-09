import { useEffect, useRef, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ApiRequestError, inventoryApi, type InventoryAdjustmentBucket, type InventoryAdjustmentInput } from "@/lib/api";
import { formatQuantity } from "@/lib/formatQuantity";

export interface AdjustmentItem {
  id: string;
  name: string;
  unitSymbol: string;
  portioned?: boolean;
}

interface Props {
  item: AdjustmentItem | null;
  onClose: () => void;
  onAdjusted: () => void;
}

const fieldClass = "w-full rounded-lg border border-surface-03 bg-surface-01 px-3 py-2 text-sm text-cream focus:border-gold focus:outline-none";
type PendingOperation = { key: string; businessKey: string; body?: InventoryAdjustmentInput };
const unresolvedAdjustments = new Map<string, PendingOperation>();
const pendingStorageKey = (itemId: string) => `inventory-adjustment-pending:${itemId}`;

function pendingAdjustment(itemId: string): PendingOperation | undefined {
  const inMemory = unresolvedAdjustments.get(itemId);
  if (inMemory) return inMemory;
  if (typeof window === "undefined") return undefined;
  try {
    const stored = window.sessionStorage.getItem(pendingStorageKey(itemId));
    if (!stored) return undefined;
    const parsed = JSON.parse(stored) as PendingOperation;
    if (!parsed.key || !parsed.businessKey || !parsed.body) return undefined;
    unresolvedAdjustments.set(itemId, parsed);
    return parsed;
  } catch {
    return undefined;
  }
}

function rememberPendingAdjustment(itemId: string, pending: PendingOperation) {
  unresolvedAdjustments.set(itemId, pending);
  try { window.sessionStorage.setItem(pendingStorageKey(itemId), JSON.stringify(pending)); } catch { /* Storage may be unavailable. */ }
}

function clearPendingAdjustment(itemId: string) {
  unresolvedAdjustments.delete(itemId);
  try { window.sessionStorage.removeItem(pendingStorageKey(itemId)); } catch { /* Storage may be unavailable. */ }
}

export const hasUnresolvedAdjustment = (itemId: string) => Boolean(pendingAdjustment(itemId));

export function selectedAdjustmentBucket(buckets: InventoryAdjustmentBucket[], index: string) {
  return index === "" ? undefined : buckets[Number(index)];
}

export function validAdjustmentQuantity(value: string, kind: "correction" | "loss", portioned: boolean) {
  const normalized = value.trim().replace(",", ".");
  const amount = Number(normalized);
  return /^\d+(?:\.\d{1,6})?$/.test(normalized) && Number.isFinite(amount) && (kind === "loss" ? amount > 0 : amount >= 0) && (!portioned || Number.isInteger(amount));
}

export function adjustmentReady(bucket: InventoryAdjustmentBucket | undefined, quantityValid: boolean, reason: string, confirmed: boolean) {
  return Boolean(bucket && quantityValid && reason.trim() && confirmed);
}

export function adjustmentInput(bucket: InventoryAdjustmentBucket, businessKey: string, kind: "correction" | "loss", quantity: string, reason: string, notes: string): InventoryAdjustmentInput {
  return {
    business_key: businessKey,
    kind,
    quantity: quantity.trim().replace(",", "."),
    expected_physical: bucket.physical,
    location_id: bucket.location_id,
    lot_id: bucket.lot_id,
    reason: reason.trim(),
    ...(notes.trim() ? { notes: notes.trim() } : {}),
  };
}

export default function InventoryStockAdjustmentDialog({ item, onClose, onAdjusted }: Props) {
  const [buckets, setBuckets] = useState<InventoryAdjustmentBucket[]>([]);
  const [bucketIndex, setBucketIndex] = useState("");
  const [kind, setKind] = useState<"correction" | "loss">("correction");
  const [quantity, setQuantity] = useState("");
  const [reason, setReason] = useState("");
  const [notes, setNotes] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [retryPending, setRetryPending] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [reconciled, setReconciled] = useState(false);
  const [rechecked, setRechecked] = useState(false);
  const operation = useRef<PendingOperation | null>(null);

  const itemId = item?.id;
  useEffect(() => {
    setBuckets([]);
    setBucketIndex("");
    const pending = itemId ? pendingAdjustment(itemId) : undefined;
    setKind(pending?.body?.kind ?? "correction");
    setQuantity(pending?.body?.quantity ?? "");
    setReason(pending?.body?.reason ?? "");
    setNotes(pending?.body?.notes ?? "");
    setConfirmed(false);
    setError("");
    setRetryPending(Boolean(pending));
    setUncertain(Boolean(pending));
    setReconciled(false);
    setRechecked(false);
    operation.current = itemId ? pending ?? { key: crypto.randomUUID(), businessKey: crypto.randomUUID() } : null;
    if (!itemId) return;
    let current = true;
    setLoading(true);
    inventoryApi.adjustmentBuckets(itemId)
      .then((result) => {
        if (!current) return;
        setBuckets(result);
        const pendingBody = pending?.body;
        const matchingIndex = pendingBody ? result.findIndex((bucket) => bucket.location_id === (pendingBody.location_id ?? null) && bucket.lot_id === (pendingBody.lot_id ?? null)) : -1;
        setBucketIndex(matchingIndex >= 0 ? String(matchingIndex) : result.length === 1 ? "0" : "");
        if (pendingBody) {
          setRechecked(true);
          setError("Há um resultado pendente. Confira o saldo e repita a mesma operação para obter a resposta, sem criar outro ajuste.");
        }
      })
      .catch((cause) => { if (current) setError(cause instanceof Error ? cause.message : "Não foi possível carregar locais e lotes."); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [itemId]);

  const selected = selectedAdjustmentBucket(buckets, bucketIndex);
  const unit = item?.portioned ? "PRQ" : selected?.unit_symbol || item?.unitSymbol || "unid.";
  const normalizedQuantity = quantity.trim().replace(",", ".");
  const validQuantity = validAdjustmentQuantity(quantity, kind, Boolean(item?.portioned));
  const canSubmit = Boolean(!loading && !saving && (retryPending || adjustmentReady(selected, validQuantity, reason, confirmed)));

  const reloadBuckets = async () => {
    if (!itemId) return;
    setLoading(true);
    setError("");
    if (!retryPending) setConfirmed(false);
    try {
      const result = await inventoryApi.adjustmentBuckets(itemId);
      setBuckets(result);
      setRechecked(true);
      const pending = operation.current?.body;
      const matchingIndex = pending ? result.findIndex((bucket) => bucket.location_id === (pending.location_id ?? null) && bucket.lot_id === (pending.lot_id ?? null)) : -1;
      setBucketIndex(matchingIndex >= 0 ? String(matchingIndex) : result.length === 1 ? "0" : "");
      if (pending) setError("Saldo atualizado para conferência. O resultado anterior pode ser incerto; repetir usa exatamente a mesma chave e os mesmos dados.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Não foi possível atualizar os saldos.");
    } finally {
      setLoading(false);
    }
  };

  const submit = async () => {
    if (!itemId || (!selected && !retryPending) || !canSubmit || !operation.current) return;
    setSaving(true);
    setError("");
    try {
      const body = operation.current.body ?? adjustmentInput(selected!, operation.current.businessKey, kind, quantity, reason, notes);
      operation.current.body = body;
      await inventoryApi.createAdjustment(itemId, body, operation.current.key);
      clearPendingAdjustment(itemId);
      setRetryPending(false);
      setUncertain(false);
      onClose();
      onAdjusted();
    } catch (cause) {
      setRetryPending(true);
      const ambiguous = !(cause instanceof ApiRequestError) || cause.status >= 500;
      setUncertain(ambiguous);
      if (ambiguous) { setRechecked(false); setReconciled(false); }
      if (ambiguous && operation.current) rememberPendingAdjustment(itemId, operation.current);
      setError(`${cause instanceof Error ? cause.message : "Não foi possível confirmar o ajuste."} ${ambiguous ? "O resultado é incerto. Atualize o saldo e repita a mesma operação; a chave será preservada." : "Repita a mesma operação ou cancele e abra um novo ajuste."}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={Boolean(item)} onOpenChange={(open) => { if (!open && !saving && !uncertain) onClose(); }}>
      <DialogContent className="max-h-[90vh] overflow-y-auto border-surface-03 bg-surface-02 text-cream">
        <DialogHeader>
          <DialogTitle>Corrigir / registrar perda</DialogTitle>
          <DialogDescription className="text-stone">{item?.name || "Item"} · {unit}</DialogDescription>
        </DialogHeader>
        {item?.portioned && <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-100">O ajuste ou a perda altera o saldo de porções produzidas. Não altera a matéria-prima nem as etiquetas históricas.</p>}
        {loading ? <p className="flex items-center gap-2 text-sm text-stone"><Loader2 size={16} className="animate-spin" /> Carregando saldos...</p> : (
          <fieldset className="space-y-4" disabled={retryPending}>
            {buckets.length === 0 ? <p className="text-sm text-stone">Nenhum local/lote disponível para ajuste. Atualize os saldos ou confira o cadastro do item.</p> : (
              <>
                {buckets.length > 1 && <label className="block text-sm font-semibold text-cream">Local e lote <span className="text-red-300">*</span>
                  <select className={`${fieldClass} mt-1`} value={bucketIndex} onChange={(event) => { setBucketIndex(event.target.value); setConfirmed(false); }}>
                    <option value="">Selecione o saldo a ajustar</option>
                    {buckets.map((bucket, index) => <option key={`${bucket.location_id || "none"}-${bucket.lot_id || "none"}-${index}`} value={index}>{bucket.location_name || "Local não informado"} · {bucket.lot_code || "Sem lote"} · físico {formatQuantity(bucket.physical)} {bucket.unit_symbol || unit}</option>)}
                  </select>
                </label>}
                {selected && <div className="rounded-lg border border-surface-03 bg-surface-01 p-3 text-sm text-stone">
                  <p className="font-semibold text-cream">{selected.location_name || "Local não informado"} · {selected.lot_code || "Sem lote"}</p>
                  <div className="mt-2 grid grid-cols-3 gap-2"><span>Físico<br /><strong className="text-cream">{formatQuantity(selected.physical)} {unit}</strong></span><span>Reservado<br /><strong className="text-cream">{formatQuantity(selected.reserved)} {unit}</strong></span><span>Disponível<br /><strong className="text-cream">{formatQuantity(selected.available)} {unit}</strong></span></div>
                </div>}
                <fieldset className="space-y-2"><legend className="text-sm font-semibold">Operação</legend><div className="flex flex-wrap gap-4 text-sm"><label className="flex items-center gap-2"><input type="radio" name="inventory-adjustment-kind" checked={kind === "correction"} onChange={() => { setKind("correction"); setQuantity(""); setConfirmed(false); }} /> Corrigir saldo</label><label className="flex items-center gap-2"><input type="radio" name="inventory-adjustment-kind" checked={kind === "loss"} onChange={() => { setKind("loss"); setQuantity(""); setConfirmed(false); }} /> Registrar perda</label></div></fieldset>
                <label className="block text-sm font-semibold">{kind === "correction" ? "Saldo físico contado" : "Quantidade perdida"} ({unit}) <span className="text-red-300">*</span>
                  <input className={`${fieldClass} mt-1`} type="number" min={kind === "correction" ? "0" : item?.portioned ? "1" : "0.000001"} step={item?.portioned ? "1" : "0.000001"} inputMode={item?.portioned ? "numeric" : "decimal"} value={quantity} onChange={(event) => { setQuantity(event.target.value); setConfirmed(false); }} placeholder={kind === "correction" ? "Informe o total contado, não a diferença" : "Informe a quantidade que será baixada"} />
                  <span className="mt-1 block text-xs font-normal text-stone">{kind === "correction" ? "O valor informado substituirá o saldo físico deste local/lote." : "A perda será descontada do saldo físico deste local/lote."}</span>
                </label>
                <label className="block text-sm font-semibold">Motivo <span className="text-red-300">*</span><input className={`${fieldClass} mt-1`} value={reason} onChange={(event) => { setReason(event.target.value); setConfirmed(false); }} maxLength={120} placeholder="Descreva o motivo do ajuste" /></label>
                <label className="block text-sm font-semibold">Observações (opcional)<textarea className={`${fieldClass} mt-1`} rows={2} maxLength={2000} value={notes} onChange={(event) => { setNotes(event.target.value); setConfirmed(false); }} /></label>
                {selected && validQuantity && reason.trim() && <label className="flex items-start gap-2 rounded-lg border border-gold/40 bg-gold/10 p-3 text-sm text-cream"><input className="mt-1" type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /><span>Confirmo {kind === "correction" ? `o saldo físico contado de ${formatQuantity(normalizedQuantity)} ${unit}` : `a perda de ${formatQuantity(normalizedQuantity)} ${unit}`} em {selected.location_name || "local não informado"}, {selected.lot_code || "sem lote"}.</span></label>}
              </>
            )}
          </fieldset>
        )}
        {error && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
        {retryPending && <div className="space-y-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-100"><p>Se precisar encerrar esta tentativa, atualize o saldo e confira o histórico de movimentos antes de iniciar outro ajuste.</p>{!rechecked && <p>Use “Atualizar saldos” para habilitar a conferência.</p>}<label className="flex items-start gap-2"><input className="mt-1" type="checkbox" disabled={!rechecked} checked={reconciled} onChange={(event) => setReconciled(event.target.checked)} /> Conferi o saldo atualizado e o histórico deste item.</label>{reconciled && <button type="button" className="rounded-lg border border-amber-300/50 px-3 py-2 font-semibold" disabled={saving || loading} onClick={() => { if (itemId) clearPendingAdjustment(itemId); onClose(); }}>Encerrar pendência após conferência</button>}</div>}
        <DialogFooter className="gap-2">
          <button type="button" className="inline-flex items-center justify-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm text-stone" disabled={saving} onClick={() => void reloadBuckets()}><RefreshCw size={15} /> Atualizar saldos</button>
          <button type="button" className="rounded-lg border border-surface-03 px-3 py-2 text-sm text-stone disabled:opacity-50" disabled={saving} onClick={onClose}>{uncertain ? "Sair com resultado pendente" : "Cancelar"}</button>
          <button type="button" className="inline-flex items-center justify-center gap-2 rounded-lg bg-gold px-3 py-2 text-sm font-bold text-black disabled:opacity-50" disabled={!canSubmit} onClick={() => void submit()}>{saving && <Loader2 size={15} className="animate-spin" />} {retryPending ? "Repetir mesma operação" : `Confirmar ${kind === "correction" ? "correção" : "perda"}`}</button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
