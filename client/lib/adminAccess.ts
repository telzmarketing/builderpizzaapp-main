import {
  adminNavigation,
  adminNavigationGroups,
  type AdminNavigationGroup,
  type AdminNavigationItem,
} from "@/config/adminNavigation";
import type { ApiEffectivePermissions } from "@/lib/api";

function moduleAllowed(permissions: ApiEffectivePermissions, moduleKey: string): boolean {
  const modulePerms = permissions.modules[moduleKey];
  return !!modulePerms?.view || Object.values(modulePerms ?? {}).some(Boolean);
}

export function canAccessAdminItem(
  permissions: ApiEffectivePermissions | null,
  item: AdminNavigationItem,
): boolean {
  if (!permissions) return false;
  if (permissions.is_master) return true;
  if (!item.permissions?.length) return true;
  return item.permissions.some((moduleKey) => moduleAllowed(permissions, moduleKey));
}

export function filterAdminNavigation(
  permissions: ApiEffectivePermissions | null,
): AdminNavigationGroup[] {
  return adminNavigationGroups
    .map((group) => {
      const children = group.children.filter((item) => canAccessAdminItem(permissions, item));
      return { ...group, children, items: children };
    })
    .filter((group) => group.children.length > 0);
}

export function findAdminNavigationItem(pathname: string): AdminNavigationItem | null {
  const sorted = [...adminNavigation].sort((a, b) => b.path.length - a.path.length);
  return sorted.find((item) => {
    const paths = [item.path, ...(item.aliases ?? [])];
    return paths.some((path) =>
      item.exact ? pathname === path : pathname === path || pathname.startsWith(`${path}/`),
    );
  }) ?? null;
}

export function firstAllowedAdminPath(permissions: ApiEffectivePermissions | null): string {
  return filterAdminNavigation(permissions)[0]?.children[0]?.path ?? "/painel/login";
}
