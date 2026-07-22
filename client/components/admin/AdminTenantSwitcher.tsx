import { useEffect, useState } from "react";
import { Building2, Loader2 } from "lucide-react";
import { adminAuthApi, type ApiAdminTenantMembership } from "@/lib/api";

const TENANT_SWITCHER_ENABLED =
  String(import.meta.env.VITE_MULTI_TENANT_AUTH_ENABLED ?? "").toLowerCase() === "true";

function getTokenTenantId(): string {
  try {
    const token = localStorage.getItem("admin_token");
    const encodedPayload = token?.split(".")[1];
    if (!encodedPayload) return "";
    const normalizedPayload = encodedPayload.replace(/-/g, "+").replace(/_/g, "/");
    const paddedPayload = normalizedPayload.padEnd(Math.ceil(normalizedPayload.length / 4) * 4, "=");
    const payload = JSON.parse(atob(paddedPayload)) as {
      tenant_id?: unknown;
    };
    return typeof payload.tenant_id === "string" ? payload.tenant_id : "";
  } catch {
    return "";
  }
}

export default function AdminTenantSwitcher() {
  const [memberships, setMemberships] = useState<ApiAdminTenantMembership[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState("");
  const [switching, setSwitching] = useState(false);

  useEffect(() => {
    if (!TENANT_SWITCHER_ENABLED) return;
    let cancelled = false;
    adminAuthApi.listTenants()
      .then((items) => {
        if (cancelled || !Array.isArray(items)) return;
        setMemberships(items);
        const tokenTenantId = getTokenTenantId();
        // The JWT is the only authority for the active tenant.  When a user
        // has multiple memberships but no selected tenant claim, keep the
        // control empty so choosing even the first item actually requests a
        // server-validated token instead of merely looking selected.
        const selected = items.find((item) => item.tenant_id === tokenTenantId);
        setSelectedTenantId(selected?.tenant_id ?? "");
      })
      .catch(() => {
        if (!cancelled) setMemberships([]);
      });
    return () => { cancelled = true; };
  }, []);

  if (!TENANT_SWITCHER_ENABLED || memberships.length < 2) return null;

  const handleChange = async (tenantId: string) => {
    if (!tenantId || tenantId === selectedTenantId || switching) return;
    const previousTenantId = selectedTenantId;
    setSelectedTenantId(tenantId);
    setSwitching(true);
    try {
      const session = await adminAuthApi.selectTenant(tenantId);
      localStorage.setItem("admin_token", session.access_token);
      localStorage.removeItem("admin_permissions");
      window.location.assign("/painel");
    } catch {
      setSelectedTenantId(previousTenantId);
      setSwitching(false);
    }
  };

  return (
    <label className="hidden h-10 max-w-48 items-center gap-2 rounded-xl border border-surface-03 bg-surface-01 px-2 text-stone xl:flex">
      {switching ? <Loader2 size={14} className="shrink-0 animate-spin text-gold" aria-hidden="true" /> : <Building2 size={14} className="shrink-0 text-gold" aria-hidden="true" />}
      <span className="sr-only">Empresa ativa</span>
      <select
        value={selectedTenantId}
        disabled={switching}
        onChange={(event) => void handleChange(event.target.value)}
        className="min-w-0 flex-1 cursor-pointer truncate bg-transparent text-xs font-bold text-cream outline-none disabled:cursor-wait"
        aria-label="Empresa ativa"
      >
        {!selectedTenantId && <option value="">Selecione uma empresa</option>}
        {memberships.map((membership) => (
          <option key={membership.membership_id} value={membership.tenant_id} className="bg-surface-02 text-cream">
            {membership.name}
          </option>
        ))}
      </select>
    </label>
  );
}
