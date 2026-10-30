import { orderDisplayCode } from "@/lib/orderIdentity";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, ChevronLeft, ChevronRight, CreditCard, Loader2, Plus, Printer, Search, ShoppingBag, Store, Trash2, Truck, UserRound, X } from "lucide-react";
import Product from "@/pages/Product";
import { ApiRequestError, customersApi, manualOrdersApi, ordersApi, paymentsApi, productsApi, isAssetUrl, resolveOptimizedAssetUrl, type ApiCustomer, type ApiOrder, type ApiProduct, type ManualOrderIn, type ManualOrderQuote, type PartnerOrderOrigin } from "@/lib/api";
import { readStoredAdminSession } from "@/lib/adminSession";
import { canCreateManualOrder, configuredManualLine, newManualOrderKey, type ManualCartLine } from "@/lib/manualOrder";
import { readPlatformSupportSession } from "@/lib/platformSupportSession";
import { printOrder } from "@/lib/printing";
import { PARTNER_ORIGIN_OPTIONS, isPartnerOrigin } from "@/lib/partnerIdentification";
import PartnerOrderIdentity from "./PartnerOrderIdentity";
import type { MultiFlavorsConfig } from "@/context/AppContext";

type Draft = {
  key: string; lines: ManualCartLine[]; customer: Pick<ApiCustomer, "id" | "name" | "phone"> | null;
  orderOrigin: PartnerOrderOrigin; partnerOrderNumber: string;
  fulfillment: "delivery" | "pickup"; phone: string; street: string; city: string; neighborhood: string; zip: string; complement: string;
  method: ManualOrderIn["payment_method"]; paymentStatus: "pending" | "paid"; collection: "cash" | "card";
  cashFor: string; coupon: string; submission?: ManualOrderIn;
};
const input = "min-h-12 w-full rounded-xl border border-surface-03 bg-surface-01 px-3 py-3 text-base text-cream outline-none focus:border-gold";
const button = "inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-gold px-4 py-3 font-bold text-black disabled:opacity-40";
const money = (amount: number) => amount.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const errorText = (error: unknown) => error instanceof Error ? error.message : "Não foi possível concluir a operação.";
const methods: Record<ManualOrderIn["payment_method"], string> = { pix: "Pix", cash: "Dinheiro", credit_card: "Cartão de crédito", debit_card: "Cartão de débito", pay_on_delivery: "Pagamento na entrega / retirada" };

function emptyDraft(): Draft {
  return { key: newManualOrderKey(), lines: [], customer: null, orderOrigin: "own", partnerOrderNumber: "", fulfillment: "delivery", phone: "", street: "", city: "", neighborhood: "", zip: "", complement: "", method: "cash", paymentStatus: "pending", collection: "cash", cashFor: "", coupon: "" };
}

function draftStorageKey() {
  const user = readStoredAdminSession() as (ReturnType<typeof readStoredAdminSession> & { tenant_id?: string });
  const tenant = readPlatformSupportSession()?.tenant_id || user?.tenant_id || window.location.hostname;
  const token = localStorage.getItem("admin_token") || "";
  const session = Array.from(token).reduce((hash, value) => ((hash * 31) + value.charCodeAt(0)) >>> 0, 0).toString(36);
  return `telz:manual-order:${window.location.hostname}:${tenant}:${user?.id || "operator"}:${session}`;
}

function readDraft(): Draft {
  try {
    const saved = JSON.parse(sessionStorage.getItem(draftStorageKey()) || "null") as Draft | null;
    if (saved?.key && Array.isArray(saved.lines)) return { ...emptyDraft(), ...saved };
  } catch { /* A bad or unavailable cache cannot stop a new operator sale. */ }
  return emptyDraft();
}

