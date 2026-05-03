import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  Bike,
  CheckCircle2,
  Clock3,
  DollarSign,
  Eye,
  Loader2,
  LogOut,
  MapPin,
  Navigation,
  NavigationOff,
  Package,
  Phone,
  RefreshCw,
  Route,
  Send,
  Star,
  X,
} from "lucide-react";
import {
  deliveryApi,
  type DeliveryEarning,
  type DeliveryPerson,
  type DeliveryRecord,
  type DriverDashboard,
} from "@/lib/api";

let L: typeof import("leaflet") | null = null;

const ACTIVE_STATUSES = new Set(["assigned", "picked_up", "on_the_way"]);
const DONE_STATUSES = new Set(["delivered", "completed"]);

const STATUS_LABELS: Record<string, string> = {
  pending_assignment: "Aguardando",
  assigned: "Aguardando retirada",
  picked_up: "Retirada iniciada",
  on_the_way: "Em rota",
  delivered: "Entregue",
  completed: "Concluida",
  failed: "Problema na entrega",
  cancelled: "Cancelada",
};

const STATUS_CLASSES: Record<string, string> = {
  assigned: "border-blue-500/30 bg-blue-500/15 text-blue-200",
  picked_up: "border-amber-500/30 bg-amber-500/15 text-amber-200",
  on_the_way: "border-violet-500/30 bg-violet-500/15 text-violet-200",
  delivered: "border-green-500/30 bg-green-500/15 text-green-200",
  completed: "border-green-500/30 bg-green-500/15 text-green-200",
  failed: "border-red-500/30 bg-red-500/15 text-red-200",
  cancelled: "border-stone/30 bg-stone/15 text-stone",
};

const DRIVER_STATUS_LABELS: Record<string, string> = {
  available: "Disponivel",
  busy: "Em rota",
  offline: "Indisponivel",
};

