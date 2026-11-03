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
import PwaInstallButton from "@/components/PwaInstallButton";
import { useToast } from "@/hooks/use-toast";
import { kdsApi, type KdsKitchenOrder } from "@/lib/api";
import { loadSoundType, playOrderAlert } from "@/lib/orderSound";
import { activeKitchenOrders } from "@/lib/kds";
import { orderDisplayCode } from "@/lib/orderIdentity";
import { onOrderArchived } from "@/lib/orderArchive";
import {
  PIZZA_STATIONS,
  persistPizzaStation,
  pizzaStationLabel,
  readPizzaStation,
  type PizzaWorkstationId,
} from "@/lib/kdsStations";

const POLL_INTERVAL_MS = 15_000;
const KDS_ESFIHA_DEVICE_STORAGE_KEY = "kds:esfiha-device";

function errorMessage(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Não foi possível atualizar a cozinha.";
}

type KdsStationPageProps = {
  station?: string;
  title?: string;
  pwaKey?: "kds-pizzaiolo" | "kds-esfiha";
  startToastLabel?: string;
};

export default function AdminCozinha({
  station,
  title = "Pizzaiolo",
  pwaKey = "kds-pizzaiolo",
  startToastLabel = "pizzaiolo",
}: KdsStationPageProps = {}) {
  const { toast } = useToast();
  const isPizzaWorkspace = !station && pwaKey === "kds-pizzaiolo";
  const [pizzaStation, setPizzaStation] = useState<PizzaWorkstationId>(() =>
    readPizzaStation(typeof window === "undefined" ? null : window.localStorage),
  );
  const [esfihaDevice, setEsfihaDevice] = useState("esfiha");
  // Pizza 1/Pizza 2 are device lanes; the published KDS contract remains station=pizza.
  const apiStation = station ?? "pizza";
  const deviceSelectorVisible = isPizzaWorkspace || station === "esfiha";
  const deviceValue = isPizzaWorkspace ? pizzaStation : esfihaDevice;
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

  useEffect(() => {
    if (station !== "esfiha" || typeof window === "undefined") return;
    setEsfihaDevice(window.localStorage.getItem(KDS_ESFIHA_DEVICE_STORAGE_KEY) || "esfiha");
  }, [station]);

  const loadOrders = useCallback(
    async (manual = false) => {
      if (manual) setRefreshing(true);
      try {
        const data = await kdsApi.listKitchenOrders(apiStation);
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
    [apiStation, soundOn],
  );

  useEffect(() => {
    void loadOrders();
    const poll = window.setInterval(() => void loadOrders(), POLL_INTERVAL_MS);
    const unsubscribe = onOrderArchived(() => void loadOrders(true));
    return () => {
      window.clearInterval(poll);
      unsubscribe();
    };
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
      const updated = await kdsApi.startKitchenOrder(order.id, apiStation);
      setOrders((current) =>
        activeKitchenOrders(
          current.map((item) => (item.id === order.id ? updated : item)),
        ),
      );
      toast({
        title: `Unidades encaminhadas para a fila do ${startToastLabel}`,
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
      const updated = await kdsApi.markKitchenOrderReady(order.id, apiStation);
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
      className={`kds-touch kds-touch-page flex min-h-0 min-w-0 max-w-full flex-1 flex-col overflow-x-visible ${fullscreen ? "fixed inset-0 z-[100] overflow-y-auto" : "min-h-screen min-h-[100dvh] overflow-y-auto"} bg-[#040e18] pb-[env(safe-area-inset-bottom)] text-slate-100`}
    >
      <header className="sticky top-0 z-20 flex min-w-0 flex-col gap-3 rounded-b-2xl border-b border-[#20374a] bg-[#081521] p-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:p-4">
        <div className="flex min-w-0 flex-1 items-center gap-4">
          <KdsBrandLogo fallback={
            <ChefHat
              size={54}
              strokeWidth={1.6}
              className="shrink-0 text-amber-400"
            />
          } />
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-amber-400">
              KDS Touch
            </p>
            <h1 className="truncate text-2xl font-black sm:text-3xl">{title}</h1>
            <p className="mt-1 text-xs text-slate-400">
              {lastRefresh
                ? `Atualizado às ${lastRefresh.toLocaleTimeString("pt-BR")}`
                : "Sincronizando pedidos"}
            </p>
          </div>
        </div>
        <div className="flex w-full min-w-0 flex-wrap items-center gap-2 sm:w-auto sm:max-w-full sm:justify-end">
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
          <PwaInstallButton only={[pwaKey]} inline />
          <KdsSessionActions />
        </div>
      </header>
      {deviceSelectorVisible && (
        <div className="flex flex-wrap items-center gap-3 border-b border-[#20374a] bg-[#07111c] px-3 py-3 sm:px-4">
          <label className="flex items-center gap-2 text-sm font-bold text-slate-200">
            Dispositivo da estação
            <select
              aria-label="Dispositivo da estação"
              value={deviceValue}
              onChange={(event) => {
                if (isPizzaWorkspace) {
                  const next = event.target.value as PizzaWorkstationId;
                  setPizzaStation(next);
                  persistPizzaStation(next, window.localStorage);
                } else {
                  setEsfihaDevice(event.target.value);
                  window.localStorage.setItem(KDS_ESFIHA_DEVICE_STORAGE_KEY, event.target.value);
                }
              }}
              className="min-h-11 rounded-xl border border-[#30485d] bg-[#0b1926] px-3 text-slate-100 outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-amber-400"
            >
              {(isPizzaWorkspace ? PIZZA_STATIONS : [{ id: "esfiha", label: "Esfiha" }]).map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <span className="text-xs text-slate-400">
            Confirmado neste dispositivo: {isPizzaWorkspace ? pizzaStationLabel(pizzaStation) : "Esfiha"}
          </span>
        </div>
      )}
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
        station={apiStation}
        renderWorkspace={(workspace) => (
          <KdsTouchWorkspace
            {...workspace}
            orders={sortedOrders}
            ordersLoading={loading}
            updating={updating}
            startOrder={startOrder}
            finishOrder={finishOrder}
            station={apiStation}
          />
        )}
      />
    </section>
  );
}
