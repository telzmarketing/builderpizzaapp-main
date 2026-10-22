import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, FileCheck2, FileUp, Loader2, RefreshCw, ShieldAlert } from "lucide-react";
import {
  inventoryApi,
  inventoryReceiptApi,
  type InventoryItem,
  type InventoryPayablesReconcileInput,
  type InventoryReceiptDocument,
} from "@/lib/api";

const panelClass = "rounded-lg border border-surface-03 bg-surface-02 p-5";
const inputClass = "w-full rounded-lg border border-surface-03 bg-surface-01 px-3 py-2 text-sm text-cream outline-none focus:border-gold";
const buttonClass = "inline-flex items-center justify-center gap-2 rounded-lg bg-gold px-3 py-2 text-sm font-black text-black disabled:cursor-not-allowed disabled:opacity-60";
const ghostClass = "inline-flex items-center justify-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm font-bold text-stone hover:bg-surface-03 hover:text-cream disabled:opacity-60";

function commandKey(prefix: string, id: string) {
  return `${prefix}-${id}-${Date.now()}`;
}

function currency(value?: string | null) {
  const numeric = Number(value ?? 0);
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number.isFinite(numeric) ? numeric : 0);
}

function statusLabel(status: string) {
  return ({ pending_review: "Pendente de conferência", ready: "Pronto para aprovação", approved: "Aprovado", rejected: "Rejeitado", cancelled: "Cancelado" } as Record<string, string>)[status] ?? status;
}

