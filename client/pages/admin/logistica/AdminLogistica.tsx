import { useState } from "react";
import { Truck, Users, MapPin, Settings } from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import LogisticaMotoboys from "./LogisticaMotoboys";
import LogisticaAtivas from "./LogisticaAtivas";
import LogisticaConfig from "./LogisticaConfig";

type Tab = "motoboys" | "ativas" | "config";

const TABS: { id: Tab; icon: React.ReactNode; label: string }[] = [
  { id: "motoboys", icon: <Users size={15} />,   label: "Motoboys" },
  { id: "ativas",   icon: <MapPin size={15} />,   label: "Entregas Ativas" },
  { id: "config",   icon: <Settings size={15} />, label: "Configurações" },
];

export default function AdminLogistica() {
  const [tab, setTab] = useState<Tab>("motoboys");

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00">
      <div className="flex flex-col md:flex-row min-h-screen md:h-screen">
        <AdminSidebar />
        <div className="flex-1 flex flex-col overflow-hidden">

          {/* Top bar */}
          <div className="bg-surface-02 px-8 py-4 border-b border-surface-03 flex items-center gap-3 flex-shrink-0">
            <Truck size={22} className="text-gold" />
            <div>
              <h2 className="text-xl font-bold text-cream">Logística</h2>
              <p className="text-stone text-xs">Gerenciamento de entregas e motoboys</p>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 px-6 pt-4 border-b border-surface-03 overflow-x-auto flex-shrink-0 bg-surface-02">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`flex items-center gap-1.5 px-4 py-2.5 rounded-t-lg text-xs font-medium whitespace-nowrap transition-colors ${
                  tab === t.id
                    ? "bg-surface-01 text-gold border border-b-0 border-surface-03"
                    : "text-stone hover:text-parchment"
                }`}
              >
                {t.icon}
                {t.label}
              </button>
            ))}
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto bg-surface-01 p-6">
            {tab === "motoboys" && <LogisticaMotoboys />}
            {tab === "ativas"   && <LogisticaAtivas />}
            {tab === "config"   && <LogisticaConfig />}
          </div>

        </div>
      </div>
    </div>
  );
}
