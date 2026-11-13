import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, Camera, CheckCircle2, FileUp, Loader2, RefreshCw, Send, X } from "lucide-react";
import { Link } from "react-router-dom";
import { printOrderApi, type ApiPrintOrderImport, type ApiPrintOrderReviewInput, type PrintOrderPlatform } from "@/lib/api";

const platformLabels: Record<PrintOrderPlatform, string> = { ifood: "iFood", "99food": "99Food", keeta: "Keeta", unknown: "Não identificada" };
const platformSelectClass = "mt-1 w-full rounded-lg border border-[var(--border-color)] bg-white p-3 text-slate-900 [color-scheme:light]";
const platformOptionClass = "bg-white text-slate-900";

export const PRINT_ORDER_REVIEW_FIELDS = [
  { name: "external_order_number", label: "Número original" },
  { name: "customer_name", label: "Cliente" },
  { name: "customer_phone", label: "Telefone" },
  { name: "delivery_street", label: "Endereço" },
  { name: "delivery_city", label: "Cidade" },
  { name: "delivery_complement", label: "Complemento" },
  { name: "payment_method", label: "Forma de pagamento" },
] as const;

export const PRINT_ORDER_FINANCIAL_FIELDS = [
  { name: "subtotal", label: "Subtotal" },
  { name: "delivery_fee", label: "Taxa de entrega" },
  { name: "service_fee", label: "Taxa de serviço" },
  { name: "store_discount", label: "Desconto da loja" },
  { name: "platform_discount", label: "Desconto da plataforma" },
  { name: "total_paid", label: "Valor pago pelo cliente" },
  { name: "printed_total", label: "Total impresso" },
] as const;

export function formatPrintOrderMoney(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "Não informado";
  const amount = Number(value);
  return Number.isFinite(amount) ? amount.toLocaleString("pt-BR", { style: "currency", currency: "BRL" }) : String(value);
}

export function parsePrintOrderFlavorNames(value: string): string[] {
  return value.split(",").map((name) => name.trim()).filter(Boolean);
}

function fieldValue(selected: ApiPrintOrderImport, name: string): string {
  const value = selected[name as keyof ApiPrintOrderImport];
  return value === null || value === undefined ? "" : String(value);
}

