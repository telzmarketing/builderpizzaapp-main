import { useState } from "react";
import { AlertTriangle, BarChart2, DollarSign, Map, MapPin, Settings, Truck, Users } from "lucide-react";
import {
  AdminPageContent,
  AdminPageHeader,
  AdminPageShell,
  AdminPageTabs,
  type AdminPageTab,
} from "@/components/admin/AdminPageChrome";
import LogisticaMotoboys from "./LogisticaMotoboys";
import LogisticaAtivas from "./LogisticaAtivas";
import LogisticaMapa from "./LogisticaMapa";
import LogisticaConfig from "./LogisticaConfig";
import LogisticaFinanceiro from "./LogisticaFinanceiro";
import LogisticaAnalytics from "./LogisticaAnalytics";
import LogisticaAlertas from "./LogisticaAlertas";

type Tab = "motoboys" | "ativas" | "mapa" | "financeiro" | "analytics" | "alertas" | "config";

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
      <AdminPageTabs tabs={TABS} active={tab} onChange={(next) => setTab(next as Tab)} />
      <AdminPageContent>
        {tab === "motoboys" && <LogisticaMotoboys />}
        {tab === "ativas" && <LogisticaAtivas />}
        {tab === "mapa" && <LogisticaMapa />}
        {tab === "financeiro" && <LogisticaFinanceiro />}
        {tab === "analytics" && <LogisticaAnalytics />}
        {tab === "alertas" && <LogisticaAlertas />}
        {tab === "config" && <LogisticaConfig />}
      </AdminPageContent>
    </AdminPageShell>
  );
}
