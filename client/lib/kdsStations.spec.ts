import { describe, expect, it } from "vitest";
import {
  PIZZA_STATIONS,
  persistPizzaStation,
  productionVisionStationOptions,
  readPizzaStation,
} from "./kdsStations";

describe("KDS pizza workstation choices", () => {
  it("keeps two fixed pizza lanes mapped to the canonical pizza API station", () => {
    expect(PIZZA_STATIONS.map((station) => station.id)).toEqual(["pizza-1", "pizza-2"]);
    expect(PIZZA_STATIONS.every((station) => station.apiStationId === "pizza")).toBe(true);
  });

  it("persists only the supported Pizza 1/Pizza 2 selection", () => {
    const values = new Map<string, string>();
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
    } as unknown as Storage;
    expect(readPizzaStation(storage)).toBe("pizza-1");
    persistPizzaStation("pizza-2", storage);
    expect(readPizzaStation(storage)).toBe("pizza-2");
    values.set("kds:pizzaiolo-station", "invalid");
    expect(readPizzaStation(storage)).toBe("pizza-1");
  });

  it("keeps API-provided non-pizza stations for camera configuration", () => {
    expect(productionVisionStationOptions([
      { id: "esfiha", name: "Esfiha" },
      { id: "pizza-1", name: "Pizza 1" },
    ]).map((station) => station.label)).toEqual(["Esfiha", "Pizza 1"]);
  });
});
