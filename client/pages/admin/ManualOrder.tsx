import { Link } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import ManualOrderComposer from "@/components/admin/ManualOrderComposer";

export default function ManualOrder() {
  return <main className="mx-auto min-h-screen max-w-5xl bg-surface-00 text-cream"><header className="flex items-center gap-4 border-b border-surface-03 p-4"><Link to="/painel/orders" aria-label="Voltar às Operações" className="flex min-h-12 min-w-12 items-center justify-center rounded-xl border border-surface-03"><ChevronLeft /></Link><div><p className="text-xs font-bold uppercase tracking-widest text-gold">Operações</p><h1 className="text-2xl font-black">Fazer Pedido</h1></div></header><ManualOrderComposer /></main>;
}
