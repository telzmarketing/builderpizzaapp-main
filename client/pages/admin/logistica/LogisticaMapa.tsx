import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, MapPin, RefreshCw, Navigation } from "lucide-react";
import { deliveryApi, type LogisticsOverview } from "@/lib/api";

// Leaflet types loaded dynamically to avoid SSR issues
let L: typeof import("leaflet") | null = null;

const VEHICLE_EMOJI: Record<string, string> = {
  motorcycle: "🏍️",
  bicycle: "🚲",
  car: "🚗",
  walking: "🚶",
};

const STATUS_LABEL: Record<string, string> = {
  assigned: "Designado",
  picked_up: "Coletado",
  on_the_way: "A caminho",
};

function etaMinutes(assignedAt?: string, estimatedMinutes?: number): number | null {
  if (!assignedAt || !estimatedMinutes) return null;
  const deadline = new Date(assignedAt).getTime() + estimatedMinutes * 60_000;
  const remaining = Math.round((deadline - Date.now()) / 60_000);
  return remaining;
}

function EtaBadge({ assignedAt, estimatedMinutes }: { assignedAt?: string; estimatedMinutes?: number }) {
  const [eta, setEta] = useState(() => etaMinutes(assignedAt, estimatedMinutes));
  useEffect(() => {
    const id = setInterval(() => setEta(etaMinutes(assignedAt, estimatedMinutes)), 30_000);
    return () => clearInterval(id);
  }, [assignedAt, estimatedMinutes]);

  if (eta === null) return null;
  const cls = eta < 0 ? "text-red-300" : eta <= 5 ? "text-orange-300" : "text-green-300";
  return (
    <span className={`text-xs font-bold ${cls}`}>
      {eta < 0 ? `${Math.abs(eta)}min atrasado` : `${eta}min restantes`}
    </span>
  );
}

