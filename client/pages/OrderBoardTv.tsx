import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Bike, Box, Expand, Maximize2, PackageCheck, RefreshCw, WifiOff,
} from "lucide-react";
import {
  ApiRequestError, orderBoardApi, type OrderBoardActivation, type OrderBoardSnapshot,
} from "@/lib/api";
import {
  ORDER_BOARD_COLUMNS, ORDER_BOARD_POLL_INTERVAL_MS, groupBoardOrders, visiblePage,
  type OrderBoardColumnId, type OrderBoardDeliveryOrder,
} from "@/lib/orderBoard";

type ScreenState = "loading" | "activation" | "board" | "disabled";

const columnTheme: Record<OrderBoardColumnId, {
  icon: typeof Box;
  shell: string;
  header: string;
  empty: string;
}> = {
  waiting: {
    icon: Box,
    shell: "border-orange-500/85 shadow-[0_0_50px_rgba(249,115,22,0.08)]",
    header: "border-orange-400/70 bg-gradient-to-r from-[#7b2f05] via-[#8d3d0b] to-[#61300f]",
    empty: "text-orange-100/45",
  },
  ready: {
    icon: PackageCheck,
    shell: "border-emerald-400/85 shadow-[0_0_55px_rgba(16,185,129,0.1)]",
    header: "border-emerald-400/70 bg-gradient-to-r from-[#006235] via-[#087844] to-[#075632]",
    empty: "text-emerald-100/45",
  },
};

function useClock() {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(timer);
  }, []);
  return now;
}

