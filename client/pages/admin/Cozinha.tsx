import { useCallback, useEffect, useRef, useState } from "react";
import { Bell, BellOff, Bike, CheckCircle2, ChefHat, Clock3, Loader2, Maximize2, Minimize2, RefreshCw, UtensilsCrossed, WifiOff } from "lucide-react";
import KdsSessionActions from "@/components/kds/KdsSessionActions";
import KdsRecipeDetails from "@/components/kds/KdsRecipeDetails";
import KdsMultiOperatorBoard from "@/components/kds/KdsMultiOperatorBoard";
import { useToast } from "@/hooks/use-toast";
import { kdsApi, type KdsKitchenOrder, type KdsOrderItem, type KdsProductionUnit } from "@/lib/api";
import { loadSoundType, playOrderAlert } from "@/lib/orderSound";
import { activeKitchenOrders } from "@/lib/kds";

const POLL_INTERVAL_MS = 15_000;

function elapsed(date: string) {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(date).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}min`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}min`;
}

function itemDescription(item: KdsOrderItem) {
  const parts: string[] = [];
  parts.push(item.flavors?.length ? item.flavors.map((flavor) => flavor.name).join(" / ") : item.product_name);
  if (item.selected_size) parts.push(`(${item.selected_size})`);
  if (item.selected_crust_type) parts.push(`· ${item.selected_crust_type}`);
  if (item.selected_drink_variant) parts.push(`· ${item.selected_drink_variant}`);
  return parts.join(" ");
}

function productionUnitStatus(unit: KdsProductionUnit) {
  const labels: Record<string, string> = {
    unassigned: "Não iniciada", queued: "Aguardando pizzaiolo", assembling: "Em montagem",
    assembled: "Montada", baking: "No forno", checking: "Em conferência", ready: "Pronta",
    blocked: "Bloqueada", cancelled: "Cancelada",
  };
  return labels[unit.state] ?? unit.state;
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Não foi possível atualizar a cozinha.";
}

