import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, ChevronDown, LogOut, Menu, Search, User, X } from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import AdminTopActions from "@/components/admin/AdminTopActions";
import { useApp } from "@/context/AppContext";
import { filterAdminNavigation, findAdminNavigationGroup } from "@/lib/adminAccess";
import { preloadAdminRoute } from "@/lib/adminRoutePreload";
import { isAssetUrl, resolveAssetUrl, type ApiEffectivePermissions } from "@/lib/api";
import type { AdminNavigationGroup, AdminNavigationItem } from "@/config/adminNavigation";

const LAST_MODULE_PATH_PREFIX = "admin:last-module-path:";

function readJson<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) as T : null;
  } catch {
    return null;
  }
}

function getInitials(name: string): string {
  return name
    .split(" ")
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

function itemMatchesPath(item: AdminNavigationItem, pathname: string) {
  return [item.path, ...(item.aliases ?? [])].some((path) =>
    item.exact ? pathname === path : pathname === path || pathname.startsWith(`${path}/`),
  );
}

function moduleTarget(group: AdminNavigationGroup): string {
  const saved = localStorage.getItem(`${LAST_MODULE_PATH_PREFIX}${group.label}`);
  if (saved && group.children.some((item) => itemMatchesPath(item, saved))) return saved;
  return group.children[0]?.path ?? "/painel";
}

export default function TopNavigation({
  mobileMenuOpen,
  onMobileMenuChange,
}: {
  mobileMenuOpen: boolean;
  onMobileMenuChange: (open: boolean) => void;
}) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { siteContent } = useApp();
  const searchRef = useRef<HTMLDivElement>(null);
  const profileRef = useRef<HTMLDivElement>(null);
  const permissions = readJson<ApiEffectivePermissions>("admin_permissions");
  const adminUser = readJson<{ name?: string; email?: string; role_name?: string }>("admin_user");
  const navigationGroups = useMemo(() => filterAdminNavigation(permissions), [JSON.stringify(permissions)]);
  const activeGroup = findAdminNavigationGroup(pathname, navigationGroups);
  const [mobileModuleLabel, setMobileModuleLabel] = useState(activeGroup?.label ?? navigationGroups[0]?.label ?? "");
  const [query, setQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);

  const adminName = adminUser?.name ?? "Administrador";
  const adminEmail = adminUser?.email ?? "";
  const adminRole = adminUser?.role_name ?? permissions?.role_name ?? "Admin";
  const initials = getInitials(adminName);

  useEffect(() => {
    if (!activeGroup) return;
    localStorage.setItem(`${LAST_MODULE_PATH_PREFIX}${activeGroup.label}`, pathname);
    setMobileModuleLabel(activeGroup.label);
  }, [activeGroup?.label, pathname]);

  useEffect(() => {
    if (!searchOpen && !profileOpen) return;
    const closeDropdowns = (event: MouseEvent) => {
      const target = event.target as Node;
      if (searchOpen && searchRef.current && !searchRef.current.contains(target)) setSearchOpen(false);
      if (profileOpen && profileRef.current && !profileRef.current.contains(target)) setProfileOpen(false);
    };
    document.addEventListener("mousedown", closeDropdowns);
    return () => document.removeEventListener("mousedown", closeDropdowns);
  }, [profileOpen, searchOpen]);

  useEffect(() => {
    if (!mobileMenuOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [mobileMenuOpen]);

  const searchResults = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return [];
    return navigationGroups
      .flatMap((group) => group.children.map((item) => ({ group, item })))
      .filter(({ group, item }) => `${group.label} ${item.label}`.toLowerCase().includes(normalized))
      .slice(0, 8);
  }, [navigationGroups, query]);

  const mobileGroup = navigationGroups.find((group) => group.label === mobileModuleLabel) ?? activeGroup ?? navigationGroups[0];

  const handleLogout = () => {
    localStorage.removeItem("admin_token");
    localStorage.removeItem("admin_user");
    localStorage.removeItem("admin_permissions");
    navigate("/painel/login");
  };

  const handleModuleClick = (group: AdminNavigationGroup) => {
    navigate(moduleTarget(group));
  };

  const executeSearch = () => {
    const firstResult = searchResults[0];
    if (firstResult) {
      navigate(firstResult.item.path);
    } else if (query.trim()) {
      navigate(`/painel/orders?q=${encodeURIComponent(query.trim())}`);
    }
    setQuery("");
    setSearchOpen(false);
    onMobileMenuChange(false);
  };

  const handleSearchSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    executeSearch();
  };

  const logo = siteContent.brand.logo;

  return (
    <>
      <header className="admin-top-navigation sticky top-0 z-50 flex h-[68px] flex-shrink-0 items-center gap-3 border-b border-surface-03 bg-surface-02/95 px-3 shadow-lg backdrop-blur-xl md:px-5">
        <button
          type="button"
          onClick={() => onMobileMenuChange(true)}
          className="flex h-10 w-10 items-center justify-center rounded-xl border border-surface-03 text-stone transition-colors hover:bg-surface-03 hover:text-cream lg:hidden"
          aria-label="Abrir navegacao"
        >
          <Menu size={20} />
        </button>

        <Link to="/painel" className="flex h-10 w-[5.75rem] shrink-0 items-center sm:w-[6.75rem] lg:h-11 xl:w-[7.5rem]" aria-label="Ir para o dashboard">
          <span className="flex h-full w-full items-center justify-start sm:justify-center">
            {isAssetUrl(logo) ? (
              <img src={resolveAssetUrl(logo)} alt="" className="max-h-8 w-full object-contain sm:max-h-9 lg:max-h-10" />
            ) : logo ? (
              <span className="truncate text-xl leading-none sm:text-2xl">{logo}</span>
            ) : (
              <MoschettieriLogo className="w-full text-[0.9rem] leading-none text-gold sm:text-[1rem] lg:text-[1.1rem]" />
            )}
          </span>
        </Link>

        <nav className="hidden min-w-0 flex-1 items-center gap-1 overflow-x-auto pl-2 lg:flex" aria-label="Modulos principais">
          {navigationGroups.map((group) => {
            const Icon = group.children[0]?.icon;
            const active = activeGroup?.label === group.label;
            const target = moduleTarget(group);
            return (
              <button
                key={group.label}
                type="button"
                onMouseEnter={() => preloadAdminRoute(target)}
                onFocus={() => preloadAdminRoute(target)}
                onClick={() => handleModuleClick(group)}
                className={`flex h-10 shrink-0 items-center gap-2 rounded-xl px-3 text-xs font-bold outline-none transition-colors ${
                  active
                    ? "bg-surface-03 text-cream"
                    : "text-stone hover:bg-surface-03 hover:text-cream"
                }`}
              >
                {Icon && <Icon size={15} />}
                <span>{group.label}</span>
              </button>
            );
          })}
        </nav>

        <div ref={searchRef} className="relative ml-auto hidden lg:block">
          <form
            onSubmit={handleSearchSubmit}
            className="flex h-10 w-44 items-center gap-2 rounded-xl border border-surface-03 bg-surface-01 px-3 transition-colors focus-within:border-gold/50 xl:w-56 2xl:w-72"
          >
            <Search size={15} className="shrink-0 text-stone" />
            <input
              value={query}
              onFocus={() => setSearchOpen(true)}
              onChange={(event) => {
                setQuery(event.target.value);
                setSearchOpen(true);
              }}
              placeholder="Buscar no painel..."
              className="min-w-0 flex-1 bg-transparent text-sm text-cream outline-none placeholder:text-stone/60"
            />
          </form>
          {searchOpen && query.trim() && (
            <div className="absolute right-0 top-12 z-50 w-80 overflow-hidden rounded-2xl border border-surface-03 bg-surface-02 shadow-2xl">
              {searchResults.length > 0 ? (
                searchResults.map(({ group, item }) => {
                  const Icon = item.icon;
                  return (
                    <button
                      key={`${group.label}-${item.path}`}
                      type="button"
                      onClick={() => {
                        navigate(item.path);
                        setQuery("");
                        setSearchOpen(false);
                      }}
                      className="flex w-full items-center gap-3 border-b border-surface-03/50 px-4 py-3 text-left transition-colors last:border-0 hover:bg-surface-03/60"
                    >
                      <Icon size={16} className="text-gold" />
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-bold text-cream">{item.label}</span>
                        <span className="block text-[11px] text-stone">{group.label}</span>
                      </span>
                    </button>
                  );
                })
              ) : (
                <button
                  type="button"
                  onClick={executeSearch}
                  className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm text-stone transition-colors hover:bg-surface-03/60 hover:text-cream"
                >
                  <Search size={15} className="text-gold" />
                  Buscar pedido por "{query.trim()}"
                </button>
              )}
            </div>
          )}
        </div>

        <AdminTopActions force hideSearch />

        <div ref={profileRef} className="relative">
          <button
            type="button"
            onClick={() => setProfileOpen((open) => !open)}
            className="flex h-10 items-center gap-2 rounded-xl border border-surface-03 bg-surface-01 px-2 text-left transition-colors hover:bg-surface-03"
            aria-label="Abrir perfil"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gold/20 text-[11px] font-black text-gold">
              {initials || <User size={14} />}
            </span>
            <span className="hidden max-w-28 truncate text-xs font-bold text-cream 2xl:block">{adminName}</span>
            <ChevronDown size={13} className="hidden text-stone 2xl:block" />
          </button>
          {profileOpen && (
            <div className="absolute right-0 top-12 z-50 w-64 overflow-hidden rounded-2xl border border-surface-03 bg-surface-02 shadow-2xl">
              <div className="border-b border-surface-03 px-4 py-3">
                <p className="truncate text-sm font-bold text-cream">{adminName}</p>
                {adminEmail && <p className="mt-1 truncate text-xs text-stone">{adminEmail}</p>}
                <span className="mt-2 inline-flex rounded-md border border-gold/25 bg-gold/10 px-2 py-1 text-[10px] font-bold text-gold">
                  {adminRole}
                </span>
              </div>
              <Link
                to="/"
                onClick={() => setProfileOpen(false)}
                className="flex items-center gap-3 px-4 py-3 text-sm text-stone transition-colors hover:bg-surface-03 hover:text-cream"
              >
                <ArrowLeft size={15} />
                Voltar ao App
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm text-red-300 transition-colors hover:bg-red-500/10"
              >
                <LogOut size={15} />
                Sair
              </button>
            </div>
          )}
        </div>
      </header>

      {mobileMenuOpen && (
        <div className="fixed inset-0 z-[70] flex flex-col bg-surface-00 lg:hidden">
          <div className="flex h-[68px] shrink-0 items-center justify-between border-b border-surface-03 bg-surface-02 px-4">
            <div>
              <p className="text-sm font-black text-cream">Navegacao do painel</p>
              <p className="text-xs text-stone">Escolha um modulo e uma pagina</p>
            </div>
            <button
              type="button"
              onClick={() => onMobileMenuChange(false)}
              className="flex h-10 w-10 items-center justify-center rounded-xl border border-surface-03 text-stone"
              aria-label="Fechar navegacao"
            >
              <X size={19} />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            <form onSubmit={handleSearchSubmit} className="mb-4 flex h-11 items-center gap-2 rounded-xl border border-surface-03 bg-surface-02 px-3">
              <Search size={16} className="shrink-0 text-stone" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Buscar no painel..."
                className="min-w-0 flex-1 bg-transparent text-sm text-cream outline-none placeholder:text-stone/60"
              />
            </form>
            {query.trim() && (
              <div className="mb-5 overflow-hidden rounded-2xl border border-surface-03 bg-surface-02">
                {searchResults.length > 0 ? (
                  searchResults.map(({ group, item }) => {
                    const Icon = item.icon;
                    return (
                      <button
                        key={`mobile-search-${group.label}-${item.path}`}
                        type="button"
                        onClick={() => {
                          navigate(item.path);
                          setQuery("");
                          onMobileMenuChange(false);
                        }}
                        className="flex w-full items-center gap-3 border-b border-surface-03/50 px-4 py-3 text-left transition-colors last:border-0 hover:bg-surface-03/60"
                      >
                        <Icon size={16} className="text-gold" />
                        <span className="min-w-0">
                          <span className="block truncate text-sm font-bold text-cream">{item.label}</span>
                          <span className="block text-[11px] text-stone">{group.label}</span>
                        </span>
                      </button>
                    );
                  })
                ) : (
                  <button type="button" onClick={executeSearch} className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm text-stone">
                    <Search size={15} className="text-gold" />
                    Buscar pedido por "{query.trim()}"
                  </button>
                )}
              </div>
            )}
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {navigationGroups.map((group) => {
                const Icon = group.children[0]?.icon;
                const active = mobileGroup?.label === group.label;
                return (
                  <button
                    key={group.label}
                    type="button"
                    onClick={() => setMobileModuleLabel(group.label)}
                    className={`flex items-center gap-2 rounded-xl border px-3 py-3 text-left text-xs font-bold transition-colors ${
                      active
                        ? "border-gold/40 bg-gold/15 text-gold"
                        : "border-surface-03 bg-surface-02 text-stone"
                    }`}
                  >
                    {Icon && <Icon size={15} />}
                    {group.label}
                  </button>
                );
              })}
            </div>
            {mobileGroup && (
              <div className="mt-6">
                <p className="mb-2 text-[10px] font-black uppercase tracking-[0.2em] text-gold">{mobileGroup.label}</p>
                <div className="space-y-1">
                  {mobileGroup.children.map((item) => {
                    const Icon = item.icon;
                    const active = itemMatchesPath(item, pathname);
                    return (
                      <Link
                        key={item.path}
                        to={item.path}
                        onClick={() => onMobileMenuChange(false)}
                        className={`flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-semibold transition-colors ${
                          active ? "bg-gold text-black" : "bg-surface-02 text-stone hover:bg-surface-03 hover:text-cream"
                        }`}
                      >
                        <Icon size={17} />
                        {item.label}
                      </Link>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
          <div className="grid grid-cols-2 gap-2 border-t border-surface-03 bg-surface-02 p-4">
            <Link to="/" className="flex items-center justify-center gap-2 rounded-xl border border-surface-03 px-3 py-3 text-sm font-bold text-stone">
              <ArrowLeft size={15} />
              Voltar ao App
            </Link>
            <button type="button" onClick={handleLogout} className="flex items-center justify-center gap-2 rounded-xl bg-red-500/10 px-3 py-3 text-sm font-bold text-red-300">
              <LogOut size={15} />
              Sair
            </button>
          </div>
        </div>
      )}
    </>
  );
}
