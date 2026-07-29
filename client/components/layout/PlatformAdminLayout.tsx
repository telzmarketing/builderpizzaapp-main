import "@/admin.css";
import { LogOut } from "lucide-react";
import { Outlet, useNavigate } from "react-router-dom";
import TelzLogo from "@/components/TelzLogo";

function readAdminUser(): { name?: string; email?: string } {
  try {
    return JSON.parse(localStorage.getItem("admin_user") ?? "{}");
  } catch {
    return {};
  }
}

export default function PlatformAdminLayout() {
  const navigate = useNavigate();
  const admin = readAdminUser();

  const logout = () => {
    localStorage.removeItem("admin_token");
    localStorage.removeItem("admin_user");
    localStorage.removeItem("admin_permissions");
    navigate("/painel/login", { replace: true });
  };

  return (
    <div className="min-h-screen bg-surface-00 text-cream">
      <header className="sticky top-0 z-40 border-b border-surface-03 bg-surface-02/95 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 md:px-6">
          <div>
            <TelzLogo className="text-xl text-gold" />
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-stone">
              Administracao da plataforma
            </p>
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
              <LogOut size={16} /> Sair
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 md:px-6">
        <div className="mb-6">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-gold">Multiempresa</p>
          <h1 className="mt-1 text-2xl font-black text-cream">Empresas e lojas</h1>
          <p className="mt-1 text-sm text-stone">
            Cadastre empresas e associe o endereco publico de cada loja.
          </p>
        </div>
        <Outlet />
      </main>
    </div>
  );
}