export default function AdminCozinha() {
  const { toast } = useToast();
  const [orders, setOrders] = useState<KdsKitchenOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [updating, setUpdating] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [soundOn, setSoundOn] = useState(true);
  const [fullscreen, setFullscreen] = useState(false);
  const [, setTick] = useState(0);
  const knownWaitingIds = useRef<Set<string>>(new Set());
  const initialLoad = useRef(true);
  const actionLock = useRef(false);

  const loadOrders = useCallback(async (manual = false) => {
    if (manual) setRefreshing(true);
    try {
      const data = await kdsApi.listKitchenOrders();
      const active = activeKitchenOrders(data);
      const waiting = active.filter((order) => order.status === "paid" || order.status === "pago");
      const hasNewOrder = waiting.some((order) => !knownWaitingIds.current.has(order.id));
      if (!initialLoad.current && soundOn && hasNewOrder) playOrderAlert(loadSoundType());
      knownWaitingIds.current = new Set(waiting.map((order) => order.id));
      initialLoad.current = false;
      setOrders(active);
      setError(null);
      setLastRefresh(new Date());
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [soundOn]);

  useEffect(() => {
    void loadOrders();
    const poll = window.setInterval(() => void loadOrders(), POLL_INTERVAL_MS);
    return () => window.clearInterval(poll);
  }, [loadOrders]);

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

  const startOrder = async (order: KdsKitchenOrder) => {
    if ((order.status !== "paid" && order.status !== "pago") || actionLock.current) return;
    actionLock.current = true;
    setUpdating(order.id);
    try {
      const updated = await kdsApi.startKitchenOrder(order.id);
      setOrders((current) => activeKitchenOrders(current.map((item) => item.id === order.id ? updated : item)));
      toast({ title: "Unidades encaminhadas para a fila do pizzaiolo", description: `Pedido #${(order.order_code || order.id.slice(0, 8)).toUpperCase()}` });
      setError(null);
      setLastRefresh(new Date());
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast({ title: "Ação não concluída", description: message, variant: "destructive" });
    } finally {
      actionLock.current = false;
      setUpdating(null);
    }
  };

  const finishOrder = async (order: KdsKitchenOrder) => {
    const units = order.production_units ?? [];
    if (units.length === 0 || units.some((unit) => unit.state !== "ready") || actionLock.current) return;
    actionLock.current = true;
    setUpdating(order.id);
    try {
      const updated = await kdsApi.markKitchenOrderReady(order.id);
      setOrders((current) => current.map((item) => item.id === order.id ? updated : item));
      setError(null);
      setLastRefresh(new Date());
      toast({ title: "Preparo finalizado", description: `Pedido #${(order.order_code || order.id.slice(0, 8)).toUpperCase()} enviado à expedição.` });
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast({ title: "Preparo não finalizado", description: message, variant: "destructive" });
    } finally {
      actionLock.current = false;
      setUpdating(null);
    }
  };

  const waitingOrders = orders.filter((order) => order.status === "paid" || order.status === "pago").sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at));
  const preparingOrders = orders.filter((order) => order.status === "preparing").sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at));
  return (
    <section className={`${fullscreen ? "fixed inset-0 z-[100]" : "min-h-screen"} flex flex-col overflow-hidden bg-surface-00 text-cream`}>
      <header className="flex flex-col gap-4 border-b border-surface-03 bg-surface-02 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-gold/15 text-gold"><ChefHat size={28} /></span>
          <div><p className="text-xs font-bold uppercase tracking-[0.2em] text-gold">KDS touch</p><h1 className="text-2xl font-black">Pizzaiolo</h1><p className="text-sm text-stone">{lastRefresh ? `Atualizado às ${lastRefresh.toLocaleTimeString("pt-BR")}` : "Sincronizando"}</p></div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" aria-label={soundOn ? "Silenciar alertas" : "Ativar alertas"} onClick={() => setSoundOn((value) => !value)} className="flex min-h-12 min-w-12 items-center justify-center rounded-xl border border-surface-03 bg-surface-01 text-gold active:scale-95">{soundOn ? <Bell /> : <BellOff />}</button>
          <button type="button" aria-label="Atualizar pedidos" onClick={() => void loadOrders(true)} disabled={refreshing} className="flex min-h-12 min-w-12 items-center justify-center rounded-xl border border-surface-03 bg-surface-01 active:scale-95 disabled:opacity-50"><RefreshCw className={refreshing ? "animate-spin" : ""} /></button>
          <button type="button" aria-label={fullscreen ? "Sair da tela cheia" : "Entrar em tela cheia"} onClick={() => void toggleFullscreen()} className="flex min-h-12 min-w-12 items-center justify-center rounded-xl border border-surface-03 bg-surface-01 active:scale-95">{fullscreen ? <Minimize2 /> : <Maximize2 />}</button>
          <KdsSessionActions />
        </div>
      </header>

      {error && <div role="alert" className="m-3 flex items-center justify-between gap-3 rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-red-200"><span className="flex items-center gap-2"><WifiOff /> {error}</span><button type="button" onClick={() => void loadOrders(true)} className="min-h-12 rounded-lg bg-red-500 px-5 font-bold text-white active:bg-red-700">Tentar novamente</button></div>}

      <div className="p-3 pb-0"><KdsMultiOperatorBoard /></div>

      {loading ? <div className="flex flex-1 items-center justify-center gap-3 text-lg text-stone"><Loader2 className="animate-spin text-gold" /> Carregando pedidos...</div> : (
        <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-y-auto p-3 lg:grid-cols-2 lg:items-start">
          <section className="flex min-w-0 flex-col rounded-2xl border border-surface-03 bg-surface-01">
            <div className="flex items-center justify-between border-b border-surface-03 px-5 py-4"><h2 className="text-lg font-black text-amber-300">Aguardando preparo</h2><span className="rounded-full bg-surface-03 px-3 py-1 font-black">{waitingOrders.length}</span></div>
            <div className="grid gap-4 p-4 xl:grid-cols-2">
              {waitingOrders.length === 0 && <div className="col-span-full flex min-h-36 flex-col items-center justify-center gap-3 text-center text-stone"><UtensilsCrossed size={36} /><strong>Nenhum pedido aguardando início</strong></div>}
              {waitingOrders.map((order) => <article key={order.id} className="flex flex-col gap-4 rounded-2xl border border-surface-03 bg-surface-02 p-4 shadow-soft">
                <div className="flex items-start justify-between gap-3"><div><strong className="text-xl">#{(order.order_code || order.id.slice(0, 8)).toUpperCase()}</strong><p className="text-sm text-stone">{order.sales_channel === "dine_in" || order.fulfillment_type === "dine_in" ? "Salão" : order.fulfillment_type === "pickup" ? "Retirada no balcão" : "Entrega"}</p>{order.delivery?.delivery_person_name && <p className="mt-2 flex items-center gap-1.5 text-sm font-bold text-emerald-300"><Bike size={16} /> Motoboy: {order.delivery.delivery_person_name}</p>}</div><span className="flex items-center gap-1 rounded-lg bg-surface-01 px-2 py-1 text-sm font-bold text-amber-300"><Clock3 size={16} />{elapsed(order.created_at)}</span></div>
                <div className="space-y-3 border-y border-surface-03 py-4">{order.items.map((item) => <div key={item.id} className="space-y-2"><p className="font-bold"><span className="mr-2 text-lg text-gold">{item.quantity}x</span>{itemDescription(item)}</p>{item.add_ons?.length > 0 && <p className="text-xs text-stone">Adicionais: {item.add_ons.join(", ")}</p>}{item.notes && <p className="mt-1 rounded-lg bg-amber-500/10 p-2 text-sm font-semibold text-amber-200">Obs.: {item.notes}</p>}<KdsRecipeDetails recipe={item.recipe} /></div>)}</div>
                <button type="button" disabled={Boolean(updating)} onClick={() => void startOrder(order)} className="mt-auto flex min-h-16 w-full items-center justify-center gap-2 rounded-xl bg-orange-500 px-4 text-lg font-black text-white transition-transform active:scale-[0.98] disabled:opacity-50">{updating === order.id ? <Loader2 className="animate-spin" /> : <CheckCircle2 />}{updating === order.id ? "Inicializando unidades..." : "Iniciar preparo"}</button>
              </article>)}
            </div>
          </section>
          <section className="flex min-w-0 flex-col rounded-2xl border border-surface-03 bg-surface-01">
            <div className="flex items-center justify-between border-b border-surface-03 px-5 py-4"><div><h2 className="text-lg font-black text-orange-300">Em preparo</h2><p className="text-sm text-stone">Acompanhe cada unidade e finalize o pedido quando todas estiverem prontas.</p></div><span className="rounded-full bg-surface-03 px-3 py-1 font-black">{preparingOrders.length}</span></div>
            <div className="grid gap-4 p-4 xl:grid-cols-2">
              {preparingOrders.length === 0 && <div className="col-span-full flex min-h-36 flex-col items-center justify-center gap-3 text-center text-stone"><UtensilsCrossed size={36} /><strong>Nenhum pedido em preparo</strong></div>}
              {preparingOrders.map((order) => {
                const units = order.production_units ?? [];
                const readyCount = units.filter((unit) => unit.state === "ready").length;
                const allReady = units.length > 0 && readyCount === units.length;
                return <article key={order.id} className="flex flex-col gap-4 rounded-2xl border border-surface-03 bg-surface-02 p-4 shadow-soft">
                  <div className="flex items-start justify-between gap-3"><div><strong className="text-xl">#{(order.order_code || order.id.slice(0, 8)).toUpperCase()}</strong><p className="text-sm text-stone">{order.sales_channel === "dine_in" || order.fulfillment_type === "dine_in" ? "Salão" : order.fulfillment_type === "pickup" ? "Retirada no balcão" : "Entrega"}</p>{order.delivery?.delivery_person_name && <p className="mt-2 flex items-center gap-1.5 text-sm font-bold text-emerald-300"><Bike size={16} /> Motoboy: {order.delivery.delivery_person_name}</p>}</div><span className="flex items-center gap-1 rounded-lg bg-surface-01 px-2 py-1 text-sm font-bold text-amber-300"><Clock3 size={16} />{elapsed(order.created_at)}</span></div>
                  <section aria-label="Progresso por unidade" className="space-y-2 border-y border-surface-03 py-4">
                    <div className="flex items-center justify-between"><h3 className="font-black">Progresso das unidades</h3><span className="text-sm font-bold text-stone">{readyCount}/{units.length} prontas</span></div>
                    {units.length === 0 ? <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm font-semibold text-amber-200">As unidades de produção ainda não foram carregadas. O pedido não pode ser finalizado.</p> : units.map((unit) => {
                      const item = order.items.find((candidate) => candidate.id === unit.order_item_id);
                      const isDrink = unit.product_type === "drink" || Boolean(item?.is_drink) || item?.product_type === "drink";
                      return <div key={unit.id} className="flex items-center justify-between gap-3 rounded-lg bg-surface-01 px-3 py-2"><span className="min-w-0 truncate font-semibold">{isDrink ? "Bebida" : "Pizza"} {unit.unit_index} · {item ? itemDescription(item) : unit.product_name}</span><span className={`shrink-0 text-sm font-bold ${unit.state === "ready" ? "text-emerald-300" : unit.state === "blocked" ? "text-red-300" : "text-stone"}`}>{productionUnitStatus(unit)}</span></div>;
                    })}
                  </section>
                  <button type="button" disabled={!allReady || Boolean(updating)} onClick={() => void finishOrder(order)} className="mt-auto flex min-h-16 w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 text-lg font-black text-white transition-transform active:scale-[0.98] disabled:opacity-50">{updating === order.id ? <Loader2 className="animate-spin" /> : <CheckCircle2 />}{updating === order.id ? "Finalizando preparo..." : allReady ? "Finalizar preparo" : "Aguardando todas as unidades"}</button>
                </article>;
              })}
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
