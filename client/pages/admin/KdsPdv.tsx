import { ArrowLeft, BadgeCheck, MonitorSmartphone, ReceiptText, ShoppingCart } from "lucide-react";
import { Link } from "react-router-dom";
import ManualOrderComposer from "@/components/admin/ManualOrderComposer";

export default function KdsPdv() {
  return (
    <main className="kds-pdv min-h-screen w-full bg-surface-00 text-cream">
      <header className="sticky top-0 z-30 border-b border-surface-03 bg-surface-00/95 px-4 py-3 backdrop-blur-xl md:px-6">
        <div className="kds-pdv-inner flex w-full items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <Link to="/painel/kds" aria-label="Voltar ao KDS Principal" className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-surface-03 text-stone transition-colors hover:bg-surface-03 hover:text-cream">
              <ArrowLeft size={19} />
            </Link>
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.2em] text-gold"><MonitorSmartphone size={14} /> Atendimento no balcão</div>
              <h1 className="truncate text-xl font-black md:text-2xl">KDS PDV</h1>
              <p className="hidden text-sm text-stone sm:block">Monte e envie pedidos rapidamente pelo tablet.</p>
            </div>
          </div>
          <div className="hidden items-center gap-3 text-xs text-stone md:flex">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-surface-03 px-3 py-2"><ShoppingCart size={14} className="text-gold" /> Catálogo integrado</span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-surface-03 px-3 py-2"><BadgeCheck size={14} className="text-emerald-300" /> Pedido seguro</span>
          </div>
        </div>
      </header>
      <div className="kds-pdv-inner grid w-full gap-5 px-3 py-4 md:px-6 md:py-6 lg:grid-cols-[minmax(0,1fr)_280px]">
        <section className="min-w-0 overflow-hidden rounded-2xl border border-surface-03 bg-surface-01 shadow-2xl"><ManualOrderComposer mode="pos" /></section>
        <aside className="hidden space-y-4 lg:block">
          <div className="rounded-2xl border border-gold/20 bg-gold/10 p-5">
            <ReceiptText className="mb-3 text-gold" size={22} />
            <h2 className="font-black">Como funciona</h2>
            <ol className="mt-3 space-y-3 text-sm text-stone">
              <li><strong className="text-cream">1.</strong> Selecione o cliente ou cadastre rapidamente.</li>
              <li><strong className="text-cream">2.</strong> Escolha os produtos e personalize o pedido.</li>
              <li><strong className="text-cream">3.</strong> Confira, imprima e confirme o pagamento.</li>
            </ol>
          </div>
          <div className="rounded-2xl border border-surface-03 bg-surface-02 p-5 text-sm text-stone"><p className="font-bold text-cream">Fluxo conectado</p><p className="mt-2">Os pedidos enviados aparecem automaticamente no KDS Principal e seguem para a operação da cozinha.</p></div>
        </aside>
      </div>
    </main>
  );
}
