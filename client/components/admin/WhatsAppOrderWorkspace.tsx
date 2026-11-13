import { useEffect, useState } from "react";
import { ClipboardList, History, Menu, UserRound } from "lucide-react";
import ManualOrderComposer from "./ManualOrderComposer";
import {
  customersApi,
  type ApiAgenteWhatsAppSession,
  type ApiCustomer,
  type ApiCustomerOrder,
  type ApiOrder,
} from "@/lib/api";

type WorkspaceTab = "order" | "catalog" | "history";

function money(value: number) {
  return Number(value || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default function WhatsAppOrderWorkspace({
  session,
  onCreated,
}: {
  session: ApiAgenteWhatsAppSession;
  onCreated?: (order: ApiOrder) => void;
}) {
  const [tab, setTab] = useState<WorkspaceTab>("order");
  const [customer, setCustomer] = useState<ApiCustomer | null>(null);
  const [orders, setOrders] = useState<ApiCustomerOrder[]>([]);
  const [loadingCustomer, setLoadingCustomer] = useState(true);
  const [historyError, setHistoryError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoadingCustomer(true);
    setCustomer(null);
    setOrders([]);
    setHistoryError("");
    const resolve = async () => {
      try {
        const identity = session.customer_id
          ? { customer: await customersApi.get(session.customer_id) }
          : session.phone
            ? await customersApi.findIdentityByPhone(session.phone)
            : null;
        if (!cancelled && identity?.customer) setCustomer(identity.customer);
      } catch (error) {
        if (!cancelled) setHistoryError(error instanceof Error ? error.message : "Não foi possível identificar o cliente.");
      } finally {
        if (!cancelled) setLoadingCustomer(false);
      }
    };
    void resolve();
    return () => { cancelled = true; };
  }, [session.customer_id, session.phone]);

  useEffect(() => {
    if (tab !== "history" || !customer) return;
    let cancelled = false;
    setHistoryError("");
    void customersApi.getOrders(customer.id).then((value) => {
      if (!cancelled) setOrders(value);
    }).catch((error) => {
      if (!cancelled) setHistoryError(error instanceof Error ? error.message : "Não foi possível carregar o histórico.");
    });
    return () => { cancelled = true; };
  }, [customer, tab]);

  return (
    <section className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden border-l border-surface-03 bg-surface-00 text-cream" aria-label="Pedido do cliente">
      <header className="shrink-0 border-b border-surface-03 p-3">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-gold">Atendimento integrado</p>
            <h2 className="truncate text-lg font-black">Pedido do cliente</h2>
          </div>
          <div className="flex items-center gap-2 text-xs text-stone">
            <UserRound size={14} />
            <span className="truncate">{loadingCustomer ? "Identificando..." : customer?.name || session.phone}</span>
          </div>
        </div>
        <nav className="mt-3 grid grid-cols-3 gap-1 rounded-xl bg-surface-01 p-1" aria-label="Área comercial">
          {([
            ["order", "Pedido", ClipboardList],
            ["catalog", "Cardápio", Menu],
            ["history", "Histórico", History],
          ] as const).map(([value, label, Icon]) => (
            <button key={value} type="button" onClick={() => setTab(value)} className={`flex min-h-10 items-center justify-center gap-1 rounded-lg px-2 text-xs font-bold ${tab === value ? "bg-gold text-black" : "text-stone hover:text-cream"}`}>
              <Icon size={14} /> {label}
            </button>
          ))}
        </nav>
      </header>
      {tab === "history" ? (
        <div className="min-h-0 flex-1 space-y-2 overflow-y-auto overscroll-contain p-3">
          {!customer && <p className="rounded-xl bg-amber-500/10 p-3 text-sm text-amber-200">Cliente ainda não identificado pelo telefone.</p>}
          {historyError && <p role="alert" className="rounded-xl bg-red-500/10 p-3 text-sm text-red-200">{historyError}</p>}
          {customer && !orders.length && !historyError && <p className="py-8 text-center text-sm text-stone">Nenhum pedido anterior encontrado.</p>}
          {orders.map((order) => (
            <article key={order.id} className="rounded-xl border border-surface-03 bg-surface-01 p-3">
              <div className="flex items-center justify-between gap-2"><strong>{new Date(order.created_at).toLocaleDateString("pt-BR")}</strong><span className="font-bold text-gold">{money(order.total)}</span></div>
              <p className="mt-1 text-xs text-stone">{order.status} · {order.delivery_city || "Retirada"}</p>
              <p className="mt-2 text-sm text-parchment">{order.items.map((item) => `${item.quantity}x ${item.selected_size || "item"}`).join(" · ")}</p>
            </article>
          ))}
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
          <ManualOrderComposer
            key={`${session.id}:${tab}`}
            mode="embedded"
            defaultStep={tab === "catalog" ? 1 : 2}
            initialCustomer={customer}
            storageScope={`whatsapp:${session.id}`}
            onCreated={onCreated}
          />
        </div>
      )}
    </section>
  );
}
