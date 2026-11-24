import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AlertTriangle, BarChart3, Database, ShoppingCart } from "lucide-react";
import { AdminPageTabs, type AdminPageTab } from "@/components/admin/AdminPageChrome";
import PurchaseDashboardPanel from "@/components/admin/PurchaseDashboardPanel";
import PurchasePlanningPanel from "@/components/admin/PurchasePlanningPanel";
import PurchaseQuotationPanel from "@/components/admin/PurchaseQuotationPanel";
import PurchaseReceiptPanel from "@/components/admin/PurchaseReceiptPanel";
import PurchaseOrdersPanel from "@/components/admin/PurchaseOrdersPanel";
import AdminGestao from "./AdminGestao";
import { inventoryApi, type InventoryOverview } from "@/lib/api";

type PurchaseSection = "replenishment" | "purchases" | "quotations" | "dashboard" | "receipts";

const purchaseRouteBase = "/painel/gestao/compras";
const sectionSlugs: Record<PurchaseSection, string> = {
  replenishment: "reposicao",
  purchases: "compras",
  quotations: "cotacoes",
  dashboard: "bi-compras",
  receipts: "recebimentos",
};

const sections: AdminPageTab<PurchaseSection>[] = [
  { id: "replenishment", label: "Reposição", icon: AlertTriangle },
  { id: "purchases", label: "Compras", icon: ShoppingCart },
  { id: "quotations", label: "Cotações", icon: ShoppingCart },
  { id: "dashboard", label: "BI de Compras", icon: BarChart3 },
  { id: "receipts", label: "Recebimentos", icon: Database },
];

function sectionFromPath(pathname: string): PurchaseSection | null {
  const slug = pathname.replace(`${purchaseRouteBase}/`, "").replace(/\/$/, "");
  if (!slug || slug === pathname) return null;
  return (Object.entries(sectionSlugs) as Array<[PurchaseSection, string]>).find(([, value]) => value === slug)?.[0] ?? null;
}

export default function GestaoPurchases() {
  const location = useLocation();
  const navigate = useNavigate();
  const section = sectionFromPath(location.pathname) ?? "purchases";

  useEffect(() => {
    if (!sectionFromPath(location.pathname)) navigate(`${purchaseRouteBase}/${sectionSlugs.purchases}`, { replace: true });
  }, [location.pathname, navigate]);

  const changeSection = (next: PurchaseSection) => navigate(`${purchaseRouteBase}/${sectionSlugs[next]}`);

  return (
    <AdminGestao
      moduleKey="inventory"
      showSettings={false}
      moduleTabs={<AdminPageTabs<PurchaseSection> tabs={sections} active={section} onChange={changeSection} />}
    >
      {section === "replenishment" ? <PurchasePlanningPanel /> : section === "quotations" ? <PurchaseQuotationPanel /> : section === "receipts" ? <PurchaseReceiptPanel /> : section === "dashboard" ? <PurchaseDashboardPanel /> : <PurchaseOrdersContainer />}
    </AdminGestao>
  );
}

function PurchaseOrdersContainer() {
  const [data, setData] = useState<InventoryOverview>({ units: [], categories: [], locations: [], suppliers: [], items: [], purchases: [], manual_entries: [], movements: [], balances: [] });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { inventoryApi.overview().then(setData).catch((err) => setError(err instanceof Error ? err.message : "Nao foi possivel carregar compras.")); }, []);
  const run = async (action: () => Promise<unknown>, success: string) => { setSaving(true); setError(""); try { await action(); setData(await inventoryApi.overview()); } catch (err) { setError(err instanceof Error ? err.message : success); } finally { setSaving(false); } };
  return <section className="space-y-5 rounded-lg border border-surface-03 bg-surface-02 p-5"><div><h2 className="text-lg font-black text-cream">Compras</h2><p className="mt-1 text-sm text-stone">Crie, revise e confirme compras sem alterar o saldo antes do recebimento.</p></div>{error && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</p>}<PurchaseOrdersPanel data={data} saving={saving} run={run} /></section>;
}
