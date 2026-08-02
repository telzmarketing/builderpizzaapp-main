import { describe, expect, it } from "vitest";
import {
  normalizePlatformCatalogKey,
  parseOptionalPlatformNumber,
  parsePlatformModuleDefaultConfig,
  parsePlatformModuleDependencies,
  platformModuleDefaultConfigPayload,
  platformModuleToDraft,
  togglePlatformSelection,
} from "./platformCatalog";

describe("platform catalog helpers", () => {
  it("normalizes module keys and parses unique dependency keys", () => {
    expect(normalizePlatformCatalogKey("  CRM / Pipeline  ")).toBe("crmpipeline");
    expect(parsePlatformModuleDependencies('["orders", "crm.pipeline", "orders", 42]')).toEqual([
      "orders",
      "crm.pipeline",
    ]);
    expect(parsePlatformModuleDependencies("invalid-json")).toEqual([]);
  });

  it("accepts only JSON objects as module default configuration", () => {
    expect(parsePlatformModuleDefaultConfig('{"limit": 3}')).toEqual({ limit: 3 });
    expect(() => parsePlatformModuleDefaultConfig("[]")).toThrow(/objeto JSON/);
    expect(() => parsePlatformModuleDefaultConfig("invalid-json")).toThrow();
  });

  it("builds an editable draft without trusting malformed persisted JSON", () => {
    const draft = platformModuleToDraft({
      id: "module-1",
      key: "orders",
      name: "Pedidos",
      module_group: "operation",
      active: true,
      dependencies_json: "invalid",
      default_config_json: "[]",
    });
    expect(draft.dependencies).toEqual([]);
    expect(draft.default_config_text).toBe("{}");
  });

  it("does not expose or round-trip hidden integration defaults", () => {
    const draft = platformModuleToDraft({
      id: "module-integration",
      key: "payments.gateway",
      name: "Gateway",
      module_group: "integrations",
      active: true,
      default_config_json: null,
      config_configured: true,
    });

    expect(draft.default_config_text).toBe("");
    expect(platformModuleDefaultConfigPayload(draft, "integrations")).not.toHaveProperty("default_config");
  });

  it("keeps plan numeric limits nullable and module selections unique", () => {
    expect(parseOptionalPlatformNumber("")).toBeNull();
    expect(parseOptionalPlatformNumber("25")).toBe(25);
    expect(parseOptionalPlatformNumber("invalid")).toBeNull();
    expect(togglePlatformSelection(["orders"], "orders", true)).toEqual(["orders"]);
    expect(togglePlatformSelection(["orders"], "crm", true)).toEqual(["orders", "crm"]);
    expect(togglePlatformSelection(["orders", "crm"], "orders", false)).toEqual(["crm"]);
  });
});