function money(value?: number | null) {
  return (value || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function shortOrder(id: string) {
  return `#${id.slice(0, 8).toUpperCase()}`;
}

function deliveryAddress(delivery: DeliveryRecord): string | null {
  const order = delivery.order;
  if (!order?.delivery_street) return null;
  return [order.delivery_street, order.delivery_complement, order.delivery_city, "Brasil"]
    .filter(Boolean)
    .join(", ");
}

function effectiveDate(delivery: DeliveryRecord): string | undefined {
  return delivery.order?.paid_at || delivery.order?.created_at || delivery.assigned_at || delivery.created_at;
}

function isToday(value?: string) {
  if (!value) return false;
  const date = new Date(value);
  const now = new Date();
  return date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth() && date.getDate() === now.getDate();
}

function googleMapsRouteUrl(destination: string, origin?: { lat: number; lng: number } | null, waypoints: string[] = []) {
  const params = new URLSearchParams({ api: "1", destination, travelmode: "driving" });
  if (origin) params.set("origin", `${origin.lat},${origin.lng}`);
  if (waypoints.length) params.set("waypoints", waypoints.join("|"));
  return `https://www.google.com/maps/dir/?${params.toString()}`;
}

function googleMapsSearchUrl(address: string) {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address)}`;
}

function buildQueueRoute(deliveries: DeliveryRecord[], origin?: { lat: number; lng: number } | null) {
  const addresses = deliveries.map(deliveryAddress).filter((address): address is string => Boolean(address));
  if (!addresses.length) return null;
  if (addresses.length === 1) return origin ? googleMapsRouteUrl(addresses[0], origin) : googleMapsSearchUrl(addresses[0]);
  return googleMapsRouteUrl(addresses[addresses.length - 1], origin, addresses.slice(0, -1));
}

function EtaLine({ delivery }: { delivery: DeliveryRecord }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(id);
  }, []);

  if (!delivery.assigned_at || !delivery.estimated_minutes) return null;
  const deadline = new Date(delivery.assigned_at).getTime() + delivery.estimated_minutes * 60_000;
  const remaining = Math.round((deadline - now) / 60_000);
  const urgent = remaining <= 5;
  const text = remaining < 0 ? `${Math.abs(remaining)}min atrasada` : `${remaining}min restantes`;
  return <span className={urgent ? "text-orange-300" : "text-green-300"}>{text}</span>;
}

function DriverLocationMap({ location }: { location: { lat: number; lng: number } | null }) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<import("leaflet").Map | null>(null);
  const markerRef = useRef<import("leaflet").Marker | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
    document.head.appendChild(link);
    import("leaflet").then((mod) => {
      L = mod.default ?? mod;
      setReady(true);
    });
    return () => {
      document.head.removeChild(link);
      mapInstanceRef.current?.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!ready || !L || !mapRef.current || mapInstanceRef.current) return;
    const center: [number, number] = location ? [location.lat, location.lng] : [-23.55, -46.63];
    const map = L.map(mapRef.current, { center, zoom: location ? 16 : 12, zoomControl: false });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "OpenStreetMap",
      maxZoom: 19,
    }).addTo(map);
    mapInstanceRef.current = map;
  }, [ready, location]);

  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !L || !location) return;
    markerRef.current?.remove();
    const icon = L.divIcon({
      html: '<div style="background:#d9a441;border:3px solid white;border-radius:50%;width:30px;height:30px;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 10px rgba(0,0,0,.45)"><div style="background:#111827;border-radius:50%;width:10px;height:10px"></div></div>',
      iconSize: [30, 30],
      iconAnchor: [15, 15],
      className: "",
    });
    markerRef.current = L.marker([location.lat, location.lng], { icon }).addTo(map).bindPopup("Sua localizacao");
    map.setView([location.lat, location.lng], 16);
  }, [location]);

  return (
    <div className="relative h-44 overflow-hidden rounded-[8px] border border-surface-03 bg-surface-02">
      {!ready && <div className="absolute inset-0 z-10 grid place-items-center"><Loader2 className="animate-spin text-gold" /></div>}
      {!location && ready && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-surface-02/90 px-6 text-center">
          <NavigationOff size={22} className="mb-2 text-stone" />
          <p className="text-sm text-stone">Ative o GPS para exibir seu pin.</p>
        </div>
      )}
      <div ref={mapRef} className="h-full w-full" />
    </div>
  );
}

function DeliveryCard({
  delivery,
  currentLocation,
  busy,
  onStart,
  onComplete,
  onProblem,
  onView,
}: {
  delivery: DeliveryRecord;
  currentLocation: { lat: number; lng: number } | null;
  busy: boolean;
  onStart: (delivery: DeliveryRecord) => void;
  onComplete: (delivery: DeliveryRecord) => void;
  onProblem: (delivery: DeliveryRecord) => void;
  onView: (delivery: DeliveryRecord) => void;
}) {
  const order = delivery.order;
  const address = deliveryAddress(delivery);
  const mapsUrl = address ? googleMapsRouteUrl(address, currentLocation) : null;
  const searchUrl = address ? googleMapsSearchUrl(address) : null;
  const statusClass = STATUS_CLASSES[delivery.status] || "border-surface-03 bg-surface-03 text-stone";
  const canStart = delivery.status === "assigned" || delivery.status === "picked_up";
  const canComplete = delivery.status === "on_the_way" || delivery.status === "picked_up" || delivery.status === "assigned";

  return (
    <article className="overflow-hidden rounded-[8px] border border-surface-03 bg-surface-02">
      <div className="flex items-start justify-between gap-3 border-b border-surface-03 p-4">
        <div className="min-w-0">
          <p className="font-mono text-base font-black text-cream">{shortOrder(delivery.order_id)}</p>
          <p className="mt-1 truncate text-sm font-semibold text-parchment">{order?.delivery_name || "Cliente"}</p>
        </div>
        <span className={`shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-bold ${statusClass}`}>
          {STATUS_LABELS[delivery.status] || delivery.status}
        </span>
      </div>

      <div className="space-y-3 p-4">
        {address && (
          <div className="flex gap-2 text-sm text-stone">
            <MapPin size={16} className="mt-0.5 shrink-0 text-gold" />
            <p className="leading-snug">{address}</p>
          </div>
        )}
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-[8px] border border-surface-03 bg-surface-01 px-3 py-2">
            <p className="text-stone">Pedido</p>
            <p className="mt-1 font-bold text-cream">{money(order?.total)}</p>
          </div>
          <div className="rounded-[8px] border border-surface-03 bg-surface-01 px-3 py-2">
            <p className="text-stone">Taxa entrega</p>
            <p className="mt-1 font-bold text-cream">{money(order?.shipping_fee)}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs text-stone">
          <span className="inline-flex items-center gap-1"><Clock3 size={13} /><EtaLine delivery={delivery} /></span>
          {order?.payment?.method && <span>{order.payment.method}</span>}
          {order?.delivery_phone && <span className="inline-flex items-center gap-1"><Phone size={13} />{order.delivery_phone}</span>}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 border-t border-surface-03 p-3">
        <button onClick={() => onView(delivery)} className="flex h-12 items-center justify-center gap-2 rounded-[8px] border border-surface-03 bg-surface-01 text-sm font-bold text-parchment">
          <Eye size={16} /> Ver pedido
        </button>
        {mapsUrl || searchUrl ? (
          <a href={mapsUrl || searchUrl || "#"} target="_blank" rel="noreferrer" className="flex h-12 items-center justify-center gap-2 rounded-[8px] border border-green-500/25 bg-green-500/15 text-sm font-bold text-green-200">
            <Navigation size={16} /> Maps
          </a>
        ) : (
          <button disabled className="flex h-12 items-center justify-center gap-2 rounded-[8px] border border-surface-03 bg-surface-01 text-sm font-bold text-stone opacity-50">
            <Navigation size={16} /> Maps
          </button>
        )}
        {canStart && (
          <button disabled={busy} onClick={() => onStart(delivery)} className="col-span-2 flex h-13 items-center justify-center gap-2 rounded-[8px] bg-gold px-4 py-4 text-base font-black text-cream disabled:opacity-50">
            <Send size={18} /> Iniciar entrega
          </button>
        )}
        {canComplete && (
          <button disabled={busy} onClick={() => onComplete(delivery)} className="col-span-2 flex h-13 items-center justify-center gap-2 rounded-[8px] bg-green-600 px-4 py-4 text-base font-black text-white disabled:opacity-50">
            <CheckCircle2 size={18} /> Marcar como entregue
          </button>
        )}
        <button disabled={busy} onClick={() => onProblem(delivery)} className="col-span-2 flex h-11 items-center justify-center gap-2 rounded-[8px] border border-red-500/30 bg-red-500/10 text-sm font-bold text-red-200 disabled:opacity-50">
          <AlertTriangle size={16} /> Reportar problema
        </button>
      </div>
    </article>
  );
}

export default function Motoboy() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("driver_token"));
  const [driver, setDriver] = useState<DeliveryPerson | null>(null);
  const [dashboard, setDashboard] = useState<DriverDashboard | null>(null);
  const [earnings, setEarnings] = useState<DeliveryEarning[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [tab, setTab] = useState<"fila" | "concluidas" | "financeiro">("fila");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const [error, setError] = useState("");
  const [gpsActive, setGpsActive] = useState(false);
  const [gpsError, setGpsError] = useState("");
  const [currentLocation, setCurrentLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [detail, setDetail] = useState<DeliveryRecord | null>(null);
  const [problem, setProblem] = useState<DeliveryRecord | null>(null);
  const [problemText, setProblemText] = useState("");
  const gpsWatchRef = useRef<number | null>(null);
  const gpsIntervalRef = useRef<number | null>(null);

  const loadDashboard = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const [dash, finance] = await Promise.all([
        deliveryApi.driverDashboard(),
        deliveryApi.driverEarnings(),
      ]);
      setDashboard(dash);
      setDriver(dash.person);
      setEarnings(finance ?? []);
      setError("");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Sessao expirada.";
      setError(message);
      if (message.toLowerCase().includes("token")) {
        localStorage.removeItem("driver_token");
        setToken(null);
      }
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (token) void loadDashboard();
  }, [token, loadDashboard]);

  useEffect(() => {
    if (!token) return;
    const id = window.setInterval(loadDashboard, 30_000);
    return () => window.clearInterval(id);
  }, [token, loadDashboard]);

  const sendLocation = useCallback((lat: number, lng: number) => {
    setCurrentLocation({ lat, lng });
    deliveryApi.driverUpdateLocation(lat, lng).then(setDriver).catch(() => {});
  }, []);

  const startGps = useCallback(() => {
    if (!navigator.geolocation) {
      setGpsError("GPS nao suportado neste dispositivo.");
      return;
    }
    setGpsError("");
    gpsWatchRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        sendLocation(pos.coords.latitude, pos.coords.longitude);
        setGpsActive(true);
      },
      (err) => {
        setGpsError(`GPS: ${err.message}`);
        setGpsActive(false);
      },
      { enableHighAccuracy: true, maximumAge: 10_000 },
    );
    gpsIntervalRef.current = window.setInterval(() => {
      navigator.geolocation.getCurrentPosition(
        (pos) => sendLocation(pos.coords.latitude, pos.coords.longitude),
        () => {},
      );
    }, 30_000);
  }, [sendLocation]);

  const stopGps = useCallback(() => {
    if (gpsWatchRef.current !== null) navigator.geolocation.clearWatch(gpsWatchRef.current);
    if (gpsIntervalRef.current !== null) window.clearInterval(gpsIntervalRef.current);
    gpsWatchRef.current = null;
    gpsIntervalRef.current = null;
    setGpsActive(false);
  }, []);

  useEffect(() => () => stopGps(), [stopGps]);

  async function handleLogin(event: React.FormEvent) {
    event.preventDefault();
    setLoginLoading(true);
    setError("");
    try {
      const data = await deliveryApi.driverLogin(email, password);
      localStorage.setItem("driver_token", data.token);
      setToken(data.token);
      setDriver(data.person);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Credenciais invalidas.");
    } finally {
      setLoginLoading(false);
    }
  }

  function handleLogout() {
    stopGps();
    localStorage.removeItem("driver_token");
    setToken(null);
    setDriver(null);
    setDashboard(null);
    setCurrentLocation(null);
  }

  async function runAction(id: string, action: () => Promise<unknown>) {
    setActionLoading(id);
    setError("");
    try {
      await action();
      await loadDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel concluir a acao.");
    } finally {
      setActionLoading(null);
    }
  }

  const allDeliveries = dashboard?.queue ?? [];
  const activeDeliveries = useMemo(
    () => allDeliveries.filter((d) => ACTIVE_STATUSES.has(d.status)),
    [allDeliveries],
  );
  const completedDeliveries = useMemo(
    () => allDeliveries.filter((d) => DONE_STATUSES.has(d.status)),
    [allDeliveries],
  );
  const completedToday = completedDeliveries.filter((d) => isToday(d.delivered_at)).length;
  const pendingToday = activeDeliveries.filter((d) => isToday(effectiveDate(d))).length;
  const pendingAmount = dashboard?.pending_earnings ?? 0;
  const paidAmount = dashboard?.paid_earnings ?? 0;
  const mapLocation = currentLocation || (
    driver?.location_lat && driver?.location_lng
      ? { lat: driver.location_lat, lng: driver.location_lng }
      : null
  );
  const routeUrl = buildQueueRoute(activeDeliveries, mapLocation);
  const initials = (driver?.name || "M")
    .split(" ")
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-00 p-6">
        <form onSubmit={handleLogin} className="w-full max-w-sm space-y-5">
          <div className="text-center">
            <div className="mx-auto mb-5 grid h-20 w-20 place-items-center rounded-[8px] border border-gold/20 bg-gold/15 text-gold">
              <Bike size={36} />
            </div>
            <h1 className="text-2xl font-black text-cream">App do Entregador</h1>
            <p className="mt-2 text-sm text-stone">Acesso exclusivo para motoboys.</p>
          </div>
          <label className="block">
            <span className="text-xs font-bold uppercase text-stone">Email</span>
            <input value={email} onChange={(e) => setEmail(e.target.value)} required type="email" className="mt-2 w-full rounded-[8px] border border-surface-03 bg-surface-02 px-4 py-4 text-cream outline-none focus:border-gold" />
          </label>
          <label className="block">
            <span className="text-xs font-bold uppercase text-stone">Senha</span>
            <input value={password} onChange={(e) => setPassword(e.target.value)} required type="password" className="mt-2 w-full rounded-[8px] border border-surface-03 bg-surface-02 px-4 py-4 text-cream outline-none focus:border-gold" />
          </label>
          {error && <div className="rounded-[8px] border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>}
          <button disabled={loginLoading} className="flex w-full items-center justify-center gap-2 rounded-[8px] bg-gold py-4 font-black text-cream disabled:opacity-60">
            {loginLoading && <Loader2 size={18} className="animate-spin" />} Entrar
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface-00 text-cream">
      <div className="mx-auto flex min-h-screen w-full max-w-3xl flex-col">
        <header className="sticky top-0 z-30 border-b border-surface-03 bg-surface-02/95 px-4 py-3 backdrop-blur">
          <div className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <div className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-gold/15 text-sm font-black text-gold">{initials}</div>
              <div className="min-w-0">
                <p className="truncate text-sm font-black">{driver?.name || "Motoboy"}</p>
                <p className="text-xs text-stone">{DRIVER_STATUS_LABELS[driver?.status || "offline"] || driver?.status}</p>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <button onClick={gpsActive ? stopGps : startGps} className={`grid h-11 w-11 place-items-center rounded-[8px] ${gpsActive ? "bg-green-500/15 text-green-300" : "bg-surface-03 text-stone"}`} title={gpsActive ? "Desativar GPS" : "Ativar GPS"}>
                {gpsActive ? <Navigation size={18} /> : <NavigationOff size={18} />}
              </button>
              <button onClick={loadDashboard} className="grid h-11 w-11 place-items-center rounded-[8px] bg-surface-03 text-stone" title="Atualizar">
                <RefreshCw size={18} className={loading ? "animate-spin" : ""} />
              </button>
              <button onClick={handleLogout} className="grid h-11 w-11 place-items-center rounded-[8px] bg-surface-03 text-stone" title="Sair">
                <LogOut size={18} />
              </button>
            </div>
          </div>
          {gpsError && <div className="mt-3 rounded-[8px] border border-orange-500/30 bg-orange-500/10 px-3 py-2 text-xs text-orange-200">{gpsError}</div>}
        </header>

        <main className="flex-1 space-y-5 px-4 pb-28 pt-4">
          {error && <div className="rounded-[8px] border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>}

          <section className="grid grid-cols-3 gap-2">
            <div className="rounded-[8px] border border-surface-03 bg-surface-02 p-3">
              <Package size={16} className="mb-2 text-gold" />
              <p className="text-[11px] font-bold uppercase text-stone">Atribuidas</p>
              <p className="mt-1 text-2xl font-black">{pendingToday}</p>
            </div>
            <div className="rounded-[8px] border border-surface-03 bg-surface-02 p-3">
              <CheckCircle2 size={16} className="mb-2 text-green-300" />
              <p className="text-[11px] font-bold uppercase text-stone">Concluidas</p>
              <p className="mt-1 text-2xl font-black">{completedToday}</p>
            </div>
            <div className="rounded-[8px] border border-surface-03 bg-surface-02 p-3">
              <DollarSign size={16} className="mb-2 text-gold" />
              <p className="text-[11px] font-bold uppercase text-stone">A receber</p>
              <p className="mt-1 text-lg font-black">{money(pendingAmount)}</p>
            </div>
          </section>

          <DriverLocationMap location={mapLocation} />

          {activeDeliveries.length > 1 && routeUrl && (
            <section className="rounded-[8px] border border-green-500/25 bg-green-500/10 p-4">
              <div className="flex items-start gap-3">
                <Route className="mt-0.5 shrink-0 text-green-300" size={20} />
                <div className="min-w-0 flex-1">
                  <p className="font-black text-green-100">Rota sugerida</p>
                  <p className="mt-1 text-sm text-green-200/80">Sequencia por horario de efetivacao do pedido.</p>
                </div>
              </div>
              <ol className="mt-3 space-y-2 text-sm text-parchment">
                {activeDeliveries.map((delivery, index) => (
                  <li key={delivery.id} className="flex gap-2">
                    <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-green-500/20 text-xs font-black text-green-200">{index + 1}</span>
                    <span className="min-w-0 truncate">{shortOrder(delivery.order_id)} - {delivery.order?.delivery_street || "Endereco nao informado"}</span>
                  </li>
                ))}
              </ol>
              <a href={routeUrl} target="_blank" rel="noreferrer" className="mt-4 flex h-12 items-center justify-center gap-2 rounded-[8px] bg-green-600 font-black text-white">
                <Navigation size={18} /> Abrir rota no Google Maps
              </a>
            </section>
          )}

          {activeDeliveries[0] && (
            <section>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-lg font-black">Proxima entrega</h2>
                <span className="text-xs text-stone">{activeDeliveries.length} na fila</span>
              </div>
              <DeliveryCard
                delivery={activeDeliveries[0]}
                currentLocation={mapLocation}
                busy={actionLoading === activeDeliveries[0].id}
                onStart={(d) => runAction(d.id, () => deliveryApi.driverStartDelivery(d.id))}
                onComplete={(d) => runAction(d.id, () => deliveryApi.driverCompleteDelivery(d.id))}
                onProblem={setProblem}
                onView={setDetail}
              />
            </section>
          )}

          <nav className="grid grid-cols-3 gap-2 rounded-[8px] border border-surface-03 bg-surface-02 p-1">
            {[
              ["fila", "Fila"],
              ["concluidas", "Concluidas"],
              ["financeiro", "Financeiro"],
            ].map(([key, label]) => (
              <button key={key} onClick={() => setTab(key as typeof tab)} className={`h-10 rounded-[8px] text-sm font-bold ${tab === key ? "bg-gold text-cream" : "text-stone"}`}>
                {label}
              </button>
            ))}
          </nav>

          {tab === "fila" && (
            <section className="space-y-3">
              {activeDeliveries.length === 0 ? (
                <div className="rounded-[8px] border border-dashed border-surface-03 py-12 text-center">
                  <Package className="mx-auto mb-3 text-stone" size={36} />
                  <p className="font-bold text-stone">Nenhuma entrega ativa.</p>
                </div>
              ) : activeDeliveries.slice(1).map((delivery) => (
                <DeliveryCard
                  key={delivery.id}
                  delivery={delivery}
                  currentLocation={mapLocation}
                  busy={actionLoading === delivery.id}
                  onStart={(d) => runAction(d.id, () => deliveryApi.driverStartDelivery(d.id))}
                  onComplete={(d) => runAction(d.id, () => deliveryApi.driverCompleteDelivery(d.id))}
                  onProblem={setProblem}
                  onView={setDetail}
                />
              ))}
            </section>
          )}

          {tab === "concluidas" && (
            <section className="space-y-3">
              {completedDeliveries.length === 0 ? <p className="rounded-[8px] border border-surface-03 bg-surface-02 p-6 text-center text-stone">Sem entregas concluidas ainda.</p> : completedDeliveries.map((delivery) => (
                <button key={delivery.id} onClick={() => setDetail(delivery)} className="flex w-full items-center justify-between rounded-[8px] border border-surface-03 bg-surface-02 p-4 text-left">
                  <div>
                    <p className="font-mono font-black text-cream">{shortOrder(delivery.order_id)}</p>
                    <p className="mt-1 text-sm text-stone">{delivery.order?.delivery_name || "Cliente"}</p>
                  </div>
                  <span className="rounded-full border border-green-500/30 bg-green-500/10 px-2.5 py-1 text-xs font-bold text-green-200">{STATUS_LABELS[delivery.status]}</span>
                </button>
              ))}
            </section>
          )}

          {tab === "financeiro" && (
            <section className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-[8px] border border-surface-03 bg-surface-02 p-4">
                  <p className="text-xs font-bold uppercase text-stone">Pendente</p>
                  <p className="mt-1 text-2xl font-black text-gold">{money(pendingAmount)}</p>
                </div>
                <div className="rounded-[8px] border border-surface-03 bg-surface-02 p-4">
                  <p className="text-xs font-bold uppercase text-stone">Pago</p>
                  <p className="mt-1 text-2xl font-black text-green-300">{money(paidAmount)}</p>
                </div>
              </div>
              {earnings.length === 0 ? <p className="rounded-[8px] border border-surface-03 bg-surface-02 p-6 text-center text-stone">Sem repasses registrados.</p> : earnings.map((earning) => (
                <div key={earning.id} className="flex items-center justify-between rounded-[8px] border border-surface-03 bg-surface-02 p-4">
                  <div>
                    <p className="font-mono text-sm font-black text-cream">{shortOrder(earning.delivery_id)}</p>
                    <p className="mt-1 text-xs text-stone">{earning.period_date || earning.created_at || "-"}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-black text-gold">{money(earning.amount)}</p>
                    <p className="mt-1 text-xs text-stone">{earning.status}</p>
                  </div>
                </div>
              ))}
            </section>
          )}
        </main>
      </div>

      {detail && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/70">
          <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-t-[8px] border border-surface-03 bg-surface-02 p-5">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-black">Pedido {shortOrder(detail.order_id)}</h3>
              <button onClick={() => setDetail(null)} className="grid h-10 w-10 place-items-center rounded-[8px] bg-surface-03 text-stone"><X size={18} /></button>
            </div>
            <div className="space-y-3 text-sm">
              <p><span className="text-stone">Cliente:</span> {detail.order?.delivery_name || "-"}</p>
              <p><span className="text-stone">Telefone:</span> {detail.order?.delivery_phone || "-"}</p>
              <p><span className="text-stone">Endereco:</span> {deliveryAddress(detail) || "-"}</p>
              <p><span className="text-stone">Pagamento:</span> {detail.order?.payment?.method || detail.order?.payment_status || "-"}</p>
              <p><span className="text-stone">Valor pedido:</span> {money(detail.order?.total)}</p>
              <p><span className="text-stone">Taxa entrega:</span> {money(detail.order?.shipping_fee)}</p>
              <p><span className="text-stone">Status pedido:</span> {detail.order?.status || "-"}</p>
              <p><span className="text-stone">Efetivado em:</span> {effectiveDate(detail) ? new Date(effectiveDate(detail) as string).toLocaleString("pt-BR") : "-"}</p>
              <p><span className="text-stone">Observacoes:</span> {detail.order?.notes || detail.notes || "-"}</p>
            </div>
          </div>
        </div>
      )}

      {problem && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/70">
          <div className="w-full max-w-2xl rounded-t-[8px] border border-surface-03 bg-surface-02 p-5">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-black">Reportar problema</h3>
              <button onClick={() => setProblem(null)} className="grid h-10 w-10 place-items-center rounded-[8px] bg-surface-03 text-stone"><X size={18} /></button>
            </div>
            <textarea value={problemText} onChange={(e) => setProblemText(e.target.value)} rows={4} className="w-full rounded-[8px] border border-surface-03 bg-surface-01 p-3 text-cream outline-none focus:border-gold" placeholder="Descreva o que aconteceu" />
            <button
              disabled={problemText.trim().length < 3 || actionLoading === problem.id}
              onClick={() => runAction(problem.id, () => deliveryApi.driverReportProblem(problem.id, "problema_na_entrega", problemText)).then(() => { setProblem(null); setProblemText(""); })}
              className="mt-4 flex w-full items-center justify-center gap-2 rounded-[8px] bg-red-600 py-4 font-black text-white disabled:opacity-50"
            >
              <AlertTriangle size={18} /> Enviar problema
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
