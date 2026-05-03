import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, MapPin, RefreshCw, Navigation, Route } from "lucide-react";
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

// ── Helpers ───────────────────────────────────────────────────────────────────

function etaMinutes(assignedAt?: string, estimatedMinutes?: number): number | null {
  if (!assignedAt || !estimatedMinutes) return null;
  const deadline = new Date(assignedAt).getTime() + estimatedMinutes * 60_000;
  return Math.round((deadline - Date.now()) / 60_000);
}

/** Haversine distance in km between two lat/lng pairs. */
function haversineKm(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/** Build the canonical geocoding query for a delivery's address. */
function addressQuery(order: { delivery_street?: string | null; delivery_city?: string | null } | undefined): string | null {
  if (!order?.delivery_street) return null;
  const parts = [order.delivery_street, order.delivery_city, "Brasil"].filter(Boolean);
  return parts.join(", ");
}

function hasGps(person: { location_lat?: number | null; location_lng?: number | null }): person is {
  location_lat: number;
  location_lng: number;
} {
  return typeof person.location_lat === "number" && typeof person.location_lng === "number";
}

function googleMapsRouteUrl(origin: { lat: number; lng: number }, destination: { lat: number; lng: number }): string {
  const params = new URLSearchParams({
    api: "1",
    origin: `${origin.lat},${origin.lng}`,
    destination: `${destination.lat},${destination.lng}`,
    travelmode: "driving",
  });
  return `https://www.google.com/maps/dir/?${params.toString()}`;
}

// ── Sub-components ────────────────────────────────────────────────────────────

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

// ── Main component ────────────────────────────────────────────────────────────

export default function LogisticaMapa() {
  const mapRef         = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<import("leaflet").Map | null>(null);
  const markersRef     = useRef<import("leaflet").Marker[]>([]);
  const destMarkersRef = useRef<import("leaflet").Marker[]>([]);

  const [overview, setOverview] = useState<LogisticsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [leafletReady, setLeafletReady] = useState(false);

  // Geocoding cache: address string → {lat, lng} | null
  const [geocodedAddrs, setGeocodedAddrs] = useState<Record<string, { lat: number; lng: number } | null>>({});
  const geocodingInFlight = useRef<Set<string>>(new Set());

  // ── Load Leaflet ──────────────────────────────────────────────────────────

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

  // ── Poll overview ─────────────────────────────────────────────────────────

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

  // ── Geocode delivery addresses ────────────────────────────────────────────

  useEffect(() => {
    if (!overview) return;
    const toFetch = new Set<string>();
    for (const { active_deliveries } of overview.persons_on_duty) {
      for (const d of active_deliveries) {
        const q = addressQuery(d.order);
        if (q && !(q in geocodedAddrs) && !geocodingInFlight.current.has(q)) {
          toFetch.add(q);
        }
      }
    }
    for (const q of toFetch) {
      geocodingInFlight.current.add(q);
      deliveryApi
        .geocode(q)
        .then((res) => {
          setGeocodedAddrs((prev) => ({
            ...prev,
            [q]: res.lat !== null && res.lng !== null ? { lat: res.lat, lng: res.lng! } : null,
          }));
        })
        .catch(() => {
          setGeocodedAddrs((prev) => ({ ...prev, [q]: null }));
        })
        .finally(() => {
          geocodingInFlight.current.delete(q);
        });
    }
  }, [overview]); // intentionally omit geocodedAddrs to avoid loop

  // ── Initialize map ────────────────────────────────────────────────────────

  useEffect(() => {
    if (!leafletReady || !L || !mapRef.current || mapInstanceRef.current) return;
    const map = L.map(mapRef.current, { center: [-23.55, -46.63], zoom: 13 });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap",
      maxZoom: 19,
    }).addTo(map);
    mapInstanceRef.current = map;
  }, [leafletReady]);

  // ── Driver markers ────────────────────────────────────────────────────────

  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !L || !overview) return;

    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    const bounds: [number, number][] = [];

    overview.persons_on_duty.forEach(({ person, active_deliveries }) => {
      if (!hasGps(person)) return;

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
    });

    if (bounds.length >= 2) {
      map.fitBounds(bounds, { padding: [40, 40] });
    } else if (bounds.length === 1) {
      map.setView(bounds[0], 15);
    }
  }, [overview]);

  // ── Destination markers (geocoded) ────────────────────────────────────────

  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !L || !overview) return;

    destMarkersRef.current.forEach((m) => m.remove());
    destMarkersRef.current = [];

    for (const { active_deliveries } of overview.persons_on_duty) {
      for (const d of active_deliveries) {
        const q = addressQuery(d.order);
        if (!q) continue;
        const geo = geocodedAddrs[q];
        if (!geo) continue;

        const icon = L!.divIcon({
          html: `<div style="background:#f97316;border:2px solid white;border-radius:50% 50% 50% 0;transform:rotate(-45deg);width:18px;height:18px;box-shadow:0 2px 4px rgba(0,0,0,0.4)"></div>`,
          iconSize: [18, 18],
          iconAnchor: [9, 18],
          className: "",
        });

        const popup = `
          <div style="font-family:sans-serif;font-size:12px;min-width:160px">
            <b style="color:#f97316">📍 Destino</b><br>
            ${d.order?.delivery_street ?? ""}${d.order?.delivery_city ? ` — ${d.order.delivery_city}` : ""}
            <br><span style="color:#6b7280">Pedido #${d.order_id.slice(0, 8).toUpperCase()}</span>
          </div>`;

        const marker = L!.marker([geo.lat, geo.lng], { icon }).addTo(map).bindPopup(popup);
        destMarkersRef.current.push(marker);
      }
    }
  }, [overview, geocodedAddrs]);

  // ── Derived totals ────────────────────────────────────────────────────────

  const totalOnDuty = overview?.persons_on_duty.length ?? 0;
  const totalActive = overview?.total_active ?? 0;
  const geocodedCount = Object.values(geocodedAddrs).filter(Boolean).length;

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col gap-4">
      {/* Header stats */}
      <div className="flex items-center justify-between">
        <div className="flex gap-3 flex-wrap">
          <div className="rounded-xl border border-surface-03 bg-surface-02 px-4 py-2.5 text-center">
            <p className="text-stone text-[10px] uppercase tracking-widest">Em rota</p>
            <p className="text-gold text-xl font-black">{totalOnDuty}</p>
          </div>
          <div className="rounded-xl border border-surface-03 bg-surface-02 px-4 py-2.5 text-center">
            <p className="text-stone text-[10px] uppercase tracking-widest">Entregas ativas</p>
            <p className="text-gold text-xl font-black">{totalActive}</p>
          </div>
          {geocodedCount > 0 && (
            <div className="rounded-xl border border-orange-500/30 bg-orange-500/10 px-4 py-2.5 text-center">
              <p className="text-stone text-[10px] uppercase tracking-widest">Destinos no mapa</p>
              <p className="text-orange-300 text-xl font-black">{geocodedCount}</p>
            </div>
          )}
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
        {loading && !overview && (
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

        {/* Map legend */}
        {leafletReady && (
          <div className="absolute bottom-3 right-3 z-[1000] flex flex-col gap-1.5 rounded-xl bg-surface-02/90 backdrop-blur-sm border border-surface-03 px-3 py-2 text-[10px]">
            <div className="flex items-center gap-1.5">
              <div className="w-3.5 h-3.5 rounded-full bg-blue-500 border border-white flex-shrink-0" />
              <span className="text-stone">Motoboy (GPS)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-full bg-orange-500 border border-white flex-shrink-0" style={{ borderRadius: "50% 50% 50% 0", transform: "rotate(-45deg)" }} />
              <span className="text-stone">Destino (geocodificado)</span>
            </div>
          </div>
        )}
      </div>

      {/* Driver cards with route suggestion */}
      {overview && overview.persons_on_duty.length === 0 ? (
        <div className="rounded-xl border border-dashed border-surface-03 p-8 text-center">
          <Navigation size={32} className="text-stone mx-auto mb-2" />
          <p className="text-stone text-sm">Nenhum motoboy em rota no momento</p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {overview?.persons_on_duty.map(({ person, active_deliveries }) => {
            // Sort deliveries by distance from driver (if driver has GPS + destinations geocoded)
            const sorted = [...active_deliveries].map((d) => {
              const q = addressQuery(d.order);
              const geo = q ? geocodedAddrs[q] : undefined;
              const dist =
                hasGps(person) && geo
                  ? haversineKm(person.location_lat, person.location_lng, geo.lat, geo.lng)
                  : null;
              return { d, geo, dist };
            });
            const hasDistances = sorted.some((s) => s.dist !== null);
            if (hasDistances) {
              sorted.sort((a, b) => {
                if (a.dist === null) return 1;
                if (b.dist === null) return -1;
                return a.dist - b.dist;
              });
            }

            return (
              <div key={person.id} className="rounded-2xl border border-surface-03 bg-surface-02 p-4">
                {/* Driver header */}
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-2xl">{VEHICLE_EMOJI[person.vehicle_type] ?? "🏍️"}</span>
                  <div>
                    <p className="text-cream font-bold text-sm">{person.name}</p>
                    <p className="text-stone text-xs">{person.phone}</p>
                  </div>
                  {hasGps(person) ? (
                    <span className="ml-auto flex items-center gap-1 text-green-300 text-xs">
                      <MapPin size={11} /> GPS ativo
                    </span>
                  ) : (
                    <span className="ml-auto text-stone/50 text-xs">Sem GPS</span>
                  )}
                </div>

                {sorted.length === 0 ? (
                  <p className="text-stone text-xs">Sem entregas ativas</p>
                ) : (
                  <div className="space-y-2">
                    {hasDistances && (
                      <div className="flex items-center gap-1 text-[10px] text-stone/60 mb-1">
                        <Route size={10} />
                        <span>Rota sugerida por distância</span>
                      </div>
                    )}
                    {sorted.map(({ d, geo, dist }, idx) => {
                      const mapsUrl = hasGps(person) && geo
                        ? googleMapsRouteUrl(
                            { lat: person.location_lat, lng: person.location_lng },
                            { lat: geo.lat, lng: geo.lng },
                          )
                        : null;
                      return (
                      <div key={d.id} className="rounded-xl bg-surface-03/50 px-3 py-2">
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            {hasDistances && (
                              <span className="w-5 h-5 rounded-full bg-gold/20 text-gold text-[10px] font-black flex items-center justify-center flex-shrink-0">
                                {idx + 1}
                              </span>
                            )}
                            <p className="text-parchment text-xs font-bold font-mono">
                              #{d.order_id.slice(0, 8).toUpperCase()}
                            </p>
                          </div>
                          <div className="flex items-center gap-2">
                            {dist !== null && (
                              <span className="text-stone/60 text-[10px]">{dist.toFixed(1)} km</span>
                            )}
                            <EtaBadge assignedAt={d.assigned_at} estimatedMinutes={d.estimated_minutes} />
                          </div>
                        </div>
                        {d.order?.delivery_street && (
                          <p className="text-stone text-xs mt-0.5 truncate ml-7">
                            {d.order.delivery_street}
                            {d.order.delivery_complement ? `, ${d.order.delivery_complement}` : ""}
                            {d.order.delivery_city ? ` — ${d.order.delivery_city}` : ""}
                          </p>
                        )}
                        <p className="text-stone/70 text-[10px] mt-0.5 ml-7">
                          {STATUS_LABEL[d.status] ?? d.status}
                        </p>
                        {mapsUrl && (
                          <a
                            href={mapsUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-1 ml-7 inline-flex text-[10px] font-bold text-green-300 hover:text-green-200"
                          >
                            Google Maps
                          </a>
                        )}
                      </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
