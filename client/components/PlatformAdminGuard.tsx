import { useEffect, useState } from "react";
import { Loader2, RefreshCw, ShieldX } from "lucide-react";
import { Navigate, Outlet } from "react-router-dom";
import { adminAuthApi, isApiRequestErrorStatus, platformTenantsApi } from "@/lib/api";
import { isPlatformHostname } from "@/lib/platformHost";

type SessionState = "checking" | "authenticated" | "password_required" | "denied" | "unavailable";

export default function PlatformAdminGuard() {
  const isPlatform = isPlatformHostname(window.location.hostname);
  const token = localStorage.getItem("admin_token");
  const [sessionState, setSessionState] = useState<SessionState>(
    token ? "checking" : "unavailable",
  );
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    setSessionState("checking");
    adminAuthApi.me()
      .then(async (admin) => {
        if (cancelled) return;
        localStorage.setItem("admin_user", JSON.stringify(admin));
        if (admin.force_password_change) {
          setSessionState("password_required");
          return;
        }
        await platformTenantsApi.dashboard();
        if (!cancelled) setSessionState("authenticated");
      })
      .catch((error) => {
        if (!cancelled && localStorage.getItem("admin_token")) {
          if (isApiRequestErrorStatus(error, 403)) {
            setSessionState("denied");
            return;
          }
          // A falha pode ser operacional (5xx/rede). O cliente HTTP remove o
          // token somente quando o servidor confirma 401.
          setSessionState("unavailable");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [token, retryKey]);

  if (!isPlatform) return <Navigate to="/painel" replace />;
  if (!token) return <Navigate to="/painel/login" replace />;
  if (sessionState === "password_required") return <Navigate to="/painel/trocar-senha" replace />;

  if (sessionState === "checking") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-00">
        <Loader2 size={36} className="animate-spin text-gold" />
      </div>
    );
  }

  if (sessionState === "denied") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-00 px-6">
        <div className="max-w-md rounded-2xl border border-surface-03 bg-surface-02 p-6 text-center">
          <ShieldX size={38} className="mx-auto text-red-300" />
          <h1 className="mt-4 text-lg font-black text-cream">Acesso Master nao autorizado</h1>
          <p className="mt-2 text-sm text-stone">
            Sua sessao foi preservada, mas este usuario nao possui permissao para administrar a plataforma.
          </p>
          <a href="/painel/login" className="mt-5 inline-flex rounded-xl border border-surface-03 px-4 py-3 text-sm font-black text-cream hover:bg-surface-03">
            Entrar com outra conta
          </a>
        </div>
      </div>
    );
  }

  if (sessionState === "unavailable") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-00 px-6">
        <div className="max-w-md rounded-2xl border border-surface-03 bg-surface-02 p-6 text-center">
          <h1 className="text-lg font-black text-cream">Nao foi possivel validar a sessao</h1>
          <p className="mt-2 text-sm text-stone">
            Sua sessao foi preservada. Verifique a conexao com a API e tente novamente.
          </p>
          <button
            type="button"
            onClick={() => setRetryKey((value) => value + 1)}
            className="mt-5 inline-flex items-center gap-2 rounded-xl bg-gold px-4 py-3 text-sm font-black text-surface-00"
          >
            <RefreshCw size={16} /> Tentar novamente
          </button>
        </div>
      </div>
    );
  }

  return <Outlet />;
}
