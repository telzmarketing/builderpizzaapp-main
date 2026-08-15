export const PLATFORM_PERMISSIONS_STORAGE_KEY = "platform_permissions";

export type PlatformCapability =
  | "tenants.view"
  | "platform_users.view"
  | "support.impersonate"
  | "audit.view"
  | "platform_settings.view"
  | "monitoring.view"
  | "integrations.view"
  | "jobs.view"
  | "gateway.view"
  | "errors.view"
  | "errors.manage"
  | "storage.view"
  | "backups.view";

type ReadableStorage = Pick<Storage, "getItem">;
type WritableStorage = Pick<Storage, "setItem" | "removeItem">;

export function normalizePlatformPermissions(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return [...new Set(value.filter((permission): permission is string => (
    typeof permission === "string" && permission.trim().length > 0
  )).map((permission) => permission.trim()))];
}

export function readPlatformPermissions(
  storage: ReadableStorage = localStorage,
): string[] {
  try {
    return normalizePlatformPermissions(JSON.parse(
      storage.getItem(PLATFORM_PERMISSIONS_STORAGE_KEY) ?? "[]",
    ));
  } catch {
    return [];
  }
}

export function storePlatformPermissions(
  permissions: unknown,
  storage: WritableStorage = localStorage,
): string[] {
  const normalized = normalizePlatformPermissions(permissions);
  storage.setItem(PLATFORM_PERMISSIONS_STORAGE_KEY, JSON.stringify(normalized));
  return normalized;
}

export function clearPlatformPermissions(
  storage: Pick<Storage, "removeItem"> = localStorage,
): void {
  storage.removeItem(PLATFORM_PERMISSIONS_STORAGE_KEY);
}

export function hasPlatformCapability(
  permissions: readonly string[] | null | undefined,
  capability?: string,
): boolean {
  if (!capability) return true;
  return Array.isArray(permissions) && permissions.includes(capability);
}
