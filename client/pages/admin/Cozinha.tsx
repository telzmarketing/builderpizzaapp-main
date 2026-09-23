import { useCallback, useEffect, useRef, useState } from "react";
import { Bell, BellOff, CheckCircle2, ChefHat, Clock3, Loader2, Maximize2, Minimize2, RefreshCw, UtensilsCrossed, WifiOff } from "lucide-react";
import KdsSessionActions from "@/components/kds/KdsSessionActions";
import { useToast } from "@/hooks/use-toast";
import { kdsApi, type KdsKitchenOrder, type KdsOrderItem } from "@/lib/api";
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

  const advanceOrder = async (order: KdsKitchenOrder) => {
    if (actionLock.current) return;
    actionLock.current = true;
    setUpdating(order.id);
    try {
      if (order.status === "ready_for_pickup") {
        await kdsApi.completeKitchenPickup(order.id);
        setOrders((current) => current.filter((item) => item.id !== order.id));
      } else if (order.status === "preparing") {
        const updated = await kdsApi.markKitchenOrderReady(order.id);
        setOrders((current) => order.fulfillment_type === "pickup"
          ? current.map((item) => item.id === order.id ? updated : item)
          : current.filter((item) => item.id !== order.id));
      } else {
        const updated = await kdsApi.startKitchenOrder(order.id);
        setOrders((current) => current.map((item) => item.id === order.id ? updated : item));
      }
      toast({
        title: order.status === "ready_for_pickup"
          ? "Retirada concluída"
          : order.status === "preparing"
            ? (order.fulfillment_type === "pickup" ? "Pedido pronto para retirada" : "Pedido enviado para expedição")
            : "Preparo iniciado",
        description: `Pedido #${(order.order_code || order.id.slice(0, 8)).toUpperCase()}`,
      });
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

  const columns = [
    { key: "waiting", label: "Aguardando preparo", statuses: ["paid", "pago"], accent: "text-amber-300", action: "Iniciar preparo", button: "bg-orange-500 active:bg-orange-700" },
    { key: "preparing", label: "Em preparo", statuses: ["preparing"], accent: "text-orange-300", action: "Finalizar preparo", button: "bg-emerald-600 active:bg-emerald-800" },
    { key: "pickup", label: "Aguardando retirada", statuses: ["ready_for_pickup"], accent: "text-sky-300", action: "Concluir retirada", button: "bg-sky-600 active:bg-sky-800" },
  ];

  return (
    <section className={`${fullscreen ? "fixed inset-0 z-[100]" : "min-h-screen"} flex flex-col overflow-hidden bg-surface-00 text-cream`}>
      <header className="flex flex-col gap-4 border-b border-surface-03 bg-surface-02 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-gold/15 text-gold"><ChefHat size={28} /></span>
          <div><p className="text-xs font-bold uppercase tracking-[0.2em] text-gold">KDS touch</p><h1 className="text-2xl font-black">Cozinha</h1><p className="text-sm text-stone">{lastRefresh ? `Atualizado às ${lastRefresh.toLocaleTimeString("pt-BR")}` : "Sincronizando"}</p></div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" aria-label={soundOn ? "Silenciar alertas" : "Ativar alertas"} onClick={() => setSoundOn((value) => !value)} className="flex min-h-12 min-w-12 items-center justify-center rounded-xl border border-surface-03 bg-surface-01 text-gold active:scale-95">{soundOn ? <Bell /> : <BellOff />}</button>
          <button type="button" aria-label="Atualizar pedidos" onClick={() => void loadOrders(true)} disabled={refreshing} className="flex min-h-12 min-w-12 items-center justify-center rounded-xl border border-surface-03 bg-surface-01 active:scale-95 disabled:opacity-50"><RefreshCw className={refreshing ? "animate-spin" : ""} /></button>
          <button type="button" aria-label={fullscreen ? "Sair da tela cheia" : "Entrar em tela cheia"} onClick={() => void toggleFullscreen()} className="flex min-h-12 min-w-12 items-center justify-center rounded-xl border border-surface-03 bg-surface-01 active:scale-95">{fullscreen ? <Minimize2 /> : <Maximize2 />}</button>
          <KdsSessionActions />
        </div>
      </header>

      {error && <div role="alert" className="m-3 flex items-center justify-between gap-3 rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-red-200"><span className="flex items-center gap-2"><WifiOff /> {error}</span><button type="button" onClick={() => void loadOrders(true)} className="min-h-12 rounded-lg bg-red-500 px-5 font-bold text-white active:bg-red-700">Tentar novamente</button></div>}

      {loading ? <div className="flex flex-1 items-center justify-center gap-3 text-lg text-stone"><Loader2 className="animate-spin text-gold" /> Carregando pedidos...</div> : (
        <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-y-auto p-3 lg:grid-cols-3 lg:overflow-hidden">
          {columns.map((column) => {
            const items = orders.filter((order) => column.statuses.includes(order.status)).sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at));
            return <div key={column.key} className="flex min-h-[20rem] flex-col overflow-hidden rounded-2xl border border-surface-03 bg-surface-01">
              <div className="flex items-center justify-between border-b border-surface-03 px-5 py-4"><h2 className={`text-lg font-black ${column.accent}`}>{column.label}</h2><span className="rounded-full bg-surface-03 px-3 py-1 font-black">{items.length}</span></div>
              <div className="grid flex-1 auto-rows-max gap-4 overflow-y-auto p-4 xl:grid-cols-2">
                {items.length === 0 && <div className="col-span-full flex min-h-52 flex-col items-center justify-center gap-3 text-center text-stone"><UtensilsCrossed size={42} /><strong>Nenhum pedido nesta etapa</strong></div>}
                {items.map((order) => <article key={order.id} className="flex flex-col gap-4 rounded-2xl border border-surface-03 bg-surface-02 p-4 shadow-soft">
                  <div className="flex items-start justify-between gap-3"><div><strong className="text-xl">#{(order.order_code || order.id.slice(0, 8)).toUpperCase()}</strong><p className="text-sm text-stone">{order.fulfillment_type === "pickup" ? "Retirada no balcão" : "Entrega"}</p></div><span className="flex items-center gap-1 rounded-lg bg-surface-01 px-2 py-1 text-sm font-bold text-amber-300"><Clock3 size={16} />{elapsed(order.created_at)}</span></div>
                  <div className="space-y-3 border-y border-surface-03 py-4">{order.items.map((item) => <div key={item.id}><p className="font-bold"><span className="mr-2 text-lg text-gold">{item.quantity}x</span>{itemDescription(item)}</p>{item.notes && <p className="mt-1 rounded-lg bg-amber-500/10 p-2 text-sm font-semibold text-amber-200">Obs.: {item.notes}</p>}</div>)}</div>
                  <button type="button" disabled={Boolean(updating)} onClick={() => void advanceOrder(order)} className={`mt-auto flex min-h-16 w-full items-center justify-center gap-2 rounded-xl px-4 text-lg font-black text-white transition-transform active:scale-[0.98] disabled:opacity-50 ${column.button}`}>{updating === order.id ? <Loader2 className="animate-spin" /> : <CheckCircle2 />}{updating === order.id ? "Processando..." : order.status === "preparing" && order.fulfillment_type === "pickup" ? "Pronto para retirada" : column.action}</button>
                </article>)}
              </div>
            </div>;
          })}
        </div>
      )}
    </section>
  );
}
