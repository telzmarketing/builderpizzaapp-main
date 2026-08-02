import type { ApiPlatformModule } from "@/lib/api";

export const PLATFORM_MODULE_GROUPS = [
  "operation",
  "delivery",
  "management",
  "marketing",
  "crm",
  "integrations",
] as const;

export type PlatformModuleGroup = typeof PLATFORM_MODULE_GROUPS[number];

export interface PlatformModuleDraft {
  key: string;
  name: string;
  description: string;
  module_group: PlatformModuleGroup;
  active: boolean;
  display_order: number;
  dependencies: string[];
  default_config_text: string;
}

export const EMPTY_PLATFORM_MODULE_DRAFT: PlatformModuleDraft = {
  key: "",
  name: "",
  description: "",
  module_group: "operation",
  active: true,
  display_order: 0,
  dependencies: [],
  default_config_text: "{}",
};

export function normalizePlatformCatalogKey(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9_.-]/g, "");
}

export function parsePlatformModuleDependencies(value?: string | null): string[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    if (!Array.isArray(parsed)) return [];
    return Array.from(new Set(
      parsed
        .filter((item): item is string => typeof item === "string")
        .map(normalizePlatformCatalogKey)
        .filter(Boolean),
    ));
  } catch {
    return [];
  }
}

export function parsePlatformModuleDefaultConfig(value: string): Record<string, unknown> {
  const parsed: unknown = JSON.parse(value || "{}");
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("A configuracao padrao precisa ser um objeto JSON.");
  }
  return parsed as Record<string, unknown>;
}

export function platformModuleToDraft(module: ApiPlatformModule): PlatformModuleDraft {
  if (module.module_group === "integrations") {
    return {
      key: module.key,
      name: module.name,
      description: module.description ?? "",
      module_group: module.module_group,
      active: module.active,
      display_order: module.display_order ?? 0,
      dependencies: parsePlatformModuleDependencies(module.dependencies_json),
      default_config_text: "",
    };
  }
  let defaultConfig: Record<string, unknown> = {};
  try {
    defaultConfig = parsePlatformModuleDefaultConfig(module.default_config_json ?? "{}");
  } catch {
    defaultConfig = {};
  }
  return {
    key: module.key,
    name: module.name,
    description: module.description ?? "",
    module_group: module.module_group,
    active: module.active,
    display_order: module.display_order ?? 0,
    dependencies: parsePlatformModuleDependencies(module.dependencies_json),
    default_config_text: JSON.stringify(defaultConfig, null, 2),
  };
}

export function platformModuleDefaultConfigPayload(
  draft: PlatformModuleDraft,
  sourceGroup?: PlatformModuleGroup,
): { default_config?: Record<string, unknown> } {
  if (draft.module_group === "integrations" || sourceGroup === "integrations") return {};
  return { default_config: parsePlatformModuleDefaultConfig(draft.default_config_text) };
}

export function parseOptionalPlatformNumber(value: string): number | null {
  if (value.trim() === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function togglePlatformSelection(
  values: string[],
  value: string,
  selected: boolean,
): string[] {
  if (selected) return values.includes(value) ? values : [...values, value];
  return values.filter((item) => item !== value);
}
