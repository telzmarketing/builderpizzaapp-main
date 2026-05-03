import { useCallback, useEffect, useRef, useState } from "react";
import {
  Loader2, LogOut, Package, CheckCircle, Clock, Bike,
  Navigation, NavigationOff, MapPin, Star, RotateCcw, X,
} from "lucide-react";
import { deliveryApi, type DeliveryPerson, type DeliveryRecord } from "@/lib/api";

function etaText(assignedAt?: string, estimatedMinutes?: number): { text: string; urgent: boolean } | null {
  if (!assignedAt || !estimatedMinutes) return null;
  const deadline = new Date(assignedAt).getTime() + estimatedMinutes * 60_000;
  const remaining = Math.round((deadline - Date.now()) / 60_000);
  if (remaining < 0) return { text: `${Math.abs(remaining)}min de atraso`, urgent: true };
  return { text: `${remaining}min restantes`, urgent: remaining <= 5 };
}

function EtaLine({ assignedAt, estimatedMinutes }: { assignedAt?: string; estimatedMinutes?: number }) {
  const [eta, setEta] = useState(() => etaText(assignedAt, estimatedMinutes));
  useEffect(() => {
    const id = setInterval(() => setEta(etaText(assignedAt, estimatedMinutes)), 30_000);
    return () => clearInterval(id);
  }, [assignedAt, estimatedMinutes]);
  if (!eta) return null;
  return (
    <span className={`text-xs font-semibold flex items-center gap-1 ${eta.urgent ? "text-orange-400" : "text-green-400"}`}>
      <Clock size={11} />
      {eta.text}
    </span>
  );
}

const VEHICLE_EMOJI: Record<string, string> = {
  motorcycle: "🏍️", bicycle: "🚲", car: "🚗", walking: "🚶",
};

const STATUS_LABELS: Record<string, string> = {
  assigned: "Designado", picked_up: "Coletado", on_the_way: "A caminho",
  delivered: "Entregue", completed: "Finalizado", pending_assignment: "Aguardando",
};

const STATUS_CLS: Record<string, string> = {
  assigned:   "bg-blue-500/20 text-blue-300 border-blue-500/30",
  picked_up:  "bg-amber-500/20 text-amber-300 border-amber-500/30",
  on_the_way: "bg-violet-500/20 text-violet-300 border-violet-500/30",
  delivered:  "bg-green-500/20 text-green-300 border-green-500/30",
  completed:  "bg-green-500/20 text-green-300 border-green-500/30",
};

const DRIVER_STATUS_CLS: Record<string, string> = {
  available: "bg-green-500/20 text-green-400",
  busy:      "bg-amber-500/20 text-amber-400",
  offline:   "bg-stone/20 text-stone",
};

const DRIVER_STATUS_LABELS: Record<string, string> = {
  available: "Disponível", busy: "Em rota", offline: "Offline",
};

const ACTIVE_STATUSES = new Set(["assigned", "picked_up", "on_the_way"]);

