import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, ChevronDown, LogOut, User } from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import { useApp } from "@/context/AppContext";
import { adminNavigationGroups } from "@/config/adminNavigation";

function getInitials(name: string): string {
  return name
    .split(" ")
    .slice(0, 2)
    .map((n) => n[0]?.toUpperCase() ?? "")
    .join("");
}

export default function AppSidebar() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { siteContent } = useApp();
  const navRef = useRef<HTMLElement>(null);

  const adminUserRaw = localStorage.getItem("admin_user");
  const adminUser = adminUserRaw ? JSON.parse(adminUserRaw) : null;
  const adminName: string = adminUser?.name ?? "Administrador";
  const adminEmail: string = adminUser?.email ?? "";
  const initials = getInitials(adminName);
  const { brand } = siteContent;

  const handleLogout = () => {
    localStorage.removeItem("admin_token");
    localStorage.removeItem("admin_user");
    navigate("/painel/login");
  };

  const isActive = (path: string, exact?: boolean) =>
    exact ? pathname === path : pathname === path || pathname.startsWith(`${path}/`);

  const isItemActive = (item: { path: string; exact?: boolean; aliases?: string[] }) =>
    isActive(item.path, item.exact) ||
    (item.aliases ?? []).some((alias) => isActive(alias, item.exact));

  const activeGroups = useMemo(
    () =>
      adminNavigationGroups
        .filter((group) => group.children.some((item) => isItemActive(item)))
        .map((group) => group.label),
    [pathname],
  );

  const [openGroups, setOpenGroups] = useState<Set<string>>(
    () => new Set(adminNavigationGroups.map((group) => group.label)),
  );

  useEffect(() => {
    if (!activeGroups.length) return;
    setOpenGroups((current) => {
      const next = new Set(current);
      activeGroups.forEach((group) => next.add(group));
      return next;
    });
  }, [activeGroups]);

  const toggleGroup = (label: string) => {
    setOpenGroups((current) => {
      const next = new Set(current);
      if (next.has(label)) next.delete(label);
      else next.add(label);
      return next;
    });
  };

  useEffect(() => {
    const nav = navRef.current;
    if (!nav) return;
    const saved = sessionStorage.getItem("admin-sidebar-scroll");
    if (saved) nav.scrollTop = parseInt(saved, 10);
  }, []);

  useEffect(() => {
    const nav = navRef.current;
    if (!nav) return;
    const onScroll = () =>
      sessionStorage.setItem("admin-sidebar-scroll", String(nav.scrollTop));
    nav.addEventListener("scroll", onScroll, { passive: true });
    return () => nav.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <aside className="app-sidebar admin-sidebar w-full md:w-64 bg-surface-02 border-b md:border-b-0 md:border-r border-surface-03 flex flex-col flex-shrink-0 h-auto md:h-full max-h-[52vh] md:max-h-none">
      <div className="px-4 md:px-5 pt-5 pb-4 border-b border-surface-03 flex-shrink-0">
        <div className="flex min-h-[66px] flex-col items-center justify-center text-center">
          {brand.logo && (brand.logo.startsWith("http") || brand.logo.startsWith("data:")) ? (
            <img
              src={brand.logo}
              alt="logo"
              className="mb-1 h-10 max-w-[8.75rem] object-contain"
            />
          ) : brand.logo ? (
            <span className="mb-1 text-xl leading-none">{brand.logo}</span>
          ) : (
            <MoschettieriLogo className="text-gold text-[1.15rem] leading-tight" />
          )}
          <div className="mt-1 w-full">
            <p className="text-stone text-[10px] leading-none">Painel administrativo</p>
          </div>
        </div>
      </div>

      <div className="hidden md:block px-4 py-3 border-b border-surface-03 flex-shrink-0">
        <div className="flex items-center gap-3 bg-surface-01 rounded-xl px-3 py-2.5 border border-surface-03/60">
          <div className="relative flex-shrink-0">
            <div className="w-9 h-9 rounded-full bg-gold/20 border border-gold/40 flex items-center justify-center">
              {initials ? (
                <span className="text-gold text-xs font-bold">{initials}</span>
              ) : (
                <User size={16} className="text-gold" />
              )}
            </div>
            <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-emerald-500 border-2 border-surface-02 rounded-full" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <p className="text-cream text-xs font-semibold truncate leading-none">{adminName}</p>
              <span className="flex-shrink-0 text-[9px] font-bold text-gold bg-gold/15 border border-gold/25 rounded px-1 py-0.5 leading-none">
                Admin
              </span>
            </div>
            {adminEmail && (
              <p className="text-stone text-[10px] truncate mt-1 leading-none">{adminEmail}</p>
            )}
          </div>
        </div>
      </div>

      <nav ref={navRef} className="flex-1 overflow-y-auto py-3 px-3">
        {adminNavigationGroups.map((group, groupIndex) => {
          const groupActive = activeGroups.includes(group.label);
          const groupOpen = openGroups.has(group.label);
          return (
          <div key={group.label} className={groupIndex > 0 ? "mt-4" : ""}>
            <button
              type="button"
              onClick={() => toggleGroup(group.label)}
              className={`mb-1 flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-[10px] font-bold uppercase tracking-[0.15em] transition-colors ${
                groupActive ? "text-gold bg-gold/10" : "text-stone/60 hover:bg-surface-03/60 hover:text-stone"
              }`}
            >
              <span>{group.label}</span>
              <ChevronDown
                size={13}
                className={`transition-transform ${groupOpen ? "rotate-180" : ""}`}
              />
            </button>
            {groupOpen && (
              <div className="space-y-0.5">
                {group.children.map((item) => {
                const { path, icon: Icon, label } = item;
                const active = isItemActive(item);
                return (
                  <Link
                    key={path}
                    to={path}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                      active
                        ? "bg-gold text-cream shadow-sm shadow-gold/20"
                        : "text-stone hover:bg-surface-03 hover:text-parchment"
                    }`}
                  >
                    <Icon
                      size={16}
                      className={`flex-shrink-0 ${active ? "text-cream" : "text-stone/70"}`}
                    />
                    <span className="truncate">{label}</span>
                    {active && (
                      <span className="ml-auto w-1.5 h-1.5 rounded-full bg-cream/70 flex-shrink-0" />
                    )}
                  </Link>
                );
                })}
              </div>
            )}
          </div>
          );
        })}
      </nav>

      <div className="hidden md:block px-3 py-3 border-t border-surface-03 space-y-0.5 flex-shrink-0">
        <Link
          to="/"
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-stone hover:bg-surface-03 hover:text-parchment transition-colors"
        >
          <ArrowLeft size={16} className="flex-shrink-0 text-stone/70" />
          <span>Voltar ao App</span>
        </Link>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-red-400/80 hover:bg-red-500/10 hover:text-red-400 transition-colors"
        >
          <LogOut size={16} className="flex-shrink-0" />
          <span>Sair</span>
        </button>
      </div>
    </aside>
  );
}
