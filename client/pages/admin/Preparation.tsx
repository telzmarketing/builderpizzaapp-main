import { Link } from "react-router-dom";
import { ChefHat } from "lucide-react";
import PreparationOperationsPanel from "@/components/admin/PreparationOperationsPanel";
import KdsSessionActions from "@/components/kds/KdsSessionActions";
import KdsBrandLogo from "@/components/kds/KdsBrandLogo";

export default function Preparation() {
  return <main className="kds-preparation min-h-screen bg-surface-00 text-cream"><header className="sticky top-0 z-20 flex flex-wrap items-center justify-between gap-3 border-b border-surface-03 bg-surface-02 p-4"><div className="flex items-center gap-3"><KdsBrandLogo fallback={<ChefHat size={30} className="shrink-0 text-gold" />} /><div><h1 className="text-2xl font-black">KDS Cozinha Preparo</h1><p className="text-sm text-stone">Preparação antecipada de insumos e porções</p></div></div><div className="flex items-center gap-3"><Link className="min-h-12 py-3 text-sm font-bold text-gold" to="/painel/gestao/estoque">Gestão de Estoque</Link><KdsSessionActions /></div></header><div className="mx-auto max-w-6xl p-3 sm:p-6"><PreparationOperationsPanel showKdsLink={false} /></div></main>;
}
