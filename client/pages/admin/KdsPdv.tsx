import { ArrowLeft, BadgeCheck, CalendarDays, Clock3, MonitorSmartphone, ReceiptText, ShoppingCart, Store, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import ManualOrderComposer from "@/components/admin/ManualOrderComposer";
import KdsBrandLogo from "@/components/kds/KdsBrandLogo";
import KdsSessionActions from "@/components/kds/KdsSessionActions";

type AdminUser = { name?: string; email?: string; role_name?: string };

function readAdminUser(): AdminUser {
  try {
    return JSON.parse(localStorage.getItem("admin_user") ?? "{}") as AdminUser;
  } catch {
    return {};
  }
}

export default function KdsPdv() {
  const [now, setNow] = useState(() => new Date());
  const [operator] = useState(readAdminUser);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1_000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <main className="kds-pdv w-full bg-surface-00 text-cream">
      <header className="kds-pdv-header sticky top-0 z-30 border-b border-surface-03 bg-surface-00/95 px-3 py-3 backdrop-blur-xl sm:px-4 md:px-6">
        <div className="kds-pdv-inner flex w-full flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <Link to="/painel/kds" aria-label="Voltar ao KDS Principal" className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-surface-03 text-stone transition-colors hover:bg-surface-03 hover:text-cream"><ArrowLeft size={19} /></Link>
            <KdsBrandLogo className="h-11 w-16 shrink-0 object-contain sm:h-14 sm:w-20" fallback={<Store size={32} className="shrink-0 text-gold" />} />
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.16em] text-gold"><MonitorSmartphone size={14} /> Atendimento no balcão</div>
              <h1 className="truncate text-xl font-black md:text-2xl">KDS PDV</h1>
              <p className="hidden text-sm text-stone sm:block">Monte e envie pedidos rapidamente pelo tablet.</p>
            </div>
          </div>
          <div className="kds-pdv-session flex min-w-0 flex-1 flex-wrap items-center justify-end gap-2 text-xs text-stone sm:gap-3">
            <div className="hidden items-center gap-2 rounded-xl border border-surface-03 bg-surface-01 px-2 py-2 sm:flex sm:px-3"><UserRound size={16} className="text-gold" /><span className="max-w-28 truncate font-bold text-cream sm:max-w-36">{operator.name || operator.email || "Operador"}</span><span className="hidden text-stone md:inline">· Balcão</span></div>
            <div className="hidden items-center gap-2 rounded-xl border border-surface-03 bg-surface-01 px-3 py-2 sm:flex"><CalendarDays size={15} className="text-gold" /><span>{now.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" })}</span><Clock3 size={15} className="text-gold" /><span className="tabular-nums">{now.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}</span></div>
            <span className="hidden items-center gap-1.5 rounded-full border border-surface-03 px-3 py-2 xl:inline-flex"><ShoppingCart size={14} className="text-gold" /> Catálogo integrado</span>
            <span className="hidden items-center gap-1.5 rounded-full border border-surface-03 px-3 py-2 xl:inline-flex"><BadgeCheck size={14} className="text-emerald-300" /> Pedido seguro</span>
            <KdsSessionActions />
          </div>
        </div>
      </header>
      <div className="kds-pdv-workspace kds-pdv-inner grid w-full gap-5 px-2 py-3 sm:px-3 md:px-6 md:py-5 lg:grid-cols-[minmax(0,1fr)_280px]">
        <section className="kds-pdv-frame min-w-0 rounded-2xl border border-surface-03 bg-surface-01 shadow-2xl"><ManualOrderComposer mode="pos" /></section>
        <aside className="hidden space-y-4 lg:block">
          <div className="rounded-2xl border border-gold/20 bg-gold/10 p-5"><ReceiptText className="mb-3 text-gold" size={22} /><h2 className="font-black">Como funciona</h2><ol className="mt-3 space-y-3 text-sm text-stone"><li><strong className="text-cream">1.</strong> Selecione o cliente ou cadastre rapidamente.</li><li><strong className="text-cream">2.</strong> Escolha os produtos e personalize o pedido.</li><li><strong className="text-cream">3.</strong> Confira, imprima e confirme o pagamento.</li></ol></div>
          <div className="rounded-2xl border border-surface-03 bg-surface-02 p-5 text-sm text-stone"><p className="font-bold text-cream">Fluxo conectado</p><p className="mt-2">Os pedidos enviados aparecem automaticamente no KDS Principal e seguem para a operação da cozinha.</p></div>
        </aside>
      </div>
    </main>
  );
}
