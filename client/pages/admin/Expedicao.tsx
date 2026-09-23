import { useCallback, useEffect, useRef, useState } from "react";
import { Bike, CheckCircle2, Clock3, Loader2, MapPin, Maximize2, Minimize2, PackageCheck, RefreshCw, Truck, UserRound, WifiOff } from "lucide-react";
import KdsSessionActions from "@/components/kds/KdsSessionActions";
import { useToast } from "@/hooks/use-toast";
import { kdsApi, type KdsDispatchOrder, type KdsDriver, type KdsOrderItem } from "@/lib/api";
import { loadSoundType, playOrderAlert } from "@/lib/orderSound";
import { clearAssignedDriverSelections } from "@/lib/kds";

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

function paymentLabel(order: KdsDispatchOrder) {
  if (!order.pay_on_delivery) return "Pagamento confirmado";
  if (order.delivery_payment_method === "cash") {
    return order.cash_needs_change && order.cash_change_for ? `Dinheiro · troco para R$ ${order.cash_change_for.toFixed(2).replace(".", ",")}` : "Dinheiro na entrega";
  }
  if (order.delivery_payment_method === "card") return "Cartão na entrega";
  return "Pagamento na entrega";
}

export default function AdminExpedicao() {
  const { toast } = useToast();
  const [orders, setOrders] = useState<KdsDispatchOrder[]>([]);
  const [drivers, setDrivers] = useState<KdsDriver[]>([]);
  const [selectedDrivers, setSelectedDrivers] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [assigning, setAssigning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const [, setTick] = useState(0);
  const knownOrderIds = useRef<Set<string>>(new Set());
  const initialLoad = useRef(true);
  const actionLock = useRef(false);

  const loadData = useCallback(async (manual = false) => {
    if (manual) setRefreshing(true);
    try {
      const [nextOrders, nextDrivers] = await Promise.all([kdsApi.listDispatchOrders(), kdsApi.listDispatchDrivers()]);
      const hasNewOrder = nextOrders.some((order) => !knownOrderIds.current.has(order.id));
      if (!initialLoad.current && hasNewOrder) playOrderAlert(loadSoundType());
      initialLoad.current = false;
      knownOrderIds.current = new Set(nextOrders.map((order) => order.id));
      setOrders(nextOrders);
      setDrivers(nextDrivers);
      setSelectedDrivers((current) => Object.fromEntries(Object.entries(current).filter(([orderId, driverId]) => nextOrders.some((order) => order.id === orderId) && nextDrivers.some((driver) => driver.id === driverId))));
      setError(null);
      setLastRefresh(new Date());
    } catch (caught) {
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

  const assign = async (order: KdsDispatchOrder) => {
    const driverId = selectedDrivers[order.id];
    if (!driverId || actionLock.current) return;
    actionLock.current = true;
    setAssigning(order.id);
    try {
      await kdsApi.assignDispatchOrder(order.id, driverId);
      const driver = drivers.find((item) => item.id === driverId);
      setOrders((current) => current.filter((item) => item.id !== order.id));
      setDrivers((current) => current.filter((item) => item.id !== driverId));
      setSelectedDrivers((current) => clearAssignedDriverSelections(current, driverId));
      setError(null);
      toast({ title: "Pedido liberado", description: `${driver?.name ?? "Motoboy"} recebeu o pedido #${(order.order_code || order.id.slice(0, 8)).toUpperCase()}.` });
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast({ title: "Despacho não concluído", description: message, variant: "destructive" });
      void loadData();
    } finally {
      actionLock.current = false;
      setAssigning(null);
    }
  };

  return (
    <section className={`${fullscreen ? "fixed inset-0 z-[100]" : "min-h-screen"} flex flex-col overflow-hidden bg-surface-00 text-cream`}>
      <header className="flex flex-col gap-4 border-b border-surface-03 bg-surface-02 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3"><span className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-300"><Truck size={28} /></span><div><p className="text-xs font-bold uppercase tracking-[0.2em] text-emerald-300">KDS touch</p><h1 className="text-2xl font-black">Expedição</h1><p className="text-sm text-stone">{lastRefresh ? `Atualizado às ${lastRefresh.toLocaleTimeString("pt-BR")}` : "Sincronizando"}</p></div></div>
        <div className="flex flex-wrap gap-2"><div className="flex min-h-12 items-center gap-2 rounded-xl border border-surface-03 bg-surface-01 px-4 font-bold text-emerald-300"><Bike /> {drivers.length} disponiveis</div><button type="button" aria-label="Atualizar expedicao" onClick={() => void loadData(true)} disabled={refreshing} className="flex min-h-12 min-w-12 items-center justify-center rounded-xl border border-surface-03 bg-surface-01 active:scale-95 disabled:opacity-50"><RefreshCw className={refreshing ? "animate-spin" : ""} /></button><button type="button" aria-label={fullscreen ? "Sair da tela cheia" : "Entrar em tela cheia"} onClick={() => void toggleFullscreen()} className="flex min-h-12 min-w-12 items-center justify-center rounded-xl border border-surface-03 bg-surface-01 active:scale-95">{fullscreen ? <Minimize2 /> : <Maximize2 />}</button><KdsSessionActions /></div>
      </header>

      {error && <div role="alert" className="m-3 flex items-center justify-between gap-3 rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-red-200"><span className="flex items-center gap-2"><WifiOff /> {error}</span><button type="button" onClick={() => void loadData(true)} className="min-h-12 rounded-lg bg-red-500 px-5 font-bold text-white active:bg-red-700">Tentar novamente</button></div>}

      {loading ? <div className="flex flex-1 items-center justify-center gap-3 text-lg text-stone"><Loader2 className="animate-spin text-emerald-300" /> Carregando expedição...</div> : orders.length === 0 ? <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center text-stone"><PackageCheck size={64} className="text-emerald-400" /><h2 className="text-2xl font-black text-cream">Expedição em dia</h2><p>Nenhum pedido aguarda conferência e motoboy.</p></div> : (
        <div className="grid flex-1 auto-rows-max gap-4 overflow-y-auto p-4 xl:grid-cols-2 2xl:grid-cols-3">
          {orders.map((order) => {
            const selectedDriver = selectedDrivers[order.id];
            return <article key={order.id} className="flex flex-col gap-4 rounded-2xl border border-surface-03 bg-surface-02 p-5 shadow-soft">
              <div className="flex items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wider text-emerald-300">Pronto para despachar</p><h2 className="text-2xl font-black">#{(order.order_code || order.id.slice(0, 8)).toUpperCase()}</h2><p className="flex items-center gap-1 text-stone"><UserRound size={15} />{order.delivery_name}</p></div><span className="flex items-center gap-1 rounded-lg bg-amber-500/10 px-3 py-2 font-bold text-amber-300"><Clock3 size={17} />{elapsed(order.updated_at || order.created_at)}</span></div>
              <div className="rounded-xl bg-surface-01 p-3 text-sm"><p className="flex items-start gap-2 font-semibold"><MapPin size={18} className="mt-0.5 shrink-0 text-gold" />{order.delivery_street}{order.delivery_complement ? `, ${order.delivery_complement}` : ""} · {order.delivery_city}</p><p className="mt-2 font-bold text-emerald-300">{paymentLabel(order)}</p></div>
              <div className="space-y-3 border-y border-surface-03 py-4">{order.items.map((item) => <div key={item.id}><p className="font-bold"><span className="mr-2 text-lg text-gold">{item.quantity}x</span>{itemDescription(item)}</p>{item.notes && <p className="mt-1 rounded-lg bg-amber-500/10 p-2 text-sm font-semibold text-amber-200">Obs.: {item.notes}</p>}</div>)}</div>
              <fieldset className="space-y-2"><legend className="mb-2 font-black">Escolha o motoboy</legend>{drivers.length === 0 ? <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-center font-bold text-amber-200">Nenhum motoboy disponivel</div> : <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">{drivers.map((driver) => <button type="button" key={driver.id} aria-pressed={selectedDriver === driver.id} disabled={Boolean(assigning)} onClick={() => setSelectedDrivers((current) => ({ ...current, [order.id]: driver.id }))} className={`min-h-14 rounded-xl border px-3 text-left font-bold transition-transform active:scale-[0.98] disabled:opacity-50 ${selectedDriver === driver.id ? "border-emerald-400 bg-emerald-500/20 text-emerald-200" : "border-surface-03 bg-surface-01 text-parchment"}`}><span className="flex items-center gap-2"><Bike size={18} />{driver.name}</span></button>)}</div>}</fieldset>
              <button type="button" disabled={!selectedDriver || Boolean(assigning)} onClick={() => void assign(order)} className="mt-auto flex min-h-16 w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 text-lg font-black text-white transition-transform active:scale-[0.98] active:bg-emerald-800 disabled:opacity-40">{assigning === order.id ? <Loader2 className="animate-spin" /> : <CheckCircle2 />}{assigning === order.id ? "Finalizando..." : "Finalizar e atribuir"}</button>
            </article>;
          })}
        </div>
      )}
    </section>
  );
}
