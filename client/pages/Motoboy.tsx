import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, LogOut, Package, CheckCircle, Clock, Bike, Navigation, NavigationOff, MapPin } from "lucide-react";
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
    <div className={`flex items-center gap-1.5 text-xs font-medium ${eta.urgent ? "text-orange-300" : "text-green-300"}`}>
      <Clock size={11} />
      {eta.text}
    </div>
  );
}

const VEHICLE_EMOJI: Record<string, string> = {
  motorcycle: "🏍️",
  bicycle:    "🚲",
  car:        "🚗",
  walking:    "🚶",
};

const STATUS_LABELS: Record<string, string> = {
  assigned:           "Designado",
  picked_up:          "Coletado",
  on_the_way:         "A caminho",
  delivered:          "Entregue",
  completed:          "Finalizado",
  pending_assignment: "Aguardando",
};

const STATUS_CLS: Record<string, string> = {
  assigned:   "bg-blue-500/15 text-blue-300",
  picked_up:  "bg-gold/15 text-gold",
  on_the_way: "bg-violet-500/15 text-violet-300",
  delivered:  "bg-green-500/15 text-green-300",
  completed:  "bg-green-500/15 text-green-300",
};

const DRIVER_STATUS_CLS: Record<string, string> = {
  available: "text-green-300",
  busy:      "text-gold",
  offline:   "text-stone",
};

const DRIVER_STATUS_LABELS: Record<string, string> = {
  available: "Disponível",
  busy:      "Em rota",
  offline:   "Offline",
};

const ACTIVE_STATUSES = new Set(["assigned", "picked_up", "on_the_way"]);

