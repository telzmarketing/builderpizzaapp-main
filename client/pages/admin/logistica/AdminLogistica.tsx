import { lazy, Suspense, useState, type ComponentType } from "react";
import { AlertTriangle, BarChart2, DollarSign, Map, MapPin, Settings, Truck, Users } from "lucide-react";
import {
  AdminPageContent,
  AdminPageHeader,
  AdminPageShell,
  AdminPageTabs,
  type AdminPageTab,
} from "@/components/admin/AdminPageChrome";

type Tab = "motoboys" | "ativas" | "mapa" | "financeiro" | "analytics" | "alertas" | "config";

const tabLoaders: Record<Tab, () => Promise<{ default: ComponentType }>> = {
  motoboys: () => import("./LogisticaMotoboys"),
  ativas: () => import("./LogisticaAtivas"),
  mapa: () => import("./LogisticaMapa"),
  config: () => import("./LogisticaConfig"),
  financeiro: () => import("./LogisticaFinanceiro"),
  analytics: () => import("./LogisticaAnalytics"),
  alertas: () => import("./LogisticaAlertas"),
};

const preloadedTabs = new Set<Tab>();

function preloadLogisticaTab(tab: Tab) {
  if (preloadedTabs.has(tab)) return;
  preloadedTabs.add(tab);
  tabLoaders[tab]().catch(() => preloadedTabs.delete(tab));
}

const LogisticaMotoboys = lazy(tabLoaders.motoboys);
const LogisticaAtivas = lazy(tabLoaders.ativas);
const LogisticaMapa = lazy(tabLoaders.mapa);
const LogisticaConfig = lazy(tabLoaders.config);
const LogisticaFinanceiro = lazy(tabLoaders.financeiro);
const LogisticaAnalytics = lazy(tabLoaders.analytics);
const LogisticaAlertas = lazy(tabLoaders.alertas);

const TABS: AdminPageTab<Tab>[] = [
  { id: "motoboys", icon: <Users size={15} />, label: "Motoboys" },
  { id: "ativas", icon: <MapPin size={15} />, label: "Entregas Ativas" },
  { id: "mapa", icon: <Map size={15} />, label: "Mapa" },
  { id: "financeiro", icon: <DollarSign size={15} />, label: "Financeiro" },
  { id: "analytics", icon: <BarChart2 size={15} />, label: "Analises" },
  { id: "alertas", icon: <AlertTriangle size={15} />, label: "Alertas" },
  { id: "config", icon: <Settings size={15} />, label: "Configuracoes" },
];

export default function AdminLogistica() {
  const [tab, setTab] = useState<Tab>("motoboys");

  return (
    <AdminPageShell>
      <AdminPageHeader
        icon={<Truck size={20} />}
        title="Logistica"
        description="Gerenciamento de entregas e motoboys"
      />
      <AdminPageTabs
        tabs={TABS}
        active={tab}
        onPreview={preloadLogisticaTab}
        onChange={(next) => {
          preloadLogisticaTab(next);
          setTab(next as Tab);
        }}
      />
      <AdminPageContent>
        <Suspense fallback={<LogisticaTabFallback />}>
          {tab === "motoboys" && <LogisticaMotoboys />}
          {tab === "ativas" && <LogisticaAtivas />}
          {tab === "mapa" && <LogisticaMapa />}
          {tab === "financeiro" && <LogisticaFinanceiro />}
          {tab === "analytics" && <LogisticaAnalytics />}
          {tab === "alertas" && <LogisticaAlertas />}
          {tab === "config" && <LogisticaConfig />}
        </Suspense>
      </AdminPageContent>
    </AdminPageShell>
  );
}

function LogisticaTabFallback() {
  return (
    <div className="rounded-2xl border border-surface-03 bg-surface-02 p-8 text-center text-sm text-stone">
      Carregando...
    </div>
  );
}
