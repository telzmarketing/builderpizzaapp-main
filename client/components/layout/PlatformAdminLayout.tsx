import "@/admin.css";
import { useEffect, useState } from "react";
import { LogOut, Menu, X } from "lucide-react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import TelzLogo from "@/components/TelzLogo";
import {
  platformItemMatchesPath,
  platformItemAllowed,
  platformNavigationGroups,
} from "@/config/platformNavigation";
import { getPlatformPageMeta } from "@/config/platformPageMeta";
import { readPlatformPermissions } from "@/lib/platformCapabilities";

function readAdminUser(): { name?: string; email?: string } {
  try {
    return JSON.parse(localStorage.getItem("admin_user") ?? "{}");
  } catch {
    return {};
  }
}

export default function PlatformAdminLayout() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const admin = readAdminUser();
  const meta = getPlatformPageMeta(pathname);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const permissions = readPlatformPermissions();

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!mobileMenuOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [mobileMenuOpen]);

  const logout = () => {
    localStorage.removeItem("admin_token");
    localStorage.removeItem("admin_user");
    localStorage.removeItem("admin_permissions");
    localStorage.removeItem("platform_permissions");
    navigate("/painel/login", { replace: true });
  };

  return (
    <div className="admin-shell text-cream">
      <div className="flex h-[100dvh] min-h-screen overflow-hidden bg-surface-00">
        {mobileMenuOpen && (
          <button
            type="button"
            aria-label="Fechar navegacao"
            className="fixed inset-0 z-40 bg-black/70 md:hidden"
            onClick={() => setMobileMenuOpen(false)}
          />
        )}

        <aside className={`fixed inset-y-0 left-0 z-50 flex w-[18rem] max-w-[86vw] flex-col border-r border-surface-03 bg-surface-02 transition-transform md:static md:z-auto md:w-64 md:translate-x-0 ${
          mobileMenuOpen ? "translate-x-0" : "-translate-x-full"
        }`}>
          <div className="flex h-16 shrink-0 items-center justify-between border-b border-surface-03 px-4">
            <div className="min-w-0">
              <TelzLogo className="text-xl text-gold" />
              <p className="truncate text-[9px] font-bold uppercase tracking-[0.18em] text-stone">
                Administracao da plataforma
              </p>
            </div>
            <button
              type="button"
              onClick={() => setMobileMenuOpen(false)}
              className="flex h-9 w-9 items-center justify-center rounded-xl border border-surface-03 text-stone md:hidden"
              aria-label="Fechar menu"
            >
              <X size={18} />
            </button>
          </div>

          <nav className="flex-1 overflow-y-auto px-3 py-4" aria-label="Navegacao da plataforma">
            {platformNavigationGroups.map((group) => (
              <div key={group.label} className="mb-6 last:mb-0">
                <p className="mb-2 px-3 text-[10px] font-black uppercase tracking-[0.18em] text-gold">
                  {group.label}
                </p>
                <div className="space-y-1">
                  {group.items.map((item) => {
                    const Icon = item.icon;
                    if (!platformItemAllowed(item, permissions)) return null;
                    if (!item.available || !item.path) {
                      return (
                        <div
                          key={item.label}
                          aria-disabled="true"
                          title="Funcionalidade indisponivel: backend ainda nao publicado"
                          className="flex cursor-not-allowed items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-stone/45"
                        >
                          <Icon size={17} />
                          <span className="min-w-0 flex-1 truncate">{item.label}</span>
                          <span className="text-[8px] font-black uppercase tracking-wide">Indisponivel</span>
                        </div>
                      );
                    }
                    return (
                      <NavLink
                        key={item.label}
                        to={item.path}
                        className={() => {
                          const active = platformItemMatchesPath(item, pathname);
                          return `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition ${
                            active
                              ? "bg-gold text-surface-00 shadow-sm shadow-gold/20"
                              : "text-stone hover:bg-surface-03 hover:text-cream"
                          }`;
                        }}
                      >
                        <Icon size={17} />
                        <span className="truncate">{item.label}</span>
                      </NavLink>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          <header className="flex h-16 shrink-0 items-center justify-between gap-3 border-b border-surface-03 bg-surface-02/95 px-4 backdrop-blur-xl md:px-6">
            <div className="flex min-w-0 items-center gap-3">
              <button
                type="button"
                onClick={() => setMobileMenuOpen(true)}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-surface-03 text-stone md:hidden"
                aria-label="Abrir navegacao"
              >
                <Menu size={19} />
              </button>
              <div className="min-w-0">
                <p className="truncate text-[9px] font-bold uppercase tracking-[0.18em] text-gold">
                  {meta.eyebrow}
                </p>
                <h1 className="truncate text-base font-black text-cream md:text-lg">{meta.title}</h1>
              </div>
            </div>
            <div className="flex min-w-0 items-center gap-3">
              <div className="hidden min-w-0 text-right sm:block">
                <p className="truncate text-sm font-bold text-cream">{admin.name || "Administrador"}</p>
                <p className="truncate text-xs text-stone">{admin.email}</p>
              </div>
              <button
                type="button"
                onClick={logout}
                className="inline-flex items-center gap-2 rounded-xl border border-surface-03 px-3 py-2 text-sm font-bold text-stone transition hover:bg-surface-03 hover:text-cream"
              >
                <LogOut size={16} /> <span className="hidden sm:inline">Sair</span>
              </button>
            </div>
          </header>

          <main className="min-h-0 flex-1 overflow-y-auto bg-surface-01">
            <div className="mx-auto min-h-full max-w-[100rem] space-y-6 p-4 md:p-6">
              <div>
                <p className="text-sm text-stone">{meta.subtitle}</p>
              </div>
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
