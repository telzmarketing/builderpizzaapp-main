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
  RefreshCw,
  Route,
  Send,
  Star,
  X,
} from "lucide-react";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import MotoboyInstallButton from "@/components/MotoboyInstallButton";
import {
  deliveryApi,
  type DeliveryEarning,
  type DeliveryPerson,
  type DeliveryRecord,
  type DriverDashboard,
} from "@/lib/api";

let L: typeof import("leaflet") | null = null;

const ACTIVE_STATUSES = new Set(["assigned", "picked_up", "on_the_way"]);
const DONE_STATUSES   = new Set(["delivered", "completed"]);

const STATUS_LABELS: Record<string, string> = {
  pending_assignment: "Aguardando",
  assigned:           "Aguardando retirada",
  picked_up:          "Retirada iniciada",
  on_the_way:         "Em rota",
  delivered:          "Entregue",
  completed:          "Concluída",
  failed:             "Problema na entrega",
  cancelled:          "Cancelada",
};

const STATUS_CLASSES: Record<string, string> = {
  assigned:   "border-blue-500/30 bg-blue-500/10 text-blue-300",
  picked_up:  "border-amber-500/30 bg-amber-500/10 text-amber-300",
  on_the_way: "border-violet-500/30 bg-violet-500/10 text-violet-300",
  delivered:  "border-green-500/30 bg-green-500/10 text-green-300",
  completed:  "border-green-500/30 bg-green-500/10 text-green-300",
  failed:     "border-red-500/30 bg-red-500/10 text-red-300",
  cancelled:  "border-surface-03 bg-surface-03/50 text-stone",
};

const DRIVER_STATUS_LABELS: Record<string, string> = {
  available: "Disponível",
  busy:      "Em rota",
  offline:   "Indisponível",
};

const DRIVER_STATUS_DOT: Record<string, string> = {
  available: "bg-green-400",
  busy:      "bg-amber-400",
  offline:   "bg-stone",
};

const PAYMENT_DELIVERY_PROBLEM_REASONS = [
  { value: "cliente_nao_quis_receber", label: "Cliente nao quis receber" },
  { value: "cliente_recebeu_nao_pagou", label: "Cliente recebeu e nao pagou" },
  { value: "cliente_devolveu_pedido", label: "Cliente devolveu o pedido" },
  { value: "problema_pagamento_entrega", label: "Outro problema de pagamento" },
];