function safeDateParts(now: number, timezone: string) {
  try {
    const formatter = new Intl.DateTimeFormat("pt-BR", {
      timeZone: timezone,
      weekday: "short",
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
    const parts = Object.fromEntries(formatter.formatToParts(now).map((part) => [part.type, part.value]));
    const title = (value: string) => {
      const clean = value.replaceAll(".", "");
      return clean.charAt(0).toUpperCase() + clean.slice(1);
    };
    return `${title(parts.weekday ?? "")} ${parts.day ?? ""} ${title(parts.month ?? "")} ${parts.year ?? ""}`.trim();
  } catch {
    return new Intl.DateTimeFormat("pt-BR", { dateStyle: "medium" }).format(now);
  }
}

function safeTime(now: number, timezone: string) {
  try {
    return new Intl.DateTimeFormat("pt-BR", {
      timeZone: timezone,
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).format(now);
  } catch {
    return new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" }).format(now);
  }
}

function ActivationScreen({ activation, error, onRetry }: {
  activation: OrderBoardActivation | null;
  error: string | null;
  onRetry: () => void;
}) {
  return (
    <main className="grid min-h-screen place-items-center bg-[#061013] px-6 py-10 text-white">
      <section className="w-full max-w-2xl rounded-[2rem] border border-white/10 bg-white/[0.055] p-8 text-center shadow-2xl md:p-12">
        <div className="mx-auto mb-6 grid h-20 w-20 place-items-center rounded-3xl bg-amber-400 text-[#111] shadow-lg shadow-amber-400/20">
          <Expand size={42} />
        </div>
        <p className="text-sm font-black uppercase tracking-[0.3em] text-amber-300">Painel de motoboys</p>
        <h1 className="mt-3 text-3xl font-black md:text-5xl">Vincular esta TV</h1>
        <p className="mx-auto mt-4 max-w-xl text-base text-white/60 md:text-lg">
          Em outro dispositivo, abra Configurações → Painéis TV e informe o código abaixo.
          Esta tela não exibe dados pessoais dos clientes.
        </p>
        {activation ? (
          <>
            <div className="my-9 rounded-3xl border border-amber-300/25 bg-black/35 px-5 py-8">
              <span className="font-mono text-5xl font-black tracking-[0.22em] text-amber-300 md:text-7xl" aria-label={`Código ${activation.code}`}>
                {activation.code}
              </span>
            </div>
            <div className="flex items-center justify-center gap-3 text-white/55">
              <RefreshCw className="animate-spin" size={18} /> Aguardando autorização do administrador…
            </div>
          </>
        ) : (
          <button type="button" onClick={onRetry} className="mt-8 rounded-xl bg-amber-400 px-6 py-3 font-black text-black">
            Gerar código de ativação
          </button>
        )}
        {error && <p role="alert" className="mt-5 text-sm font-bold text-red-300">{error}</p>}
      </section>
    </main>
  );
}

function providerPresentation(order: OrderBoardDeliveryOrder) {
  const key = (order.delivery.provider_key || "delivery").toLocaleLowerCase("pt-BR");
  const label = order.delivery.provider_label?.trim() || "Serviço de entrega";
  const isOwn = ["own", "internal", "motoboy", "motoboy_proprio", "motoboy-próprio"].some((value) => key.includes(value));
  const initials = label
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase() || "EN";
  let badge = "border-slate-400/35 bg-slate-700 text-white";
  if (key.includes("ifood")) badge = "border-red-300/35 bg-[#ea1733] text-white";
  else if (key.includes("99")) badge = "border-yellow-200/50 bg-[#ffd600] text-black";
  else if (key.includes("uber")) badge = "border-white/25 bg-black text-white";
  else if (isOwn) badge = "border-red-300/35 bg-[#f5163f] text-white";
  return { label, initials, badge, isOwn };
}

function OrderCard({ order }: { order: OrderBoardDeliveryOrder }) {
  const provider = providerPresentation(order);
  const driver = order.delivery.driver_name?.trim() || "Entregador aguardando definição";
  return (
    <article className="animate-in fade-in slide-in-from-bottom-2 grid min-h-[7.5rem] grid-cols-[minmax(7.5rem,0.43fr)_1fr] items-center overflow-hidden rounded-2xl border border-white/15 bg-gradient-to-r from-white/[0.075] to-white/[0.035] shadow-xl duration-500 2xl:min-h-[8.4rem]">
      <div className="flex h-[64%] items-center justify-center border-r border-white/45 px-3">
        <strong className="whitespace-nowrap text-[clamp(2.3rem,4vw,4.4rem)] font-black leading-none tracking-[-0.05em] text-white">
          #{order.order_code}
        </strong>
      </div>
      <div className="flex min-w-0 items-center gap-4 px-5 2xl:gap-5 2xl:px-7">
        <span className={`grid h-16 w-16 shrink-0 place-items-center rounded-2xl border text-2xl font-black shadow-lg 2xl:h-[4.6rem] 2xl:w-[4.6rem] ${provider.badge}`} aria-hidden="true">
          {provider.isOwn ? <Bike size={38} strokeWidth={2.5} /> : provider.initials}
        </span>
        <span className="min-w-0">
          <span className="block truncate text-[clamp(1.05rem,1.65vw,1.75rem)] font-extrabold leading-tight text-white">{provider.label}</span>
          <span className="mt-1 block truncate text-[clamp(0.95rem,1.45vw,1.45rem)] font-medium leading-tight text-slate-300">{driver}</span>
        </span>
      </div>
    </article>
  );
}

function BoardColumn({ id, orders, page, pageSize }: {
  id: OrderBoardColumnId;
  orders: OrderBoardDeliveryOrder[];
  page: number;
  pageSize: number;
}) {
  const definition = ORDER_BOARD_COLUMNS.find((column) => column.id === id)!;
  const theme = columnTheme[id];
  const Icon = theme.icon;
  const shown = visiblePage(orders, page, pageSize);
  const pageCount = Math.max(1, Math.ceil(orders.length / pageSize));
  const emptyLabel = id === "waiting" ? "Nenhum pedido aguardando." : "Nenhum pedido pronto para retirada.";
  return (
    <section className={`flex min-w-0 flex-col overflow-hidden rounded-2xl border-2 bg-black/20 ${theme.shell}`} aria-labelledby={`column-${id}`}>
      <header className={`flex min-h-[5.5rem] items-center justify-between border-b-2 px-5 py-3 lg:px-7 2xl:min-h-[6.5rem] ${theme.header}`}>
        <h2 id={`column-${id}`} className="flex min-w-0 items-center gap-4 text-[clamp(1.35rem,2.4vw,2.65rem)] font-black leading-none tracking-tight text-white">
          <Icon className="shrink-0" size={46} strokeWidth={2.4} />
          <span className="truncate">{definition.label}</span>
        </h2>
        <span className="ml-3 grid min-w-12 place-items-center rounded-xl border border-white/25 bg-black/20 px-2 py-1 text-2xl font-black">{orders.length}</span>
      </header>
      <div className="flex min-h-0 flex-1 flex-col gap-3 p-3 lg:p-4">
        {shown.length ? shown.map((order) => <OrderCard key={order.id} order={order} />) : (
          <div className={`grid flex-1 place-items-center rounded-2xl border border-dashed border-white/10 px-5 text-center text-lg font-bold ${theme.empty}`}>
            {emptyLabel}
          </div>
        )}
      </div>
      {pageCount > 1 && (
        <p className="pb-3 text-center text-sm font-bold text-white/45">
          Página {(page % pageCount) + 1} de {pageCount} · troca automática
        </p>
      )}
    </section>
  );
}

export default function OrderBoardTv() {
  const [screen, setScreen] = useState<ScreenState>("loading");
  const [snapshot, setSnapshot] = useState<OrderBoardSnapshot | null>(null);
  const [activation, setActivation] = useState<OrderBoardActivation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(() => !navigator.onLine);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(() => window.innerHeight >= 900 ? 5 : window.innerHeight >= 720 ? 4 : 3);
  const etagRef = useRef<string | null>(null);
  const snapshotRef = useRef<OrderBoardSnapshot | null>(null);
  const now = useClock();

  const loadSnapshot = useCallback(async () => {
    try {
      const result = await orderBoardApi.snapshot(etagRef.current);
      if (result.snapshot) {
        snapshotRef.current = result.snapshot;
        setSnapshot(result.snapshot);
      }
      etagRef.current = result.etag;
      setOffline(false);
      setError(null);
      setScreen("board");
      return true;
    } catch (reason) {
      if (reason instanceof ApiRequestError && reason.status === 401) {
        snapshotRef.current = null;
        etagRef.current = null;
        setSnapshot(null);
        setActivation(null);
        setOffline(false);
        setError("O acesso desta TV foi revogado ou expirou. Gere um novo código para vinculá-la novamente.");
        setScreen("activation");
        return false;
      }
      if (reason instanceof ApiRequestError && reason.status === 403) {
        snapshotRef.current = null;
        etagRef.current = null;
        setSnapshot(null);
        setOffline(false);
        setScreen("disabled");
        setError(reason.message);
        return true;
      }
      if (snapshotRef.current) {
        setOffline(true);
        setScreen("board");
      } else {
        setError(reason instanceof Error ? reason.message : "Não foi possível carregar o painel.");
      }
      return false;
    }
  }, []);

  const createActivation = useCallback(async () => {
    setError(null);
    setActivation(null);
    try {
      const created = await orderBoardApi.createActivation();
      setActivation(created);
      setScreen("activation");
    } catch (reason) {
      setScreen("activation");
      setError(reason instanceof Error ? reason.message : "Não foi possível gerar o código.");
    }
  }, []);

  useEffect(() => {
    let active = true;
    loadSnapshot().then((loaded) => {
      if (active && !loaded && !snapshotRef.current) void createActivation();
    });
    return () => { active = false; };
  }, [createActivation, loadSnapshot]);

  useEffect(() => {
    if (!activation || screen !== "activation") return;
    const delay = Math.max(2, activation.poll_after_seconds) * 1_000;
    let timer = 0;
    let cancelled = false;
    const poll = async () => {
      try {
        const status = await orderBoardApi.activationStatus(activation);
        if (status.status === "approved" || status.status === "claimed") {
          await loadSnapshot();
          return;
        }
        if (status.status === "expired") {
          setActivation(null);
          setError("O código expirou. Gere um novo código para continuar.");
          return;
        }
      } catch (reason) {
        if (reason instanceof ApiRequestError && [404, 410].includes(reason.status)) {
          setActivation(null);
          setError("O código expirou. Gere um novo código para continuar.");
          return;
        }
      }
      if (!cancelled) timer = window.setTimeout(poll, delay);
    };
    timer = window.setTimeout(poll, delay);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [activation, loadSnapshot, screen]);

  useEffect(() => {
    if (screen !== "board") return;
    let timer = 0;
    let cancelled = false;
    const schedule = () => {
      const configured = snapshotRef.current?.settings.polling_interval_seconds;
      const base = (configured ?? ORDER_BOARD_POLL_INTERVAL_MS / 1_000) * 1_000;
      const delay = document.hidden ? base * 4 : base;
      timer = window.setTimeout(async () => {
        await loadSnapshot();
        if (!cancelled) schedule();
      }, delay + Math.floor(Math.random() * 500));
    };
    schedule();
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [loadSnapshot, screen]);

  useEffect(() => {
    if (screen !== "board") return;
    const timer = window.setInterval(() => orderBoardApi.heartbeat().catch(() => setOffline(true)), 30_000);
    return () => window.clearInterval(timer);
  }, [screen]);

  useEffect(() => {
    const onOffline = () => setOffline(true);
    const onOnline = () => { setOffline(false); void loadSnapshot(); };
    window.addEventListener("offline", onOffline);
    window.addEventListener("online", onOnline);
    return () => {
      window.removeEventListener("offline", onOffline);
      window.removeEventListener("online", onOnline);
    };
  }, [loadSnapshot]);

  useEffect(() => {
    const resize = () => setPageSize(window.innerHeight >= 900 ? 5 : window.innerHeight >= 720 ? 4 : 3);
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => setPage((value) => value + 1), 10_000);
    return () => window.clearInterval(timer);
  }, []);

  const groups = useMemo(() => groupBoardOrders(snapshot?.orders ?? []), [snapshot]);

  if (screen === "loading") {
    return <main className="grid min-h-screen place-items-center bg-[#061013] text-white"><span className="flex items-center gap-3 text-lg font-bold text-white/65"><RefreshCw className="animate-spin text-amber-300" size={36} /> Carregando painel…</span></main>;
  }
  if (screen === "activation") return <ActivationScreen activation={activation} error={error} onRetry={createActivation} />;
  if (screen === "disabled") {
    return <main className="grid min-h-screen place-items-center bg-[#061013] p-6 text-white"><section className="max-w-xl text-center"><WifiOff className="mx-auto text-amber-300" size={56} /><h1 className="mt-5 text-3xl font-black">Painel ainda não habilitado</h1><p className="mt-3 text-white/60">Ative o Painel TV nas configurações do estabelecimento e tente novamente.</p><button type="button" onClick={() => window.location.reload()} className="mt-7 rounded-xl bg-amber-400 px-6 py-3 font-black text-black">Tentar novamente</button></section></main>;
  }
  if (!snapshot) return null;

  const tenant = snapshot.tenant;
  const tenantDate = safeDateParts(now, tenant.timezone);
  const tenantTime = safeTime(now, tenant.timezone);

  return (
    <main className="flex h-screen min-h-[32rem] flex-col overflow-hidden bg-[radial-gradient(circle_at_50%_-20%,#17343b_0%,#071318_43%,#020608_100%)] p-3 text-white lg:p-4">
      <header className="relative mb-3 grid min-h-[6.7rem] grid-cols-[1fr_auto_1fr] items-center gap-4 border-b border-white/25 px-4 pb-3 lg:min-h-[7.5rem] lg:px-8">
        <div className="flex min-w-0 items-center gap-4">
          {tenant.logo_url && <img src={tenant.logo_url} alt={`Logo de ${tenant.name}`} className="h-16 w-16 shrink-0 object-contain lg:h-20 lg:w-20" onError={(event) => { event.currentTarget.style.display = "none"; }} />}
          <div className="min-w-0">
            <p className="truncate text-[clamp(1.2rem,2.1vw,2.5rem)] font-black uppercase tracking-[0.08em]">{tenant.name}</p>
            <div className="mt-2 h-1 w-28 rounded-full bg-gradient-to-r from-amber-400 via-orange-300 to-amber-600" />
          </div>
        </div>
        <div className="border-x border-white/35 px-7 text-center lg:px-14">
          <h1 className="text-[clamp(1.9rem,3.5vw,4rem)] font-black uppercase leading-none tracking-tight">Motoboys</h1>
          <p className="mt-2 whitespace-nowrap text-[clamp(0.65rem,1.1vw,1.2rem)] font-bold uppercase tracking-wide text-slate-300">Acompanhe seus pedidos aqui</p>
        </div>
        <div className="flex min-w-0 items-center justify-end gap-3">
          {offline && <span className="absolute bottom-1 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-full border border-amber-300/25 bg-amber-950/85 px-4 py-1.5 text-xs font-black text-amber-200"><RefreshCw className="animate-spin" size={14} /> Reconectando…</span>}
          <button type="button" onClick={() => void document.documentElement.requestFullscreen?.()} title="Abrir em tela cheia" aria-label="Abrir em tela cheia" className="rounded-xl border border-white/15 bg-white/5 p-2 text-white/65 transition-colors hover:bg-white/10 hover:text-white"><Maximize2 size={20} /></button>
          <div className="text-right">
            <p className="truncate text-[clamp(0.7rem,1.2vw,1.2rem)] font-medium text-slate-300">{tenantDate}</p>
            <time className="font-mono text-[clamp(2rem,3.7vw,4.3rem)] font-black leading-none tracking-tight">{tenantTime}</time>
          </div>
        </div>
      </header>

      <section className="grid min-h-0 flex-1 grid-cols-2 gap-3 lg:gap-5" aria-label="Pedidos de entrega">
        {ORDER_BOARD_COLUMNS.map((column) => (
          <BoardColumn key={column.id} id={column.id} orders={groups[column.id]} page={page} pageSize={pageSize} />
        ))}
      </section>
    </main>
  );
}
