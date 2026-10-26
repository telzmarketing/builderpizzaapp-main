import { Link } from "react-router-dom";
import { ChefHat } from "lucide-react";
import PreparationOperationsPanel from "@/components/admin/PreparationOperationsPanel";
import KdsSessionActions from "@/components/kds/KdsSessionActions";

export default function Preparation() {
  return <main className="min-h-screen bg-surface-00 text-cream"><header className="flex flex-wrap items-center justify-between gap-3 border-b border-surface-03 bg-surface-02 p-4"><div className="flex items-center gap-3"><ChefHat size={30} className="text-gold" /><div><h1 className="text-2xl font-black">KDS Cozinha Preparo</h1><p className="text-sm text-stone">Preparação antecipada de insumos e porções</p></div></div><div className="flex items-center gap-3"><Link className="min-h-12 py-3 text-sm font-bold text-gold" to="/painel/gestao/estoque">Gestão de Estoque</Link><KdsSessionActions /></div></header><div className="mx-auto max-w-6xl p-3 sm:p-6"><PreparationOperationsPanel /></div></main>;
}