export default function PrintOrder() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [imports, setImports] = useState<ApiPrintOrderImport[]>([]);
  const [selected, setSelected] = useState<ApiPrintOrderImport | null>(null);
  const [platform, setPlatform] = useState<PrintOrderPlatform>("unknown");
  const [extractedText, setExtractedText] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    setLoading(true); setError("");
    try { setImports(await printOrderApi.list()); } catch (e) { setError(e instanceof Error ? e.message : "Não foi possível carregar as importações."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);

  async function capture(file: File) {
    setBusy(true); setError(""); setNotice("");
    try { const created = await printOrderApi.capture(file, platform, extractedText); setSelected(created); setNotice("Comanda recebida. Revise os dados antes de confirmar."); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Falha ao enviar a comanda."); }
    finally { setBusy(false); }
  }

  async function review(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selected) return;
    const data = new FormData(event.currentTarget);
    const itemNames = data.getAll("item_name").map(String).filter(Boolean);
    const itemIds = data.getAll("product_id").map(String);
    const value = (name: string) => String(data.get(name) || "") || null;
    const body: ApiPrintOrderReviewInput = {
      platform: String(data.get("platform") || "unknown") as PrintOrderPlatform,
      external_order_number: value("external_order_number"),
      customer_name: value("customer_name"),
      customer_phone: value("customer_phone"),
      delivery_street: value("delivery_street"),
      delivery_city: value("delivery_city"),
      delivery_complement: value("delivery_complement"),
      fulfillment_type: String(data.get("fulfillment_type") || selected.fulfillment_type || "delivery") as "delivery" | "pickup",
      payment_method: value("payment_method"),
      subtotal: value("subtotal"),
      delivery_fee: value("delivery_fee"),
      service_fee: value("service_fee"),
      store_discount: value("store_discount"),
      platform_discount: value("platform_discount"),
      total_paid: value("total_paid"),
      printed_total: value("printed_total"),
      items: itemNames.map((name, index) => ({ external_name: name, product_id: itemIds[index] || null, quantity: Number(data.getAll("quantity")[index] || 1), flavor_names: parsePrintOrderFlavorNames(String(data.getAll("flavor_names")[index] || "")), customizations: {} })),
    };
    setBusy(true); setError("");
    try { const updated = await printOrderApi.review(selected.id, body); setSelected(updated); setImports((rows) => rows.map((row) => row.id === updated.id ? updated : row)); setNotice(updated.status === "ready" ? "Revisão salva. O pedido pode ser confirmado." : "Revisão salva; ainda há campos críticos pendentes."); }
    catch (e) { setError(e instanceof Error ? e.message : "Falha ao salvar a revisão."); }
    finally { setBusy(false); }
  }

  async function confirm() {
    if (!selected || selected.status !== "ready") return;
    setBusy(true); setError("");
    try { const updated = await printOrderApi.confirm(selected.id, crypto.randomUUID()); setSelected(updated); setImports((rows) => rows.map((row) => row.id === updated.id ? updated : row)); setNotice(updated.order_id ? `Pedido confirmado: ${updated.order_id}` : "Importação processada."); }
    catch (e) { setError(e instanceof Error ? e.message : "Não foi possível confirmar o pedido."); }
    finally { setBusy(false); }
  }

  const active = useMemo(() => imports.filter((row) => ["awaiting_review", "ready"].includes(row.status)), [imports]);
  return <main className="min-h-screen bg-[var(--bg-main)] px-4 py-5 text-[var(--text-primary)] sm:px-6">
    <header className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-3 border-b border-[var(--border-color)] pb-4">
      <div><p className="text-xs font-bold uppercase tracking-[.18em] text-[var(--color-primary)]">Operações</p><h1 className="text-2xl font-black sm:text-3xl">Print Pedido</h1><p className="mt-1 text-sm text-[var(--text-secondary)]">Fotografe, revise e envie a comanda para o fluxo central do ERP.</p></div>
      <div className="flex gap-2"><Link to="/painel/orders" className="rounded-lg border border-[var(--border-color)] px-3 py-2 text-sm font-bold">Pedidos</Link><button onClick={() => void load()} className="rounded-lg border border-[var(--border-color)] p-2" aria-label="Atualizar"><RefreshCw size={18} /></button></div>
    </header>
    <section className="mx-auto mt-5 grid w-full max-w-6xl gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]">
      <div className="space-y-4">
        <div className="rounded-2xl border border-[var(--border-color)] bg-[var(--bg-card)] p-5 shadow-sm"><h2 className="text-lg font-black">Nova captura</h2><p className="mt-1 text-sm text-[var(--text-secondary)]">A leitura automática será usada quando a IA multimodal ou o OCR estiver configurado. Nunca inventamos dados.</p><div className="mt-4 grid gap-3 sm:grid-cols-2"><label className="text-sm font-bold">Plataforma<select value={platform} onChange={(e) => setPlatform(e.target.value as PrintOrderPlatform)} className={platformSelectClass}><option className={platformOptionClass} value="unknown">Identificar depois</option><option className={platformOptionClass} value="ifood">iFood</option><option className={platformOptionClass} value="99food">99Food</option><option className={platformOptionClass} value="keeta">Keeta</option></select></label><label className="text-sm font-bold">Texto extraído (opcional)<textarea value={extractedText} onChange={(e) => setExtractedText(e.target.value)} placeholder="Cole OCR apenas se já tiver sido feito" className="mt-1 min-h-12 w-full rounded-lg border border-[var(--border-color)] bg-transparent p-3 text-sm" /></label></div><input ref={inputRef} hidden type="file" accept="image/*,application/pdf" capture="environment" onChange={(e) => { const file = e.target.files?.[0]; if (file) void capture(file); e.currentTarget.value = ""; }} /><div className="mt-4 flex flex-wrap gap-3"><button disabled={busy} onClick={() => inputRef.current?.click()} className="inline-flex min-h-12 items-center gap-2 rounded-xl bg-[var(--color-primary)] px-5 py-3 font-black text-white disabled:opacity-50"><Camera size={20} /> Fotografar pedido</button><button disabled={busy} onClick={() => inputRef.current?.click()} className="inline-flex min-h-12 items-center gap-2 rounded-xl border border-[var(--border-color)] px-5 py-3 font-bold disabled:opacity-50"><FileUp size={19} /> Enviar imagem/PDF</button></div></div>
        {error && <div role="alert" className="flex gap-2 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200"><AlertTriangle size={18} />{error}</div>}{notice && <div role="status" className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-200"><CheckCircle2 className="mr-2 inline" size={18} />{notice}</div>}
        <div className="rounded-2xl border border-[var(--border-color)] bg-[var(--bg-card)] p-5"><div className="flex items-center justify-between"><h2 className="text-lg font-black">Importações pendentes e histórico</h2>{loading && <Loader2 className="animate-spin" size={18} />}</div>{!loading && imports.length === 0 ? <p className="mt-4 text-sm text-[var(--text-secondary)]">Nenhuma comanda importada.</p> : <div className="mt-3 space-y-2">{imports.map((row) => <button key={row.id} onClick={() => setSelected(row)} className={`w-full rounded-xl border p-3 text-left ${selected?.id === row.id ? "border-[var(--color-primary)]" : "border-[var(--border-color)]"}`}><div className="flex justify-between gap-3"><span className="font-bold">{platformLabels[row.platform]} · {row.external_order_number || "Número não identificado"}</span><span className="text-xs uppercase text-[var(--text-secondary)]">{row.status}</span></div><p className="mt-1 text-xs text-[var(--text-secondary)]">{row.items.length} item(ns) · {new Date(row.created_at).toLocaleString("pt-BR")}</p></button>)}</div>}</div>
      </div>
      {selected && <form onSubmit={review} className="h-fit rounded-2xl border border-[var(--border-color)] bg-[var(--bg-card)] p-5"><div className="flex items-start justify-between"><div><h2 className="text-lg font-black">Conferência</h2><p className="text-sm text-[var(--text-secondary)]">Parser: {selected.parser_version || "não informado"}</p></div><button type="button" onClick={() => setSelected(null)} aria-label="Fechar"><X size={19} /></button></div>
        {selected.review_notes.length > 0 && <div role="alert" className="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-100"><p className="font-bold">Avisos da leitura</p><ul className="mt-1 list-disc space-y-1 pl-5">{selected.review_notes.map((note, index) => <li key={`${note}-${index}`}>{note}</li>)}</ul></div>}
        <div className="mt-4 grid gap-3"><label className="text-sm font-bold">Plataforma<select name="platform" defaultValue={selected.platform} className={platformSelectClass.replace("p-3", "p-2")}><option className={platformOptionClass} value="unknown">Não identificada</option><option className={platformOptionClass} value="ifood">iFood</option><option className={platformOptionClass} value="99food">99Food</option><option className={platformOptionClass} value="keeta">Keeta</option></select></label><label className="text-sm font-bold">Tipo de atendimento<select name="fulfillment_type" defaultValue={selected.fulfillment_type || "delivery"} className={platformSelectClass.replace("p-3", "p-2")}><option className={platformOptionClass} value="delivery">Entrega</option><option className={platformOptionClass} value="pickup">Retirada</option></select></label>{PRINT_ORDER_REVIEW_FIELDS.map(({ name, label }) => <label key={name} className="text-sm font-bold">{label}<input name={name} defaultValue={fieldValue(selected, name)} className="mt-1 w-full rounded-lg border border-[var(--border-color)] bg-transparent p-2" /></label>)}<div><p className="mb-2 text-sm font-bold">Itens e produto interno</p>{selected.items.map((item) => <div key={item.id || item.external_name} className="mb-2 grid gap-2"><div className="grid grid-cols-[1fr_80px] gap-2"><input name="item_name" defaultValue={item.external_name} aria-label={`Item ${item.external_name}`} className="rounded-lg border border-[var(--border-color)] bg-transparent p-2 text-sm" /><input name="product_id" defaultValue={item.product_id || ""} placeholder="ID catálogo" aria-label={`Produto interno ${item.external_name}`} className="rounded-lg border border-[var(--border-color)] bg-transparent p-2 text-sm" /><input name="quantity" type="number" min="1" defaultValue={item.quantity} aria-label={`Quantidade ${item.external_name}`} className="rounded-lg border border-[var(--border-color)] bg-transparent p-2 text-sm" /></div><label className="text-xs font-bold">Sabores separados por vírgula<input name="flavor_names" defaultValue={item.flavor_names.join(", ")} aria-label={`Sabores ${item.external_name}`} className="mt-1 w-full rounded-lg border border-[var(--border-color)] bg-transparent p-2 text-sm" /></label></div>)}</div></div>
        <div className="mt-4 rounded-xl border border-[var(--border-color)] p-3"><p className="font-bold">Conciliação financeira</p><div className="mt-3 grid gap-3 sm:grid-cols-2">{PRINT_ORDER_FINANCIAL_FIELDS.map(({ name, label }) => <label key={name} className="text-sm font-bold">{label}<input name={name} inputMode="decimal" defaultValue={name === "printed_total" ? (selected.reconciliation?.printed_total ?? selected.printed_total ?? "") : fieldValue(selected, name)} className="mt-1 w-full rounded-lg border border-[var(--border-color)] bg-transparent p-2" /></label>)}</div><div className="mt-3 text-sm"><span className="font-bold">Status: </span>{selected.reconciliation?.status || "incompleta"}{selected.reconciliation?.delta !== undefined && <span> · diferença {formatPrintOrderMoney(selected.reconciliation.delta)}</span>}</div></div>
        <button disabled={busy} className="mt-4 w-full rounded-xl border border-[var(--border-color)] px-4 py-3 font-black disabled:opacity-50">Salvar revisão</button><button type="button" disabled={busy || selected.status !== "ready"} onClick={() => void confirm()} className="mt-2 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 font-black text-white disabled:opacity-40"><Send size={18} /> Confirmar e enviar pedido</button>{selected.status !== "ready" && <p className="mt-2 text-xs text-amber-200">Mapeie todos os itens e preencha os campos críticos para confirmar.</p>}</form>}
    </section>
    {active.length > 0 && <p className="mx-auto mt-4 max-w-6xl text-xs text-[var(--text-secondary)]">{active.length} importação(ões) aguardando conferência humana.</p>}
  </main>;
}