function money(value?: number | null) {
  return (value || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function shortOrder(id: string) {
  return `#${id.slice(0, 8).toUpperCase()}`;
}

function maskCustomerName(name?: string | null) {
  const firstName = (name || "Cliente").trim().split(/\s+/)[0] || "Cliente";
  return `${firstName} ********`;
}

function deliveryAddress(delivery: DeliveryRecord): string | null {
  const order = delivery.order;
  if (!order?.delivery_street) return null;
  return [order.delivery_street, order.delivery_complement, order.delivery_city]
    .filter(Boolean)
    .join(", ");
}

function isPayOnDelivery(delivery: DeliveryRecord) {
  return Boolean(delivery.order?.payment?.pay_on_delivery || delivery.order?.pay_on_delivery);
}

function isDeliveryPaymentConfirmed(delivery: DeliveryRecord) {
  const status = delivery.order?.payment?.status || delivery.order?.payment_status;
  return status === "approved" || status === "paid";
}

function paymentLine(delivery: DeliveryRecord) {
  if (isPayOnDelivery(delivery)) return "Pagamento na entrega";
  if (isDeliveryPaymentConfirmed(delivery)) return "Pagamento online efetuado";
  return "Pagamento online";
}

function effectiveDate(delivery: DeliveryRecord): string | undefined {
  return delivery.order?.paid_at || delivery.order?.created_at || delivery.assigned_at || delivery.created_at;
}

function isToday(value?: string) {
  if (!value) return false;
  const d = new Date(value);
  const n = new Date();
  return d.getFullYear() === n.getFullYear() && d.getMonth() === n.getMonth() && d.getDate() === n.getDate();
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
  const addresses = deliveries.map(deliveryAddress).filter((a): a is string => Boolean(a));
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
  const deadline  = new Date(delivery.assigned_at).getTime() + delivery.estimated_minutes * 60_000;
  const remaining = Math.round((deadline - now) / 60_000);
  const urgent    = remaining <= 5;
  const text      = remaining < 0 ? `${Math.abs(remaining)}min atrasada` : `${remaining}min restantes`;
  return <span className={urgent ? "text-orange-300 font-bold" : "text-green-300"}>{text}</span>;
}

function DriverLocationMap({ location }: { location: { lat: number; lng: number } | null }) {
  const mapRef         = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<import("leaflet").Map | null>(null);
  const markerRef      = useRef<import("leaflet").Marker | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const link = document.createElement("link");
    link.rel   = "stylesheet";
    link.href  = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
    document.head.appendChild(link);
    import("leaflet").then((mod) => { L = mod.default ?? mod; setReady(true); });
    return () => { document.head.removeChild(link); mapInstanceRef.current?.remove(); mapInstanceRef.current = null; };
  }, []);

  useEffect(() => {
    if (!ready || !L || !mapRef.current || mapInstanceRef.current) return;
    const center: [number, number] = location ? [location.lat, location.lng] : [-23.55, -46.63];
    const map = L.map(mapRef.current, { center, zoom: location ? 16 : 12, zoomControl: false });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "OpenStreetMap", maxZoom: 19 }).addTo(map);
    mapInstanceRef.current = map;
  }, [ready, location]);

  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !L || !location) return;
    markerRef.current?.remove();
    const icon = L.divIcon({
      html: '<div style="background:#d9a441;border:3px solid white;border-radius:50%;width:30px;height:30px;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 10px rgba(0,0,0,.5)"><div style="background:#111827;border-radius:50%;width:10px;height:10px"></div></div>',
      iconSize: [30, 30], iconAnchor: [15, 15], className: "",
    });
    markerRef.current = L.marker([location.lat, location.lng], { icon }).addTo(map).bindPopup("Sua localização");
    map.setView([location.lat, location.lng], 16);
  }, [location]);

  return (
    <div className="relative overflow-hidden rounded-xl border border-surface-03 bg-surface-02" style={{ height: 176 }}>
      {!ready && <div className="absolute inset-0 z-10 grid place-items-center"><Loader2 className="animate-spin text-gold" size={28} /></div>}
      {!location && ready && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-surface-02/90 text-center px-6">
          <NavigationOff size={24} className="mb-2 text-stone" />
          <p className="text-sm text-stone">Ative o GPS para exibir sua posição.</p>
        </div>
      )}
      <div ref={mapRef} className="h-full w-full" />
    </div>
  );
}

