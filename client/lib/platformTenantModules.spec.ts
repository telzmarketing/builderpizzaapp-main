import { describe, expect, it } from "vitest";
import {
  buildPlatformTenantModulePayload,
  platformTenantModuleDraft,
} from "./platformTenantModules";

const moduleItem = {
  id: "module-1",
  key: "finance",
  name: "Financeiro",
  module_group: "management" as const,
  active: true,
  entitlement: {
    id: "entitlement-1",
    enabled: true,
    origin: "courtesy" as const,
    starts_at: "2026-01-01T12:00:00Z",
    ends_at: "2026-12-31T12:00:00Z",
    limit_value: 50,
    additional_price: 19.9,
    config_json: '{"mode":"safe"}',
  },
};

describe("platform tenant module payload", () => {
  it("preserves every persisted entitlement field instead of replacing config with an empty object", () => {
    const draft = platformTenantModuleDraft(moduleItem);
    const [payload] = buildPlatformTenantModulePayload(
      [moduleItem],
      { [moduleItem.id]: draft },
      "Ajuste administrativo",
    );
    expect(payload.origin).toBe("courtesy");
    expect(payload.limit_value).toBe(50);
    expect(payload.additional_price).toBe(19.9);
    expect(payload.config).toEqual({ mode: "safe" });
    expect(payload.starts_at).toBeTruthy();
    expect(payload.ends_at).toBeTruthy();
  });

  it("omits untouched catalog modules that have no tenant entitlement", () => {
    const catalogOnly = { ...moduleItem, id: "module-2", entitlement: null };
    const draft = platformTenantModuleDraft(catalogOnly);
    expect(buildPlatformTenantModulePayload(
      [catalogOnly],
      { [catalogOnly.id]: draft },
      "Ajuste administrativo",
    )).toEqual([]);
  });

  it("blocks malformed configuration rather than destructively sending an empty object", () => {
    const draft = { ...platformTenantModuleDraft(moduleItem), config_text: "invalid" };
    expect(() => buildPlatformTenantModulePayload(
      [moduleItem],
      { [moduleItem.id]: draft },
      "Ajuste administrativo",
    )).toThrow();
  });

  it("never parses or sends hidden integration configuration", () => {
    const integration = {
      ...moduleItem,
      id: "module-integration",
      module_group: "integrations" as const,
      entitlement: {
        ...moduleItem.entitlement,
        config_json: "hidden-or-omitted-by-api",
      },
    };
    const draft = platformTenantModuleDraft(integration);
    const [payload] = buildPlatformTenantModulePayload(
      [integration],
      { [integration.id]: draft },
      "Ajuste administrativo",
    );

    expect(payload).not.toHaveProperty("config");
    expect(payload).toMatchObject({
      module_id: integration.id,
      enabled: true,
      origin: "courtesy",
      limit_value: 50,
      additional_price: 19.9,
    });
  });
});