export default function ManualOrderComposer({ onCreated, mode = "default" }: { onCreated?: (order: ApiOrder) => void; mode?: "default" | "pos" }) {
  const [draft, setDraft] = useState<Draft>(readDraft);
  const [storageKey] = useState(draftStorageKey);
  const [sessionChanged, setSessionChanged] = useState(false);
  const [step, setStep] = useState(mode === "pos" ? 1 : 0);
  const [catalog, setCatalog] = useState<ApiProduct[]>([]);
  const [customers, setCustomers] = useState<ApiCustomer[]>([]);
  const [flavorConfig, setFlavorConfig] = useState<MultiFlavorsConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [customerQuery, setCustomerQuery] = useState("");
  const [newName, setNewName] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [selectedProduct, setSelectedProduct] = useState<string | null>(null);
  const [quote, setQuote] = useState<{ signature: string; value: ManualOrderQuote } | null>(null);
  const [quoteError, setQuoteError] = useState("");
  const [created, setCreated] = useState<ApiOrder | null>(null);
  const [printed, setPrinted] = useState(false);
  const [paymentBusy, setPaymentBusy] = useState(false);
  const [paymentError, setPaymentError] = useState("");
  const submitting = useRef(false);
  const allowed = useMemo(() => {
    try { return canCreateManualOrder(JSON.parse(localStorage.getItem("admin_permissions") || "null")); } catch { return false; }
  }, []);
  const locked = busy || !!draft.submission;
  const patch = (values: Partial<Draft>) => setDraft((current) => ({ ...current, ...values }));

  async function load() {
    setLoading(true); setLoadError("");
    const results = await Promise.allSettled([productsApi.list(true, undefined, "delivery"), customersApi.list(), productsApi.getMultiFlavorsConfig()]);
    if (draftStorageKey() !== storageKey) { setSessionChanged(true); return; }
    if (results[0].status === "fulfilled") setCatalog(results[0].value);
    if (results[1].status === "fulfilled") setCustomers(results[1].value);
    if (results[2].status === "fulfilled") { const value = results[2].value; setFlavorConfig({ maxFlavors: value.max_flavors, pricingRule: value.pricing_rule, flavorCategoryFilters: value.flavor_category_filters ?? [] }); }
    const failures = results.filter((result) => result.status === "rejected");
    if (failures.length) setLoadError("Não foi possível carregar catálogo e clientes. Tente novamente.");
    setLoading(false);
  }
  useEffect(() => { if (allowed) void load(); }, [allowed]);
  useEffect(() => {
    if (created || draftStorageKey() !== storageKey) return;
    try { sessionStorage.setItem(storageKey, JSON.stringify(draft)); } catch { /* In-memory draft remains usable. */ }
  }, [draft, created]);

  const payload: ManualOrderIn | null = useMemo(() => {
    if (!draft.customer || !draft.phone.trim() || !draft.lines.length) return null;
    if (draft.fulfillment === "delivery" && (!draft.street.trim() || !draft.city.trim())) return null;
    if (isPartnerOrigin(draft.orderOrigin) && !draft.partnerOrderNumber.trim()) return null;
    return {
      customer_id: draft.customer.id, sales_channel: "counter", fulfillment_type: draft.fulfillment,
      order_origin: draft.orderOrigin,
      partner_order_number: isPartnerOrigin(draft.orderOrigin) ? draft.partnerOrderNumber.trim() : null,
      items: draft.lines.map((line) => line.item),
      delivery: { name: draft.customer.name, phone: draft.phone, street: draft.fulfillment === "pickup" ? "Retirada no local" : draft.street, city: draft.fulfillment === "pickup" ? "Retirada" : draft.city, neighborhood: draft.neighborhood || undefined, zip_code: draft.zip || undefined, complement: draft.complement || undefined, is_pickup: draft.fulfillment === "pickup" },
      // Manual orders are created pending; payment is confirmed after printing.
      payment_method: draft.method, payment_status: "pending",
      delivery_payment_method: draft.method === "pay_on_delivery" ? draft.collection : null,
      cash_needs_change: (draft.method === "cash" || (draft.method === "pay_on_delivery" && draft.collection === "cash")) && !!draft.cashFor,
      cash_change_for: draft.cashFor && (draft.method === "cash" || (draft.method === "pay_on_delivery" && draft.collection === "cash")) ? Number(draft.cashFor.replace(",", ".")) : null,
      coupon_code: draft.coupon.trim() || undefined,
    };
  }, [draft]);
  const signature = payload ? JSON.stringify(payload) : "";
  useEffect(() => {
    if (!payload || draft.submission || created) return;
    let cancelled = false;
    setQuoteError("");
    const timer = window.setTimeout(() => {
      manualOrdersApi.quote(payload).then((value) => { if (!cancelled) setQuote({ signature, value }); })
        .catch((caught) => { if (!cancelled) { setQuote(null); setQuoteError(errorText(caught)); } });
    }, 350);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [signature, draft.submission, created]);
  const currentQuote = quote?.signature === signature ? quote.value : null;
  const categories = useMemo(() => [...new Set(catalog.map((product) => product.category).filter((value): value is string => !!value))], [catalog]);
  const filteredProducts = catalog.filter((product) => (!category || product.category === category) && `${product.name} ${product.description}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  const filteredCustomers = customerQuery.trim() ? customers.filter((customer) => `${customer.name} ${customer.phone || ""}`.toLocaleLowerCase().includes(customerQuery.toLocaleLowerCase()) || (customerQuery.replace(/\D/g, "").length > 2 && (customer.phone || "").replace(/\D/g, "").includes(customerQuery.replace(/\D/g, "")))).slice(0, 15) : [];

  function selectCustomer(customer: ApiCustomer) {
    const address = customer.addresses?.find((value) => value.is_default) || customer.addresses?.[0];
    patch({ customer: { id: customer.id, name: customer.name, phone: customer.phone }, phone: customer.phone || "", street: address ? [address.street, address.number].filter(Boolean).join(", ") : "", city: address?.city || "", neighborhood: address?.neighborhood || "", zip: address?.zip_code || "", complement: address?.complement || "" });
    setCustomerQuery("");
    setStep(1);
  }
  async function createCustomer() {
    if (draftStorageKey() !== storageKey) { setSessionChanged(true); return; }
    setBusy(true); setError("");
    try { const customer = await customersApi.createAdmin({ name: newName, phone: newPhone }); setCustomers((items) => [...items, customer]); selectCustomer(customer); setNewName(""); setNewPhone(""); }
    catch (caught) { setError(errorText(caught)); }
    finally { setBusy(false); }
  }
  async function submit() {
    if (draftStorageKey() !== storageKey) { setSessionChanged(true); return; }
    if (submitting.current || (!draft.submission && (!payload || !currentQuote))) return;
    const body = draft.submission || { ...payload!, expected_total: currentQuote!.total, items: payload!.items.map((item, index) => ({ ...item, final_price: currentQuote!.items[index].unit_price })) };
    submitting.current = true; setBusy(true); setError("");
    patch({ submission: body });
    // Persist before network I/O, so refresh/retry uses the exact same request/key.
    try { sessionStorage.setItem(storageKey, JSON.stringify({ ...draft, submission: body })); } catch { /* Key remains stable for this mounted session. */ }
    try {
      const order = await manualOrdersApi.create(body, draft.key);
      setCreated(order); try { sessionStorage.removeItem(storageKey); } catch { /* The confirmed order remains visible. */ } onCreated?.(order);
    } catch (caught) {
      setError(errorText(caught));
      if (caught instanceof ApiRequestError && caught.status >= 400 && caught.status < 500 && caught.status !== 409) {
        patch({ submission: undefined, key: newManualOrderKey() });
      }
    } finally { submitting.current = false; setBusy(false); }
  }

  if (!allowed) return <p role="alert" className="p-6 text-amber-200">Seu perfil não possui permissão para criar pedidos.</p>;
  if (sessionChanged) return <p role="alert" className="p-6 text-amber-200">A sessão ou empresa mudou. Feche e abra novamente o atendimento.</p>;
  if (created) {
    const payOnDelivery = Boolean(created.pay_on_delivery);
    const paymentReceived = ["paid", "approved"].includes(created.payment_status || "");
    async function confirmPayment() {
      if (!printed || paymentBusy || paymentReceived || payOnDelivery) return;
      setPaymentBusy(true); setPaymentError("");
      try {
        await paymentsApi.approve(created.id);
        setCreated(await ordersApi.get(created.id));
      } catch (caught) {
        setPaymentError(errorText(caught));
      } finally { setPaymentBusy(false); }
    }
    return <section className="space-y-5 p-6 text-center"><CheckCircle2 size={56} className="mx-auto text-emerald-300" /><h2 className="text-2xl font-black">Pedido #{orderDisplayCode(created)} finalizado</h2><p>{created.delivery_name} - {money(created.total)}</p><p>Situação do pedido: <strong>{["paid", "pago"].includes(created.status) ? "Confirmado — aguardando preparo" : created.status}</strong></p><p>Situação do pagamento: <strong>{paymentReceived ? "Recebido" : payOnDelivery ? "Pendente — receber na entrega" : "Pendente"}</strong></p>{created.cash_change_amount != null && <p className="text-xl font-bold text-gold">Troco: {money(created.cash_change_amount)}</p>}<p className="text-sm text-stone">{payOnDelivery ? "O pedido segue para a cozinha. O motoboy confirma o recebimento na entrega." : "Imprima o pedido antes de confirmar o pagamento."}</p>{paymentError && <p role="alert" className="rounded-xl bg-red-500/10 p-4 text-red-200">{paymentError}</p>}<div className="flex flex-wrap justify-center gap-3"><button type="button" className={button} onClick={() => { if (printOrder(created)) setPrinted(true); }}><Printer size={18} /> {printed ? "Imprimir novamente" : "Imprimir pedido"}</button>{!payOnDelivery && <button type="button" className={button} disabled={!printed || paymentBusy || paymentReceived} onClick={() => void confirmPayment()}>{paymentBusy ? <Loader2 className="animate-spin" size={18} /> : <CheckCircle2 size={18} />}{paymentReceived ? "Pagamento confirmado" : "Confirmar pagamento"}</button>}</div><div><button type="button" className="py-3 text-gold" onClick={() => { setDraft(emptyDraft()); setCreated(null); setPrinted(false); setPaymentError(""); setStep(0); }}>Novo pedido</button><Link to="/painel/orders" className="ml-4 inline-block py-3 text-gold">Ver Operacoes</Link></div></section>;
  }
  if (selectedProduct && flavorConfig) return <Product productId={selectedProduct} catalog={catalog} flavorConfig={flavorConfig} embedded onBack={() => setSelectedProduct(null)} onAdd={(...args) => { patch({ lines: [...draft.lines, configuredManualLine(args, newManualOrderKey())] }); setSelectedProduct(null); }} />;

  if (mode === "pos") return <section className="flex min-h-[calc(100vh-6rem)] min-w-0 flex-col bg-surface-00 text-cream" aria-label="KDS PDV">
    <div className="grid min-h-0 flex-1 lg:grid-cols-[76px_minmax(0,1fr)_380px] xl:grid-cols-[88px_minmax(0,1fr)_430px]">
      <aside className="hidden flex-col items-center border-r border-surface-03 bg-surface-01 py-5 lg:flex">
        <div className="grid h-11 w-11 place-items-center rounded-2xl bg-gold text-black shadow-lg shadow-gold/20"><Store size={21} /></div>
        <nav className="mt-8 flex flex-1 flex-col items-center gap-3" aria-label="Atalhos do PDV"><button type="button" className="grid h-14 w-14 place-items-center rounded-2xl bg-gold text-black" aria-label="Novo pedido"><ShoppingBag size={20} /></button><button type="button" className="grid h-14 w-14 place-items-center rounded-2xl text-stone transition-colors hover:bg-surface-02 hover:text-cream" aria-label="Buscar clientes"><UserRound size={19} /></button></nav>
        <span className="mb-2 text-[9px] font-black uppercase tracking-[0.2em] text-stone [writing-mode:vertical-rl]">Balcão</span>
      </aside>
      <div className="min-w-0 overflow-y-auto p-4 md:p-6 xl:p-8">
        <div className="mb-5 flex flex-wrap items-end justify-between gap-3"><div><p className="text-[10px] font-black uppercase tracking-[0.24em] text-gold">Atendimento no balcão</p><h2 className="mt-1 text-2xl font-black tracking-tight md:text-3xl">Novo pedido</h2><p className="mt-1 text-sm text-stone">Escolha os produtos e monte o pedido do cliente.</p></div><div className="flex rounded-xl border border-surface-03 bg-surface-01 p-1"><button type="button" onClick={() => patch({ fulfillment: "pickup" })} className={`flex min-h-11 items-center gap-2 rounded-lg px-3 text-sm font-bold ${draft.fulfillment === "pickup" ? "bg-gold text-black" : "text-stone"}`}><Store size={16} /> Retirada</button><button type="button" onClick={() => patch({ fulfillment: "delivery" })} className={`flex min-h-11 items-center gap-2 rounded-lg px-3 text-sm font-bold ${draft.fulfillment === "delivery" ? "bg-gold text-black" : "text-stone"}`}><Truck size={16} /> Entrega</button></div></div>
        {loadError && <div role="alert" className="mb-4 rounded-xl bg-red-500/10 p-4 text-red-200">{loadError} <button type="button" className="underline" onClick={() => void load()}>Tentar novamente</button></div>}
        {error && <p role="alert" className="mb-4 rounded-xl border border-red-400/40 bg-red-500/10 p-4 text-red-200">{error}</p>}
        <label className="relative block"><Search className="absolute left-4 top-1/2 -translate-y-1/2 text-stone" size={18} /><input aria-label="Pesquisar produtos" className="min-h-14 w-full rounded-2xl border border-surface-03 bg-surface-01 pl-12 pr-4 text-base text-cream outline-none transition-colors placeholder:text-stone/70 focus:border-gold" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar no cardápio..." /></label>
        <div className="mt-4 flex gap-2 overflow-x-auto pb-2">{["", ...categories].map((value) => <button type="button" key={value} onClick={() => setCategory(value)} className={`min-h-11 shrink-0 rounded-xl border px-4 text-sm font-bold transition-colors ${category === value ? "border-gold bg-gold text-black" : "border-surface-03 bg-surface-01 text-stone hover:border-gold/50 hover:text-cream"}`}>{value || "Todos"}</button>)}</div>
        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">{filteredProducts.map((product) => <button type="button" key={product.id} disabled={product.inventory_available === false} onClick={() => setSelectedProduct(product.id)} className="group min-w-0 overflow-hidden rounded-2xl border border-surface-03 bg-surface-01 p-2 text-left transition-all hover:-translate-y-0.5 hover:border-gold/60 hover:bg-surface-02 disabled:opacity-40"><div className="flex aspect-[1.25] items-center justify-center overflow-hidden rounded-xl bg-surface-02">{isAssetUrl(product.icon) ? <img src={resolveOptimizedAssetUrl(product.icon, 256)} alt="" className="h-full w-full object-contain transition-transform group-hover:scale-105" loading="lazy" /> : <span className="text-5xl transition-transform group-hover:scale-105">{product.icon}</span>}</div><div className="px-2 pb-2 pt-3"><strong className="block truncate text-sm font-black">{product.name}</strong><span className="mt-1 block text-xs text-stone">{product.inventory_available === false ? "Indisponível" : "Configurar produto"}</span></div></button>)}</div>
        {!filteredProducts.length && !loading && <p className="py-12 text-center text-stone">Nenhum produto nesta seleção.</p>}{loading && <p role="status" className="mt-6 flex items-center justify-center gap-2 text-stone"><Loader2 className="animate-spin" size={18} /> Carregando catálogo...</p>}
      </div>
      <aside className="flex min-h-0 flex-col border-t border-surface-03 bg-surface-01 lg:border-l lg:border-t-0">
        <div className="border-b border-surface-03 px-5 py-5"><div className="flex items-center justify-between"><div><p className="text-[10px] font-black uppercase tracking-[0.2em] text-gold">Pedido atual</p><h2 className="mt-1 text-xl font-black">Balcão</h2></div><span className="rounded-full bg-surface-02 px-3 py-1 text-xs font-bold text-stone">{draft.lines.reduce((total, line) => total + line.item.quantity, 0)} itens</span></div></div>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-5">
          <label className="block text-xs font-bold uppercase tracking-wide text-stone">Cliente<input className={`${input} mt-2`} value={customerQuery} onChange={(event) => setCustomerQuery(event.target.value)} placeholder="Nome ou telefone" /></label>
          {customerQuery && <div className="max-h-36 space-y-1 overflow-y-auto">{filteredCustomers.length ? filteredCustomers.map((customer) => <button type="button" key={customer.id} onClick={() => selectCustomer(customer)} className="flex min-h-12 w-full items-center justify-between gap-2 rounded-xl border border-surface-03 px-3 text-left text-sm hover:border-gold/50"><strong className="truncate">{customer.name}</strong><span className="shrink-0 text-xs text-stone">{customer.phone}</span></button>) : <p className="text-xs text-stone">Nenhum cliente encontrado.</p>}</div>}
          {!draft.customer && <details className="rounded-xl border border-dashed border-surface-03 px-3 py-2"><summary className="cursor-pointer text-xs font-bold text-gold">Cadastrar cliente rápido</summary><div className="mt-3 space-y-2"><input aria-label="Nome do novo cliente" className={input} value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="Nome" /><input aria-label="Telefone do novo cliente" className={input} value={newPhone} onChange={(event) => setNewPhone(event.target.value)} placeholder="Telefone" /><button type="button" disabled={!newName.trim() || !newPhone.trim()} className={`${button} w-full`} onClick={() => void createCustomer()}><Plus size={16} /> Cadastrar</button></div></details>}
          {draft.customer && <div className="flex items-center justify-between rounded-xl border border-gold/30 bg-gold/5 px-3 py-3 text-sm"><span className="min-w-0 truncate"><strong className="block">{draft.customer.name}</strong><span className="text-xs text-stone">{draft.phone}</span></span><button type="button" aria-label="Remover cliente" className="text-stone hover:text-cream" onClick={() => patch({ customer: null, phone: "" })}><X size={17} /></button></div>}
          <div className="space-y-2">{draft.lines.map((line, index) => <div key={line.id} className="rounded-xl border border-surface-03 bg-surface-02/60 p-3"><div className="flex items-start gap-2"><span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-gold/15 text-xs font-black text-gold">{line.item.quantity}</span><div className="min-w-0 flex-1"><strong className="block truncate text-sm">{line.name}</strong><p className="mt-1 truncate text-xs text-stone">{line.item.flavors.map((flavor) => flavor.name).join(" / ")} · {line.item.selected_size}</p>{currentQuote?.items[index] && <p className="mt-2 text-sm font-black text-gold">{money(currentQuote.items[index].line_total)}</p>}</div><button type="button" aria-label={`Remover ${line.name}`} className="text-stone hover:text-red-300" onClick={() => patch({ lines: draft.lines.filter((value) => value.id !== line.id) })}><Trash2 size={16} /></button></div></div>)}</div>
          {!draft.lines.length && <div className="rounded-xl border border-dashed border-surface-03 px-4 py-8 text-center text-sm text-stone"><ShoppingBag className="mx-auto mb-2 text-gold" size={24} />Seu pedido está vazio.<br />Toque em um produto para começar.</div>}
          {draft.fulfillment === "delivery" && <div className="space-y-2"><p className="text-xs font-bold uppercase tracking-wide text-stone">Endereço de entrega</p>{([['street', 'Endereço e número'], ['city', 'Cidade']] as const).map(([field, label]) => <input key={field} aria-label={label} className={input} value={draft[field]} onChange={(event) => patch({ [field]: event.target.value })} placeholder={label} />)}</div>}
          <label className="block text-xs font-bold uppercase tracking-wide text-stone">Pagamento<select className={`${input} mt-2`} value={draft.method} onChange={(event) => patch({ method: event.target.value as Draft["method"] })}>{Object.entries(methods).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>{quoteError && <p role="alert" className="rounded-xl bg-amber-500/10 p-3 text-xs text-amber-200">{quoteError}</p>}
        </div>
        <div className="border-t border-surface-03 bg-surface-00 p-5"><div className="mb-4 flex items-center justify-between"><span className="text-sm text-stone">Total do pedido</span><strong className="text-2xl font-black text-gold">{currentQuote ? money(currentQuote.total) : "—"}</strong></div><button type="button" disabled={busy || !currentQuote || !payload} className={`${button} w-full min-h-14 text-base`} onClick={() => void submit()}>{busy ? <Loader2 className="animate-spin" size={19} /> : <CreditCard size={19} />}{draft.submission ? "Tentar novamente" : "Finalizar pedido"}</button><p className="mt-3 text-center text-[11px] text-stone">O pagamento será confirmado após a impressão.</p></div>
      </aside>
    </div>
  </section>;

  return <section className="flex min-h-0 flex-col text-cream" aria-label="Criar pedido manual">
    <nav className="sticky top-0 z-10 grid grid-cols-3 gap-2 border-b border-surface-03 bg-surface-02 p-3" aria-label="Etapas do pedido">{["Cliente", "Produtos", "Pagamento"].map((label, index) => <button type="button" key={label} disabled={busy} aria-current={step === index ? "step" : undefined} onClick={() => setStep(index)} className={`min-h-12 rounded-xl px-2 font-bold ${step === index ? "bg-gold text-black" : "bg-surface-01 text-stone"}`}>{index + 1}. {label}</button>)}</nav>
    <div className="space-y-5 p-4 md:p-6">
      {loadError && <div role="alert" className="rounded-xl bg-red-500/10 p-4 text-red-200">{loadError} <button type="button" className="underline" onClick={() => void load()}>Tentar novamente</button></div>}
      {error && <p role="alert" className="rounded-xl border border-red-400/40 bg-red-500/10 p-4 text-red-200">{error}</p>}
      {draft.submission && <p role="status" className="rounded-xl bg-amber-500/10 p-4 text-amber-200">{busy ? "Confirmando pedido…" : "A confirmação ainda precisa ser consultada. Use Tentar novamente; os dados foram preservados para evitar duplicidade."}</p>}
      <fieldset disabled={locked || loading} className="min-w-0 space-y-4 disabled:opacity-70">
        {step === 0 && <>
          <h2 className="flex items-center gap-2 text-xl font-bold"><UserRound /> Cliente e atendimento</h2>
          <div className="space-y-3 rounded-2xl border border-gold/30 bg-gold/5 p-4">
            <label className="block text-sm font-bold">Origem do pedido<select aria-label="Origem do pedido" className={`${input} mt-2`} value={draft.orderOrigin} onChange={(event) => patch({ orderOrigin: event.target.value as PartnerOrderOrigin, partnerOrderNumber: "" })}>{PARTNER_ORIGIN_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}{option.value === "own" ? " · Gran Torino" : ""}</option>)}</select></label>
            <PartnerOrderIdentity order={{ order_origin: draft.orderOrigin, partner_order_number: isPartnerOrigin(draft.orderOrigin) ? draft.partnerOrderNumber || "número pendente" : null }} />
            {isPartnerOrigin(draft.orderOrigin) && <label className="block text-sm font-bold">Número do pedido no aplicativo<input aria-label="Número do pedido no aplicativo" required className={`${input} mt-2`} value={draft.partnerOrderNumber} onChange={(event) => patch({ partnerOrderNumber: event.target.value })} placeholder="Ex.: 123456789" /></label>}
            {isPartnerOrigin(draft.orderOrigin) && !draft.partnerOrderNumber.trim() && <p className="text-xs text-amber-200">Informe o número do pedido para continuar.</p>}
          </div>
          <label className="block text-sm">Pesquisar por nome ou telefone<input className={`${input} mt-2`} value={customerQuery} onChange={(event) => setCustomerQuery(event.target.value)} placeholder="Quem está fazendo o pedido?" /></label>
          {customerQuery && <div className="max-h-56 space-y-2 overflow-y-auto">{filteredCustomers.length ? filteredCustomers.map((customer) => <button type="button" key={customer.id} onClick={() => selectCustomer(customer)} className="flex min-h-14 w-full justify-between gap-3 rounded-xl border border-surface-03 p-3 text-left"><strong>{customer.name}</strong><span className="text-stone">{customer.phone}</span></button>) : <p className="p-3 text-stone">Nenhum cliente encontrado. Cadastre abaixo.</p>}</div>}
          {draft.customer && <div className="rounded-xl border border-emerald-400/30 bg-emerald-500/10 p-4"><strong>{draft.customer.name}</strong><label className="mt-3 block text-sm">Telefone do pedido<input className={`${input} mt-2`} type="tel" value={draft.phone} onChange={(event) => patch({ phone: event.target.value })} /></label></div>}
          {!draft.customer && <details className="rounded-xl border border-surface-03 p-4"><summary className="cursor-pointer font-bold">Cadastrar cliente rapidamente</summary><div className="mt-4 grid gap-3 sm:grid-cols-2"><input aria-label="Nome do novo cliente" className={input} value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="Nome" /><input aria-label="Telefone do novo cliente" className={input} type="tel" value={newPhone} onChange={(event) => setNewPhone(event.target.value)} placeholder="Telefone" /><button type="button" disabled={!newName.trim() || !newPhone.trim()} className={`${button} sm:col-span-2`} onClick={() => void createCustomer()}><Plus size={18} /> Cadastrar e selecionar</button></div></details>}
          <label className="block text-sm">Modalidade<select className={`${input} mt-2`} value={draft.fulfillment} onChange={(event) => patch({ fulfillment: event.target.value as Draft["fulfillment"] })}><option value="delivery">Entrega</option><option value="pickup">Retirada</option></select></label>
          <Link to="/painel/salao" className="inline-block min-h-12 py-3 text-gold underline">Consumo no local: abrir mesas e comandas</Link>
          {draft.fulfillment === "delivery" && <div className="grid gap-3 sm:grid-cols-2">{([['street', 'Endereço e número'], ['city', 'Cidade'], ['neighborhood', 'Bairro'], ['zip', 'CEP'], ['complement', 'Complemento']] as const).map(([field, label]) => <label key={field} className={`text-sm ${field === "street" ? "sm:col-span-2" : ""}`}>{label}<input className={`${input} mt-2`} value={draft[field]} onChange={(event) => patch({ [field]: event.target.value })} /></label>)}</div>}
        </>}
        {step === 1 && <>
          <h2 className="text-xl font-bold">Catálogo</h2><label className="relative block"><Search className="absolute left-3 top-4 text-stone" size={18} /><input aria-label="Pesquisar produtos" className={`${input} pl-10`} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Pizzas, bebidas e outros produtos" /></label>
          <div className="flex gap-2 overflow-x-auto pb-2">{["", ...categories].map((value) => <button type="button" key={value} onClick={() => setCategory(value)} className={`min-h-12 shrink-0 rounded-full border px-4 font-bold ${category === value ? "border-gold bg-gold text-black" : "border-surface-03"}`}>{value || "Todos"}</button>)}</div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">{filteredProducts.map((product) => <button type="button" key={product.id} disabled={product.inventory_available === false} onClick={() => setSelectedProduct(product.id)} className="flex min-h-44 flex-col items-center gap-3 rounded-2xl border border-surface-03 bg-surface-02 p-4 text-center disabled:opacity-40">{isAssetUrl(product.icon) ? <img src={resolveOptimizedAssetUrl(product.icon, 128)} alt="" className="h-20 w-20 object-contain" loading="lazy" /> : <span className="text-5xl">{product.icon}</span>}<strong>{product.name}</strong><span className="text-xs text-stone">{product.inventory_available === false ? "Indisponível" : "Configurar e consultar preço"}</span></button>)}</div>
          {!filteredProducts.length && !loading && <p className="py-8 text-center text-stone">Nenhum produto nesta seleção.</p>}
        </>}
        {step === 2 && <>
          <h2 className="text-xl font-bold">Conferência e pagamento</h2>
          {draft.lines.map((line, index) => <div key={line.id} className="rounded-xl border border-surface-03 p-4"><div className="flex justify-between gap-3"><strong>{line.item.quantity} × {line.name}</strong><button type="button" aria-label={`Remover ${line.name}`} className="min-h-12 min-w-12 rounded-lg text-red-300" onClick={() => patch({ lines: draft.lines.filter((value) => value.id !== line.id) })}><Trash2 size={18} /></button></div><p className="text-sm text-stone">{line.item.flavors.map((flavor) => flavor.name).join(" / ")} · {line.item.selected_size}</p>{line.item.notes && <p className="mt-2 text-amber-200">{line.item.notes}</p>}{currentQuote?.items[index] && <p className="mt-2 font-bold text-gold">{money(currentQuote.items[index].line_total)}</p>}</div>)}
          {!draft.lines.length && <p className="py-6 text-stone">Seu pedido está vazio. Selecione os produtos.</p>}
          <label className="block text-sm">Forma de pagamento<select className={`${input} mt-2`} value={draft.method} onChange={(event) => patch({ method: event.target.value as Draft["method"] })}>{Object.entries(methods).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          {draft.method === "pay_on_delivery" && <label className="block text-sm">Como será recebido<select className={`${input} mt-2`} value={draft.collection} onChange={(event) => patch({ collection: event.target.value as Draft["collection"] })}><option value="cash">Dinheiro</option><option value="card">Cartão</option></select></label>}
          <p className="rounded-xl bg-surface-02 p-4 text-sm text-stone">O pagamento sera confirmado depois da impressao do pedido.</p>
          {(draft.method === "cash" || (draft.method === "pay_on_delivery" && draft.collection === "cash")) && <label className="block text-sm">Valor entregue para troco (opcional)<input className={`${input} mt-2`} inputMode="decimal" value={draft.cashFor} onChange={(event) => patch({ cashFor: event.target.value })} placeholder="Ex.: 100,00" /></label>}
          <label className="block text-sm">Cupom (opcional)<input className={`${input} mt-2`} value={draft.coupon} onChange={(event) => patch({ coupon: event.target.value })} /></label>
          <div className="space-y-2 rounded-xl bg-surface-02 p-4"><p>Cliente: <strong>{draft.customer?.name || "Selecione o cliente"}</strong></p><p>{draft.fulfillment === "pickup" ? "Retirada" : "Entrega"} · {methods[draft.method]}</p><p className="font-bold">Pagamento sera confirmado apos a impressao</p>{currentQuote && <><p>Produtos: {money(currentQuote.subtotal)}</p><p>Entrega: {money(currentQuote.delivery_fee_final)}</p><p>Desconto: {money(currentQuote.discount || 0)}</p>{currentQuote.cash_change_amount != null && <p className="text-xl font-bold text-gold">Troco: {money(currentQuote.cash_change_amount)}</p>}</>}</div>
        </>}
      </fieldset>
      {loading && <p role="status" className="flex items-center gap-2 text-stone"><Loader2 className="animate-spin" size={18} /> Carregando catálogo e clientes…</p>}
      {quoteError && <p role="alert" className="rounded-xl bg-amber-500/10 p-4 text-amber-200">{quoteError}</p>}
    </div>
    <footer className="sticky bottom-0 z-20 flex flex-wrap items-center justify-between gap-3 border-t border-surface-03 bg-surface-00 p-4"><button type="button" disabled={busy} onClick={() => setStep(2)} className="flex min-h-12 items-center gap-2 text-left"><ShoppingBag className="text-gold" /><span><strong className="block">{draft.lines.reduce((total, line) => total + line.item.quantity, 0)} itens · {currentQuote ? money(currentQuote.total) : "Aguardando orçamento"}</strong><span className="text-xs text-stone">Carrinho e resumo</span></span></button><div className="flex gap-2">{step > 0 && <button type="button" aria-label="Etapa anterior" disabled={busy} onClick={() => setStep(step - 1)} className="min-h-12 rounded-xl border border-surface-03 px-3"><ChevronLeft /></button>}{step < 2 && !draft.submission ? <button type="button" disabled={busy} className={button} onClick={() => setStep(step + 1)}>Continuar <ChevronRight size={18} /></button> : <button type="button" disabled={busy || (!draft.submission && !currentQuote)} className={button} onClick={() => void submit()}>{busy ? <Loader2 className="animate-spin" size={18} /> : <CheckCircle2 size={18} />}{draft.submission ? "Tentar novamente" : "Finalizar pedido"}</button>}</div></footer>
  </section>;
}
