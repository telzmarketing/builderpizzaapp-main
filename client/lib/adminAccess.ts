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

function itemMatchesPath(item: AdminNavigationItem, pathname: string, path: string): boolean {
  return item.exact ? pathname === path : pathname === path || pathname.startsWith(`${path}/`);
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
  return adminNavigation
    .flatMap((item) => [item.path, ...(item.aliases ?? [])].map((path) => ({ item, path })))
    .filter(({ item, path }) => itemMatchesPath(item, pathname, path))
    .sort((a, b) => b.path.length - a.path.length)[0]?.item ?? null;
}

export function findAdminNavigationGroup(
  pathname: string,
  groups: AdminNavigationGroup[] = adminNavigationGroups,
): AdminNavigationGroup | null {
  return groups
    .flatMap((group) =>
      group.children.flatMap((item) =>
        [item.path, ...(item.aliases ?? [])].map((path) => ({ group, item, path })),
      ),
    )
    .filter(({ item, path }) => itemMatchesPath(item, pathname, path))
    .sort((a, b) => b.path.length - a.path.length)[0]?.group ?? groups[0] ?? null;
}

export function firstAllowedAdminPath(permissions: ApiEffectivePermissions | null): string {
  return filterAdminNavigation(permissions)[0]?.children[0]?.path ?? "/painel/login";
}
