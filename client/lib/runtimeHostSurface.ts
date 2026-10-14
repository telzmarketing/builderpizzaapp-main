/**
 * Runtime host resolution is authoritative over the host list embedded at
 * build time. This keeps a newly-added platform hostname working until the
 * next frontend build, without treating an arbitrary hostname as platform.
 */
export type RuntimeHostSurface =
  | {
    surface: "platform";
    hostname: string;
    tenant_id?: never;
  }
  | {
    surface: "store";
    hostname: string;
    tenant_id: string;
  };

export function isPlatformRuntimeSurface(
  surface: RuntimeHostSurface,
): surface is Extract<RuntimeHostSurface, { surface: "platform" }> {
  return surface.surface === "platform";
}

export function isStoreRuntimeSurface(
  surface: RuntimeHostSurface,
): surface is Extract<RuntimeHostSurface, { surface: "store" }> {
  return surface.surface === "store" && Boolean(surface.tenant_id);
}
