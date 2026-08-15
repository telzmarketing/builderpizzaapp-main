import { ShieldX } from "lucide-react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { firstAllowedPlatformPath } from "@/config/platformNavigation";
import type { PlatformCapability } from "@/lib/platformCapabilities";
import { hasPlatformCapability, readPlatformPermissions } from "@/lib/platformCapabilities";

export default function PlatformCapabilityGuard({ capability }: { capability: PlatformCapability }) {
  const { pathname } = useLocation();
  const permissions = readPlatformPermissions();
  if (hasPlatformCapability(permissions, capability)) return <Outlet />;

  const fallbackPath = firstAllowedPlatformPath(permissions);
  if (pathname === "/painel/plataforma" && fallbackPath && fallbackPath !== pathname) {
    return <Navigate to={fallbackPath} replace />;
  }

  return (
    <section role="alert" className="rounded-2xl border border-red-500/30 bg-red-500/10 p-8 text-center text-red-100">
      <ShieldX size={34} className="mx-auto" />
      <h2 className="mt-3 font-black">Modulo nao autorizado</h2>
      <p className="mx-auto mt-2 max-w-xl text-sm text-red-100/80">
        Sua sessao nao possui a capacidade necessaria para consultar este modulo da Central Master.
      </p>
    </section>
  );
}
