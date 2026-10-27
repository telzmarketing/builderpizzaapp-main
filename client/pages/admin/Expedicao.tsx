import { orderDisplayCode } from "@/lib/orderIdentity";
import { operationalPaymentLines } from "@/lib/operationalPayment";
import { operationalDrinks, isOperationalDrink } from "@/lib/operationalDrinks";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Bike, CheckCircle2, Clock3, Loader2, MapPin, Maximize2, Minimize2, PackageCheck, Printer, RefreshCw, Truck, UserRound, WifiOff } from "lucide-react";
import KdsSessionActions from "@/components/kds/KdsSessionActions";
import KdsBrandLogo from "@/components/kds/KdsBrandLogo";
import LabelPrintDialog from "@/components/kds/LabelPrintDialog";
import { useToast } from "@/hooks/use-toast";
import { deliveryApi, kdsApi, type KdsDispatchOrder, type KdsDriver, type KdsOrderItem } from "@/lib/api";
import { loadSoundType, playOrderAlert } from "@/lib/orderSound";
import { replaceDispatchOrder } from "@/lib/kds";

const POLL_INTERVAL_MS = 15_000;

function elapsed(date: string) {
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(date).getTime()) / 60_000));
  return minutes < 60 ? `${minutes}min` : `${Math.floor(minutes / 60)}h ${minutes % 60}min`;
}

function itemDescription(item: KdsOrderItem) {
  const base = item.flavors?.length ? item.flavors.map((flavor) => flavor.name).join(" / ") : item.product_name;
  return [base, item.selected_size, item.selected_crust_type, item.selected_drink_variant].filter(Boolean).join(" · ");
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Não foi possível atualizar a expedição.";
}

function productionUnitStatus(unit: NonNullable<KdsDispatchOrder["production_units"]>[number]) {
  if (unit.dispatch_completed_at) return "Fechada na expedição";
  const labels: Record<string, string> = {
    unassigned: "Aguardando preparo", queued: "Aguardando preparo", assembling: "Em montagem",
    assembled: "Montada", baking: "No forno", checking: "Em conferência", ready: "Pronta para fechar",
    blocked: "Bloqueada", cancelled: "Cancelada",
  };
  return labels[unit.state] ?? unit.state;
}

function hasDispatchManagePermission() {
  try {
    const permissions = JSON.parse(localStorage.getItem("admin_permissions") || "null") as {
      is_master?: boolean;
      modules?: Record<string, Record<string, boolean>>;
    } | null;
    return permissions?.is_master === true || permissions?.modules?.expedicao?.manage === true;
  } catch {
    return false;
  }
}