export default function InventoryReceiptDocumentsPanel() {
  const [documents, setDocuments] = useState<InventoryReceiptDocument[]>([]);
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [installmentsText, setInstallmentsText] = useState("[]");

  const selected = useMemo(() => documents.find((document) => document.id === selectedId) ?? null, [documents, selectedId]);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [nextDocuments, overview] = await Promise.all([inventoryReceiptApi.list(), inventoryApi.overview()]);
      setDocuments(nextDocuments);
      setItems(overview.items);
      setSelectedId((current) => nextDocuments.some((document) => document.id === current) ? current : nextDocuments[0]?.id ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar os documentos recebidos.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const run = async (key: string, action: () => Promise<unknown>, success: string) => {
    setSaving(key);
    setError("");
    setMessage("");
    try {
      await action();
      setMessage(success);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Operação não concluída.");
    } finally {
      setSaving("");
    }
  };

  const upload = () => {
    if (!file) return;
    return run("upload", () => inventoryReceiptApi.uploadXml(file, null, commandKey("document", file.name)), "XML importado para conferência.").then(() => setFile(null));
  };

  const updateLine = (lineId: string, inventoryItemId: string) => {
    if (!selected) return;
    return run(`line-${lineId}`, async () => {
      const updated = await inventoryReceiptApi.update(selected.id, {
        expected_version: selected.version,
        lines: [{ id: lineId, inventory_item_id: inventoryItemId || null, association_status: inventoryItemId ? "confirmed" : "pending" }],
      });
      setDocuments((current) => current.map((document) => document.id === updated.id ? updated : document));
    }, "Associação salva. A versão do documento foi atualizada.");
  };

  const approve = () => {
    if (!selected) return;
    return run("approve", () => inventoryReceiptApi.approve(selected.id, selected.version, commandKey("approve", selected.id)), "Documento aprovado para recebimento.");
  };

  const reconcile = () => {
    if (!selected) return;
    let input: InventoryPayablesReconcileInput;
    try {
      input = { expected_version: selected.version, installments: JSON.parse(installmentsText) };
      if (!Array.isArray(input.installments)) throw new Error("Parcelas devem ser uma lista JSON.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Parcelas inválidas.");
      return;
    }
    return run("reconcile", () => inventoryReceiptApi.reconcilePayables(selected.id, input, commandKey("payables", selected.id)), "Obrigação vinculada. Nenhum pagamento foi efetuado.");
  };

  return (
    <section className="space-y-5">
      <div className={panelClass}>
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <h2 className="text-lg font-black text-cream">NF-e de fornecedor</h2>
            <p className="mt-1 text-sm text-stone">Importe o XML, confira as associações e gere a obrigação financeira quando as parcelas estiverem confirmadas.</p>
          </div>
          <button type="button" className={ghostClass} disabled={loading} onClick={() => void load()}><RefreshCw size={15} /> Atualizar</button>
        </div>
        <div className="mt-4 flex flex-col gap-3 md:flex-row md:items-center">
          <input className={inputClass} type="file" accept=".xml,application/xml,text/xml" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          <button type="button" className={buttonClass} disabled={!file || !!saving} onClick={() => void upload()}><FileUp size={15} /> Importar XML</button>
        </div>
        <p className="mt-3 text-xs text-stone">O arquivo permanece privado e a importação não lança estoque, cria dívida ou efetua pagamento automaticamente.</p>
      </div>

      {error && <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>}
      {message && <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">{message}</div>}

      {loading ? <div className={`${panelClass} flex min-h-32 items-center justify-center text-stone`}><Loader2 size={18} className="mr-2 animate-spin" /> Carregando documentos...</div> : (
        <div className="grid gap-5 xl:grid-cols-[20rem_minmax(0,1fr)]">
          <div className="overflow-hidden rounded-lg border border-surface-03 bg-surface-01">
            {documents.map((document) => (
              <button type="button" key={document.id} onClick={() => setSelectedId(document.id)} className={`block w-full border-b border-surface-03 px-4 py-3 text-left last:border-b-0 ${document.id === selectedId ? "bg-gold/10" : "hover:bg-surface-03"}`}>
                <span className="block font-bold text-cream">NF-e {document.document_number || "sem número"}</span>
                <span className="mt-1 block text-xs text-stone">{document.supplier_name || document.supplier_document || "Fornecedor pendente"}</span>
                <span className="mt-1 block text-xs text-gold">{statusLabel(document.status)} · {currency(document.total_document)}</span>
              </button>
            ))}
            {!documents.length && <p className="px-4 py-8 text-center text-sm text-stone">Nenhum XML recebido.</p>}
          </div>

          {selected ? <div className={`${panelClass} space-y-5`}>
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div><h3 className="text-lg font-black text-cream">{selected.supplier_name || "Fornecedor pendente"}</h3><p className="text-sm text-stone">Chave: {selected.access_key || "pendente"} · versão {selected.version}</p></div>
              <span className="rounded-full border border-gold/40 px-3 py-1 text-xs font-bold text-gold">{statusLabel(selected.status)}</span>
            </div>
            {!!selected.pending_fields.length && <div className="flex gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-100"><ShieldAlert size={17} /> Pendências: {selected.pending_fields.join(", ")}</div>}
            <div className="overflow-x-auto rounded-lg border border-surface-03"><div className="min-w-[720px]">
              <div className="grid grid-cols-[.5fr_1.5fr_1fr_1.5fr] gap-3 bg-surface-01 px-4 py-3 text-xs font-black uppercase text-stone"><span>Linha</span><span>Descrição</span><span>Quantidade</span><span>Insumo oficial</span></div>
              {selected.lines.map((line) => <div key={line.id} className="grid grid-cols-[.5fr_1.5fr_1fr_1.5fr] items-center gap-3 border-t border-surface-03 px-4 py-3 text-sm"><span className="text-stone">{line.line_number}</span><span className="text-cream">{line.description}</span><span className="text-stone">{line.commercial_quantity || "-"} {line.commercial_unit || ""}</span><select className={inputClass} value={line.inventory_item_id || ""} disabled={!!saving || selected.status === "approved"} onChange={(event) => void updateLine(line.id, event.target.value)}><option value="">Selecionar insumo</option>{items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>)}
            </div></div>
            <div className="flex flex-wrap gap-3"><button type="button" className={buttonClass} disabled={!!saving || selected.status === "approved" || !!selected.pending_fields.length} onClick={() => void approve()}><CheckCircle2 size={15} /> Aprovar documento</button><span className="self-center text-xs text-stone">A aprovação não confirma recebimento físico.</span></div>
            <div className="border-t border-surface-03 pt-5"><h4 className="font-black text-cream">Vincular obrigação financeira</h4><p className="mt-1 text-sm text-stone">Informe parcelas conferidas em JSON. O vínculo é idempotente e não registra pagamento.</p><textarea className={`${inputClass} mt-3 min-h-28 font-mono text-xs`} value={installmentsText} onChange={(event) => setInstallmentsText(event.target.value)} placeholder='[{"number":1,"due_date":"2026-11-01","amount":"400.00"}]' /><button type="button" className={`${buttonClass} mt-3`} disabled={!!saving || selected.status !== "approved"} onClick={() => void reconcile()}><FileCheck2 size={15} /> Vincular parcelas</button></div>
          </div> : <div className={`${panelClass} flex min-h-48 items-center justify-center text-stone`}>Selecione um documento para conferir.</div>}
        </div>
      )}
    </section>
  );
}
