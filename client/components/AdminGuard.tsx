/**
 * AdminGuard — redireciona para /painel/login se não houver token JWT válido
 * e bloqueia rotas que o perfil atual não pode acessar.
 */
import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { findAdminNavigationItem, firstAllowedAdminPath, canAccessAdminItem } from "@/lib/adminAccess";
import { adminAuthApi, rbacApi, type ApiEffectivePermissions } from "@/lib/api";
import { clearAdminSession } from "@/lib/adminSession";
import {
  PLATFORM_SUPPORT_PERMISSIONS,
  isPlatformSupportPanelPathAllowed,
  isPlatformSupportSessionActive,
  readPlatformSupportSession,
  restorePlatformMasterSession,
  shouldLoadRegularAdminPermissions,
} from "@/lib/platformSupportSession";

export default function AdminGuard() {
  const { pathname } = useLocation();
  const token = localStorage.getItem("admin_token");
  const supportSession = readPlatformSupportSession();
  const supportSessionId = supportSession?.session_id;
  const [permissions, setPermissions] = useState<ApiEffectivePermissions | null>(null);
  const [loading, setLoading] = useState(!!token);
  const [passwordRequired, setPasswordRequired] = useState(false);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    setLoading(true);
    if (supportSession && !isPlatformSupportSessionActive(supportSession)) {
      restorePlatformMasterSession();
      window.location.replace("/painel/plataforma");
      return;
    }
    adminAuthApi.me()
      .then(async (admin) => {
        if (cancelled) return;
        localStorage.setItem("admin_user", JSON.stringify(admin));
        if (admin.force_password_change) {
          setPasswordRequired(true);
          setPermissions(null);
          return;
        }
        setPasswordRequired(false);
        if (!shouldLoadRegularAdminPermissions(supportSession)) {
          setPermissions(PLATFORM_SUPPORT_PERMISSIONS);
          localStorage.setItem("admin_permissions", JSON.stringify(PLATFORM_SUPPORT_PERMISSIONS));
          return;
        }
        const data = await rbacApi.myPermissions();
        if (cancelled) return;
        setPermissions(data);
        localStorage.setItem("admin_permissions", JSON.stringify(data));
      })
      .catch(() => {
        if (cancelled) return;
        if (supportSession) {
          restorePlatformMasterSession();
          window.location.replace("/painel/plataforma");
          return;
        }
        clearAdminSession();
        setPermissions(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [supportSessionId, token]);

  if (!token) return <Navigate to="/painel/login" replace />;
  if (supportSession && !isPlatformSupportPanelPathAllowed(pathname)) {
    return <Navigate to="/painel/gestao/financeiro" replace />;
  }
  if (loading) {
    return (
      <div className="min-h-screen bg-surface-00 flex items-center justify-center">
        <Loader2 size={36} className="animate-spin text-gold" />
      </div>
    );
  }

  if (passwordRequired) return <Navigate to="/painel/trocar-senha" replace />;
  if (!permissions) return <Navigate to="/painel/login" replace />;

  const item = findAdminNavigationItem(pathname);
  if (!item && !permissions.is_master) {
    return <Navigate to={firstAllowedAdminPath(permissions)} replace />;
  }
  if (item && !canAccessAdminItem(permissions, item)) {
    return <Navigate to={firstAllowedAdminPath(permissions)} replace />;
  }

  return <Outlet />;
}