function DeliveryCard({
  delivery, currentLocation, busy, onStart, onComplete, onProblem, onView,
}: {
  delivery: DeliveryRecord;
  currentLocation: { lat: number; lng: number } | null;
  busy: boolean;
  onStart:    (d: DeliveryRecord) => void;
  onComplete: (d: DeliveryRecord, paymentReceived: boolean) => void;
  onProblem:  (d: DeliveryRecord) => void;
  onView:     (d: DeliveryRecord) => void;
}) {
  const [paymentReceived, setPaymentReceived] = useState(false);
  const order      = delivery.order;
  const address    = deliveryAddress(delivery);
  const mapsUrl    = address ? googleMapsRouteUrl(address, currentLocation) : null;
  const searchUrl  = address ? googleMapsSearchUrl(address) : null;
  const statusCls  = STATUS_CLASSES[delivery.status] || "border-surface-03 bg-surface-03/50 text-stone";
  const canStart   = delivery.status === "assigned" || delivery.status === "picked_up";
  const canComplete= delivery.status === "on_the_way" || delivery.status === "picked_up" || delivery.status === "assigned";
  const requiresPaymentReceipt = isPayOnDelivery(delivery) && !isDeliveryPaymentConfirmed(delivery);

  return (
    <article className="overflow-hidden rounded-xl border border-surface-03 bg-surface-02 shadow-lg shadow-black/20">
      {/* Header do card */}
      <div className="flex items-center justify-between gap-3 border-b border-surface-03 px-4 py-3">
        <div className="min-w-0">
          <p className="font-mono text-base font-black text-gold">{shortOrder(delivery.order_id)}</p>
          <p className="mt-0.5 truncate text-sm font-semibold text-cream">{maskCustomerName(order?.delivery_name)}</p>
        </div>
        <span className={`shrink-0 rounded-full border px-3 py-1 text-[11px] font-bold tracking-wide ${statusCls}`}>
          {STATUS_LABELS[delivery.status] || delivery.status}
        </span>
      </div>

      {/* Corpo */}
      <div className="space-y-3 px-4 py-3">
        {address && (
          <div className="flex gap-2 text-sm text-parchment">
            <MapPin size={15} className="mt-0.5 shrink-0 text-gold" />
            <p className="leading-snug">{address}</p>
          </div>
        )}

        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-lg border border-surface-03 bg-surface-01 px-3 py-2">
            <p className="text-stone">Valor do pedido</p>
            <p className="mt-1 font-black text-cream">{money(order?.total)}</p>
          </div>
          <div className="rounded-lg border border-surface-03 bg-surface-01 px-3 py-2">
            <p className="text-stone">Taxa de entrega</p>
            <p className="mt-1 font-black text-gold">{money(order?.shipping_fee)}</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-xs text-stone">
          <span className="inline-flex items-center gap-1"><Clock3 size={12} /><EtaLine delivery={delivery} /></span>
        </div>

        <div className="rounded-lg border border-surface-03 bg-surface-01 px-3 py-2 text-xs">
          <p className="font-bold text-parchment">{paymentLine(delivery)}</p>
        </div>
      </div>

      {/* Ações */}
      <div className="grid grid-cols-2 gap-2 border-t border-surface-03 px-3 pb-3 pt-3">
        <button
          onClick={() => onView(delivery)}
          className="flex h-11 items-center justify-center gap-1.5 rounded-lg border border-surface-03 bg-surface-01 text-sm font-bold text-parchment hover:border-gold/40 transition-colors"
        >
          <Eye size={15} /> Detalhes
        </button>

        {mapsUrl || searchUrl ? (
          <a
            href={mapsUrl || searchUrl || "#"}
            target="_blank"
            rel="noreferrer"
            className="flex h-11 items-center justify-center gap-1.5 rounded-lg border border-green-500/30 bg-green-500/10 text-sm font-bold text-green-300 hover:bg-green-500/20 transition-colors"
          >
            <Navigation size={15} /> Maps
          </a>
        ) : (
          <button disabled className="flex h-11 items-center justify-center gap-1.5 rounded-lg border border-surface-03 bg-surface-01 text-sm font-bold text-stone opacity-40 cursor-not-allowed">
            <Navigation size={15} /> Maps
          </button>
        )}

        {canStart && (
          <button
            disabled={busy}
            onClick={() => onStart(delivery)}
            className="col-span-2 flex h-12 items-center justify-center gap-2 rounded-lg bg-gold font-black text-cream disabled:opacity-50 hover:bg-gold/90 transition-colors"
          >
            {busy ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
            Iniciar entrega
          </button>
        )}

        {canComplete && (
          <>
            {requiresPaymentReceipt && (
              <label className="col-span-2 flex items-center gap-2 rounded-lg border border-gold/25 bg-gold/10 px-3 py-2 text-sm font-bold text-parchment">
                <input
                  type="checkbox"
                  checked={paymentReceived}
                  onChange={(event) => setPaymentReceived(event.target.checked)}
                  className="h-4 w-4 accent-gold"
                />
                Confirmo que recebi o pagamento na entrega
              </label>
            )}
            <button
              disabled={busy || (requiresPaymentReceipt && !paymentReceived)}
              onClick={() => onComplete(delivery, requiresPaymentReceipt ? paymentReceived : false)}
              className="col-span-2 flex h-12 items-center justify-center gap-2 rounded-lg bg-green-600 font-black text-white disabled:opacity-50 hover:bg-green-700 transition-colors"
            >
              {busy ? <Loader2 size={18} className="animate-spin" /> : <CheckCircle2 size={18} />}
              Marcar como entregue
            </button>
          </>
        )}

        <button
          disabled={busy}
          onClick={() => onProblem(delivery)}
          className="col-span-2 flex h-10 items-center justify-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 text-sm font-bold text-red-300 disabled:opacity-50 hover:bg-red-500/20 transition-colors"
        >
          <AlertTriangle size={15} /> Reportar problema
        </button>
      </div>
    </article>
  );
}

export default function Motoboy() {
  const [token,         setToken]         = useState<string | null>(() => localStorage.getItem("driver_token"));
  const [driver,        setDriver]        = useState<DeliveryPerson | null>(null);
  const [dashboard,     setDashboard]     = useState<DriverDashboard | null>(null);
  const [earnings,      setEarnings]      = useState<DeliveryEarning[]>([]);
  const [loading,       setLoading]       = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [tab,           setTab]           = useState<"fila" | "concluidas" | "financeiro">("fila");
  const [email,         setEmail]         = useState("");
  const [password,      setPassword]      = useState("");
  const [loginLoading,  setLoginLoading]  = useState(false);
  const [error,         setError]         = useState("");
  const [gpsActive,     setGpsActive]     = useState(false);
  const [gpsError,      setGpsError]      = useState("");
  const [currentLocation, setCurrentLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [detail,        setDetail]        = useState<DeliveryRecord | null>(null);
  const [problem,       setProblem]       = useState<DeliveryRecord | null>(null);
  const [problemReason, setProblemReason] = useState(PAYMENT_DELIVERY_PROBLEM_REASONS[0].value);
  const [problemText,   setProblemText]   = useState("");
  const gpsWatchRef    = useRef<number | null>(null);
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
      const message = err instanceof Error ? err.message : "Sessão expirada.";
      setError(message);
      if (message.toLowerCase().includes("token")) {
        localStorage.removeItem("driver_token");
        setToken(null);
      }
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { if (token) void loadDashboard(); }, [token, loadDashboard]);
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
    if (!navigator.geolocation) { setGpsError("GPS não suportado neste dispositivo."); return; }
    setGpsError("");
    gpsWatchRef.current = navigator.geolocation.watchPosition(
      (pos) => { sendLocation(pos.coords.latitude, pos.coords.longitude); setGpsActive(true); },
      (err) => { setGpsError(`GPS: ${err.message}`); setGpsActive(false); },
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
    if (gpsWatchRef.current !== null)    navigator.geolocation.clearWatch(gpsWatchRef.current);
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
      setError(err instanceof Error ? err.message : "Credenciais inválidas.");
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
      setError(err instanceof Error ? err.message : "Não foi possível concluir a ação.");
    } finally {
      setActionLoading(null);
    }
  }

  const allDeliveries       = dashboard?.queue ?? [];
  const activeDeliveries    = useMemo(() => allDeliveries.filter((d) => ACTIVE_STATUSES.has(d.status)),  [allDeliveries]);
  const completedDeliveries = useMemo(() => allDeliveries.filter((d) => DONE_STATUSES.has(d.status)),   [allDeliveries]);
  const problemDeliveries   = useMemo(() => allDeliveries.filter((d) => d.status === "failed" && d.problem_report), [allDeliveries]);
  const completedToday      = completedDeliveries.filter((d) => isToday(d.delivered_at)).length;
  const pendingToday        = activeDeliveries.filter((d) => isToday(effectiveDate(d))).length;
  const pendingAmount       = dashboard?.pending_earnings ?? 0;
  const paidAmount          = dashboard?.paid_earnings    ?? 0;
  const mapLocation         = currentLocation || (driver?.location_lat && driver?.location_lng ? { lat: driver.location_lat, lng: driver.location_lng } : null);
  const routeUrl            = buildQueueRoute(activeDeliveries, mapLocation);
  const initials            = (driver?.name || "M").split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  const driverStatus        = driver?.status || "offline";

  /* ── Tela de login ── */
  if (!token) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-surface-00 to-surface-01 px-6 py-10">
        <MotoboyInstallButton />
        <div className="w-full max-w-sm">
          {/* Logo */}
          <div className="mb-10 flex flex-col items-center gap-4">
            <MoschettieriLogo className="text-cream text-xl scale-125 origin-center" />
            <div className="mt-2 flex items-center gap-2 rounded-full border border-gold/30 bg-gold/10 px-4 py-1.5">
              <Bike size={14} className="text-gold" />
              <span className="text-xs font-bold uppercase tracking-widest text-gold">App do Entregador</span>
            </div>
          </div>

          {/* Formulário */}
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="mb-2 block text-xs font-bold uppercase tracking-widest text-stone">E-mail</label>
              <input
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                type="email"
                autoComplete="email"
                placeholder="seu@email.com"
                className="w-full rounded-xl border border-surface-03 bg-surface-02 px-4 py-3.5 text-cream placeholder-stone/50 outline-none focus:border-gold transition-colors"
              />
            </div>
            <div>
              <label className="mb-2 block text-xs font-bold uppercase tracking-widest text-stone">Senha</label>
              <input
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                type="password"
                autoComplete="current-password"
                placeholder="••••••••"
                className="w-full rounded-xl border border-surface-03 bg-surface-02 px-4 py-3.5 text-cream placeholder-stone/50 outline-none focus:border-gold transition-colors"
              />
            </div>

            {error && (
              <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
                {error}
              </div>
            )}

            <button
              disabled={loginLoading}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-gold py-4 font-black text-cream disabled:opacity-60 hover:bg-gold/90 transition-colors"
            >
              {loginLoading ? <Loader2 size={18} className="animate-spin" /> : <Bike size={18} />}
              {loginLoading ? "Entrando..." : "Entrar"}
            </button>
          </form>

          <p className="mt-8 text-center text-xs text-stone/60">
            Acesso exclusivo para entregadores credenciados.
          </p>
        </div>
      </div>
    );
  }

  /* ── App principal ── */
  return (
    <div className="min-h-screen bg-surface-00 text-cream">
      <MotoboyInstallButton />
      <div className="mx-auto flex min-h-screen w-full max-w-3xl flex-col">

        {/* Header */}
        <header className="sticky top-0 z-30 border-b border-surface-03 bg-surface-01/95 backdrop-blur">
          {/* Barra com logo */}
          <div className="flex items-center justify-between gap-3 border-b border-surface-03/50 px-4 py-3">
            <div className="flex min-w-0 items-center gap-3">
              <MoschettieriLogo className="shrink-0 text-cream text-lg leading-none" />
              <div className="min-w-0 border-l border-gold/25 pl-3">
                <p className="truncate text-[10px] font-bold uppercase tracking-[0.22em] text-gold">App do Motoboy</p>
                <p className="truncate text-xs font-medium text-stone">Entregas Moschettieri</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {/* GPS */}
              <button
                onClick={gpsActive ? stopGps : startGps}
                title={gpsActive ? "Desativar GPS" : "Ativar GPS"}
                className={`flex h-9 w-9 items-center justify-center rounded-lg transition-colors ${
                  gpsActive
                    ? "bg-green-500/15 text-green-300 hover:bg-green-500/25"
                    : "bg-surface-03 text-stone hover:text-parchment"
                }`}
              >
                {gpsActive ? <Navigation size={16} /> : <NavigationOff size={16} />}
              </button>
              {/* Refresh */}
              <button
                onClick={loadDashboard}
                title="Atualizar"
                className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-03 text-stone hover:text-parchment transition-colors"
              >
                <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
              </button>
              {/* Logout */}
              <button
                onClick={handleLogout}
                title="Sair"
                className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-03 text-stone hover:text-red-400 transition-colors"
              >
                <LogOut size={16} />
              </button>
            </div>
          </div>

          {/* Info do entregador */}
          <div className="flex items-center gap-3 px-4 py-3">
            <div className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-gold/15 text-sm font-black text-gold ring-2 ring-gold/20">
              {initials}
              <span className={`absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-surface-01 ${DRIVER_STATUS_DOT[driverStatus] || "bg-stone"}`} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-black text-cream">{driver?.name || "Entregador"}</p>
              <p className="text-xs text-stone">{DRIVER_STATUS_LABELS[driverStatus] || driverStatus}</p>
            </div>
            {driver?.average_rating != null && (
              <div className="flex items-center gap-1 rounded-full border border-gold/20 bg-gold/10 px-2.5 py-1 text-xs font-bold text-gold">
                <Star size={11} fill="currentColor" />
                {driver.average_rating.toFixed(1)}
              </div>
            )}
          </div>

          {gpsError && (
            <div className="mx-4 mb-3 rounded-lg border border-orange-500/30 bg-orange-500/10 px-3 py-2 text-xs text-orange-300">
              {gpsError}
            </div>
          )}
        </header>

        {/* Conteúdo */}
        <main className="flex-1 space-y-5 px-4 pb-28 pt-5">
          {error && (
            <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}

          {/* Cards de resumo */}
          <section className="grid grid-cols-3 gap-2">
            {[
              { icon: <Package size={18} className="text-gold" />,         label: "Atribuídas",  value: pendingToday,            cls: "text-cream" },
              { icon: <CheckCircle2 size={18} className="text-green-300" />, label: "Concluídas",  value: completedToday,          cls: "text-cream" },
              { icon: <DollarSign size={18} className="text-gold" />,       label: "A receber",   value: money(pendingAmount),     cls: "text-gold text-sm" },
            ].map(({ icon, label, value, cls }) => (
              <div key={label} className="rounded-xl border border-surface-03 bg-surface-02 p-3 shadow-sm">
                <div className="mb-2">{icon}</div>
                <p className="text-[10px] font-bold uppercase tracking-wide text-stone">{label}</p>
                <p className={`mt-1 text-xl font-black leading-none ${cls}`}>{value}</p>
              </div>
            ))}
          </section>

          {/* Mapa GPS */}
          <DriverLocationMap location={mapLocation} />

          {problemDeliveries.length > 0 && (
            <section className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-black text-cream">Problemas reportados</h2>
                <span className="text-xs text-stone">Atualiza a cada 30s</span>
              </div>
              {problemDeliveries.map((delivery) => {
                const resolved = Boolean(delivery.problem_resolved_at);
                return (
                  <button
                    key={delivery.id}
                    onClick={() => setDetail(delivery)}
                    className={`w-full rounded-xl border p-4 text-left transition-colors ${
                      resolved
                        ? "border-green-500/30 bg-green-500/10 hover:bg-green-500/15"
                        : "border-red-500/30 bg-red-500/10 hover:bg-red-500/15"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className={resolved ? "text-sm font-black text-green-200" : "text-sm font-black text-red-200"}>
                          {resolved ? "Resolvido pela administraÃ§Ã£o" : "Aguardando administraÃ§Ã£o"}
                        </p>
                        <p className="mt-1 font-mono text-xs font-bold text-gold">{shortOrder(delivery.order_id)}</p>
                        <p className="mt-1 line-clamp-2 text-xs text-parchment">
                          {resolved
                            ? delivery.admin_resolution_note || "Problema resolvido. Verifique a orientaÃ§Ã£o da loja."
                            : delivery.problem_report}
                        </p>
                      </div>
                      {resolved ? <CheckCircle2 size={18} className="shrink-0 text-green-300" /> : <AlertTriangle size={18} className="shrink-0 text-red-300" />}
                    </div>
                  </button>
                );
              })}
            </section>
          )}

          {/* Rota sugerida */}
          {activeDeliveries.length > 1 && routeUrl && (
            <section className="rounded-xl border border-green-500/20 bg-green-500/5 p-4">
              <div className="mb-3 flex items-center gap-2">
                <Route size={18} className="text-green-300" />
                <p className="font-black text-green-100">Rota sugerida</p>
                <span className="ml-auto text-xs text-green-300/70">{activeDeliveries.length} paradas</span>
              </div>
              <ol className="space-y-2">
                {activeDeliveries.map((delivery, i) => (
                  <li key={delivery.id} className="flex items-start gap-2.5 text-sm text-parchment">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-green-500/20 text-[11px] font-black text-green-200">
                      {i + 1}
                    </span>
                    <span className="min-w-0 truncate leading-tight">
                      <span className="font-mono text-xs text-gold">{shortOrder(delivery.order_id)}</span>
                      {" — "}
                      {delivery.order?.delivery_street || "Endereço não informado"}
                    </span>
                  </li>
                ))}
              </ol>
              <a
                href={routeUrl}
                target="_blank"
                rel="noreferrer"
                className="mt-4 flex h-11 items-center justify-center gap-2 rounded-xl bg-green-600 font-black text-white hover:bg-green-700 transition-colors"
              >
                <Navigation size={16} /> Abrir no Google Maps
              </a>
            </section>
          )}

          {/* Próxima entrega */}
          {activeDeliveries[0] && (
            <section>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-base font-black text-cream">Próxima entrega</h2>
                <span className="text-xs text-stone">{activeDeliveries.length} na fila</span>
              </div>
              <DeliveryCard
                delivery={activeDeliveries[0]}
                currentLocation={mapLocation}
                busy={actionLoading === activeDeliveries[0].id}
                onStart={(d) => runAction(d.id, () => deliveryApi.driverStartDelivery(d.id))}
                onComplete={(d, paymentReceived) => runAction(d.id, () => deliveryApi.driverCompleteDelivery(d.id, undefined, paymentReceived))}
                onProblem={setProblem}
                onView={setDetail}
              />
            </section>
          )}

          {/* Abas */}
          <nav className="grid grid-cols-3 overflow-hidden rounded-xl border border-surface-03 bg-surface-02">
            {(["fila", "concluidas", "financeiro"] as const).map((key, i) => {
              const labels = ["Fila", "Concluídas", "Financeiro"];
              return (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className={`h-11 text-sm font-bold transition-colors ${
                    tab === key
                      ? "bg-gold text-cream"
                      : "text-stone hover:text-parchment"
                  } ${i < 2 ? "border-r border-surface-03" : ""}`}
                >
                  {labels[i]}
                </button>
              );
            })}
          </nav>

          {/* Aba: Fila */}
          {tab === "fila" && (
            <section className="space-y-3">
              {activeDeliveries.length === 0 ? (
                <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-surface-03 py-14 text-center">
                  <Package size={40} className="mb-3 text-stone/50" />
                  <p className="font-bold text-stone">Nenhuma entrega ativa.</p>
                  <p className="mt-1 text-xs text-stone/60">Aguardando novas atribuições.</p>
                </div>
              ) : (
                activeDeliveries.slice(1).map((delivery) => (
                  <DeliveryCard
                    key={delivery.id}
                    delivery={delivery}
                    currentLocation={mapLocation}
                    busy={actionLoading === delivery.id}
                    onStart={(d) => runAction(d.id, () => deliveryApi.driverStartDelivery(d.id))}
                    onComplete={(d, paymentReceived) => runAction(d.id, () => deliveryApi.driverCompleteDelivery(d.id, undefined, paymentReceived))}
                    onProblem={setProblem}
                    onView={setDetail}
                  />
                ))
              )}
            </section>
          )}

          {/* Aba: Concluídas */}
          {tab === "concluidas" && (
            <section className="space-y-2">
              {completedDeliveries.length === 0 ? (
                <div className="rounded-xl border border-surface-03 bg-surface-02 p-8 text-center">
                  <CheckCircle2 size={36} className="mx-auto mb-3 text-stone/40" />
                  <p className="text-stone">Sem entregas concluídas ainda.</p>
                </div>
              ) : completedDeliveries.map((delivery) => (
                <button
                  key={delivery.id}
                  onClick={() => setDetail(delivery)}
                  className="flex w-full items-center justify-between rounded-xl border border-surface-03 bg-surface-02 px-4 py-3.5 text-left hover:border-surface-03/80 transition-colors"
                >
                  <div>
                    <p className="font-mono text-sm font-black text-gold">{shortOrder(delivery.order_id)}</p>
                    <p className="mt-0.5 text-xs text-stone">{maskCustomerName(delivery.order?.delivery_name)}</p>
                  </div>
                  <span className="rounded-full border border-green-500/30 bg-green-500/10 px-2.5 py-1 text-xs font-bold text-green-300">
                    {STATUS_LABELS[delivery.status]}
                  </span>
                </button>
              ))}
            </section>
          )}

          {/* Aba: Financeiro */}
          {tab === "financeiro" && (
            <section className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-xl border border-gold/20 bg-gold/5 p-4">
                  <p className="text-xs font-bold uppercase tracking-wide text-stone">A receber</p>
                  <p className="mt-2 text-2xl font-black text-gold">{money(pendingAmount)}</p>
                </div>
                <div className="rounded-xl border border-green-500/20 bg-green-500/5 p-4">
                  <p className="text-xs font-bold uppercase tracking-wide text-stone">Recebido</p>
                  <p className="mt-2 text-2xl font-black text-green-300">{money(paidAmount)}</p>
                </div>
              </div>

              {earnings.length === 0 ? (
                <div className="rounded-xl border border-surface-03 bg-surface-02 p-8 text-center">
                  <DollarSign size={36} className="mx-auto mb-3 text-stone/40" />
                  <p className="text-stone">Sem repasses registrados.</p>
                </div>
              ) : earnings.map((earning) => (
                <div key={earning.id} className="flex items-center justify-between rounded-xl border border-surface-03 bg-surface-02 px-4 py-3.5">
                  <div>
                    <p className="font-mono text-sm font-black text-parchment">{shortOrder(earning.delivery_id)}</p>
                    <p className="mt-0.5 text-xs text-stone">{earning.period_date || earning.created_at || "—"}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-black text-gold">{money(earning.amount)}</p>
                    <span className={`mt-0.5 inline-block rounded-full px-2 py-0.5 text-[10px] font-bold ${
                      earning.status === "paid"
                        ? "bg-green-500/10 text-green-300"
                        : "bg-amber-500/10 text-amber-300"
                    }`}>
                      {earning.status === "paid" ? "Pago" : "Pendente"}
                    </span>
                  </div>
                </div>
              ))}
            </section>
          )}
        </main>
      </div>

      {/* Modal: Detalhes do pedido */}
      {detail && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 backdrop-blur-sm">
          <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-t-2xl border-t border-surface-03 bg-surface-02 p-5">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <p className="font-mono text-lg font-black text-gold">{shortOrder(detail.order_id)}</p>
                <p className="text-xs text-stone">Detalhes do pedido</p>
              </div>
              <button onClick={() => setDetail(null)} className="flex h-10 w-10 items-center justify-center rounded-xl bg-surface-03 text-stone hover:text-cream transition-colors">
                <X size={18} />
              </button>
            </div>

            <div className="space-y-3 text-sm">
              {[
                ["Cliente",     maskCustomerName(detail.order?.delivery_name)],
                ["Endereço",    deliveryAddress(detail) || "—"],
                ["Pagamento",   detail.order?.payment?.method || detail.order?.payment_status || "—"],
                ["Valor",       money(detail.order?.total)],
                ["Taxa entrega",money(detail.order?.shipping_fee)],
                ["Status",      detail.order?.status || "—"],
                ...(detail.problem_report ? [["Problema", detail.problem_report]] : []),
                ...(detail.admin_resolution_note ? [["Retorno admin", detail.admin_resolution_note]] : []),
                ["Observações", detail.order?.notes || detail.notes || "—"],
              ].map(([label, value]) => (
                <div key={label} className="flex gap-2 rounded-lg bg-surface-01 px-3 py-2.5">
                  <span className="w-28 shrink-0 text-stone">{label}:</span>
                  <span className="text-parchment">{value}</span>
                </div>
              ))}
            </div>

            {deliveryAddress(detail) && (
              <a
                href={googleMapsRouteUrl(deliveryAddress(detail)!, mapLocation)}
                target="_blank"
                rel="noreferrer"
                className="mt-5 flex h-12 items-center justify-center gap-2 rounded-xl bg-green-600 font-black text-white hover:bg-green-700 transition-colors"
              >
                <Navigation size={16} /> Abrir no Maps
              </a>
            )}
          </div>
        </div>
      )}

      {/* Modal: Reportar problema */}
      {problem && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-2xl rounded-t-2xl border-t border-surface-03 bg-surface-02 p-5">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <p className="font-black text-cream">Reportar problema</p>
                <p className="text-xs text-stone">{shortOrder(problem.order_id)}</p>
              </div>
              <button onClick={() => { setProblem(null); setProblemText(""); setProblemReason(PAYMENT_DELIVERY_PROBLEM_REASONS[0].value); }} className="flex h-10 w-10 items-center justify-center rounded-xl bg-surface-03 text-stone hover:text-cream transition-colors">
                <X size={18} />
              </button>
            </div>
            <label className="mb-3 block">
              <span className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-stone">Motivo</span>
              <select
                value={problemReason}
                onChange={(e) => setProblemReason(e.target.value)}
                className="w-full rounded-xl border border-surface-03 bg-surface-01 p-3 text-cream outline-none focus:border-red-400 transition-colors"
              >
                {PAYMENT_DELIVERY_PROBLEM_REASONS.map((reason) => (
                  <option key={reason.value} value={reason.value}>{reason.label}</option>
                ))}
              </select>
            </label>
            <textarea
              value={problemText}
              onChange={(e) => setProblemText(e.target.value)}
              rows={4}
              placeholder="Detalhe o que aconteceu..."
              className="w-full resize-none rounded-xl border border-surface-03 bg-surface-01 p-3 text-cream placeholder-stone/50 outline-none focus:border-red-400 transition-colors"
            />
            <button
              disabled={actionLoading === problem.id}
              onClick={() => {
                const reason = PAYMENT_DELIVERY_PROBLEM_REASONS.find((item) => item.value === problemReason);
                const detail = problemText.trim();
                const description = detail ? `${reason?.label}: ${detail}` : reason?.label;
                runAction(problem.id, () =>
                  deliveryApi.driverReportProblem(problem.id, problemReason, description)
                ).then(() => {
                  setProblem(null);
                  setProblemText("");
                  setProblemReason(PAYMENT_DELIVERY_PROBLEM_REASONS[0].value);
                });
              }}
              className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-red-600 py-4 font-black text-white disabled:opacity-50 hover:bg-red-700 transition-colors"
            >
              {actionLoading === problem.id ? <Loader2 size={18} className="animate-spin" /> : <AlertTriangle size={18} />}
              Enviar problema
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