export default function LogisticaMapa() {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<import("leaflet").Map | null>(null);
  const markersRef = useRef<import("leaflet").Marker[]>([]);

  const [overview, setOverview] = useState<LogisticsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [leafletReady, setLeafletReady] = useState(false);

  // Load Leaflet CSS + module dynamically
  useEffect(() => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
    document.head.appendChild(link);

    import("leaflet").then((mod) => {
      L = mod.default ?? mod;
      setLeafletReady(true);
    });
    return () => { document.head.removeChild(link); };
  }, []);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const data = await deliveryApi.getOverview();
      setOverview(data);
      setError("");
    } catch {
      setError("Não foi possível carregar o mapa.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = window.setInterval(() => load(true), 15_000);
    return () => window.clearInterval(id);
  }, [load]);

  // Initialize map once Leaflet + DOM are ready
  useEffect(() => {
    if (!leafletReady || !L || !mapRef.current || mapInstanceRef.current) return;

    const map = L.map(mapRef.current, {
      center: [-23.55, -46.63], // São Paulo default
      zoom: 13,
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap",
      maxZoom: 19,
    }).addTo(map);

    mapInstanceRef.current = map;
  }, [leafletReady]);

  // Update markers when data changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !L || !overview) return;

    // Remove old markers
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    const bounds: [number, number][] = [];

    overview.persons_on_duty.forEach(({ person, active_deliveries }) => {
      // Motoboy marker (blue)
      if (person.location_lat && person.location_lng) {
        const icon = L!.divIcon({
          html: `<div style="background:#3b82f6;border:2px solid white;border-radius:50%;width:32px;height:32px;display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 6px rgba(0,0,0,0.4)">${VEHICLE_EMOJI[person.vehicle_type] ?? "🏍️"}</div>`,
          iconSize: [32, 32],
          iconAnchor: [16, 16],
          className: "",
        });

        const deliveriesSummary = active_deliveries
          .map((d) => `<li>${d.order?.delivery_street ?? "Endereço pendente"} — ${STATUS_LABEL[d.status] ?? d.status}</li>`)
          .join("");

        const popup = `
          <div style="min-width:180px;font-family:sans-serif">
            <b>${person.name}</b><br>
            <span style="color:#6b7280;font-size:12px">${person.phone}</span>
            <ul style="margin:6px 0 0;padding-left:14px;font-size:12px">${deliveriesSummary || "<li>Sem entregas ativas</li>"}</ul>
          </div>`;

        const marker = L!.marker([person.location_lat, person.location_lng], { icon })
          .addTo(map)
          .bindPopup(popup);

        markersRef.current.push(marker);
        bounds.push([person.location_lat, person.location_lng]);
      }

      // Destination markers (orange pin) for each active delivery
      active_deliveries.forEach((d) => {
        if (!d.order?.delivery_street) return;
        // We can't geocode addresses without an API, so show a placeholder marker at a slight offset
        // In production this would use a geocoding API
      });
    });

    if (bounds.length >= 2) {
      map.fitBounds(bounds, { padding: [40, 40] });
    } else if (bounds.length === 1) {
      map.setView(bounds[0], 15);
    }
  }, [overview]);

  const totalOnDuty = overview?.persons_on_duty.length ?? 0;
  const totalActive = overview?.total_active ?? 0;

  return (
    <div className="flex flex-col gap-4">
      {/* Header stats */}
      <div className="flex items-center justify-between">
        <div className="flex gap-4">
          <div className="rounded-xl border border-surface-03 bg-surface-02 px-4 py-2.5 text-center">
            <p className="text-stone text-[10px] uppercase tracking-widest">Motoboys em rota</p>
            <p className="text-gold text-xl font-black">{totalOnDuty}</p>
          </div>
          <div className="rounded-xl border border-surface-03 bg-surface-02 px-4 py-2.5 text-center">
            <p className="text-stone text-[10px] uppercase tracking-widest">Entregas ativas</p>
            <p className="text-gold text-xl font-black">{totalActive}</p>
          </div>
        </div>
        <button
          onClick={() => load()}
          className="flex items-center gap-1.5 rounded-xl border border-surface-03 px-3 py-2 text-stone text-sm hover:text-cream transition-colors"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          Atualizar
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Map */}
      <div className="relative rounded-2xl overflow-hidden border border-surface-03" style={{ height: 420 }}>
        {(loading && !overview) && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-surface-02">
            <Loader2 size={36} className="animate-spin text-gold" />
          </div>
        )}
        {!leafletReady && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-surface-02">
            <p className="text-stone text-sm">Carregando mapa...</p>
          </div>
        )}
        <div ref={mapRef} style={{ width: "100%", height: "100%" }} />
      </div>

      {/* Cards list */}
      {overview && overview.persons_on_duty.length === 0 ? (
        <div className="rounded-xl border border-dashed border-surface-03 p-8 text-center">
          <Navigation size={32} className="text-stone mx-auto mb-2" />
          <p className="text-stone text-sm">Nenhum motoboy em rota no momento</p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {overview?.persons_on_duty.map(({ person, active_deliveries }) => (
            <div key={person.id} className="rounded-2xl border border-surface-03 bg-surface-02 p-4">
              <div className="flex items-center gap-3 mb-3">
                <span className="text-2xl">{VEHICLE_EMOJI[person.vehicle_type] ?? "🏍️"}</span>
                <div>
                  <p className="text-cream font-bold text-sm">{person.name}</p>
                  <p className="text-stone text-xs">{person.phone}</p>
                </div>
                {person.location_lat ? (
                  <span className="ml-auto flex items-center gap-1 text-green-300 text-xs">
                    <MapPin size={11} /> GPS ativo
                  </span>
                ) : (
                  <span className="ml-auto text-stone/50 text-xs">Sem GPS</span>
                )}
              </div>

              {active_deliveries.length === 0 ? (
                <p className="text-stone text-xs">Sem entregas ativas</p>
              ) : (
                <div className="space-y-2">
                  {active_deliveries.map((d) => (
                    <div key={d.id} className="rounded-xl bg-surface-03/50 px-3 py-2">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-parchment text-xs font-bold font-mono">
                          #{d.order_id.slice(0, 8).toUpperCase()}
                        </p>
                        <EtaBadge assignedAt={d.assigned_at} estimatedMinutes={d.estimated_minutes} />
                      </div>
                      {d.order?.delivery_street && (
                        <p className="text-stone text-xs mt-0.5 truncate">
                          {d.order.delivery_street}
                          {d.order.delivery_complement ? `, ${d.order.delivery_complement}` : ""}
                          {d.order.delivery_city ? ` — ${d.order.delivery_city}` : ""}
                        </p>
                      )}
                      <p className="text-stone/70 text-[10px] mt-0.5">
                        {STATUS_LABEL[d.status] ?? d.status}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