export default function AdminExpedicao() {
  const { toast } = useToast();
  const [orders, setOrders] = useState<KdsDispatchOrder[]>([]);
  const [drivers, setDrivers] = useState<KdsDriver[]>([]);
  const [returnDrafts, setReturnDrafts] = useState<Record<string, { unitIds: string[]; reason: string }>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [assigning, setAssigning] = useState<string | null>(null);
  const [updatingUnitId, setUpdatingUnitId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const [labelOrder, setLabelOrder] = useState<KdsDispatchOrder | null>(null);
  const [, setTick] = useState(0);
  const knownOrderIds = useRef<Set<string>>(new Set());
  const initialLoad = useRef(true);
  const actionLock = useRef(false);
  const loadSequence = useRef(0);
  const canManageReturns = useMemo(hasDispatchManagePermission, []);
  const pickupCount = orders.filter((order) => order.fulfillment_type === "pickup").length;
  const deliveryCount = orders.filter((order) => order.fulfillment_type !== "pickup").length;

  const loadData = useCallback(async (manual = false) => {
    if (actionLock.current) return;
    const sequence = ++loadSequence.current;
    if (manual) setRefreshing(true);
    try {
      const [nextOrders, nextDrivers] = await Promise.all([kdsApi.listDispatchOrders(), kdsApi.listDispatchDrivers()]);
      if (sequence !== loadSequence.current) return;
      const hasNewOrder = nextOrders.some((order) => !knownOrderIds.current.has(order.id));
      if (!initialLoad.current && hasNewOrder) playOrderAlert(loadSoundType());
      initialLoad.current = false;
      knownOrderIds.current = new Set(nextOrders.map((order) => order.id));
      setOrders(nextOrders);
      setDrivers(nextDrivers);
      setError(null);
      setLastRefresh(new Date());
    } catch (caught) {
      if (sequence !== loadSequence.current) return;
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
    const poll = window.setInterval(() => void loadData(), POLL_INTERVAL_MS);
    return () => window.clearInterval(poll);
  }, [loadData]);

  useEffect(() => {
    const timer = window.setInterval(() => setTick((value) => value + 1), 10_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const onFullscreenChange = () => setFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", onFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", onFullscreenChange);
  }, []);

  const toggleFullscreen = async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch {
      toast({ title: "Tela cheia indisponível", description: "O navegador bloqueou o modo KDS." });
    }
  };

  const completeUnit = async (order: KdsDispatchOrder, unitId: string, expectedVersion: number) => {
    if (actionLock.current) return;
    actionLock.current = true;
    loadSequence.current += 1;
    setUpdatingUnitId(unitId);
    try {
      const updated = await kdsApi.completeDispatchUnit(order.id, unitId, expectedVersion);
      setOrders((current) => replaceDispatchOrder(current, updated));
      setError(null);
      const assignment = updated.auto_assignment;
      if (assignment?.status === "assigned") {
        toast({ title: "Unidade fechada e motoboy atribuído", description: assignment.delivery_person_name || `Pedido #${orderDisplayCode(order)}` });
      } else if (assignment?.status === "unavailable") {
        toast({ title: "Unidade fechada; motoboy aguardando", description: assignment.message || "Nenhum motoboy está disponível para atribuição automática.", variant: "destructive" });
      } else if (assignment?.status === "disabled") {
        toast({ title: "Unidade fechada; autoatribuição desativada", description: "Confira a regra de atribuição automática nas configurações de logística.", variant: "destructive" });
      } else if (assignment?.status === "blocked") {
        toast({ title: "Unidade fechada; despacho bloqueado", description: assignment.message || "O pedido ainda não está liberado para despacho.", variant: "destructive" });
      } else {
        toast({ title: "Unidade fechada na expedição", description: `Pedido #${orderDisplayCode(order)}` });
      }
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast({ title: "Fechamento não concluído", description: message, variant: "destructive" });
    } finally {
      actionLock.current = false;
      setUpdatingUnitId(null);
      void loadData();
    }
  };

  const updateReturnDraft = (orderId: string, update: Partial<{ unitIds: string[]; reason: string }>) => {
    setReturnDrafts((current) => ({
      ...current,
      [orderId]: { unitIds: current[orderId]?.unitIds ?? [], reason: current[orderId]?.reason ?? "", ...update },
    }));
  };

  const returnUnitsToKitchen = async (order: KdsDispatchOrder) => {
    const draft = returnDrafts[order.id];
    if (!canManageReturns || !draft?.unitIds.length || !draft.reason.trim() || actionLock.current) return;
    actionLock.current = true;
    loadSequence.current += 1;
    setAssigning(order.id);
    try {
      await kdsApi.returnDispatchUnitsToKitchen(order.id, draft.unitIds, draft.reason.trim());
      setOrders((current) => current.filter((item) => item.id !== order.id));
      setReturnDrafts((current) => { const next = { ...current }; delete next[order.id]; return next; });
      setError(null);
      toast({ title: "Unidades devolvidas à cozinha", description: `Pedido #${orderDisplayCode(order)}` });
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast({ title: "Retorno não concluído", description: message, variant: "destructive" });
    } finally {
      actionLock.current = false;
      setAssigning(null);
      void loadData();
    }
  };

  const completePickup = async (order: KdsDispatchOrder) => {
    const units = order.production_units ?? [];
    if (units.length === 0 || units.some((unit) => !unit.dispatch_completed_at) || actionLock.current) return;
    actionLock.current = true;
    loadSequence.current += 1;
    setAssigning(order.id);
    try {
      await kdsApi.completeDispatchPickup(order.id);
      setOrders((current) => current.filter((item) => item.id !== order.id));
      setError(null);
      toast({ title: "Retirada concluída", description: `Pedido #${orderDisplayCode(order)} entregue ao cliente.` });
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast({ title: "Retirada não concluída", description: message, variant: "destructive" });
    } finally {
      actionLock.current = false;
      setAssigning(null);
      void loadData();
    }
  };

  const markDriverPickedUp = async (order: KdsDispatchOrder) => {
    const deliveryId = order.delivery?.id;
    if (!deliveryId || order.delivery?.status !== "assigned" || actionLock.current) return;
    actionLock.current = true;
    loadSequence.current += 1;
    setAssigning(order.id);
    try {
      await deliveryApi.updateStatus(deliveryId, "picked_up");
      setOrders((current) => current.filter((item) => item.id !== order.id));
      setError(null);
      toast({ title: "Pedido retirado pelo motoboy", description: `Pedido #${orderDisplayCode(order)} saiu da expedição.` });
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast({ title: "Retirada não concluída", description: message, variant: "destructive" });
    } finally {
      actionLock.current = false;
      setAssigning(null);
      void loadData();
    }
  };

  const finalizationOrders = orders.filter((order) => {
    const units = order.production_units ?? [];
    return units.length === 0 || units.some((unit) => !unit.dispatch_completed_at);
  });
  const awaitingPickupOrders = orders.filter((order) => {
    const units = order.production_units ?? [];
    return units.length > 0 && units.every((unit) => Boolean(unit.dispatch_completed_at));
  });
  const pipelineOrders = [...finalizationOrders, ...awaitingPickupOrders];
  return (
    <section className={`${fullscreen ? "fixed inset-0 z-[100]" : "min-h-screen"} flex flex-col overflow-hidden bg-surface-00 text-cream`}>
      <header className="flex flex-col gap-4 border-b border-surface-03 bg-surface-02 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3"><KdsBrandLogo fallback={<span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-300"><Truck size={28} /></span>} /><div><p className="text-xs font-bold uppercase tracking-[0.2em] text-emerald-300">KDS touch</p><h1 className="text-2xl font-black">Expedição</h1><p className="text-sm text-stone">{lastRefresh ? `Atualizado às ${lastRefresh.toLocaleTimeString("pt-BR")}` : "Sincronizando"}</p></div></div>
        <div className="flex flex-wrap gap-2"><div className="flex min-h-12 items-center gap-2 rounded-xl border border-surface-03 bg-surface-01 px-4 font-bold text-emerald-300"><Bike /> {drivers.length} disponiveis</div><button type="button" aria-label="Atualizar expedicao" onClick={() => void loadData(true)} disabled={refreshing} className="flex min-h-12 min-w-12 items-center justify-center rounded-xl border border-surface-03 bg-surface-01 active:scale-95 disabled:opacity-50"><RefreshCw className={refreshing ? "animate-spin" : ""} /></button><button type="button" aria-label={fullscreen ? "Sair da tela cheia" : "Entrar em tela cheia"} onClick={() => void toggleFullscreen()} className="flex min-h-12 min-w-12 items-center justify-center rounded-xl border border-surface-03 bg-surface-01 active:scale-95">{fullscreen ? <Minimize2 /> : <Maximize2 />}</button><KdsSessionActions /></div>
      </header>

      {error && <div role="alert" className="m-3 flex items-center justify-between gap-3 rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-red-200"><span className="flex items-center gap-2"><WifiOff /> {error}</span><button type="button" onClick={() => void loadData(true)} className="min-h-12 rounded-lg bg-red-500 px-5 font-bold text-white active:bg-red-700">Tentar novamente</button></div>}

      {!loading && <div className="grid grid-cols-2 gap-3 border-b border-surface-03 bg-surface-01/80 p-3 sm:grid-cols-4">
        <div className="rounded-xl border border-emerald-500/25 bg-emerald-500/10 p-3"><p className="text-[11px] font-bold uppercase tracking-wider text-emerald-300">Na fila</p><p className="mt-1 text-2xl font-black">{orders.length}</p></div>
        <div className="rounded-xl border border-sky-500/25 bg-sky-500/10 p-3"><p className="text-[11px] font-bold uppercase tracking-wider text-sky-300">Retiradas</p><p className="mt-1 text-2xl font-black">{pickupCount}</p></div>
        <div className="rounded-xl border border-amber-500/25 bg-amber-500/10 p-3"><p className="text-[11px] font-bold uppercase tracking-wider text-amber-300">Entregas</p><p className="mt-1 text-2xl font-black">{deliveryCount}</p></div>
        <div className="rounded-xl border border-violet-500/25 bg-violet-500/10 p-3"><p className="text-[11px] font-bold uppercase tracking-wider text-violet-300">Motoboys livres</p><p className="mt-1 text-2xl font-black">{drivers.length}</p></div>
      </div>}

      {loading ? <div className="flex flex-1 items-center justify-center gap-3 text-lg text-stone"><Loader2 className="animate-spin text-emerald-300" /> Carregando expedição...</div> : orders.length === 0 ? <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center text-stone"><PackageCheck size={64} className="text-emerald-400" /><h2 className="text-2xl font-black text-cream">Expedição em dia</h2><p>Nenhum pedido aguarda conferência e motoboy.</p></div> : (
        <div className="grid flex-1 auto-rows-max gap-4 overflow-y-auto p-4 xl:grid-cols-2 2xl:grid-cols-3">
          {pipelineOrders.map((order, index) => {
            const pipelineHeading = index === 0 && finalizationOrders.length > 0 ? <div className="col-span-full rounded-xl border border-amber-500/30 bg-amber-500/5 p-4"><h2 className="text-xl font-black text-amber-200">Finalização</h2><p className="text-sm text-stone">Finalize cada unidade antes de liberar o pedido para retirada.</p></div> : index === finalizationOrders.length ? <div className="col-span-full rounded-xl border border-sky-500/30 bg-sky-500/5 p-4"><h2 className="text-xl font-black text-sky-200">Aguardando retirada</h2><p className="text-sm text-stone">Pedidos finalizados aguardando coleta.</p></div> : null;
            const units = order.production_units ?? [];
            const closedUnits = units.filter((unit) => Boolean(unit.dispatch_completed_at)).length;
            const allUnitsClosed = units.length > 0 && closedUnits === units.length;
            const isPickup = order.fulfillment_type === "pickup";
            const drinks = operationalDrinks(order);
            const title = isPickup
              ? allUnitsClosed ? "Pronto para retirada" : "Feche cada unidade para liberar a retirada"
              : order.delivery?.delivery_person_name
                ? "Motoboy atribuído — aguardando coleta"
                : allUnitsClosed
                  ? "Unidades fechadas — aguardando motoboy disponível"
                  : "Feche cada unidade para solicitar o motoboy automático";
            return <Fragment key={order.id}>{pipelineHeading}<article className="flex flex-col gap-4 rounded-2xl border border-surface-03 bg-surface-02 p-5 shadow-soft">
              <div className="flex items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wider text-emerald-300">{title}</p><h2 className="text-2xl font-black">#{orderDisplayCode(order)}</h2><p className="flex items-center gap-1 text-stone"><UserRound size={15} />{order.delivery_name}</p>{order.delivery?.delivery_person_name && <p className="mt-2 flex items-center gap-1.5 text-sm font-bold text-emerald-300"><Bike size={16} /> Motoboy: {order.delivery.delivery_person_name}</p>}{isPickup && <span className="mt-2 inline-flex rounded-full bg-sky-500/15 px-3 py-1 text-xs font-black uppercase text-sky-200">Retirada</span>}</div><span className="flex items-center gap-1 rounded-lg bg-amber-500/10 px-3 py-2 font-bold text-amber-300"><Clock3 size={17} />{elapsed(order.updated_at || order.created_at)}</span></div>
              {!isPickup && <div className="rounded-xl bg-surface-01 p-3 text-sm"><p className="flex items-start gap-2 font-semibold"><MapPin size={18} className="mt-0.5 shrink-0 text-gold" />{order.delivery_street}{order.delivery_complement ? `, ${order.delivery_complement}` : ""} · {order.delivery_city}</p></div>}
              <div className="space-y-3 border-y border-surface-03 py-4">{order.items.filter((item) => !isOperationalDrink(item)).map((item) => <div key={item.id}><p className="font-bold"><span className="mr-2 text-lg text-gold">{item.quantity}x</span>{itemDescription(item)}</p>{item.notes && <p className="mt-1 rounded-lg bg-amber-500/10 p-2 text-sm font-semibold text-amber-200">Obs.: {item.notes}</p>}</div>)}</div>
              {drinks.length > 0 && <section aria-label="Atenção — bebidas" className="rounded-xl border-2 border-stone-300 bg-stone-100 p-4 text-zinc-950"><h3 className="font-black">ATENÇÃO — BEBIDAS</h3>{drinks.map((drink, index) => <div key={`${drink.product_id || index}:${index}`} className="mt-2"><p className="text-lg font-bold">{drink.quantity} × {drink.name}</p>{drink.notes && <p className="text-sm">Obs.: {drink.notes}</p>}</div>)}</section>}
              <section aria-label="Fechamento por unidade" className="space-y-3 rounded-xl border border-surface-03 bg-surface-01 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-black">Fechamento por unidade</h3><span className="text-sm font-bold text-stone">{closedUnits}/{units.length} fechada(s)</span></div>
                {units.length === 0 ? <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm font-semibold text-amber-200">As unidades deste pedido ainda não foram carregadas; o despacho permanece bloqueado.</p> : units.map((unit) => {
                  const item = order.items.find((candidate) => candidate.id === unit.order_item_id);
                  const isDrink = unit.product_type === "drink" || Boolean(item && isOperationalDrink(item));
                  const completed = Boolean(unit.dispatch_completed_at);
                  const canClose = unit.state === "ready" && !completed;
                  const busy = updatingUnitId === unit.id;
                  return <div key={unit.id} className="flex flex-col gap-3 rounded-lg border border-surface-03 p-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="min-w-0"><p className="font-bold">{isDrink ? "Bebida" : (unit.product_type === "pizza" || item?.product_type === "pizza" || Boolean(item?.flavors?.length) ? "Pizza" : "Item")} {unit.unit_index} · {item ? itemDescription(item) : (unit.product_name || "Item")}</p><p className={`mt-1 text-sm font-semibold ${completed ? "text-emerald-300" : unit.state === "blocked" ? "text-red-300" : "text-stone"}`}>{productionUnitStatus(unit)}</p></div>
                    <div className="flex shrink-0 flex-wrap gap-2">
                      <button type="button" disabled={Boolean(updatingUnitId) || Boolean(assigning)} onClick={() => setLabelOrder(order)} className="flex min-h-11 items-center justify-center gap-2 rounded-lg border border-emerald-500/40 px-3 text-sm font-bold text-emerald-200 disabled:opacity-40"><Printer size={16} /> Etiquetas do pedido</button>
                      <button type="button" disabled={!canClose || Boolean(updatingUnitId) || Boolean(assigning)} onClick={() => void completeUnit(order, unit.id, unit.version)} className="flex min-h-11 items-center justify-center gap-2 rounded-lg bg-emerald-600 px-3 text-sm font-black text-white disabled:opacity-40">{busy ? <Loader2 className="animate-spin" size={16} /> : <CheckCircle2 size={16} />}{completed ? "Unidade fechada" : canClose ? "Fechar unidade" : "Aguardando preparo"}</button>
                    </div>
                  </div>;
                })}
                {units.length > 0 && <p className="text-xs text-stone">A impressão abre as etiquetas do pedido inteiro; o serviço atual não permite filtrar uma unidade.</p>}
              </section>
              {canManageReturns && <section aria-label="Devolver unidades à cozinha" className="space-y-3 rounded-xl border border-amber-500/30 bg-amber-500/5 p-3">
                <div><h3 className="font-black text-amber-200">Devolver unidade(s) à cozinha</h3><p className="text-xs text-stone">Selecione as unidades que precisam de retrabalho e informe o motivo.</p></div>
                {units.filter((unit) => unit.state === "ready").map((unit) => {
                  const item = order.items.find((candidate) => candidate.id === unit.order_item_id);
                  const isSelected = (returnDrafts[order.id]?.unitIds ?? []).includes(unit.id);
                  return <label key={unit.id} className="flex min-h-11 items-center gap-3 rounded-lg bg-surface-01 px-3 text-sm font-semibold">
                    <input type="checkbox" checked={isSelected} disabled={Boolean(assigning) || Boolean(updatingUnitId)} onChange={(event) => {
                      const current = returnDrafts[order.id]?.unitIds ?? [];
                      updateReturnDraft(order.id, { unitIds: event.target.checked ? [...current, unit.id] : current.filter((id) => id !== unit.id) });
                    }} />
                    {unit.product_type === "drink" || Boolean(item && isOperationalDrink(item)) ? "Bebida" : unit.product_type === "pizza" || item?.product_type === "pizza" || Boolean(item?.flavors?.length) ? "Pizza" : "Item"} {unit.unit_index} · {item ? itemDescription(item) : unit.product_name || "Item"}
                  </label>;
                })}
                <label className="block text-sm font-semibold">Motivo obrigatório<textarea maxLength={300} required aria-required="true" value={returnDrafts[order.id]?.reason ?? ""} onChange={(event) => updateReturnDraft(order.id, { reason: event.target.value })} placeholder="Descreva por que a unidade deve voltar à cozinha" className="mt-1 min-h-20 w-full rounded-lg border border-surface-03 bg-surface-01 p-3 text-cream" /></label>
                <button type="button" disabled={!returnDrafts[order.id]?.unitIds.length || !returnDrafts[order.id]?.reason.trim() || Boolean(assigning) || Boolean(updatingUnitId)} onClick={() => void returnUnitsToKitchen(order)} className="flex min-h-12 w-full items-center justify-center gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 font-black text-amber-100 disabled:opacity-40">{assigning === order.id ? <Loader2 className="animate-spin" /> : <RefreshCw />} Devolver seleção à cozinha</button>
              </section>}
              <div className="rounded-xl border border-surface-03 bg-surface-01 p-3 text-sm" aria-label="Pagamento"><p className="font-black">PAGAMENTO</p>{operationalPaymentLines(order).map((line, index) => <p key={index} className="mt-1 font-bold">{line}</p>)}</div>
              {isPickup ? <button type="button" disabled={!allUnitsClosed || Boolean(assigning) || Boolean(updatingUnitId)} onClick={() => void completePickup(order)} className="mt-auto flex min-h-16 w-full items-center justify-center gap-2 rounded-xl bg-sky-600 px-4 text-lg font-black text-white transition-transform active:scale-[0.98] disabled:opacity-40">{assigning === order.id ? <Loader2 className="animate-spin" /> : <CheckCircle2 />}{assigning === order.id ? "Concluindo..." : allUnitsClosed ? "Concluir retirada" : "Feche todas as unidades"}</button> : <div className={`mt-auto flex min-h-16 w-full items-center justify-center gap-2 rounded-xl border px-4 text-center font-black ${order.delivery?.delivery_person_name ? "border-emerald-500/35 bg-emerald-500/10 text-emerald-200" : allUnitsClosed ? "border-amber-500/35 bg-amber-500/10 text-amber-200" : "border-surface-03 bg-surface-01 text-stone"}`}><Bike />{order.delivery?.delivery_person_name ? `Motoboy atribuído: ${order.delivery.delivery_person_name}` : allUnitsClosed ? "Aguardando motoboy disponível" : "Despacho liberado ao fechar todas as unidades"}</div>}
              {!isPickup && allUnitsClosed && order.delivery?.status === "assigned" && <button type="button" disabled={Boolean(assigning) || Boolean(updatingUnitId)} onClick={() => void markDriverPickedUp(order)} className="flex min-h-14 w-full items-center justify-center gap-2 rounded-xl bg-amber-500 px-4 text-lg font-black text-zinc-950 transition-transform active:scale-[0.98] disabled:opacity-40">{assigning === order.id ? <Loader2 className="animate-spin" /> : <Bike />}{assigning === order.id ? "Confirmando..." : "Retirado pelo motoboy"}</button>}
            </article></Fragment>;
          })}
        </div>
      )}
      <LabelPrintDialog orderId={labelOrder?.id ?? null} orderCode={labelOrder?.order_code} open={Boolean(labelOrder)} onOpenChange={(next) => { if (!next) setLabelOrder(null); }}/>
    </section>
  );
}
