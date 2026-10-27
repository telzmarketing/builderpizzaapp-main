import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bell,
  BellOff,
  ChefHat,
  Clock3,
  Maximize2,
  Minimize2,
  RefreshCw,
  Wifi,
  WifiOff,
} from "lucide-react";
import KdsSessionActions from "@/components/kds/KdsSessionActions";
import KdsTouchWorkspace from "@/components/kds/KdsTouchWorkspace";
import KdsMultiOperatorBoard from "@/components/kds/KdsMultiOperatorBoard";
import KdsBrandLogo from "@/components/kds/KdsBrandLogo";
import { useToast } from "@/hooks/use-toast";
import { kdsApi, type KdsKitchenOrder } from "@/lib/api";
import { loadSoundType, playOrderAlert } from "@/lib/orderSound";
import { activeKitchenOrders } from "@/lib/kds";
import { orderDisplayCode } from "@/lib/orderIdentity";

const POLL_INTERVAL_MS = 15_000;

function errorMessage(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Não foi possível atualizar a cozinha.";
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

  const loadOrders = useCallback(
    async (manual = false) => {
      if (manual) setRefreshing(true);
      try {
        const data = await kdsApi.listKitchenOrders();
        const active = activeKitchenOrders(data);
        const waiting = active.filter(
          (order) => order.status === "paid" || order.status === "pago",
        );
        const hasNewOrder = waiting.some(
          (order) => !knownWaitingIds.current.has(order.id),
        );
        if (!initialLoad.current && soundOn && hasNewOrder)
          playOrderAlert(loadSoundType());
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
    },
    [soundOn],
  );

  useEffect(() => {
    void loadOrders();
    const poll = window.setInterval(() => void loadOrders(), POLL_INTERVAL_MS);
    return () => window.clearInterval(poll);
  }, [loadOrders]);

  useEffect(() => {
    const timer = window.setInterval(
      () => setTick((value) => value + 1),
      10_000,
    );
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const onFullscreenChange = () =>
      setFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", onFullscreenChange);
    return () =>
      document.removeEventListener("fullscreenchange", onFullscreenChange);
  }, []);

  const toggleFullscreen = async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch {
      toast({
        title: "Tela cheia indisponível",
        description: "O navegador bloqueou o modo KDS.",
      });
    }
  };

  const startOrder = async (order: KdsKitchenOrder) => {
    if (
      (order.status !== "paid" && order.status !== "pago") ||
      actionLock.current
    )
      return;
    actionLock.current = true;
    setUpdating(order.id);
    try {
      const updated = await kdsApi.startKitchenOrder(order.id);
      setOrders((current) =>
        activeKitchenOrders(
          current.map((item) => (item.id === order.id ? updated : item)),
        ),
      );
      toast({
        title: "Unidades encaminhadas para a fila do pizzaiolo",
        description: `Pedido #${orderDisplayCode(order)}`,
      });
      setError(null);
      setLastRefresh(new Date());
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast({
        title: "Ação não concluída",
        description: message,
        variant: "destructive",
      });
    } finally {
      actionLock.current = false;
      setUpdating(null);
    }
  };

  const finishOrder = async (order: KdsKitchenOrder) => {
    const units = order.production_units ?? [];
    if (
      units.length === 0 ||
      units.some((unit) => unit.state !== "ready") ||
      actionLock.current
    )
      return;
    actionLock.current = true;
    setUpdating(order.id);
    try {
      const updated = await kdsApi.markKitchenOrderReady(order.id);
      setOrders((current) =>
        activeKitchenOrders(
          current.map((item) => (item.id === order.id ? updated : item)),
        ),
      );
      setError(null);
      setLastRefresh(new Date());
      toast({
        title: "Preparo finalizado",
        description: `Pedido #${orderDisplayCode(order)} enviado à expedição.`,
      });
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast({
        title: "Preparo não finalizado",
        description: message,
        variant: "destructive",
      });
    } finally {
      actionLock.current = false;
      setUpdating(null);
    }
  };

  const sortedOrders = [...orders].sort(
    (a, b) => Date.parse(a.created_at) - Date.parse(b.created_at),
  );
  const now = new Date();
  return (
    <section
      className={`kds-touch ${fullscreen ? "fixed inset-0 z-[100] overflow-y-auto" : "min-h-screen min-h-[100dvh]"} min-w-0 max-w-full bg-[#040e18] pb-[env(safe-area-inset-bottom)] text-slate-100`}
    >
      <header className="flex flex-col gap-3 rounded-b-2xl border-b border-[#20374a] bg-[#081521] p-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:p-4">
        <div className="flex items-center gap-4">
          <KdsBrandLogo fallback={
            <ChefHat
              size={54}
              strokeWidth={1.6}
              className="shrink-0 text-amber-400"
            />
          } />
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-amber-400">
              KDS Touch
            </p>
            <h1 className="text-3xl font-black">Pizzaiolo</h1>
            <p className="mt-1 text-xs text-slate-400">
              {lastRefresh
                ? `Atualizado às ${lastRefresh.toLocaleTimeString("pt-BR")}`
                : "Sincronizando pedidos"}
            </p>
          </div>
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <div className="flex min-h-12 items-center gap-3 rounded-xl border border-[#20374a] bg-[#0b1926] px-3 py-1">
            <Clock3 size={28} className="text-slate-300" />
            <div>
              <p className="text-xl font-bold tabular-nums">
                {now.toLocaleTimeString("pt-BR", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </p>
              <p className="text-xs text-slate-400">
                {now.toLocaleDateString("pt-BR", {
                  weekday: "short",
                  day: "2-digit",
                  month: "2-digit",
                })}
              </p>
            </div>
          </div>
          <div
            role="status"
            className={`flex min-h-12 items-center gap-2 rounded-xl border border-[#20374a] bg-[#0b1926] px-3 font-bold ${error ? "text-red-300" : lastRefresh ? "text-emerald-400" : "text-slate-400"}`}
          >
            {error ? <WifiOff size={24} /> : <Wifi size={24} />}
            {error
              ? "Sem sincronização"
              : lastRefresh
                ? "Conectado"
                : "Conectando"}
          </div>
          <button
            type="button"
            aria-label={soundOn ? "Silenciar alertas" : "Ativar alertas"}
            onClick={() => setSoundOn((value) => !value)}
            className="flex min-h-12 min-w-12 items-center justify-center rounded-xl border border-[#30485d] bg-[#0b1926] text-amber-400 active:scale-95"
          >
            {soundOn ? <Bell /> : <BellOff />}
          </button>
          <button
            type="button"
            aria-label="Atualizar pedidos"
            onClick={() => void loadOrders(true)}
            disabled={refreshing}
            className="flex min-h-12 min-w-12 items-center justify-center rounded-xl border border-[#30485d] bg-[#0b1926] active:scale-95 disabled:opacity-50"
          >
            <RefreshCw className={refreshing ? "animate-spin" : ""} />
          </button>
          <button
            type="button"
            aria-label={
              fullscreen ? "Sair da tela cheia" : "Entrar em tela cheia"
            }
            onClick={() => void toggleFullscreen()}
            className="flex min-h-12 min-w-12 items-center justify-center rounded-xl border border-[#30485d] bg-[#0b1926] active:scale-95"
          >
            {fullscreen ? <Minimize2 /> : <Maximize2 />}
          </button>
          <KdsSessionActions />
        </div>
      </header>
      {error && (
        <div
          role="alert"
          className="m-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-red-200"
        >
          <span className="flex items-center gap-2">
            <WifiOff className="shrink-0" />
            {error}
          </span>
          <button
            type="button"
            onClick={() => void loadOrders(true)}
            className="min-h-12 rounded-lg bg-red-500 px-5 font-bold text-white"
          >
            Tentar novamente
          </button>
        </div>
      )}
      <KdsMultiOperatorBoard
        renderWorkspace={(workspace) => (
          <KdsTouchWorkspace
            {...workspace}
            orders={sortedOrders}
            ordersLoading={loading}
            updating={updating}
            startOrder={startOrder}
            finishOrder={finishOrder}
          />
        )}
      />
    </section>
  );
}
