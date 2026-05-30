import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { filterAdminNavigation, findAdminNavigationGroup } from "@/lib/adminAccess";
import { preloadAdminRoute } from "@/lib/adminRoutePreload";
import type { ApiEffectivePermissions } from "@/lib/api";

const SIDEBAR_COLLAPSED_KEY = "admin:context-sidebar-collapsed";

function readPermissions(): ApiEffectivePermissions | null {
  try {
    const raw = localStorage.getItem("admin_permissions");
    return raw ? JSON.parse(raw) as ApiEffectivePermissions : null;
  } catch {
    return null;
  }
}

function itemMatchesPath(
  item: { path: string; exact?: boolean; aliases?: string[] },
  pathname: string,
) {
  return [item.path, ...(item.aliases ?? [])].some((path) =>
    item.exact ? pathname === path : pathname === path || pathname.startsWith(`${path}/`),
  );
}

function getInitialCollapsedState() {
  const stored = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
  if (stored !== null) return stored === "true";
  return window.matchMedia("(max-width: 1279px)").matches;
}

export default function ContextSidebar() {
  const { pathname } = useLocation();
  const navRef = useRef<HTMLElement>(null);
  const permissions = readPermissions();
  const navigationGroups = useMemo(() => filterAdminNavigation(permissions), [JSON.stringify(permissions)]);
  const activeGroup = findAdminNavigationGroup(pathname, navigationGroups);
  const [collapsed, setCollapsed] = useState(getInitialCollapsedState);

  useEffect(() => {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(collapsed));
  }, [collapsed]);

  useEffect(() => {
    const nav = navRef.current;
    if (!nav || !activeGroup) return;
    const saved = sessionStorage.getItem(`admin:context-sidebar-scroll:${activeGroup.label}`);
    nav.scrollTop = saved ? parseInt(saved, 10) : 0;
  }, [activeGroup?.label]);

  useEffect(() => {
    const nav = navRef.current;
    if (!nav || !activeGroup) return;
    const saveScroll = () =>
      sessionStorage.setItem(`admin:context-sidebar-scroll:${activeGroup.label}`, String(nav.scrollTop));
    nav.addEventListener("scroll", saveScroll, { passive: true });
    return () => nav.removeEventListener("scroll", saveScroll);
  }, [activeGroup?.label]);

  if (!activeGroup) return null;

  return (
    <aside
      className={`context-sidebar admin-sidebar hidden h-full flex-shrink-0 flex-col border-r border-surface-03 bg-surface-02 transition-[width] duration-300 ease-out md:flex ${
        collapsed ? "w-[68px]" : "w-60"
      }`}
    >
      <div className={`flex h-[58px] flex-shrink-0 items-center border-b border-surface-03 ${collapsed ? "justify-center px-2" : "justify-between px-4"}`}>
        {!collapsed && (
          <div className="min-w-0">
            <p className="truncate text-sm font-black text-cream">{activeGroup.label}</p>
          </div>
        )}
        <button
          type="button"
          onClick={() => setCollapsed((value) => !value)}
          className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg border border-surface-03 text-stone transition-colors hover:bg-surface-03 hover:text-cream"
          aria-label={collapsed ? "Expandir menu contextual" : "Recolher menu contextual"}
          title={collapsed ? "Expandir menu" : "Recolher menu"}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      <nav ref={navRef} className={`flex-1 overflow-y-auto py-3 ${collapsed ? "px-2" : "px-3"}`} aria-label={`Navegacao contextual de ${activeGroup.label}`}>
        <div className="space-y-1">
          {activeGroup.children.map((item) => {
            const Icon = item.icon;
            const active = itemMatchesPath(item, pathname);
            return (
              <Link
                key={item.path}
                to={item.path}
                onMouseEnter={() => preloadAdminRoute(item.path)}
                onFocus={() => preloadAdminRoute(item.path)}
                onPointerDown={() => preloadAdminRoute(item.path)}
                title={collapsed ? item.label : undefined}
                className={`flex items-center rounded-xl text-sm font-semibold transition-all ${
                  collapsed ? "h-11 justify-center px-2" : "gap-3 px-3 py-2.5"
                } ${
                  active
                    ? "bg-gold text-black shadow-sm shadow-gold/20"
                    : "text-stone hover:bg-surface-03 hover:text-cream"
                }`}
              >
                <Icon size={17} className="flex-shrink-0" />
                {!collapsed && <span className="truncate">{item.label}</span>}
                {!collapsed && active && <span className="ml-auto h-1.5 w-1.5 flex-shrink-0 rounded-full bg-black/60" />}
              </Link>
            );
          })}
        </div>
      </nav>
    </aside>
  );
}