export default function Motoboy() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("driver_token"));
  const [driver, setDriver] = useState<DeliveryPerson | null>(null);
  const [deliveries, setDeliveries] = useState<DeliveryRecord[]>([]);
  const [loadingDriver, setLoadingDriver] = useState(false);
  const [loadingDeliveries, setLoadingDeliveries] = useState(false);

  const [gpsActive, setGpsActive] = useState(false);
  const [gpsError, setGpsError] = useState("");
  const gpsWatchRef = useRef<number | null>(null);
  const gpsIntervalRef = useRef<number | null>(null);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState("");

  const [confirmModal, setConfirmModal] = useState<{ deliveryId: string } | null>(null);
  const [code, setCode] = useState("");
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [confirmError, setConfirmError] = useState("");
  const [confirmSuccess, setConfirmSuccess] = useState(false);

  const loadDriver = useCallback(async () => {
    if (!token) return;
    setLoadingDriver(true);
    try {
      const data = await deliveryApi.driverMe();
      setDriver(data);
    } catch {
      localStorage.removeItem("driver_token");
      setToken(null);
    } finally {
      setLoadingDriver(false);
    }
  }, [token]);

  const loadDeliveries = useCallback(async () => {
    if (!token) return;
    setLoadingDeliveries(true);
    try {
      const data = await deliveryApi.driverDeliveries();
      setDeliveries(data ?? []);
    } catch { /* ignore */ }
    finally { setLoadingDeliveries(false); }
  }, [token]);

  useEffect(() => {
    if (token) { loadDriver(); loadDeliveries(); }
  }, [token, loadDriver, loadDeliveries]);

  useEffect(() => {
    if (!token) return;
    const id = window.setInterval(loadDeliveries, 30_000);
    return () => window.clearInterval(id);
  }, [token, loadDeliveries]);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoginLoading(true);
    setLoginError("");
    try {
      const data = await deliveryApi.driverLogin(email, password);
      localStorage.setItem("driver_token", data.token);
      setToken(data.token);
      setDriver(data.person);
    } catch (err: unknown) {
      setLoginError(err instanceof Error ? err.message : "Credenciais inválidas.");
    } finally {
      setLoginLoading(false);
    }
  }

  const sendLocation = useCallback((lat: number, lng: number) => {
    deliveryApi.driverUpdateLocation(lat, lng).catch(() => {});
  }, []);

  const startGps = useCallback(() => {
    if (!navigator.geolocation) { setGpsError("GPS não suportado neste dispositivo."); return; }
    setGpsError("");
    gpsWatchRef.current = navigator.geolocation.watchPosition(
      (pos) => { sendLocation(pos.coords.latitude, pos.coords.longitude); setGpsActive(true); setGpsError(""); },
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
    if (gpsWatchRef.current !== null) { navigator.geolocation.clearWatch(gpsWatchRef.current); gpsWatchRef.current = null; }
    if (gpsIntervalRef.current !== null) { window.clearInterval(gpsIntervalRef.current); gpsIntervalRef.current = null; }
    setGpsActive(false);
  }, []);

  useEffect(() => () => stopGps(), [stopGps]);

  function handleLogout() {
    stopGps();
    localStorage.removeItem("driver_token");
    setToken(null);
    setDriver(null);
    setDeliveries([]);
  }

  async function handleConfirm() {
    if (!confirmModal || code.length !== 4) return;
    setConfirmLoading(true);
    setConfirmError("");
    try {
      await deliveryApi.confirmCode(confirmModal.deliveryId, code);
      setConfirmSuccess(true);
      setTimeout(() => {
        setConfirmModal(null);
        setCode("");
        setConfirmSuccess(false);
        loadDeliveries();
      }, 1500);
    } catch (err: unknown) {
      setConfirmError(err instanceof Error ? err.message : "Código inválido.");
    } finally {
      setConfirmLoading(false);
    }
  }

  // ── Login ─────────────────────────────────────────────────────────────────

  if (!token) {
    return (
      <div className="min-h-screen bg-surface-00 flex flex-col items-center justify-center p-6">
        <div className="w-full max-w-xs">
          <div className="text-center mb-10">
            <div className="inline-flex h-20 w-20 items-center justify-center rounded-3xl bg-gold/15 mb-5 shadow-lg shadow-gold/10">
              <Bike size={36} className="text-gold" />
            </div>
            <h1 className="text-cream text-2xl font-black tracking-tight">App do Entregador</h1>
            <p className="text-stone text-sm mt-1.5">Acesso exclusivo para entregadores</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div className="flex flex-col gap-1.5">
              <span className="text-stone text-xs font-semibold uppercase tracking-wider">Email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                placeholder="seu@email.com"
                className="rounded-2xl bg-surface-02 border border-surface-03 text-cream px-4 py-4 text-base focus:outline-none focus:border-gold/60 placeholder:text-stone/40"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <span className="text-stone text-xs font-semibold uppercase tracking-wider">Senha</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                placeholder="••••••••"
                className="rounded-2xl bg-surface-02 border border-surface-03 text-cream px-4 py-4 text-base focus:outline-none focus:border-gold/60"
              />
            </div>

            {loginError && (
              <div className="rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-300">
                {loginError}
              </div>
            )}

            <button
              type="submit"
              disabled={loginLoading}
              className="w-full flex items-center justify-center gap-2 rounded-2xl bg-gold py-4 text-cream font-bold text-base hover:bg-gold/90 active:scale-[0.98] disabled:opacity-50 transition-all mt-2"
            >
              {loginLoading && <Loader2 size={18} className="animate-spin" />}
              Entrar
            </button>
          </form>
        </div>
      </div>
    );
  }

  // ── Loading ───────────────────────────────────────────────────────────────

  if (loadingDriver) {
    return (
      <div className="min-h-screen bg-surface-00 flex items-center justify-center">
        <Loader2 size={40} className="animate-spin text-gold" />
      </div>
    );
  }

  // ── App ───────────────────────────────────────────────────────────────────

  const activeDeliveries = deliveries.filter((d) => ACTIVE_STATUSES.has(d.status));
  const pastDeliveries   = deliveries.filter((d) => !ACTIVE_STATUSES.has(d.status));
  const initials = driver?.name.split(" ").map((n) => n[0]).slice(0, 2).join("") ?? "—";

  return (
    <div className="h-screen bg-surface-00 flex flex-col overflow-hidden">

      {/* ── Header fixo ── */}
      <header className="flex-shrink-0 bg-surface-02 border-b border-surface-03 px-4 pt-safe-top">
        <div className="flex items-center justify-between h-16">
          {/* Driver info */}
          <div className="flex items-center gap-3 min-w-0">
            <div className="h-10 w-10 flex-shrink-0 rounded-full bg-gold/20 flex items-center justify-center">
              <span className="text-gold font-black text-sm">{initials}</span>
            </div>
            <div className="min-w-0">
              <p className="text-cream font-bold text-sm leading-tight truncate">{driver?.name}</p>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="text-base leading-none">{VEHICLE_EMOJI[driver?.vehicle_type ?? "motorcycle"]}</span>
                <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${DRIVER_STATUS_CLS[driver?.status ?? "offline"]}`}>
                  {DRIVER_STATUS_LABELS[driver?.status ?? "offline"]}
                </span>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <button
              onClick={gpsActive ? stopGps : startGps}
              className={`h-10 w-10 flex items-center justify-center rounded-full transition-colors ${
                gpsActive
                  ? "bg-green-500/15 text-green-400"
                  : "bg-surface-03 text-stone"
              }`}
              title={gpsActive ? "Parar GPS" : "Ativar GPS"}
            >
              {gpsActive ? <Navigation size={18} /> : <NavigationOff size={18} />}
            </button>
            <button
              onClick={handleLogout}
              className="h-10 w-10 flex items-center justify-center rounded-full bg-surface-03 text-stone hover:text-cream transition-colors"
              title="Sair"
            >
              <LogOut size={18} />
            </button>
          </div>
        </div>

        {/* GPS error inline */}
        {gpsError && (
          <div className="pb-3">
            <div className="rounded-xl bg-orange-500/10 border border-orange-500/20 px-3 py-2 text-xs text-orange-300 flex items-center gap-2">
              <NavigationOff size={12} className="flex-shrink-0" />
              {gpsError}
            </div>
          </div>
        )}
      </header>

      {/* ── Conteúdo scrollável ── */}
      <main className="flex-1 overflow-y-auto pb-safe-bottom">

        {/* Stats */}
        <div className="grid grid-cols-2 gap-3 px-4 pt-4">
          <div className="rounded-2xl bg-surface-02 border border-surface-03 p-4 text-center">
            <div className="flex items-center justify-center gap-1 mb-1">
              <Package size={13} className="text-stone" />
              <p className="text-stone text-[10px] uppercase tracking-widest font-semibold">Entregas</p>
            </div>
            <p className="text-gold text-3xl font-black">{driver?.total_deliveries ?? 0}</p>
          </div>
          <div className="rounded-2xl bg-surface-02 border border-surface-03 p-4 text-center">
            <div className="flex items-center justify-center gap-1 mb-1">
              <Star size={13} className="text-stone" />
              <p className="text-stone text-[10px] uppercase tracking-widest font-semibold">Avaliação</p>
            </div>
            <p className="text-gold text-3xl font-black">{(driver?.average_rating ?? 5).toFixed(1)}</p>
          </div>
        </div>

        {/* Em andamento */}
        <div className="px-4 mt-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-cream font-bold text-base">Em andamento</h2>
            <button
              onClick={loadDeliveries}
              disabled={loadingDeliveries}
              className="h-8 w-8 flex items-center justify-center rounded-full bg-surface-02 border border-surface-03 text-stone disabled:opacity-40 transition-opacity"
              title="Atualizar"
            >
              <RotateCcw size={14} className={loadingDeliveries ? "animate-spin" : ""} />
            </button>
          </div>

          {activeDeliveries.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-surface-03 py-12 text-center">
              <Package size={36} className="text-stone mx-auto mb-3" />
              <p className="text-stone text-sm font-medium">Nenhuma entrega ativa</p>
              <p className="text-stone/60 text-xs mt-1">Aguarde a atribuição pelo painel</p>
            </div>
          ) : (
            <div className="space-y-4">
              {activeDeliveries.map((d) => {
                const statusCls = STATUS_CLS[d.status] ?? "bg-stone/20 text-stone border-stone/20";
                return (
                  <div key={d.id} className="rounded-2xl bg-surface-02 border border-surface-03 overflow-hidden">

                    {/* Card header */}
                    <div className="flex items-center justify-between px-4 pt-4 pb-3 border-b border-surface-03">
                      <p className="text-cream font-mono font-bold text-base tracking-wide">
                        #{d.order_id.slice(0, 8).toUpperCase()}
                      </p>
                      <span className={`text-[11px] font-bold px-2.5 py-1 rounded-full border ${statusCls}`}>
                        {STATUS_LABELS[d.status] ?? d.status}
                      </span>
                    </div>

                    {/* Endereço */}
                    {d.order && (d.order.delivery_name || d.order.delivery_street) && (
                      <div className="px-4 py-3 border-b border-surface-03">
                        {d.order.delivery_name && (
                          <p className="text-parchment text-sm font-semibold mb-1">{d.order.delivery_name}</p>
                        )}
                        {d.order.delivery_street && (
                          <div className="flex items-start gap-2">
                            <MapPin size={14} className="text-gold flex-shrink-0 mt-0.5" />
                            <p className="text-stone text-sm leading-snug">
                              {d.order.delivery_street}
                              {d.order.delivery_complement ? `, ${d.order.delivery_complement}` : ""}
                              {d.order.delivery_city ? ` — ${d.order.delivery_city}` : ""}
                            </p>
                          </div>
                        )}
                      </div>
                    )}

                    {/* ETA */}
                    <div className="px-4 py-2.5 flex items-center gap-3 border-b border-surface-03">
                      <EtaLine assignedAt={d.assigned_at} estimatedMinutes={d.estimated_minutes} />
                      <span className="text-stone text-xs">{d.estimated_minutes}min estimado</span>
                    </div>

                    {/* Código de confirmação */}
                    <div className="px-4 pt-4 pb-4">
                      {d.confirmation_code && !d.confirmed_by_code_at && (
                        <div className="rounded-2xl bg-gold/10 border border-gold/30 p-4 mb-4">
                          <p className="text-gold text-[10px] uppercase tracking-widest text-center mb-2 font-bold">
                            Código de confirmação
                          </p>
                          <p className="text-gold font-mono text-4xl font-black text-center tracking-[0.5em]">
                            {d.confirmation_code}
                          </p>
                          <p className="text-stone text-xs text-center mt-2">
                            Mostre ao cliente para confirmar a entrega
                          </p>
                        </div>
                      )}

                      {d.confirmed_by_code_at && (
                        <div className="flex items-center gap-2 text-green-400 text-sm mb-4 bg-green-500/10 rounded-xl px-3 py-2.5">
                          <CheckCircle size={16} />
                          <span className="font-medium">Confirmado pelo cliente</span>
                        </div>
                      )}

                      <button
                        onClick={() => {
                          setCode(""); setConfirmError(""); setConfirmSuccess(false);
                          setConfirmModal({ deliveryId: d.id });
                        }}
                        disabled={!!d.confirmed_by_code_at}
                        className="w-full rounded-2xl bg-gold py-4 text-cream text-base font-bold active:scale-[0.98] hover:bg-gold/90 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                      >
                        {d.confirmed_by_code_at ? "Entrega confirmada ✓" : "Confirmar entrega"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Histórico */}
        {pastDeliveries.length > 0 && (
          <div className="px-4 mt-8 mb-4">
            <h2 className="text-cream font-bold text-base mb-3">Histórico recente</h2>
            <div className="rounded-2xl bg-surface-02 border border-surface-03 divide-y divide-surface-03 overflow-hidden">
              {pastDeliveries.map((d) => {
                const statusCls = STATUS_CLS[d.status] ?? "bg-stone/20 text-stone border-stone/20";
                return (
                  <div key={d.id} className="flex items-center justify-between px-4 py-3.5">
                    <p className="text-parchment font-mono text-sm font-semibold">
                      #{d.order_id.slice(0, 8).toUpperCase()}
                    </p>
                    <span className={`text-[10px] font-bold px-2.5 py-1 rounded-full border ${statusCls}`}>
                      {STATUS_LABELS[d.status] ?? d.status}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </main>

      {/* ── Modal: confirmar entrega (bottom sheet) ── */}
      {confirmModal && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/70">
          <div className="bg-surface-02 rounded-t-3xl border-t border-x border-surface-03 w-full max-w-lg p-6 pb-safe-bottom">
            {/* Handle */}
            <div className="w-10 h-1 rounded-full bg-surface-03 mx-auto mb-6" />

            <div className="flex items-center justify-between mb-4">
              <h3 className="text-cream font-bold text-lg">Confirmar entrega</h3>
              <button
                onClick={() => setConfirmModal(null)}
                className="h-9 w-9 flex items-center justify-center rounded-full bg-surface-03 text-stone"
              >
                <X size={16} />
              </button>
            </div>

            <p className="text-stone text-sm mb-5">
              Digite o código de 4 dígitos que o cliente vai mostrar para você.
            </p>

            <input
              type="number"
              value={code}
              onChange={(e) => setCode(e.target.value.slice(0, 4))}
              placeholder="0000"
              maxLength={4}
              autoFocus
              inputMode="numeric"
              pattern="[0-9]*"
              className="w-full text-center rounded-2xl bg-surface-03 border border-surface-03 text-cream text-4xl font-mono font-black py-5 tracking-[0.5em] focus:outline-none focus:border-gold/60 placeholder:text-stone/40"
            />

            {confirmError && (
              <div className="mt-3 rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-300">
                {confirmError}
              </div>
            )}
            {confirmSuccess && (
              <div className="mt-3 flex items-center gap-2 text-green-400 text-sm bg-green-500/10 rounded-xl px-4 py-3">
                <CheckCircle size={16} />
                <span className="font-medium">Entrega confirmada com sucesso!</span>
              </div>
            )}

            <button
              onClick={handleConfirm}
              disabled={code.length !== 4 || confirmLoading || confirmSuccess}
              className="w-full flex items-center justify-center gap-2 rounded-2xl bg-gold py-4 text-cream text-base font-bold mt-5 active:scale-[0.98] hover:bg-gold/90 disabled:opacity-50 transition-all"
            >
              {confirmLoading && <Loader2 size={18} className="animate-spin" />}
              {confirmSuccess ? "Confirmado!" : "Confirmar"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