export default function Motoboy() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("driver_token"));
  const [driver, setDriver] = useState<DeliveryPerson | null>(null);
  const [deliveries, setDeliveries] = useState<DeliveryRecord[]>([]);
  const [loadingDriver, setLoadingDriver] = useState(false);
  const [loadingDeliveries, setLoadingDeliveries] = useState(false);

  // Geolocation
  const [gpsActive, setGpsActive] = useState(false);
  const [gpsError, setGpsError] = useState("");
  const gpsWatchRef = useRef<number | null>(null);
  const gpsIntervalRef = useRef<number | null>(null);

  // Login state
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState("");

  // Confirm modal
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
    } catch {
      /* ignore */
    } finally {
      setLoadingDeliveries(false);
    }
  }, [token]);

  useEffect(() => {
    if (token) {
      loadDriver();
      loadDeliveries();
    }
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

  // ── Geolocation ───────────────────────────────────────────────────────────

  const sendLocation = useCallback((lat: number, lng: number) => {
    deliveryApi.driverUpdateLocation(lat, lng).catch(() => {});
  }, []);

  const startGps = useCallback(() => {
    if (!navigator.geolocation) {
      setGpsError("Geolocalização não suportada neste dispositivo.");
      return;
    }
    setGpsError("");

    // Watch position continuously
    gpsWatchRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        sendLocation(pos.coords.latitude, pos.coords.longitude);
        setGpsActive(true);
        setGpsError("");
      },
      (err) => {
        setGpsError(`GPS: ${err.message}`);
        setGpsActive(false);
      },
      { enableHighAccuracy: true, maximumAge: 10_000 },
    );

    // Also send every 30s as fallback for browsers that throttle watchPosition
    gpsIntervalRef.current = window.setInterval(() => {
      navigator.geolocation.getCurrentPosition(
        (pos) => sendLocation(pos.coords.latitude, pos.coords.longitude),
        () => {},
      );
    }, 30_000);
  }, [sendLocation]);

  const stopGps = useCallback(() => {
    if (gpsWatchRef.current !== null) {
      navigator.geolocation.clearWatch(gpsWatchRef.current);
      gpsWatchRef.current = null;
    }
    if (gpsIntervalRef.current !== null) {
      window.clearInterval(gpsIntervalRef.current);
      gpsIntervalRef.current = null;
    }
    setGpsActive(false);
  }, []);

  // Clean up GPS on unmount / logout
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

  // ── Login screen ───────────────────────────────────────────────────────────

  if (!token) {
    return (
      <div className="min-h-screen bg-surface-00 flex flex-col items-center justify-center px-4">
        <div className="w-full max-w-sm">
          <div className="text-center mb-8">
            <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-gold/15 mb-4">
              <Bike size={32} className="text-gold" />
            </div>
            <h1 className="text-cream text-2xl font-black">App do Motoboy</h1>
            <p className="text-stone text-sm mt-1">Acesso exclusivo para entregadores</p>
          </div>

          <form onSubmit={handleLogin} className="bg-surface-02 rounded-2xl border border-surface-03 p-6 space-y-4">
            <label className="flex flex-col gap-1.5">
              <span className="text-stone text-xs font-medium">Email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="seu@email.com"
                className="rounded-xl bg-surface-03 border border-surface-03 text-cream px-4 py-3 text-sm focus:outline-none focus:border-gold/50 placeholder:text-stone/50"
              />
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-stone text-xs font-medium">Senha</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="••••••••"
                className="rounded-xl bg-surface-03 border border-surface-03 text-cream px-4 py-3 text-sm focus:outline-none focus:border-gold/50"
              />
            </label>

            {loginError && (
              <p className="text-sm text-red-300">{loginError}</p>
            )}

            <button
              type="submit"
              disabled={loginLoading}
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-gold py-3 text-cream font-bold hover:bg-gold/90 disabled:opacity-50 transition-colors"
            >
              {loginLoading && <Loader2 size={16} className="animate-spin" />}
              Entrar
            </button>
          </form>
        </div>
      </div>
    );
  }

  // ── Loading ────────────────────────────────────────────────────────────────

  if (loadingDriver) {
    return (
      <div className="min-h-screen bg-surface-00 flex items-center justify-center">
        <Loader2 size={40} className="animate-spin text-gold" />
      </div>
    );
  }

  // ── Driver app ─────────────────────────────────────────────────────────────

  const activeDeliveries = deliveries.filter((d) => ACTIVE_STATUSES.has(d.status));
  const pastDeliveries   = deliveries.filter((d) => !ACTIVE_STATUSES.has(d.status));

  return (
    <div className="min-h-screen bg-surface-00 pb-8">
      {/* Header */}
      <header className="bg-surface-02 border-b border-surface-03 px-4 py-4">
        <div className="max-w-lg mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-gold/20 flex items-center justify-center">
              <span className="text-gold font-bold text-sm">
                {driver?.name.split(" ").map((n) => n[0]).slice(0, 2).join("") ?? "—"}
              </span>
            </div>
            <div>
              <p className="text-cream font-bold text-sm">{driver?.name}</p>
              <p className={`text-xs font-medium ${DRIVER_STATUS_CLS[driver?.status ?? "offline"]}`}>
                {VEHICLE_EMOJI[driver?.vehicle_type ?? "motorcycle"]}{" "}
                {DRIVER_STATUS_LABELS[driver?.status ?? "offline"]}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={gpsActive ? stopGps : startGps}
              className={`flex items-center gap-1.5 rounded-xl border px-3 py-2 text-sm font-medium transition-colors ${
                gpsActive
                  ? "border-green-500/40 bg-green-500/10 text-green-300 hover:bg-green-500/20"
                  : "border-surface-03 bg-surface-03/40 text-stone hover:text-cream"
              }`}
              title={gpsActive ? "Parar compartilhamento de localização" : "Compartilhar localização"}
            >
              {gpsActive ? <Navigation size={14} /> : <NavigationOff size={14} />}
              <span className="hidden sm:inline">{gpsActive ? "GPS ativo" : "GPS"}</span>
            </button>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 rounded-xl border border-surface-03 px-3 py-2 text-stone text-sm hover:text-cream transition-colors"
            >
              <LogOut size={14} />
              Sair
            </button>
          </div>
        </div>
      </header>

      {/* Stats */}
      <div className="max-w-lg mx-auto px-4 mt-4 grid grid-cols-2 gap-3">
        <div className="rounded-2xl border border-surface-03 bg-surface-02 p-4 text-center">
          <p className="text-stone text-xs uppercase tracking-widest">Total entregas</p>
          <p className="text-gold text-2xl font-black mt-1">{driver?.total_deliveries ?? 0}</p>
        </div>
        <div className="rounded-2xl border border-surface-03 bg-surface-02 p-4 text-center">
          <p className="text-stone text-xs uppercase tracking-widest">Avaliação</p>
          <p className="text-gold text-2xl font-black mt-1">
            ⭐ {(driver?.average_rating ?? 5).toFixed(1)}
          </p>
        </div>
      </div>

      {/* GPS error */}
      {gpsError && (
        <div className="max-w-lg mx-auto px-4 mt-3">
          <div className="rounded-xl border border-orange-500/30 bg-orange-500/10 px-4 py-2.5 text-sm text-orange-300">
            {gpsError}
          </div>
        </div>
      )}

      {/* Active deliveries */}
      <div className="max-w-lg mx-auto px-4 mt-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-cream font-bold">Em andamento</h2>
          <button
            onClick={loadDeliveries}
            disabled={loadingDeliveries}
            className="text-stone text-xs hover:text-cream transition-colors"
          >
            {loadingDeliveries ? <Loader2 size={13} className="animate-spin" /> : "Atualizar"}
          </button>
        </div>

        {activeDeliveries.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-surface-03 p-8 text-center">
            <Package size={32} className="text-stone mx-auto mb-2" />
            <p className="text-stone text-sm">Nenhuma entrega ativa</p>
          </div>
        ) : (
          <div className="space-y-4">
            {activeDeliveries.map((d) => {
              const statusCls = STATUS_CLS[d.status] ?? "bg-stone/20 text-stone";
              return (
                <div key={d.id} className="rounded-2xl border border-surface-03 bg-surface-02 p-5">
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <p className="text-cream font-mono font-bold">
                      Pedido #{d.order_id.slice(0, 8).toUpperCase()}
                    </p>
                    <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${statusCls}`}>
                      {STATUS_LABELS[d.status] ?? d.status}
                    </span>
                  </div>

                  {/* Endereço de entrega */}
                  {d.order && (
                    <div className="rounded-xl bg-surface-03/60 px-3 py-2.5 mb-3">
                      {d.order.delivery_name && (
                        <p className="text-parchment text-sm font-medium">{d.order.delivery_name}</p>
                      )}
                      {d.order.delivery_street && (
                        <div className="flex items-start gap-1.5 mt-1">
                          <MapPin size={12} className="text-gold flex-shrink-0 mt-0.5" />
                          <p className="text-stone text-xs">
                            {d.order.delivery_street}
                            {d.order.delivery_complement ? `, ${d.order.delivery_complement}` : ""}
                            {d.order.delivery_city ? ` — ${d.order.delivery_city}` : ""}
                          </p>
                        </div>
                      )}
                    </div>
                  )}

                  <div className="flex items-center gap-4 mb-3">
                    <EtaLine assignedAt={d.assigned_at} estimatedMinutes={d.estimated_minutes} />
                    <span className="text-stone text-xs">
                      <Clock size={11} className="inline mr-1" />
                      {d.estimated_minutes} min estimado
                    </span>
                  </div>

                  {/* Confirmation code — shown prominently */}
                  {d.confirmation_code && !d.confirmed_by_code_at && (
                    <div className="rounded-xl bg-gold/10 border border-gold/30 p-4 mb-4">
                      <p className="text-gold text-[10px] uppercase tracking-widest text-center mb-1">
                        Código de confirmação
                      </p>
                      <p className="text-gold font-mono text-3xl font-black text-center tracking-[0.4em]">
                        {d.confirmation_code}
                      </p>
                      <p className="text-stone text-xs text-center mt-2">
                        Mostre este código ao cliente para confirmar a entrega
                      </p>
                    </div>
                  )}

                  {d.confirmed_by_code_at && (
                    <div className="flex items-center gap-2 text-green-300 text-sm mb-4">
                      <CheckCircle size={15} />
                      <span>Confirmado pelo cliente</span>
                    </div>
                  )}

                  <button
                    onClick={() => {
                      setCode("");
                      setConfirmError("");
                      setConfirmSuccess(false);
                      setConfirmModal({ deliveryId: d.id });
                    }}
                    disabled={!!d.confirmed_by_code_at}
                    className="w-full rounded-xl bg-gold py-3 text-cream text-sm font-bold hover:bg-gold/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    {d.confirmed_by_code_at ? "Entrega confirmada" : "Confirmar entrega com código"}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Past deliveries */}
      {pastDeliveries.length > 0 && (
        <div className="max-w-lg mx-auto px-4 mt-6">
          <h2 className="text-cream font-bold mb-3">Histórico recente</h2>
          <div className="space-y-2">
            {pastDeliveries.map((d) => {
              const statusCls = STATUS_CLS[d.status] ?? "bg-stone/20 text-stone";
              return (
                <div key={d.id} className="rounded-xl border border-surface-03 bg-surface-02 px-4 py-3 flex items-center justify-between">
                  <p className="text-parchment font-mono text-sm">
                    #{d.order_id.slice(0, 8).toUpperCase()}
                  </p>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${statusCls}`}>
                    {STATUS_LABELS[d.status] ?? d.status}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Confirm modal */}
      {confirmModal && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 p-4">
          <div className="bg-surface-02 rounded-2xl border border-surface-03 p-6 w-full max-w-sm">
            <h3 className="text-cream font-bold text-lg mb-2">Confirmar entrega</h3>
            <p className="text-stone text-sm mb-5">
              Digite o código de 4 dígitos fornecido pelo cliente para confirmar a entrega.
            </p>

            <input
              type="number"
              value={code}
              onChange={(e) => setCode(e.target.value.slice(0, 4))}
              placeholder="0000"
              maxLength={4}
              className="w-full text-center rounded-xl bg-surface-03 border border-surface-03 text-cream text-3xl font-mono font-black py-4 tracking-[0.4em] focus:outline-none focus:border-gold/50 placeholder:text-stone/40"
            />

            {confirmError && <p className="mt-3 text-sm text-red-300">{confirmError}</p>}
            {confirmSuccess && (
              <div className="mt-3 flex items-center gap-2 text-green-300 text-sm">
                <CheckCircle size={15} />
                <span>Entrega confirmada com sucesso!</span>
              </div>
            )}

            <div className="mt-5 flex gap-3">
              <button
                onClick={() => setConfirmModal(null)}
                className="flex-1 rounded-xl border border-surface-03 py-3 text-stone text-sm hover:text-cream transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleConfirm}
                disabled={code.length !== 4 || confirmLoading || confirmSuccess}
                className="flex-1 flex items-center justify-center gap-2 rounded-xl bg-gold py-3 text-cream text-sm font-bold hover:bg-gold/90 disabled:opacity-50 transition-colors"
              >
                {confirmLoading && <Loader2 size={14} className="animate-spin" />}
                Confirmar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
