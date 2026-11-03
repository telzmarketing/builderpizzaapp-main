export type PizzaWorkstationId = "pizza-1" | "pizza-2";

export type KdsStationOption = {
  id: string;
  label: string;
  apiStationId: string;
  kind: "pizza" | "canonical";
  camera_count?: number | null;
  active_sessions?: number | null;
  status?: string | null;
};

export const KDS_PIZZA_STATION_STORAGE_KEY = "kds:pizzaiolo-station";

/** The API keeps one canonical pizza station; these are frontend device lanes. */
export const PIZZA_STATIONS: ReadonlyArray<KdsStationOption> = [
  { id: "pizza-1", label: "Pizza 1", apiStationId: "pizza", kind: "pizza" },
  { id: "pizza-2", label: "Pizza 2", apiStationId: "pizza", kind: "pizza" },
];

export function readPizzaStation(storage?: Storage | null): PizzaWorkstationId {
  return storage?.getItem(KDS_PIZZA_STATION_STORAGE_KEY) === "pizza-2"
    ? "pizza-2"
    : "pizza-1";
}

export function persistPizzaStation(station: PizzaWorkstationId, storage?: Storage | null) {
  storage?.setItem(KDS_PIZZA_STATION_STORAGE_KEY, station);
}

export function pizzaStationLabel(station: string | null | undefined) {
  return PIZZA_STATIONS.find((option) => option.id === station)?.label ?? "Pizza 1";
}

export function productionVisionStationOptions(
  stations: ReadonlyArray<{ id: string; name: string }>,
): KdsStationOption[] {
  const canonical = stations
    .filter((station) => !PIZZA_STATIONS.some((option) => option.id === station.id))
    .map((station) => ({
      id: station.id,
      label: station.name || station.id,
      apiStationId: station.id,
      kind: "canonical" as const,
      camera_count: (station as { camera_count?: number | null }).camera_count,
      active_sessions: (station as { active_sessions?: number | null }).active_sessions,
      status: (station as { status?: string | null }).status,
    }));
  return [...PIZZA_STATIONS, ...canonical];
}
