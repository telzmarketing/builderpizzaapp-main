/**
 * AdminGuard — redireciona para /painel/login se não houver token JWT válido
 * e bloqueia rotas que o perfil atual não pode acessar.
 */
import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { findAdminNavigationItem, firstAllowedAdminPath, canAccessAdminItem } from "@/lib/adminAccess";
import { rbacApi, type ApiEffectivePermissions } from "@/lib/api";

export default function AdminGuard() {
  const { pathname } = useLocation();
  const token = localStorage.getItem("admin_token");
  const [permissions, setPermissions] = useState<ApiEffectivePermissions | null>(null);
  const [loading, setLoading] = useState(!!token);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    setLoading(true);
    rbacApi
      .myPermissions()
      .then((data) => {
        if (cancelled) return;
        setPermissions(data);
        localStorage.setItem("admin_permissions", JSON.stringify(data));
      })
      .catch(() => {
        if (cancelled) return;
        localStorage.removeItem("admin_token");
        localStorage.removeItem("admin_user");
        localStorage.removeItem("admin_permissions");
        setPermissions(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (!token) return <Navigate to="/painel/login" replace />;
  if (loading) {
    return (
      <div className="min-h-screen bg-surface-00 flex items-center justify-center">
        <Loader2 size={36} className="animate-spin text-gold" />
      </div>
    );
  }

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
