import { describe, expect, it } from "vitest";
import {
  captureResultState,
  defaultProductionCaptureRule,
  normalizeProductionCaptureState,
  PRODUCTION_CAPTURE_CHECKLIST,
  readProductionCaptureRules,
  writeProductionCaptureRules,
} from "./productionVisionCapture";

describe("production vision capture rules", () => {
  it("keeps the three operational checklist stages", () => {
    expect(PRODUCTION_CAPTURE_CHECKLIST.map((step) => step.label)).toEqual([
      "Foto início",
      "Fotografia pizza pronta",
      "Caixa fechada",
    ]);
  });

  it("does not turn pending or unsupported transport into OK", () => {
    expect(normalizeProductionCaptureState("pending")).toBe("pending");
    expect(normalizeProductionCaptureState("unsupported")).toBe("unsupported");
    expect(captureResultState({ status: "pending" })).toBe("pending");
    expect(captureResultState({ status: "confirmed", original_storage_key: "vision/a.jpg" })).toBe("ok");
  });

  it("round-trips per-station rules with safe delay bounds", () => {
    const values = new Map<string, string>();
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
    };
    const rules = { expedicao: { ...defaultProductionCaptureRule("expedicao"), automatic: false, delaySeconds: 20 } };
    writeProductionCaptureRules(rules, storage);
    expect(readProductionCaptureRules(storage)).toEqual(rules);
    expect(readProductionCaptureRules({ getItem: () => JSON.stringify({ pizza: { delaySeconds: 0 } }) }).pizza.delaySeconds).toBe(10);
  });
});
